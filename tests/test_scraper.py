import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bs4 import BeautifulSoup
import bookmarks_scraper as bm
import update_data

REVIEW = '''<span><div class="bookmarks_pullquote_reviewer">
<span class="review_rating rave">Rave</span>
<a class="reviewer_permalink" href="/reviewer/jane-doe/">Jane Doe,</a>
<a class="bookmarks_source_link" href="https://example.com/review">The Paper</a>
</div><div class="bookmarks_pullquote"><div class="bookmarks_a_review_pullquote">A fine book.</div></div></span>'''


class ScraperTests(unittest.TestCase):
    def test_jsonld_metadata_and_current_reviews(self):
        graph = [
            {"@type": "ImageObject", "@id": "#cover", "url": "https://example.com/cover.jpg"},
            {"@type": "Book", "name": "Example", "author": {"name": "An Author"},
             "publisher": {"name": "A Press"}, "image": {"@id": "#cover"},
             "datePublished": "2026-11-10", "isbn": "9780374618940",
             "genre": ["History"], "aggregateRating": {"ratingValue": 4, "reviewCount": 8}},
        ]
        html = '<script type="application/ld+json">' + json.dumps({"@graph": graph}) + '</script>'
        html += '<div class="book_review_stats"><div class="stat_total">Rave</div></div>'
        html += '<a class="bookmarks_detail_see_all_reviews" href="/reviews/all/example/">8 reviews</a>' + REVIEW
        meta, reviews = bm.parse_book(html)
        self.assertEqual(meta['title'], 'Example')
        self.assertEqual(meta['author'], 'An Author')
        self.assertEqual(meta['publisher'], 'A Press')
        self.assertEqual(meta['cover_url'], 'https://example.com/cover.jpg')
        self.assertEqual(meta['review_count_stated'], 8)
        self.assertEqual(meta['all_reviews_path'], '/reviews/all/example/')
        self.assertEqual(reviews[0], dict(rating_label='rave', rating_value=4, critic='Jane Doe',
            critic_slug='jane-doe', outlet='The Paper', review_url='https://example.com/review', pull_quote='A fine book.'))

    def test_legacy_microdata_and_authoritative_label(self):
        html = '''<div itemtype="http://schema.org/Book"><h1 itemprop="name">Old Book</h1>
        <span itemprop="author" itemtype="http://schema.org/Person"><span itemprop="name">Old Author</span></span>
        <div itemprop="review"><div class="bookmarks_pullquote_reviewer"><span class="review_rating">Mixed</span>
        <span itemprop="author" itemtype="http://schema.org/Person"><a href="/reviewer/critic/"><span itemprop="name">Critic</span></a></span>
        <a class="bookmarks_source_link" href="https://example.com/review">Paper</a></div>
        <span itemprop="reviewRating"><meta itemprop="ratingValue" content="44"></span>
        <div itemprop="reviewBody">Legacy quote.</div></div></div>'''
        meta, reviews = bm.parse_book(html)
        self.assertEqual((meta['title'], meta['author']), ('Old Book', 'Old Author'))
        self.assertEqual(len(reviews), 1)
        self.assertEqual((reviews[0]['rating_value'], reviews[0]['critic'], reviews[0]['pull_quote']), (2, 'Critic', 'Legacy quote.'))

    def test_unrecognized_page_preserves_existing_reviews(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / 'books.db')
            db = sqlite3.connect(path)
            db.executescript(bm.SCHEMA)
            db.execute("INSERT INTO books(slug,url,title,status) VALUES('example','https://example.com','Existing','pending')")
            db.execute("INSERT INTO reviews(book_slug,idx,pull_quote) VALUES('example',0,'Keep this')")
            db.commit(); db.close()
            response = SimpleNamespace(status_code=200, text='<html>Changed markup</html>', url='https://example.com')
            with patch.object(bm.Fetcher, 'get', return_value=response):
                bm.crawl(SimpleNamespace(db=path, delay=0, ua='test', refresh_sitemap=False, order='newest', limit=1, workers=1))
            db = sqlite3.connect(path)
            self.assertEqual(db.execute('SELECT title,status FROM books').fetchone(), ('Existing', 'error'))
            self.assertEqual(db.execute('SELECT pull_quote FROM reviews').fetchone()[0], 'Keep this')
            db.close()

    def test_refresh_errors_fail_before_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / 'books.db')
            def rebuild(db_path):
                db = sqlite3.connect(db_path); db.executescript(bm.SCHEMA)
                db.execute("INSERT INTO books(slug,status) VALUES('bad','error')"); db.commit()
                return db, {}
            with patch.object(update_data, 'rebuild', side_effect=rebuild), patch.object(bm, 'crawl'), patch.object(bm, 'export') as export, patch('sys.argv', ['update_data.py']):
                # Use a separate temporary directory because main removes its own workspace on failure.
                with self.assertRaisesRegex(RuntimeError, 'leaving committed data unchanged'):
                    update_data.main()
                export.assert_not_called()


if __name__ == '__main__':
    unittest.main()
