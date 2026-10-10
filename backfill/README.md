# Backfill pipeline

Scripts that build `data/backfill/`. Run them from an empty working directory (for example `backfill/work/`, which is git-ignored). They write raw downloads and intermediate files there.

```
export GUARDIAN_API_KEY=...   # free developer key, open-platform.theguardian.com
export NYT_API_KEY=...        # free key with the Archive API enabled, developer.nytimes.com
mkdir -p backfill/work && cd backfill/work
python3 ../cr_urls.py      # Complete Review title index -> cr_urls.txt
python3 ../cr_fetch.py     # review pages -> cr_html/ (3 workers, 1 s delay each)
python3 ../cr_parse.py     # -> cr_books.csv, cr_reviews.csv
python3 ../g_fetch.py      # Guardian books reviews -> guardian/ (about 180 calls)
python3 ../g_parse.py && python3 ../g_books.py   # -> guardian_reviews.parquet with book title/author
python3 ../nyt_fetch.py    # NYT archive, one call per month, 13 s apart -> nyt/
python3 ../build.py        # quote model, CR grade mapping, Guardian model -> backfill_all.parquet
python3 ../build_nyt.py    # NYT rows -> nyt_backfill.parquet
python3 ../export.py       # -> out/backfill/*.csv, copy into data/backfill/
```

Requires pandas, scikit-learn, scipy, pyarrow and joblib. `build.py` records the quote model's cross-validation figures from an earlier run instead of recomputing them, since the full fit takes about half an hour on two cores.
