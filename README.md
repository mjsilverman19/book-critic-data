# Book Critic Data

A dataset of professional book reviews, each reduced to a rating of rave, positive, mixed or pan, with a static explorer and a personal shelf that recommends books from critics whose judgments match yours.

The main review set covers about 62,000 books, 192,000 reviews, 30,000 critics and 2,700 outlets.

- [Explorer](#explorer)
- [Shelf and recommendations](#shelf-and-recommendations)
- [Main review set](#main-review-set)
- [Backfill: older reviews](#backfill-older-reviews)
- [Repository layout](#repository-layout)

## Explorer

`site/` is a static site published to GitHub Pages. It has four browsing views and a personal shelf:

| View | What it shows |
|---|---|
| Books | Every book with its date, overall verdict, review count, count of each rating, mean and adjusted mean. Filter by genre, publisher, year, author and minimum reviews; search by title, author, publisher or ISBN |
| Critics | Each critic's review count, outlets, rating counts, mean and "vs. others" |
| Authors | Each author's books, reviews, rating counts, mean and adjusted mean |
| Outlets | The same figures as critics, by publication |
| Shelf | Your rated and saved books, recommendations, and critics to follow (see below) |

Every column sorts. Lists load 150 rows at a time as you scroll. Filters, search, sort and the current page live in the URL, so any view can be bookmarked or shared.

Each book has a page with its publication details, rating counts, description, cover (click to enlarge) and every review with its rating, date, critic, outlet, pull quote and a link to the full review where one exists. Critic and outlet pages list every review with the book, the rating, the mean of the other reviews of that book, and the difference.

Hovering over a book title anywhere, or focusing it with the keyboard, opens a preview with the cover, synopsis, publication details and review summary. Escape dismisses it. On touch screens the title opens the book page directly.

Adding `src=bm` to the URL's query restricts every figure to the main review set, and `src=bf` to the backfill.

### Figures

- **Adjusted** pulls a book's or author's mean toward the overall mean (3.27) as if it had 10 extra average reviews, so books with a handful of raves don't dominate. See [Ranking note](#ranking-note).
- **Vs. others** is the mean difference between a critic's or outlet's rating and the average of the other reviews of the same book, counted only for books with four or more reviews and shown only when there are at least 20 such reviews.
- **Overall** is the overall verdict published with each book's reviews in the main review set.

The build merges outlet spellings ("The Guardian" and "The Guardian (UK)"), publisher spellings ("Graywolf" and "Graywolf Press"; co-published titles go to the first-named imprint), and critic spellings that share a slug or differ only in case.

### Building and deploying

```
python3 site/build.py
python3 -m http.server -d site
```

`site/build.py` turns the CSVs into `site/data/books.json`, `site/data/index.json` (one compact row per review) and 128 shards of per-book detail under `site/data/reviews/`, which pages fetch on demand. `.github/workflows/pages.yml` runs it and publishes the site on every push to `main` that touches `data/` or `site/`, and after each data refresh. On deploy the build appends a content hash to the script and stylesheet links, so a browser never pairs a new page with a cached old script.

## Shelf and recommendations

Each book page ends its stats line with a rating menu: rave, positive, mixed, pan, or want to read. Choosing one adds the book to your **Shelf**, which has the same search and filters as the books table but searches only your books. The shelf is stored in the browser's local storage, so it stays on that browser and device and is lost if site data is cleared.

Beneath the shelf, **For you** ranks books you have not shelved, 25 at a time, and **Critics to follow** lists critics who rated your books as you did, with what else they raved. Both run in the browser on the data the explorer already loads; the code is in `site/shelf.js`.

- **Baseline.** Each rated review is modeled as global mean + reviewer lean + book quality, fitted by six rounds of regularized alternating means (book quality shrunk as if it had 5 extra average reviews, reviewer lean as if 10). Book quality is the consensus with each reviewer's leniency removed. The reader gets a lean too, and each rated book a residual: how much more or less the reader liked it than expected.
- **Likely rating.** The reader's baseline for the book, plus a small adjustment from critics whose residuals correlate with the reader's over two or more shared books (correlation with 0.5 added to each sum of squares, scaled by shared / (shared + 3), the adjustment divided by total weight + 3). Shown as "Likely".
- **Taste votes.** Every critic who reviewed a book you rated gets a weight: the sum over shared books of 1 − |their rating − yours| / 3, divided by √(1 + their review count), so a specialist who matched you counts for more than an outlet that reviews everything. Their raves of books you have not shelved add the weight, their pans subtract it. Each book's total is divided by (reviews + 1)^0.15 and scaled so the largest is 1.
- **Order.** Likely rating + 2 × taste votes + 0.5 × the share of your shelf in the book's best-matching genre + 0.3 for an author you rated above expectation. Each further book by an author already listed drops 0.15. "Why" names the two critics who pushed the book up most.
- **Critics to follow.** Signed critics with five or more reviews who rated every shared book within one step of you and have raves you have not shelved, ranked by summed agreement / log2(2 + review count). Each row shows their ratings of your books and up to three of their best-regarded raves you have not shelved.

Only books with three or more rated reviews are recommended. One review per critic and book is counted, since a few critics appear in both the main set and the backfill.

### How the weights were chosen

An offline test treats 150 critics with 50 or more reviews as readers: some of their ratings become the shelf, the rest are hidden, and all of their reviews are removed from the data. With 12 rated books, 6.3% of the critic's hidden raves land in the top 100 (3.2% without the taste votes); with 30, 7.3% (2.8%). The baseline orders hidden books correctly in 64.5% of pairs at 20 ratings and 66.0% at 50, against 64.2% and 65.7% for the adjusted mean.

Agreement between critics' deviations from consensus turned out to be a weak signal, since most critics share only a book or two with any reader. A matrix factorization and a description-similarity model were also tried and added nothing.

## Main review set

### Files

| File | Contents |
|---|---|
| `data/books.csv` | One row per book: 17,362 rows |
| `data/reviews_before_2021.csv` | Reviews of books published before 2021, or with no date (68,511 rows) |
| `data/reviews_2021_onward.csv` | Reviews of books published 2021 onward (52,461 rows) |
| `data/bookmarks.db.gz` | SQLite database with both tables. Unzip with `gunzip data/bookmarks.db.gz` |

The two reviews files have the same columns. They're split only to stay under GitHub's file size limits. Stack them to get the full table.

### Columns

**books.csv**

| Column | Notes |
|---|---|
| `slug` | Source URL slug, the join key to reviews |
| `url`, `lastmod` | Book page URL and sitemap last-modified time |
| `title`, `author`, `publisher`, `date_published` | From the book page |
| `isbn` | ISBN-13 for most books. Older entries often have an ISBN-10 |
| `genres` | JSON array of the source's categories, e.g. `["Non-Fiction", "Memoir"]` |
| `description`, `cover_url` | Blurb and cover image |
| `overall_label`, `overall_value` | Published overall verdict (rave/positive/mixed/pan, 4 to 1) |
| `review_count_stated` | Review count the source shows |
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
| `review_url` | Link to the full review, where the source gives one |
| `pull_quote` | Excerpt chosen by the source's editors |
| `title`, `author`, `date_published` | Copied from the book for convenience |

### How it was collected

`bookmarks_scraper.py` reads the source's WordPress sitemaps to list every book page. For each book it parses the schema.org markup on the book page, then fetches the full review list when the book has more than the three reviews shown on the main page. The initial crawl ran with 4 parallel connections at about 1 request per second each, which is faster than the 10-second delay in the source's robots.txt.

```
pip install requests beautifulsoup4 lxml
python3 bookmarks_scraper.py crawl --db bookmarks.db --workers 4 --delay 1
python3 bookmarks_scraper.py export --db bookmarks.db --out export
python3 bookmarks_scraper.py stats --db bookmarks.db
```

A crawl can be stopped and resumed. Rerunning with `--refresh-sitemap` only fetches books whose sitemap entry has changed.

### Staying current

`.github/workflows/refresh.yml` runs daily at 6:17 a.m. Eastern. It rebuilds the database from the CSVs, reads the sitemaps, and fetches only books that are new or whose sitemap `lastmod` changed, at the 10-second pace robots.txt asks for. Changed CSVs are committed to `main` and the explorer redeploys. A book that fails to fetch keeps its previous data and is retried the next day. Each run fetches at most 900 books; anything beyond that carries over. `data/bookmarks.db.gz` is rewritten on the first of each month, since a daily rewrite of a large binary file would bloat the repository. You can also run it by hand from the Actions tab ("Refresh data", Run workflow), with an option to rewrite the database file.

To do the same locally: `python3 update_data.py --limit 50`.

### Known issues

- **Ratings come from labels.** 113 reviews had corrupt values in the source's hidden numeric rating field (0 on some positives, 5 to 44 on some raves). Every `rating_value` here is derived from the Rave/Positive/Mixed/Pan label.
- **13 books are `partial`.** Their full review list returns a server error on every request, so only the three reviews shown on the main book page are included.
- **19 books have no usable date.** Most show the source's placeholder `-0001-11-30`.
- **30 books have no ISBN.**
- **35 reviews appear twice** because they're duplicated at the source. The explorer drops the duplicates.
- **8 reviews have no outlet.**
- **Placeholder reviews were dropped.** A few books have an empty review entry in the source's markup. These are skipped, so `review_count_parsed` can be one lower than the count the source shows.

### Ranking note

A simple average of review scores favors books with very few reviews: 774 books have a perfect 4.0, mostly from three to six reviews. A fairer ranking pulls each book's average toward the overall mean (3.27) as if it had 10 extra average reviews:

```
adjusted = (n * mean_score + 10 * 3.27) / (n + 10)
```

## Backfill: older reviews

`data/backfill/` extends the data to books reviewed before the main set begins in 2016. It draws on three sources, kept separate from the main tables so the original crawl stays untouched. Every rating states how it was produced.

| Source | What it gives | Rating |
|---|---|---|
| [The Complete Review](https://www.complete-review.com) | Per-critic review summaries, mostly international fiction, with outlet, critic, date and a quote (26,074 rows) | Michael Orthofer's letter grade for the review where he gives one; otherwise predicted from the quote |
| Guardian Open Platform | Every review in the Guardian and Observer books section, 1999 onward (35,548 rows) | Predicted from the full text |
| NYT Archive API | Daily and Sunday Book Review reviews of single books, 1990 onward (31,663 rows) | None (see below) |

### Files

| File | Contents |
|---|---|
| `data/backfill/reviews_backfill.csv` | One row per review (93,285 rows) |
| `data/backfill/books_backfill.csv` | One row per book (52,800 rows), with counts of each rating |
| `data/backfill/books_enrichment.csv` | Summary, cover, publisher, first publication year, ISBN and subjects for 46,285 backfill books. Summaries come from Open Library (17,881), Hardcover (5,108) or Wikipedia intros (CC BY-SA; `wikipedia_url` links the source); 31,560 books have a cover |
| `data/backfill/model_metrics.json` | Validation figures for each rating method |
| `backfill/` | Scripts that fetch, parse, train, enrich and export. `backfill/README.md` lists the order to run them and the API keys they need |

### Columns

`reviews_backfill.csv` follows the main reviews schema where it can and adds:

| Column | Notes |
|---|---|
| `source` | `complete_review`, `guardian_api` or `nyt_api` |
| `book_key` | Normalized title plus author surname, used to group reviews of one book across sources |
| `bookmarks_slug` | The matching book in the main set, when there is one |
| `title`, `author`, `book_year` | The book reviewed, as parsed from the source |
| `review_date` | Publication date of the review |
| `rating_method` | `cr_grade` (Complete Review grade, mapped), `model_quote`, `model_fulltext`, `unrated_weak_model` (NYT), `unrated_non_english` (a German, French or other non-English quote, which the English-trained model does not score), or blank for 5,226 Complete Review entries with neither a grade nor a quote |
| `native_grade` | Complete Review letter grade, or a Guardian star rating where the Guardian printed one |
| `predicted_value` | Model score on the 1 to 4 scale, before bucketing into a label |
| `in_bookmarks` | The same review (same book and outlet, or same URL) is already in the main tables (11,749 rows) |
| `also_in_complete_review` | A Guardian or NYT review that Complete Review also lists (1,404 rows). Drop these rows to avoid counting a review twice |
| `pull_quote` | Complete Review's quote, the Guardian standfirst, or the NYT abstract. No full review text is stored |
| `review_url`, `source_url` | The review itself, and the page it was found on |

### How ratings were made

**Complete Review grades.** Orthofer grades many of the reviews he lists from A+ to F. Where a review appears in both his data and the main set, his grades line up with the main set's labels: A+ and A average 3.85 to 3.9 on the 1 to 4 scale, A- and B+ 3.0 to 3.1, B 2.7, B- and the Cs 1.6 to 2.25, D and F 1.0 to 2.0. The mapping used is A+/A to rave, A-/B+/B to positive, B- through C- to mixed, D and F to pan. On 314 overlapping reviews it matches the main set's label exactly 73% of the time and is within one step 97% of the time.

**Quote model.** A logistic regression on word and character n-grams, trained on the main set's 121,000 pull quotes and their labels. Tested on books held out of training, its expected score correlates 0.66 with the true rating for a single review and 0.75 with a book's mean rating for books with four or more reviews. Cut points are set so predicted labels match the main set's label distribution.

**Guardian full-text model.** A ridge regression on the review text plus summary features from the quote model run over each sentence, trained on the 4,414 Guardian and Observer reviews the main set has already labeled. Cross-validated correlation is 0.65, exact label agreement 60%, within one step 96%.

**NYT.** The archive API returns the headline, abstract and first paragraph, not the review. A model on those fields reached only 0.29 correlation with the main set's labels, too weak to publish as a rating. NYT rows record which books the Times reviewed, when and by whom, with `rating_label` blank and the weak score in `predicted_value`.

### In the explorer

The explorer treats backfill reviews like the main set's. Books that are not in the main set get their own pages, with covers and summaries from `books_enrichment.csv` where a match was found. Unrated reviews (NYT, non-English Complete Review quotes) appear on book, critic and outlet pages and in review counts, and are left out of the rating counts, means and recommendations. Rows marked `in_bookmarks` or `also_in_complete_review`, and rows with a blank `book_key`, are skipped so no review appears twice.

### Caveats

Model ratings carry noise at the level of a single review and are better used in aggregate. The quote model learned from pull quotes chosen to be quotable, so its scores on other text can run stronger than the review as a whole. Book identification in Guardian reviews is parsed from headlines and publication lines and fails for roundups and essays, which keep their row but have a blank `book_key` (9,607 Guardian rows). Titles are grouped on the part before any colon, so numbered volumes of one work (Knausgaard's *My Struggle*, for example) share a `book_key`. Complete Review covers international and translated fiction far more than the main set does, so the two samples differ in kind as well as in period. Some Complete Review dates are malformed at the source (a 1969 review dated `1069-05-23`, for example). Guardian content is used under the Open Platform terms; only short standfirsts and links are redistributed.

## Repository layout

| Path | Purpose |
|---|---|
| `data/` | The main review set, and `data/backfill/` for older reviews |
| `bookmarks_scraper.py` | Crawler and exporter for the main review set |
| `update_data.py` | Daily incremental refresh, run by `.github/workflows/refresh.yml` |
| `backfill/` | Pipeline for the backfill and its enrichment |
| `site/index.html` | Explorer page: views, tables, routing |
| `site/preview.js`, `site/preview.css` | Hover previews of books |
| `site/shelf.js` | Ratings, shelf, recommendations and critics to follow |
| `site/build.py` | Builds the explorer's JSON from the CSVs |
| `.github/workflows/pages.yml` | Builds and publishes the explorer |
| `requirements.txt` | Python packages for the scraper and refresh |
