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
import os
if os.path.exists('hc_enrich.jsonl'):
    hc=pd.read_json('hc_enrich.jsonl',lines=True)
    for c in ['description','cover_url','hc_slug','release_year']:
        if c not in hc: hc[c]=None
    hc=hc[['book_key','description','cover_url','hc_slug','release_year']].rename(columns={'description':'hc_desc','cover_url':'hc_cover'})
    E=E.merge(hc,on='book_key',how='outer')
else:
    E['hc_desc']=None; E['hc_cover']=None; E['hc_slug']=None; E['release_year']=None
E['description_source']=None
E.loc[E.description.notna(),'description_source']='openlibrary'
h=E.description.isna()&E.hc_desc.notna()&(E.hc_desc.astype(str).str.len()>40)
E.loc[h,'description']=E.loc[h,'hc_desc']; E.loc[h,'description_source']='hardcover'
E['cover_url']=E.cover_url.fillna(E.hc_cover)
E['first_publish_year']=E.first_publish_year.fillna(E.release_year)
m=E.description.isna()&E.wp_extract.notna()
E.loc[m,'description']=E.loc[m,'wp_extract']; E.loc[m,'description_source']='wikipedia'
E['description']=E.description.map(trim)
E['first_publish_year']=E.first_publish_year.astype('Int64')
E['subjects']=E.subjects.map(lambda x:'; '.join(x) if isinstance(x,list) else None)
E['hardcover_url']=E.hc_slug.map(lambda k:'https://hardcover.app/books/'+k if isinstance(k,str) else None)
E['openlibrary_url']=E.ol_work.map(lambda k:'https://openlibrary.org'+k if isinstance(k,str) else None)
out=E[['book_key','description','description_source','cover_url','publisher','first_publish_year','isbn','subjects','openlibrary_url','hardcover_url','wp_url']].rename(columns={'wp_url':'wikipedia_url'})
out.to_csv('out/backfill/books_enrichment.csv',index=False)
print(len(out),out.description.notna().mean().round(3),out.cover_url.notna().mean().round(3),out.description_source.value_counts().to_dict())
