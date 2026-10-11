"""Crawl Kirkus Reviews review pages, a slice at a time.

Kirkus's sitemaps only expose their first page, so the crawl walks the site instead: it starts from
the sitemap URLs and the Kirkus links already in the Book Marks data, and follows links on each
review page (more by the author, related reviews) and author pages. robots.txt asks for a 10-second
delay, which this keeps, so one run covers about 2,000 pages and the crawl advances over many runs.

State lives in data/backfill/kirkus/ so each run resumes where the last stopped:
  frontier.txt.gz   URLs still to fetch, review pages first
  visited.txt.gz    URLs already fetched
  reviews.csv.gz    one row per review page

Only metadata and the review's closing sentence (its verdict, used like a pull quote) are kept;
the full review text is not stored.

    python3 backfill/kirkus_crawl.py --minutes 330
"""
import argparse, csv, gzip, html, io, json, os, re, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "backfill" / "kirkus"
BASE = "https://www.kirkusreviews.com"
UA = "Mozilla/5.0 (compatible; book-critic-data/1.0; +https://github.com/mjsilverman19/book-critic-data)"
DELAY = 10
DISALLOW = ("/book-reviews/childrens-books/", "/book-reviews/fiction-books-literature/", "/book-reviews/indie/",
            "/book-reviews/non-fiction/", "/book-reviews/stars/", "/search/", "/features/", "/subscription/", "/admin/")
FIELDS = ["url", "title", "author", "date_published", "publisher", "isbn", "pages", "genre", "starred",
          "issue_date", "verdict", "review_words", "fetched_at"]
csv.field_size_limit(sys.maxsize)


def read_lines(name):
    p = STATE / name
    return gzip.open(p, "rt").read().split() if p.exists() else []


def write_lines(name, lines):
    with gzip.open(STATE / name, "wt") as f:
        f.write("\n".join(lines) + "\n")


def norm(href):
    href = html.unescape(href).split("#")[0].split("?")[0]
    if href.startswith(BASE):
        href = href[len(BASE):]
    if not href.startswith("/") or href.endswith("/print/") or any(href.startswith(d) for d in DISALLOW):
        return None
    if re.match(r"^/book-reviews/(a/)?[a-z0-9-]+/[a-z0-9-]+/$", href) or re.match(r"^/author/[a-z0-9-]+/$", href):
        return href
    return None


def seeds():
    out = []
    for f in ("reviews_before_2021.csv", "reviews_2021_onward.csv"):
        p = ROOT / "data" / f
        if p.exists():
            with open(p, newline="", encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    u = r.get("review_url") or ""
                    if "kirkusreviews.com" in u:
                        n = norm(u)
                        if n:
                            out.append(n)
    for kind in ("titles", "archives"):
        try:
            x = fetch(f"{BASE}/sitemap-{kind}.xml")
            out += [n for n in (norm(u) for u in re.findall(r"<loc>([^<]+)</loc>", x)) if n]
            time.sleep(DELAY)
        except Exception as e:
            print("sitemap", kind, e, flush=True)
    return out


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def parse_review(url, page):
    book = None
    for blob in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try:
            d = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and d.get("@type") == "Book":
            book = d
            break
    if not book:
        return None
    body = text((book.get("review") or {}).get("reviewBody", ""))
    sents = re.split(r"(?<=[.!?])\s+(?=[A-Z\"“])", body)
    verdict = sents[-1] if sents else ""
    if len(verdict) < 40 and len(sents) > 1:
        verdict = sents[-2] + " " + verdict
    cover = re.search(r'class="[^"]*cover-container[^"]*"', page)
    meta = lambda label: (re.search(label + r"\s*:\s*</[^>]+>\s*(?:<[^>]+>\s*)*([^<]+)", page) or [None, ""])[1].strip()
    author = book.get("author") or {}
    return {
        "url": BASE + url,
        "title": text(book.get("name", "")).strip('"'),
        "author": text(author.get("name", "") if isinstance(author, dict) else ""),
        "date_published": text(book.get("datePublished", "")),
        "publisher": text((book.get("publisher") or {}).get("name", "")),
        "isbn": text(book.get("isbn", "")),
        "pages": meta("Page Count"),
        "genre": text(book.get("genre", "")),
        "starred": int(bool(cover and "kirkus-star" in cover.group(0))),
        "issue_date": meta("Kirkus Reviews Issue"),
        "verdict": verdict[:500],
        "review_words": len(body.split()),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=330)
    args = ap.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    visited = set(read_lines("visited.txt.gz"))
    frontier = read_lines("frontier.txt.gz")
    if not frontier and not visited:
        frontier = seeds()
    queued = set(frontier)
    rows_path = STATE / "reviews.csv.gz"
    new_rows = []
    deadline = time.time() + args.minutes * 60
    fetched = 0
    while frontier and time.time() < deadline:
        # review pages before author pages, so each run adds reviews first
        i = next((k for k, u in enumerate(frontier) if u.startswith("/book-reviews/")), 0)
        url = frontier.pop(i)
        queued.discard(url)
        if url in visited:
            continue
        try:
            page = fetch(BASE + url)
        except Exception as e:
            code = getattr(e, "code", None)
            print("ERR", url, e, flush=True)
            if code in (404, 410):
                visited.add(url)
            elif code in (403, 429) or code is None:
                frontier.append(url)
                time.sleep(60)
            time.sleep(DELAY)
            continue
        visited.add(url)
        fetched += 1
        for h in re.findall(r'href="([^"]+)"', page):
            n = norm(h)
            if n and n not in visited and n not in queued:
                frontier.append(n)
                queued.add(n)
        if url.startswith("/book-reviews/"):
            row = parse_review(url, page)
            if row:
                new_rows.append(row)
        if fetched % 100 == 0:
            print(fetched, "fetched,", len(new_rows), "reviews,", len(frontier), "in frontier", flush=True)
        time.sleep(DELAY)

    old = []
    if rows_path.exists():
        with gzip.open(rows_path, "rt", newline="") as f:
            old = list(csv.DictReader(f))
    with gzip.open(rows_path, "wt", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(old + new_rows)
    write_lines("visited.txt.gz", sorted(visited))
    write_lines("frontier.txt.gz", frontier)
    print(f"done: {fetched} fetched, {len(new_rows)} new reviews, {len(old) + len(new_rows)} total, {len(frontier)} in frontier", flush=True)


if __name__ == "__main__":
    main()
