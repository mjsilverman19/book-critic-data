"""Build the static explorer's data files from data/*.csv.

    python3 site/build.py

Writes site/data/*.json, which site/index.html loads. The Pages workflow runs this on deploy.
"""
import csv, json, re, sys
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
        if k in seen or r["rating_label"] not in LABELS:
            continue
        seen.add(k)
        rows.append(r)

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
        v = LABELS[r["rating_label"]]
        c = intern(r["critic"].strip(), critics, critic_idx) if r["critic"].strip() else -1
        o = intern(outlet_name[outlet_key(r["outlet"])], outlets, outlet_idx) if r["outlet"].strip() else -1
        index.append([b, v, c, o])
        detail[shard(r["book_slug"])][r["book_slug"]]["r"].append(
            [int(r["idx"] or 0), v, r["critic"].strip(), outlet_name.get(outlet_key(r["outlet"]), ""), r["review_url"], r["pull_quote"].strip()]
        )

    # merge publisher spellings ("Graywolf", "Graywolf Press"), display the most common one
    pspell = defaultdict(Counter)
    for b in books:
        if b["publisher"].strip():
            pspell[publisher_key(b["publisher"])][b["publisher"].strip()] += 1
    pub_name = {k: c.most_common(1)[0][0] for k, c in pspell.items()}

    out_books = []
    for b in books:
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
            m, adj, b["isbn"], b["overall_label"],
        ])
        detail[shard(b["slug"])][b["slug"]]["d"] = b["description"].strip()
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
    print(f"{len(out_books)} books, {len(index)} reviews, {len(critics)} critics, {len(outlets)} outlets")


if __name__ == "__main__":
    main()
