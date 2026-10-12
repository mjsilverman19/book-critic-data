import json,re,joblib,numpy as np,pandas as pd
exec(open(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)),'catalog.py')).read())
MON={m:i for i,m in enumerate(['january','february','march','april','may','june','july','august','september','october','november','december'],1)}
L=[json.loads(l) for l in open('hns_reviews.jsonl')]
rows=[]
for d in L:
    if not d.get('title') or not d.get('author') or not d.get('text') or len(d['text'])<300: continue
    cl=d.get('classes') or []
    me=[c for c in cl if c.startswith('mag_edition-')]
    date=None
    if me:
        m=re.search(r'-(january|february|march|april|may|june|july|august|september|october|november|december)-(\d{4})',me[0])
        if m: date=f"{m.group(2)}-{MON[m.group(1)]:02d}"
    if not date and d.get('date'):
        m=re.search(r'(\d{4})',d['date'])
        if m and int(m.group(1))>=1995: date=m.group(1)
    rows.append(dict(source='historical_novel_society',book_key=nt(d['title'])+'|'+na(d['author']),title=d['title'],author=d['author'],outlet='Historical Novels Review',
        critic=d.get('critic'),review_date=date,review_url=d['url'],text=d['text'],standfirst=d['text'][:240].rsplit(' ',1)[0]+'…',
        book_year=(d.get('pub_year') or [None])[0],ec=bool(d.get('editors_choice')),genres_hns=' '.join(c for c in cl if c.startswith(('genre-','periods-','centuries-')))))
T=pd.DataFrame(rows).drop_duplicates('review_url'); print(len(T),T.book_key.nunique(),'editors choice',T.ec.sum())
m=joblib.load('ft_guardian.joblib'); p,l=m.predict(T.text.values); T['pred']=p; T['rv']=l
T.loc[T.ec,'rv']=4; T['rating_method']=np.where(T.ec,'editors_choice','model_fulltext'); T['native_grade']=np.where(T.ec,"Editors' Choice",None)
print(T.rv.value_counts(normalize=True).sort_index().round(3).to_dict())
T.drop(columns=['text']).to_parquet('extra_hns.parquet')
