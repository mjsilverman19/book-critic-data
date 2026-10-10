import pandas as pd, json
ol=pd.read_json('ol_enrich.jsonl',lines=True).drop_duplicates('book_key',keep='last')
wp=pd.read_json('wp_enrich.jsonl',lines=True).drop_duplicates('book_key',keep='last')
for c in ['wp_url','wp_extract']:
    if c not in wp: wp[c]=None
E=ol.merge(wp[['book_key','wp_url','wp_extract']],on='book_key',how='outer')
for c in ['description','cover_url','publisher','first_publish_year','isbn','ol_work','subjects']:
    if c not in E: E[c]=None
def trim(t):
    if not isinstance(t,str): return None
    t=t.strip(); return t if len(t)<=1500 else t[:1500].rsplit('. ',1)[0]+'.'
E['description_source']=None
E.loc[E.description.notna(),'description_source']='openlibrary'
m=E.description.isna()&E.wp_extract.notna()
E.loc[m,'description']=E.loc[m,'wp_extract']; E.loc[m,'description_source']='wikipedia'
E['description']=E.description.map(trim)
E['first_publish_year']=E.first_publish_year.astype('Int64')
E['subjects']=E.subjects.map(lambda x:'; '.join(x) if isinstance(x,list) else None)
E['openlibrary_url']=E.ol_work.map(lambda k:'https://openlibrary.org'+k if isinstance(k,str) else None)
out=E[['book_key','description','description_source','cover_url','publisher','first_publish_year','isbn','subjects','openlibrary_url','wp_url']].rename(columns={'wp_url':'wikipedia_url'})
out.to_csv('out/backfill/books_enrichment.csv',index=False)
print(len(out),out.description.notna().mean().round(3),out.cover_url.notna().mean().round(3),out.description_source.value_counts().to_dict())
