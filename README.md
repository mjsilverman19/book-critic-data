This is a copy of [Book Marks](https://bookmarks.reviews), Lit Hub's book review aggregator, crawled on October 9, 2026. It covers 17,362 books and 120,972 reviews from 2,415 outlets and about 19,000 critics. Most books were published 2015 to 2026.

## Explorer

`site/` is a static browser for the data: search, sortable tables of books, critics and outlets, and a page for each with its reviews. A GitHub Actions workflow builds it from the CSVs and publishes it to GitHub Pages on every push to `main` that touches `data/` or `site/`.

Hover over a book title (or focus it with the keyboard) for a preview with its cover, synopsis, publication details, and review summary. Previews also work in critic and outlet book lists. Press Escape to dismiss; clicking the title opens the full book page. Covers and descriptions load on demand from the existing review shards, with a fallback when an image or description is unavailable. Touch users can open the title directly.

To run it locally:

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

## Staying current

`.github/workflows/refresh.yml` runs daily at 6:17 a.m. Eastern. It rebuilds the database from the CSVs, reads the sitemaps, and fetches only books that are new or whose sitemap `lastmod` changed, at the 10-second pace robots.txt asks for. Changed CSVs are committed to `main` and the explorer redeploys. A book that fails to fetch keeps its previous data and is retried the next day. Each run fetches at most 900 books; anything beyond that carries over. `data/bookmarks.db.gz` is rewritten on the first of each month, since a daily rewrite of a large binary file would bloat the repository. You can also run it by hand from the Actions tab ("Refresh data", Run workflow), with an option to rewrite the database file.

To do the same locally: `python3 update_data.py --limit 50`.

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

## Backfill: reviews before Book Marks

`data/backfill/` extends the data to books reviewed before Book Marks began in 2016. It draws on two sources so far, kept separate from the Book Marks tables so the original crawl stays untouched. Every rating states how it was produced.

| Source | What it gives | Rating |
|---|---|---|
| [The Complete Review](https://www.complete-review.com) | Per-critic review summaries for about 5,600 books, mostly international fiction, with outlet, critic, date and a quote | Orthofer's letter grade for the review where he gives one; otherwise predicted from the quote |
| Guardian Open Platform | Every review in the Guardian and Observer books section, 1999 onward | Predicted from the full text |

### Files

| File | Contents |
|---|---|
| `data/backfill/reviews_backfill.csv` | One row per review (61,622 rows) |
| `data/backfill/books_backfill.csv` | One row per book (26,713 rows), with counts of each rating |
| `data/backfill/model_metrics.json` | Validation figures for each rating method |
| `backfill/` | Scripts that fetch, parse, train and export |

### Columns

`reviews_backfill.csv` follows the Book Marks reviews schema where it can and adds:

| Column | Notes |
|---|---|
| `source` | `complete_review` or `guardian_api` |
| `book_key` | Normalized title plus author surname, used to group reviews of one book across sources |
| `bookmarks_slug` | The matching Book Marks book, when there is one |
| `rating_method` | `cr_grade` (Complete Review grade, mapped), `model_quote`, or `model_fulltext` |
| `native_grade` | Complete Review letter grade, or a Guardian star rating where the Guardian printed one |
| `predicted_value` | Model score on the 1 to 4 scale, before bucketing into a label |
| `in_bookmarks` | The same review (same book and outlet, or same URL) is already in the Book Marks tables |
| `also_in_complete_review` | A Guardian review that Complete Review also lists. Drop these rows to avoid counting a review twice |
| `pull_quote` | Complete Review's quote, or the Guardian standfirst. No full review text is stored |

### How ratings were made

**Complete Review grades.** Orthofer grades many of the reviews he lists from A+ to F. Where a review appears in both his data and Book Marks, the grades line up with Book Marks labels: A+ and A average 3.85 to 3.9 on the 1 to 4 scale, A- and B+ 3.0 to 3.1, B 2.7, B- and the Cs 1.6 to 2.25, D and F 1.0 to 2.0. The mapping used is A+/A to rave, A-/B+/B to positive, B- through C- to mixed, D and F to pan. On 314 overlapping reviews it matches the Book Marks label exactly 73% of the time and is within one step 97% of the time.

**Quote model.** A logistic regression on word and character n-grams, trained on Book Marks' 121,000 pull quotes and their labels. Tested on books held out of training, its expected score correlates 0.66 with the true rating for a single review and 0.75 with a book's mean rating for books with four or more reviews. Cut points are set so predicted labels match the Book Marks label distribution.

**Guardian full-text model.** A ridge regression on the review text plus summary features from the quote model run over each sentence, trained on the 4,414 Guardian and Observer reviews that Book Marks has already labeled. Cross-validated correlation is 0.65, exact label agreement 60%, within one step 96%.

### Caveats

Model ratings carry noise at the level of a single review and are better used in aggregate. The quote model learned from Book Marks pull quotes, which are chosen to be quotable, so its scores on other text can run stronger than the review as a whole. Book identification in Guardian reviews is parsed from headlines and publication lines and fails for roundups and essays, which keep their row but have a blank `book_key`. Titles are grouped on the part before any colon, so numbered volumes of one work (Knausgaard's *My Struggle*, for example) share a `book_key`. Complete Review covers international and translated fiction far more than Book Marks does, so the two samples differ in kind as well as in period. Guardian content is used under the Open Platform terms; only short standfirsts and links are redistributed.
