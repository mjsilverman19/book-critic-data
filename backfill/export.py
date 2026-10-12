import pandas as pd, numpy as np, json, os
exec(open(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)),'common.py')).read())
LAB={1:'pan',2:'mixed',3:'positive',4:'rave'}
A=pd.read_parquet('backfill_all.parquet')
if os.path.exists('nyt_backfill.parquet'):
    N=pd.read_parquet('nyt_backfill.parquet'); N['outlet_key']=N.outlet.map(okey)
    bmset=set(zip(bm.bk,bm.ok)); bmurl=set(bm.uk.dropna())
    N['in_bookmarks']=[(b,o) in bmset or (norm_url(u) in bmurl) for b,o,u in zip(N.book_key,N.outlet_key,N.review_url)]
    N['bookmarks_slug']=N.book_key.map(slug_of)
    crk=set(zip(A[A.source=='complete_review'].book_key,A[A.source=='complete_review'].outlet_key))
    N['also_in_complete_review']=[(b,o) in crk for b,o in zip(N.book_key,N.outlet_key)]
    A=pd.concat([A,N],ignore_index=True)
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'lang.py')).read())
# the quote model is English-only: leave non-English Complete Review quotes unrated
ne=(A.rating_method=='model_quote')&~A.pull_quote.map(is_english)
A.loc[ne,['rating_value','predicted_value']]=np.nan; A.loc[ne,'rating_method']='unrated_non_english'
# full-text sources rated by the Guardian-trained model (TLS, Literary Review, Independent, ...)
import glob as _g
for p in sorted(_g.glob('extra_*.parquet')):
    X=pd.read_parquet(p)
    X=pd.DataFrame(dict(source=X.source,book_key=X.book_key,title=X.title,author=X.author,book_year=X['book_year'] if 'book_year' in X else None,outlet=X.outlet,critic=X.critic,
        review_date=X.review_date,native_grade=X.get('native_grade'),rating_value=X.rv,predicted_value=X.pred,rating_method=X.get('rating_method','model_fulltext'),
        pull_quote=X.standfirst,review_url=X.review_url,source_url=X.review_url,original_language=None,genre=None,headline=X.get('headline')))
    X['outlet_key']=X.outlet.map(okey)
    bmset=set(zip(bm.bk,bm.ok)); bmurl=set(bm.uk.dropna())
    X['in_bookmarks']=[(b,o) in bmset or (norm_url(u) in bmurl) for b,o,u in zip(X.book_key,X.outlet_key,X.review_url)]
    X['bookmarks_slug']=X.book_key.map(slug_of)
    crk=set(zip(A[A.source=='complete_review'].book_key,A[A.source=='complete_review'].outlet_key))
    X['also_in_complete_review']=[(b,o) in crk for b,o in zip(X.book_key,X.outlet_key)]
    A=pd.concat([A,X],ignore_index=True)
    print('added',p,len(X))
# ---- clean-up rules that apply to every source ----
n0=len(A)
crit=A.critic.fillna('').map(lambda c: na(c) if c else '')
auth=A.book_key.fillna('|').str.split('|').str[1]
# a reviewer's own book named in a bio line or column footer is not the book under review
own=(crit!='')&(crit==auth)&A.source.isin(['guardian_api','nyt_api','tls','independent','literary_review'])
# letters, guest columns and other non-review pieces that older archives tag with a book
junk=A.review_url.fillna('').str.contains(r'letters?-to-the-editor|/letters/|guest-word|editors-choice|best-sellers|paperback-row|new-noteworthy|notable-books|book-of-a-lifetime', regex=True) | (A.source.eq('guardian_api') & A.book_key.fillna('').str.endswith('|') & A.title.fillna('').str.contains(r"[’']s ", regex=True)) \
     | A.critic.fillna('').str.contains(r'Letters|New York City$|; ', regex=True)
