"""Build the static explorer's data files from data/*.csv.

    python3 site/build.py

Writes site/data/*.json, which site/index.html loads. The Pages workflow runs this on deploy.
"""
import csv, hashlib, json, os, re, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "site" / "data"
SHARDS = 128
PRIOR_MEAN, PRIOR_N = 3.27, 10
LABELS = {"rave": 4, "positive": 3, "mixed": 2, "pan": 1}

csv.field_size_limit(sys.maxsize)


def read(name):
    with open(DATA / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def outlet_key(name):
    k = name.strip().lower()
    k = re.sub(r"^the\s+", "", k)
    k = re.sub(r"\s*\((uk|ire|us|can|aus|nz)\)$", "", k)
    return k


PUB_ALIAS = {
    "fsg": "farrar straus and giroux", "farrar straus giroux": "farrar straus and giroux",
    "ww norton": "norton", "w w norton": "norton", "harpercollins": "harper", "harper collins": "harper",
    "william morrow": "morrow", "grove atlantic": "grove",
}


def publisher_key(name):
    k = name.lower().replace("&", "and")
    k = re.sub(r"\s*/.*$", "", k)  # "Avid Reader Press / Simon & Schuster" -> the imprint
    k = re.sub(r"\s*;.*$", "", k)  # "Liveright; 1 edition"
    k = re.sub(r",?\s*(19|20)\d\d$", "", k)  # "..., 2017"
    k = k.replace("strauss", "straus")
    k = re.sub(r"\b(alfred a\.?|the)\b", "", k)
    k = re.sub(r"\b(books?|press|publishing|publishers|corporation|group|inc\.?|llc|ltd|and company|and co\.?|company|editions?|usa|us)\b", "", k)
    k = re.sub(r"[^a-z0-9 ]", "", k)
    k = re.sub(r"\s+", " ", k).strip()
    return PUB_ALIAS.get(k, k)


def shard(slug):
    h = 0
    for ch in slug:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h % SHARDS


def main():
    books = read("books.csv")
    reviews = read("reviews_before_2021.csv") + read("reviews_2021_onward.csv")

    # drop the site's duplicated reviews
    seen, rows = set(), []
    for r in reviews:
        k = (r["book_slug"], r["critic"], r["outlet"], r["pull_quote"])
        if k in seen or r["rating_label"] not in LABELS:  # Book Marks rows always carry a rating
            continue
        seen.add(k)
        rows.append(r)

    # ---- backfill (data/backfill): pre-Book Marks reviews from Complete Review and the Guardian ----
    # src codes: 0 Book Marks, 1 Complete Review grade, 2 model-predicted
    for r in rows:
        r["src"], r["date"] = 0, ""
    bf_path = DATA / "backfill" / "reviews_backfill.csv"
    bf_books = {}
    if bf_path.exists():
        bm_slugs = {b["slug"] for b in books}
        for r in read("backfill/reviews_backfill.csv"):
            # unrated reviews (NYT, non-English quotes) are kept with rating 0: listed on book pages, left out of the averages
            if not r["book_key"] or r["in_bookmarks"] == "True" or r["also_in_complete_review"] == "True":
                continue
            slug = r["bookmarks_slug"] if r["bookmarks_slug"] in bm_slugs else "bf-" + re.sub(r"[^a-z0-9]+", "-", r["book_key"].lower()).strip("-")
            if slug.startswith("bf-"):
                bk = bf_books.setdefault(slug, {"slug": slug, "title": "", "author": "", "year": "", "first": "", "sources": set()})
                bk["title"] = bk["title"] or r["title"]
                bk["author"] = bk["author"] or r["author"]
                yr = r["book_year"][:4] if re.match(r"^1[5-9]\d\d|^20\d\d", r["book_year"] or "") else ""
                bk["year"] = bk["year"] or yr
                d = r["review_date"] if re.match(r"^(1[89]|20)\d\d", r["review_date"] or "") else ""
                if d and (not bk["first"] or d < bk["first"]):
                    bk["first"] = d
                bk["sources"].add(r["source"])
            grade = f" (CR grade {r['native_grade']})" if r["rating_method"] == "cr_grade" else ""
            rows.append({
                "book_slug": slug, "idx": "", "rating_label": r["rating_label"], "critic": r["critic"] or "", "critic_slug": "",
                "outlet": r["outlet"] or "", "review_url": r["review_url"] or r["source_url"] or "", "pull_quote": (r["pull_quote"] or "").strip(),
                "src": 1 if r["rating_method"] == "cr_grade" else 2, "date": (r["review_date"] or "")[:10], "via": r["source"],
            })
        enrich = {}
        en_path = DATA / "backfill" / "books_enrichment.csv"
        if en_path.exists():
            for e in read("backfill/books_enrichment.csv"):
                enrich["bf-" + re.sub(r"[^a-z0-9]+", "-", e["book_key"].lower()).strip("-")] = e
        for bk in bf_books.values():
            e = enrich.get(bk["slug"], {})
            year = bk["year"] or (e.get("first_publish_year") or "")[:4] or bk["first"][:4]
            books.append({
                "slug": bk["slug"], "title": bk["title"], "author": bk["author"], "publisher": e.get("publisher", ""),
                "date_published": year, "genres": "[]", "isbn": e.get("isbn", ""), "overall_label": "",
                "description": e.get("description", ""), "cover_url": e.get("cover_url", ""), "bf": "1",
            })


    # merge outlet spellings, display the most common one
    spell = defaultdict(Counter)
    for r in rows:
        if r["outlet"].strip():
            spell[outlet_key(r["outlet"])][r["outlet"].strip()] += 1
    outlet_name = {k: c.most_common(1)[0][0] for k, c in spell.items()}

    for r in rows:
        r["critic"] = re.sub(r"\\+", "", r["critic"]).replace("\u00ad", "").strip().strip('"\u201c\u201d').strip()
        r["pull_quote"] = re.sub(r"\\+(['\"])", r"\1", r["pull_quote"])

    # merge critic spellings that share a slug or differ only in case
    parent = {}
    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for r in rows:
        if r["critic"]:
            a, b = "n:" + r["critic"].lower(), "s:" + (r["critic_slug"].strip().strip("-") or r["critic"].lower())
            parent[find(a)] = find(b)
    cspell = defaultdict(Counter)
    for r in rows:
        if r["critic"]:
            cspell[find("n:" + r["critic"].lower())][r["critic"]] += 1
    critic_name = {}
    for k, c in cspell.items():
        name = max(c, key=lambda n: (not n.isupper(), c[n]))
        critic_name[k] = name.title() if name.isupper() else name
    for r in rows:
        if r["critic"]:
            r["critic"] = critic_name[find("n:" + r["critic"].lower())]

    book_idx = {b["slug"]: i for i, b in enumerate(books)}
    critics, critic_idx = [], {}
    outlets, outlet_idx = [], {}

    def intern(val, lst, idx):
        if val not in idx:
            idx[val] = len(lst)
            lst.append(val)
        return idx[val]

    index = []  # [book, rating, critic, outlet]
    detail = [defaultdict(lambda: {"d": "", "r": []}) for _ in range(SHARDS)]
    for r in rows:
        b = book_idx.get(r["book_slug"])
        if b is None:
            continue
        v = LABELS.get(r["rating_label"], 0)
        c = intern(r["critic"].strip(), critics, critic_idx) if r["critic"].strip() else -1
        o = intern(outlet_name[outlet_key(r["outlet"])], outlets, outlet_idx) if r["outlet"].strip() else -1
        index.append([b, v, c, o, r["src"]])
        detail[shard(r["book_slug"])][r["book_slug"]]["r"].append(
            [int(r["idx"] or 0) if r["src"] == 0 else 1000 + len(detail[shard(r["book_slug"])][r["book_slug"]]["r"]), v, r["critic"].strip(),
             outlet_name.get(outlet_key(r["outlet"]), ""), r["review_url"], r["pull_quote"].strip(), r["src"], r["date"]]
        )

    # merge publisher spellings ("Graywolf", "Graywolf Press"), display the most common one
    pspell = defaultdict(Counter)
    for b in books:
        if b["publisher"].strip():
            pspell[publisher_key(b["publisher"])][b["publisher"].strip()] += 1
    pub_name = {k: c.most_common(1)[0][0] for k, c in pspell.items()}

    out_books = []
    for b in books:
        if b.get("bf"):
            out_books.append([b["slug"], b["title"], b["author"], pub_name.get(publisher_key(b["publisher"]), ""), b["date_published"], [],
                              [0, 0, 0, 0], None, None, b["isbn"], "", 1])
            detail[shard(b["slug"])][b["slug"]]["d"] = b["description"].strip()
            detail[shard(b["slug"])][b["slug"]]["cover"] = b["cover_url"].strip()
            continue
        n = int(b["review_count_parsed"] or 0)
        m = float(b["mean_score"]) if b["mean_score"] else None
        d = b["date_published"] if re.match(r"^(19|20)\d\d-", b["date_published"] or "") else ""
        try:
            genres = [g for g in json.loads(b["genres"] or "[]") if g not in ("Coming Soon", "Hottest Books of the Season")]
        except json.JSONDecodeError:
            genres = []
        adj = round((n * m + PRIOR_N * PRIOR_MEAN) / (n + PRIOR_N), 3) if m is not None else None
        out_books.append([
            b["slug"], b["title"], b["author"], pub_name.get(publisher_key(b["publisher"]), ""), d, genres,
            [int(b["n_rave"] or 0), int(b["n_positive"] or 0), int(b["n_mixed"] or 0), int(b["n_pan"] or 0)],
            m, adj, b["isbn"], b["overall_label"], 0,
        ])
        detail[shard(b["slug"])][b["slug"]]["d"] = b["description"].strip()
        detail[shard(b["slug"])][b["slug"]]["cover"] = b["cover_url"].strip()
    for b in books:
        if b.get("bf"):
            detail[shard(b["slug"])][b["slug"]].setdefault("cover", "")
        detail[shard(b["slug"])][b["slug"]]["cover"] = b["cover_url"].strip()

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "reviews").mkdir(exist_ok=True)
    dump = lambda p, x: p.write_text(json.dumps(x, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    dump(OUT / "books.json", out_books)
    dump(OUT / "index.json", {"critics": critics, "outlets": outlets, "reviews": index, "shards": SHARDS})
    for i, d in enumerate(detail):
        for v in d.values():
            v["r"].sort()
        dump(OUT / "reviews" / f"{i}.json", d)
    if os.environ.get("GITHUB_ACTIONS"):
        stamp_assets()
    print(f"{len(bf_books)} backfill books")
    print(f"{len(out_books)} books, {len(index)} reviews, {len(critics)} critics, {len(outlets)} outlets")


def stamp_assets():
    """Add a content hash to each script and stylesheet link in index.html.

    GitHub Pages serves everything with a 10-minute cache, so after a deploy a browser can pair the new
    index.html with an old script. Runs only in the Pages workflow so the committed index.html stays clean.
    """
    page = ROOT / "site" / "index.html"
    html = page.read_text(encoding="utf-8")
    def stamp(m):
        digest = hashlib.sha1((ROOT / "site" / m.group(2)).read_bytes()).hexdigest()[:10]
        return f'{m.group(1)}="{m.group(2)}?v={digest}"'
    page.write_text(re.sub(r'\b(src|href)="([\w-]+\.(?:js|css))"', stamp, html), encoding="utf-8")


if __name__ == "__main__":
    main()
