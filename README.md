This is a copy of [Book Marks](https://bookmarks.reviews), Lit Hub's book review aggregator, crawled on October 9, 2026. It covers 17,362 books and 120,972 reviews from 2,415 outlets and about 19,000 critics. Most books were published 2015 to 2026.

## Explorer

`site/` is a static browser for the data: search, sortable tables of books, critics and outlets, and a page for each with its reviews. A GitHub Actions workflow builds it from the CSVs and publishes it to GitHub Pages on every push to `main` that touches `data/` or `site/`. To run it locally:

```
python3 site/build.py
python3 -m http.server -d site
```

The build merges outlet spellings ("The Guardian" and "The Guardian (UK)"), publisher spellings ("Graywolf" and "Graywolf Press"; co-published titles go to the first-named imprint), and critic spellings that share a slug or differ only in case. "Vs. others" is the mean difference between a critic's or outlet's rating and the average of the other reviews of the same book, counted only for books with four or more reviews and shown only when there are at least 20 such reviews.

## Files

| File | Contents |
|---|---|
| `data/books.csv` | One row per book: 17,362 rows |
| `data/reviews_before_2021.csv` | Reviews of books published before 2021, or with no date (68,511 rows) |
| `data/reviews_2021_onward.csv` | Reviews of books published 2021 onward (52,461 rows) |
| `data/bookmarks.db.gz` | SQLite database with both tables. Unzip with `gunzip data/bookmarks.db.gz` |
| `bookmarks_scraper.py` | The scraper used to build the data, which also refreshes it |

The two reviews files have the same columns. They're split only to stay under GitHub's file size limits. Stack them to get the full table.

## Columns

**books.csv**

| Column | Notes |
|---|---|
| `slug` | Book Marks URL slug, the join key to reviews |
| `url`, `lastmod` | Book page URL and sitemap last-modified time |
| `title`, `author`, `publisher`, `date_published` | From the book page |
| `isbn` | ISBN-13 for most books. Older entries often have an ISBN-10 |
| `genres` | JSON array of Book Marks categories, e.g. `["Non-Fiction", "Memoir"]` |
| `description`, `cover_url` | Blurb and cover image |
| `overall_label`, `overall_value` | Book Marks' overall rating (rave/positive/mixed/pan, 4 to 1) |
| `review_count_stated` | Review count the site shows |
| `review_count_parsed` | Reviews actually collected |
| `n_rave`, `n_positive`, `n_mixed`, `n_pan` | Count of each rating |
| `mean_score` | Mean of review scores (rave 4, positive 3, mixed 2, pan 1) |
| `status` | `ok`, or `partial` (see below) |
| `fetched_at` | Crawl timestamp (UTC) |

**reviews_*.csv**

| Column | Notes |
|---|---|
| `book_slug`, `idx` | Book and the review's position on the page |
| `rating_label`, `rating_value` | rave/positive/mixed/pan and 4/3/2/1 |
| `critic`, `critic_slug` | Blank for unsigned reviews (Kirkus, Publishers Weekly, etc.) |
| `outlet` | Publication |
| `review_url` | Link to the full review, where the site gives one |
| `pull_quote` | Excerpt chosen by Book Marks |
| `title`, `author`, `date_published` | Copied from the book for convenience |

## How it was collected

The scraper reads the site's WordPress sitemaps to list every book page. For each book it parses the schema.org markup on the book page, then fetches `/reviews/all/<slug>/` when the book has more than the three reviews shown on the main page. The crawl ran with 4 parallel connections at about 1 request per second each, which is faster than the 10-second delay in the site's robots.txt.

```
pip install requests beautifulsoup4 lxml
python3 bookmarks_scraper.py crawl --db bookmarks.db --workers 4 --delay 1
python3 bookmarks_scraper.py export --db bookmarks.db --out export
python3 bookmarks_scraper.py stats --db bookmarks.db
```

A crawl can be stopped and resumed. Rerunning with `--refresh-sitemap` only fetches books whose sitemap entry has changed.

## Known issues

- **Ratings come from labels.** 113 reviews had corrupt values in the site's hidden numeric rating field (0 on some positives, 5 to 44 on some raves). Every `rating_value` here is derived from the Rave/Positive/Mixed/Pan label.
- **13 books are `partial`.** Their "all reviews" page returns a server error on every request, so only the three reviews shown on the main book page are included.
- **19 books have no usable date.** Most show the site's placeholder `-0001-11-30`.
- **30 books have no ISBN.**
- **35 reviews appear twice** because they're duplicated on the site.
- **8 reviews have no outlet.**
- **Placeholder reviews were dropped.** A few books have an empty review entry in the site's markup. These are skipped, so `review_count_parsed` can be one lower than the count shown on the site.

## Ranking note

A simple average of review scores favors books with very few reviews: 774 books have a perfect 4.0, mostly from three to six reviews. A fairer ranking pulls each book's average toward the overall mean (3.27) as if it had 10 extra average reviews:

```
adjusted = (n * mean_score + 10 * 3.27) / (n + 10)
```
