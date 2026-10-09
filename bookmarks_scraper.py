#!/usr/bin/env python3
"""
Book Marks (bookmarks.reviews) mirror.

Crawls the WordPress sitemaps for every book page, then fetches each book's
detail page (metadata) and its /reviews/all/ page (every review), parsing the
schema.org microdata into SQLite. Resumable: rerun and it skips finished books.

Usage:
  python3 bookmarks_scraper.py crawl  [--db bookmarks.db] [--delay 10] [--limit N] [--order newest|oldest]
  python3 bookmarks_scraper.py export [--db bookmarks.db] [--out ./export]
  python3 bookmarks_scraper.py stats  [--db bookmarks.db]

Default delay honours the site's robots.txt crawl-delay (10 s).
"""
import argparse, csv, json, os, re, sqlite3, sys, time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://bookmarks.reviews"
UA = "BookMarksResearchMirror/1.0 (+contact: set --ua)"
RATING_VALUE = {"rave": 4, "positive": 3, "mixed": 2, "pan": 1}

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
  slug TEXT PRIMARY KEY,
  url TEXT, lastmod TEXT,
  title TEXT, author TEXT, publisher TEXT, date_published TEXT,
  isbn TEXT, genres TEXT, description TEXT, cover_url TEXT,
  overall_label TEXT, overall_value INTEGER, review_count_stated INTEGER,
  review_count_parsed INTEGER, n_rave INTEGER, n_positive INTEGER, n_mixed INTEGER, n_pan INTEGER,
  mean_score REAL,
  status TEXT, error TEXT, fetched_at TEXT
);
CREATE TABLE IF NOT EXISTS reviews (
  book_slug TEXT, idx INTEGER,
  rating_label TEXT, rating_value INTEGER,
  critic TEXT, critic_slug TEXT, outlet TEXT, review_url TEXT, pull_quote TEXT,
  PRIMARY KEY (book_slug, idx)
);
CREATE INDEX IF NOT EXISTS ix_reviews_outlet ON reviews(outlet);
CREATE INDEX IF NOT EXISTS ix_reviews_critic ON reviews(critic_slug);
"""


class Fetcher:
    def __init__(self, delay, ua):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = ua
        self.delay = delay
        self.last = 0.0

    def get(self, url, tries=4):
        for attempt in range(tries):
            wait = self.delay - (time.time() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            try:
                r = self.s.get(url, timeout=30, allow_redirects=True)
            except requests.RequestException as e:
                err = str(e)
            else:
                if r.status_code == 200:
                    return r
                if r.status_code == 404:
                    return r
                err = f"HTTP {r.status_code}"
                if r.status_code in (429, 503):
                    time.sleep(60 * (attempt + 1))
            time.sleep(5 * (attempt + 1))
        raise RuntimeError(f"{url}: {err}")


def clean(t):
    return re.sub(r"\s+", " ", t or "").strip()


def slug_of(url):
    parts = [p for p in urlparse(url).path.split("/") if p]
    return parts[-1] if parts else ""


# ---------------------------------------------------------------- sitemaps
def discover(fetch):
    idx = fetch.get(f"{BASE}/wp-sitemap.xml").text
    maps = [m for m in re.findall(r"<loc>([^<]+)</loc>", idx) if "posts-bookmark-" in m]
    out = []
    for m in maps:
        xml = fetch.get(m).text
        for block in re.findall(r"<url>(.*?)</url>", xml, re.S):
            loc = re.search(r"<loc>([^<]+)</loc>", block)
            lm = re.search(r"<lastmod>([^<]+)</lastmod>", block)
            if loc:
                out.append((loc.group(1).strip(), lm.group(1).strip() if lm else None))
        print(f"  {m.rsplit('/',1)[-1]}: {len(out)} books so far", flush=True)
    return out


# ---------------------------------------------------------------- parsing
def parse_reviews(soup):
    reviews = []
    for rv in soup.select('[itemprop="review"]'):
        head = rv.select_one(".bookmarks_pullquote_reviewer")
        if head is None:
            continue
        lab_el = head.select_one(".review_rating")
        label = clean(lab_el.get_text()).lower() if lab_el else None
        val = rv.select_one('[itemprop="reviewRating"] [itemprop="ratingValue"]')
        # the label is authoritative; the hidden numeric field is sometimes corrupt (0, 5..44)
        value = RATING_VALUE.get(label) or (int(val["content"]) if val and val.get("content", "").isdigit() else None)

        critic = critic_slug = None
        auth = head.select_one('[itemprop="author"]')
        if auth is not None and "Person" in (auth.get("itemtype") or ""):
            nm = auth.select_one('[itemprop="name"]')
            critic = clean(nm.get_text()).rstrip(",").strip() if nm else None
            a = auth.select_one("a[href]")
            if a:
                critic_slug = slug_of(a["href"])

        outlet = review_url = None
        src = head.select_one("a.bookmarks_source_link")
        if src:
            outlet, review_url = clean(src.get_text()), src.get("href")
        else:
            em = head.find("em")
            if em:
                outlet = clean(em.get_text())
            elif auth is not None and "Organization" in (auth.get("itemtype") or ""):
                m = auth.select_one('meta[itemprop="name"]')
                outlet = m["content"] if m else None
            if outlet is None:
                # fallback: reviewer header text minus label and critic
                txt = clean(head.get_text(" "))
                for strip in (lab_el.get_text() if lab_el else "", critic or ""):
                    txt = txt.replace(clean(strip), "", 1)
                outlet = txt.strip(" ,") or None
        if review_url is None:
            more = rv.select_one("a.see_more_link")
            review_url = more.get("href") if more else None

        body = rv.select_one('[itemprop="reviewBody"]')
        if not (critic or outlet or (body and clean(body.get_text()))):
            continue  # empty placeholder block in the site's markup
        reviews.append(dict(
            rating_label=label, rating_value=value, critic=critic, critic_slug=critic_slug,
            outlet=outlet, review_url=review_url or None,
            pull_quote=clean(body.get_text(" ")) if body else None,
        ))
    return reviews


def parse_book(html):
    soup = BeautifulSoup(html, "lxml")
    book = soup.select_one('[itemtype="http://schema.org/Book"]') or soup
    g = lambda sel: book.select_one(sel)

    title = g('h1[itemprop="name"]')
    authors = [clean(a.get_text()) for a in book.select('[itemprop="author"][itemtype*="Person"] > [itemprop="name"]')
               if not a.find_parent(attrs={"itemprop": "review"})]
    pub = g('[itemprop="publisher"] [itemprop="name"]')
    date = g('[itemprop="datePublished"]')
    genres = [clean(x.get_text()) for x in book.select('.book_detail_category [itemprop="genre"]')]
    desc = g(".book_manual_description")
    cover = g('img[itemprop="image"]')
    isbn = None
    w = soup.select_one("textarea.widget_embed_code")
    if w:
        m = re.search(r'data-isbn="([0-9Xx\-]+)"', w.get_text())
        isbn = m.group(1) if m else None
    if not isbn:
        m = re.search(r"bookshop\.org/a/\d+/(97[89]\d{10})", html)
        isbn = m.group(1) if m else None
    overall = g(".book_review_stats .stat_total")
    agg_val = g('[itemprop="aggregateRating"] meta[itemprop="ratingValue"]')
    count = g('[itemprop="aggregateRating"] [itemprop="ratingCount"]')
    all_link = g("a.bookmarks_detail_see_all_reviews")

    return dict(
        title=clean(title.get_text()) if title else None,
        author="; ".join(dict.fromkeys(a for a in authors if a)) or None,
        publisher=clean(pub.get_text()) if pub else None,
        date_published=date.get("content") if date else None,
        isbn=isbn.replace("-", "") if isbn else None,
        genres=json.dumps(genres),
        description=clean(desc.get_text(" ")) if desc else None,
        cover_url=cover.get("src") if cover else None,
        overall_label=clean(overall.get_text()).lower() if overall else None,
        overall_value=int(agg_val["content"]) if agg_val and agg_val.get("content", "").isdigit() else None,
        review_count_stated=int(clean(count.get_text())) if count and clean(count.get_text()).isdigit() else None,
        all_reviews_path=all_link.get("href") if all_link else None,
    ), parse_reviews(soup)


# ---------------------------------------------------------------- crawl
def crawl(args):
    db = sqlite3.connect(args.db)
    db.executescript(SCHEMA)
    fetch = Fetcher(args.delay, args.ua)

    have = db.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    if have == 0 or args.refresh_sitemap:
        print("Reading sitemaps...", flush=True)
        for url, lm in discover(fetch):
            db.execute("INSERT INTO books(slug,url,lastmod,status) VALUES(?,?,?,'pending') "
                       "ON CONFLICT(slug) DO UPDATE SET lastmod=excluded.lastmod, "
                       "status=CASE WHEN books.lastmod IS NOT excluded.lastmod THEN 'pending' ELSE books.status END",
                       (slug_of(url), url, lm))
        db.commit()

    order = "DESC" if args.order == "newest" else "ASC"
    todo = db.execute(f"SELECT slug,url FROM books WHERE status IN ('pending','error') "
                      f"ORDER BY lastmod {order} LIMIT ?", (args.limit or -1,)).fetchall()
    total = db.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    print(f"{len(todo)} books to fetch ({total} known)", flush=True)

    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    local = threading.local()

    def worker(slug, url):
        f = getattr(local, "f", None)
        if f is None:
            f = local.f = Fetcher(args.delay, args.ua)
        r = f.get(url)
        if r.status_code == 404:
            return None, None
        meta, reviews = parse_book(r.text)
        stated = meta["review_count_stated"] or 0
        if stated > len(reviews) or (meta["all_reviews_path"] and not reviews):
            path = meta["all_reviews_path"] or f"/reviews/all/{slug}/"
            try:
                r2 = f.get(urljoin(BASE, path), tries=2)
            except RuntimeError:
                meta["_partial"] = True  # full-review page errors on the site; keep book-page reviews
                r2 = None
            if r2 is not None and r2.status_code == 200:
                full = parse_reviews(BeautifulSoup(r2.text, "lxml"))
                if len(full) >= len(reviews):
                    reviews = full
        meta.pop("all_reviews_path")
        return meta, reviews

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(worker, slug, url): slug for slug, url in todo}
        for n, fut in enumerate(as_completed(futs), 1):
            slug = futs[fut]
            try:
                meta, reviews = fut.result()
                if meta is None:
                    db.execute("UPDATE books SET status='gone', fetched_at=? WHERE slug=?", (now(), slug))
                    db.commit(); continue
                counts = {k: sum(1 for x in reviews if x["rating_label"] == k) for k in RATING_VALUE}
                vals = [x["rating_value"] for x in reviews if x["rating_value"]]
                status = ("partial" if meta.pop("_partial", False) else "ok") if meta["title"] else "empty"
                db.execute("DELETE FROM reviews WHERE book_slug=?", (slug,))
                db.executemany("INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?,?)",
                               [(slug, i, x["rating_label"], x["rating_value"], x["critic"], x["critic_slug"],
                                 x["outlet"], x["review_url"], x["pull_quote"]) for i, x in enumerate(reviews)])
                db.execute("""UPDATE books SET title=:title, author=:author, publisher=:publisher,
                    date_published=:date_published, isbn=:isbn, genres=:genres, description=:description,
                    cover_url=:cover_url, overall_label=:overall_label, overall_value=:overall_value,
                    review_count_stated=:review_count_stated, review_count_parsed=:rcp,
                    n_rave=:rave, n_positive=:positive, n_mixed=:mixed, n_pan=:pan, mean_score=:mean,
                    status=:status, error=NULL, fetched_at=:at WHERE slug=:slug""",
                           dict(meta, rcp=len(reviews), mean=round(sum(vals) / len(vals), 3) if vals else None,
                                status=status, at=now(), slug=slug, **counts))
                db.commit()
            except Exception as e:
                db.execute("UPDATE books SET status='error', error=?, fetched_at=? WHERE slug=?", (str(e)[:500], now(), slug))
                db.commit()
                print(f"[{n}] ERROR {slug}: {e}", file=sys.stderr, flush=True)
            if n % 100 == 0 or n == len(todo):
                rate = n / (time.time() - t0) * 60
                print(f"[{n}/{len(todo)}] {rate:.0f} books/min, ETA {(len(todo)-n)/max(rate,1e-9)/60:.1f} h", flush=True)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------- export / stats
def export(args):
    db = sqlite3.connect(args.db)
    # drop empty placeholder reviews stored by older parser versions, then recompute per-book tallies
    db.execute("DELETE FROM reviews WHERE (critic IS NULL OR critic='') AND (outlet IS NULL OR outlet='') "
               "AND (pull_quote IS NULL OR pull_quote='')")
    db.execute("""UPDATE books SET
        review_count_parsed=(SELECT COUNT(*) FROM reviews r WHERE r.book_slug=books.slug),
        n_rave=(SELECT COUNT(*) FROM reviews r WHERE r.book_slug=books.slug AND rating_label='rave'),
        n_positive=(SELECT COUNT(*) FROM reviews r WHERE r.book_slug=books.slug AND rating_label='positive'),
        n_mixed=(SELECT COUNT(*) FROM reviews r WHERE r.book_slug=books.slug AND rating_label='mixed'),
        n_pan=(SELECT COUNT(*) FROM reviews r WHERE r.book_slug=books.slug AND rating_label='pan'),
        mean_score=(SELECT ROUND(AVG(rating_value),3) FROM reviews r WHERE r.book_slug=books.slug)
        WHERE status IN ('ok','partial')""")
    db.commit()
    os.makedirs(args.out, exist_ok=True)
    for table, q in [
        ("books", "SELECT * FROM books WHERE status IN ('ok','partial') ORDER BY date_published DESC"),
        ("reviews", "SELECT r.*, b.title, b.author, b.date_published FROM reviews r JOIN books b ON b.slug=r.book_slug "
                    "WHERE b.status IN ('ok','partial') ORDER BY b.date_published DESC, r.book_slug, r.idx"),
    ]:
        cur = db.execute(q)
        path = os.path.join(args.out, f"{table}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([d[0] for d in cur.description])
            w.writerows(cur)
        print("wrote", path)


def stats(args):
    db = sqlite3.connect(args.db)
    for label, q in [
        ("books by status", "SELECT status, COUNT(*) FROM books GROUP BY status"),
        ("reviews", "SELECT COUNT(*) FROM reviews"),
        ("count mismatches (stated != parsed)",
         "SELECT COUNT(*) FROM books WHERE status='ok' AND review_count_stated IS NOT NULL AND review_count_stated != review_count_parsed"),
        ("reviews missing outlet", "SELECT COUNT(*) FROM reviews WHERE outlet IS NULL OR outlet=''"),
        ("reviews missing label", "SELECT COUNT(*) FROM reviews WHERE rating_label IS NULL"),
    ]:
        print(f"{label}: {db.execute(q).fetchall()}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("crawl")
    c.add_argument("--db", default="bookmarks.db")
    c.add_argument("--delay", type=float, default=10.0)
    c.add_argument("--workers", type=int, default=1)
    c.add_argument("--limit", type=int, default=0)
    c.add_argument("--order", choices=["newest", "oldest"], default="newest")
    c.add_argument("--ua", default=UA)
    c.add_argument("--refresh-sitemap", action="store_true")
    e = sub.add_parser("export"); e.add_argument("--db", default="bookmarks.db"); e.add_argument("--out", default="export")
    s = sub.add_parser("stats"); s.add_argument("--db", default="bookmarks.db")
    a = p.parse_args()
    {"crawl": crawl, "export": export, "stats": stats}[a.cmd](a)
