import json,glob,pandas as pd,re
rows=[]
for f in sorted(glob.glob('guardian/p*.json')):
    for r in json.load(open(f))['results']:
        F=r.get('fields',{}); T=r.get('tags',[])
        kw=[t for t in T if t['type']=='keyword']
        rows.append(dict(guardian_id=r['id'],review_url=r['webUrl'],date=r['webPublicationDate'][:10],
          headline=F.get('headline'),standfirst=re.sub(r'<[^>]+>','',F.get('standfirst') or ''),byline=F.get('byline'),
          critic='; '.join(t['webTitle'] for t in T if t['type']=='contributor'),
          publication=F.get('publication'),star_rating=F.get('starRating'),wordcount=F.get('wordcount'),isbn=F.get('isbn'),
          person_tags='; '.join(t['webTitle'] for t in kw if t.get('keywordType')=='person'),
          keyword_tags='; '.join(t['id'] for t in kw),body=F.get('bodyText')))
d=pd.DataFrame(rows).drop_duplicates('guardian_id'); d.to_parquet('guardian_reviews.parquet')
d['y']=d.date.str[:4].astype(int)
print(len(d)); print(d.groupby(d.y//5*5).size().to_string()); print(d.publication.value_counts().head()); print('stars',d.star_rating.notna().sum(),'isbn',d.isbn.notna().sum())
print(d[d.y==2005][['headline','standfirst','critic','person_tags']].head(5).to_string())