A=A[~own & ~junk].copy()
# the same review published under several URLs, or the same critic on the same book in the same outlet and month
A['_k']=A.book_key.fillna('')+'#'+A.outlet.fillna('').map(okey)+'#'+A.critic.fillna('').map(lambda c: na(c) if c else '')+'#'+A.review_date.fillna('').astype(str).str[:7]
A=A[(A.book_key.isna())|~A.duplicated('_k')].drop(columns=['_k'])
print('clean-up removed',n0-len(A),'rows: own-book',int(own.sum()),'non-review pieces',int(junk.sum()))
# ---- clean-up rules that apply to every source ----
n0=len(A)
crit=A.critic.fillna('').map(lambda c: na(c) if c else '')
auth=A.book_key.fillna('|').str.split('|').str[1]
# a reviewer's own book named in a bio line or column footer is not the book under review
own=(crit!='')&(crit==auth)&A.source.isin(['guardian_api','nyt_api','tls','independent','literary_review'])
# letters, guest columns and other non-review pieces that older archives tag with a book
junk=A.review_url.fillna('').str.contains(r'letters?-to-the-editor|/letters/|guest-word|best-sellers|paperback-row|new-noteworthy|notable-books', regex=True) \
     | A.critic.fillna('').str.contains(r'Letters|New York City$|; ', regex=True)
A=A[~own & ~junk].copy()
# the same review published under several URLs, or the same critic on the same book in the same outlet and month
A['_k']=A.book_key.fillna('')+'#'+A.outlet.fillna('').map(okey)+'#'+A.critic.fillna('').map(lambda c: na(c) if c else '')+'#'+A.review_date.fillna('').astype(str).str[:7]
A=A[(A.book_key.isna())|~A.duplicated('_k')].drop(columns=['_k'])
print('clean-up removed',n0-len(A),'rows: own-book',int(own.sum()),'non-review pieces',int(junk.sum()))
A['rating_value']=A.rating_value.astype('Int64'); A['rating_label']=A.rating_value.map(LAB)
A['predicted_value']=pd.to_numeric(A.predicted_value,errors='coerce').round(3)
A.loc[A.critic.astype(str).str.strip().isin(['.','-','n.a.','']),'critic']=None
A.loc[A.book_key.fillna('').str.startswith('|'),'book_key']=None
A['review_year']=A.review_date.astype(str).str[:4]
cols=['source','book_key','bookmarks_slug','title','author','book_year','outlet','critic','review_date','rating_label','rating_value','rating_method',
      'native_grade','predicted_value','pull_quote','review_url','source_url','in_bookmarks','also_in_complete_review','original_language','genre','headline']
A=A[cols].sort_values(['source','review_date'])
os.makedirs('out/backfill',exist_ok=True)
# one file per source keeps each under GitHub's size limits
os.makedirs('out/backfill/reviews',exist_ok=True)
for src,part in A.groupby('source'):
    part.to_csv(f'out/backfill/reviews/{src}.csv',index=False)
# books
B=A.dropna(subset=['book_key']).copy(); B['labeled']=B.rating_method.eq('cr_grade')
g=B.groupby('book_key')
books=pd.DataFrame(dict(title=g.title.agg(lambda s:s.dropna().iloc[0] if s.notna().any() else None),author=g.author.agg(lambda s:s.dropna().iloc[0] if s.notna().any() else None),
   book_year=g.book_year.agg(lambda s:s.dropna().iloc[0] if s.notna().any() else None),first_review_date=g.review_date.min(),
   bookmarks_slug=g.bookmarks_slug.first(),n_reviews=g.size(),n_rated=g.rating_value.count(),
   mean_score=g.rating_value.mean().round(3),n_rave=g.rating_label.agg(lambda s:(s=='rave').sum()),n_positive=g.rating_label.agg(lambda s:(s=='positive').sum()),
   n_mixed=g.rating_label.agg(lambda s:(s=='mixed').sum()),n_pan=g.rating_label.agg(lambda s:(s=='pan').sum()),
   sources=g.source.agg(lambda s:';'.join(sorted(set(s)))))).reset_index()
books.to_csv('out/backfill/books_backfill.csv',index=False)
json.dump(json.load(open('metrics.json')),open('out/backfill/model_metrics.json','w'),indent=1)
print(len(A),len(books)); print(A.groupby(['source','rating_method']).size()); print(A.review_date.astype(str).str[:3].value_counts().sort_index().tail(8))
