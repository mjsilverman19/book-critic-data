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
A['rating_value']=A.rating_value.astype('Int64'); A['rating_label']=A.rating_value.map(LAB)
A['predicted_value']=A.predicted_value.round(3)
A.loc[A.book_key.fillna('').str.startswith('|'),'book_key']=None
A['review_year']=A.review_date.astype(str).str[:4]
cols=['source','book_key','bookmarks_slug','title','author','book_year','outlet','critic','review_date','rating_label','rating_value','rating_method',
      'native_grade','predicted_value','pull_quote','review_url','source_url','in_bookmarks','also_in_complete_review','original_language','genre','headline']
A=A[cols].sort_values(['source','review_date'])
os.makedirs('out/backfill',exist_ok=True)
A.to_csv('out/backfill/reviews_backfill.csv',index=False)
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
