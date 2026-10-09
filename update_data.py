#!/usr/bin/env python3
"""Refresh data/ from the live site. Used by .github/workflows/refresh.yml.

    python3 update_data.py [--limit N] [--delay 10] [--db-gz]

1. Rebuilds a SQLite database from data/*.csv (the CSVs are the source of truth).
2. Reads the sitemaps and re-fetches only books that are new or whose lastmod changed.
3. Writes data/books.csv and the two reviews files, sorted so diffs stay small.
   With --db-gz it also rewrites data/bookmarks.db.gz.

A book that could not be fetched this run keeps its previous data and its old
lastmod, so the next run tries it again instead of dropping it.
"""
import argparse, csv, gzip, os, shutil, sqlite3, sys, tempfile
from types import SimpleNamespace

import bookmarks_scraper as bm

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
UA = "BookMarksResearchMirror/1.0 (+https://github.com/mjsilverman19/book-critic-data)"
REVIEW_FILES = ("reviews_before_2021.csv", "reviews_2021_onward.csv")

csv.field_size_limit(sys.maxsize)


def read(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def rebuild(db_path):
    db = sqlite3.connect(db_path)
    db.executescript(bm.SCHEMA)
    books = read("books.csv")
    cols = list(books[0].keys())
    db.executemany(f"INSERT INTO books({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                   [[r[c] if r[c] != "" else None for c in cols] for r in books])
    rcols = ["book_slug", "idx", "rating_label", "rating_value", "critic", "critic_slug", "outlet", "review_url", "pull_quote"]
    for name in REVIEW_FILES:
        db.executemany(f"INSERT INTO reviews VALUES ({','.join('?' * len(rcols))})",
                       [[r[c] if r[c] != "" else None for c in rcols] for r in read(name)])
    db.commit()
    return db, {r["slug"]: (r["lastmod"], r["status"], r["fetched_at"] or None) for r in books}


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="max books to fetch this run (0 = all changed)")
    ap.add_argument("--delay", type=float, default=10.0, help="seconds between requests (robots.txt asks for 10)")
    ap.add_argument("--db-gz", action="store_true", help="also rewrite data/bookmarks.db.gz")
    a = ap.parse_args()

    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "bookmarks.db")
    db, before = rebuild(db_path)
    db.close()

    bm.crawl(SimpleNamespace(db=db_path, delay=a.delay, workers=1, limit=a.limit, order="newest",
                             ua=UA, refresh_sitemap=True))

    db = sqlite3.connect(db_path)
    # books we already had but could not refresh: restore old status and lastmod so they are retried next run
    stuck = db.execute("SELECT slug FROM books WHERE status IN ('pending','error')").fetchall()
    restored = 0
    for (slug,) in stuck:
        if slug in before:
            lastmod, status, fetched_at = before[slug]
            db.execute("UPDATE books SET status=?, lastmod=?, fetched_at=?, error=NULL WHERE slug=?",
                       (status, lastmod, fetched_at, slug))
            restored += 1
    db.commit()
    print(f"{restored} previously known books kept their old data; "
          f"{len(stuck) - restored} new books still pending", flush=True)

    out = os.path.join(tmp, "export")
    bm.export(SimpleNamespace(db=db_path, out=out))

    with open(os.path.join(out, "books.csv"), newline="", encoding="utf-8") as f:
        r = csv.reader(f); header = next(r)
        si, di = header.index("slug"), header.index("date_published")
        books = sorted(r, key=lambda x: (x[si],))
        books.sort(key=lambda x: x[di] or "", reverse=True)
    write_csv(os.path.join(DATA, "books.csv"), header, books)

    with open(os.path.join(out, "reviews.csv"), newline="", encoding="utf-8") as f:
        r = csv.reader(f); header = next(r)
        si, ii, di = header.index("book_slug"), header.index("idx"), header.index("date_published")
        rows = sorted(r, key=lambda x: (x[si], int(x[ii])))
        rows.sort(key=lambda x: x[di] or "", reverse=True)
    old = [x for x in rows if (x[di] or "")[:4] < "2021"]
    new = [x for x in rows if (x[di] or "")[:4] >= "2021"]
    write_csv(os.path.join(DATA, REVIEW_FILES[0]), header, old)
    write_csv(os.path.join(DATA, REVIEW_FILES[1]), header, new)
    print(f"{len(books)} books, {len(rows)} reviews ({len(old)} before 2021, {len(new)} from 2021)")

    if a.db_gz:
        with open(db_path, "rb") as src, gzip.GzipFile(os.path.join(DATA, "bookmarks.db.gz"), "wb", 9, mtime=0) as dst:
            shutil.copyfileobj(src, dst)
        print("wrote data/bookmarks.db.gz")
    shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
