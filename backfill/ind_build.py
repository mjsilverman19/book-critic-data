import json,re,joblib,numpy as np,pandas as pd,html
exec(open(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)),'catalog.py')).read())
L={}
for l in open('ind_reviews.jsonl'):
    d=json.loads(l)
    if d.get('headline') and d.get('text'): L[d['url']]=d
def parse_head(h):
    h=html.unescape(h); h=re.sub(r'\s*\|\s*The Independent.*$','',h).strip()
    h=re.sub(r'^(?:Book|Books|Audiobook|Paperback|Fiction|Non-fiction|Poetry|Book of a lifetime) ?(?:reviews?)?(?: of the week| round-up)?\s*[:\-–]\s*','',h,flags=re.I)
    h=re.split(r'\s+[-–—:]\s+(?:book review|review)\b|,\s*book review\b|\s*-\s*book review',h,flags=re.I)[0]
    m=re.match(r"^(.+?),?\s+(?:[Ee]dited )?[Bb]y\s+([A-Z][^,:;|.]{2,60}?)\s*(?:[,:;|(.]|$)",h)
    if m: return m.group(1).strip(' "\'‘’“”'),m.group(2).strip()
    return None,None
rows=[]
for u,d in L.items():
    t,a=parse_head(d['headline'])
    if not t or len(t)>150: continue
    text=d['text']
    for cut in ['More about','Join our commenting forum','Want to bookmark your favourite articles']:
        i=text.find(cut,1500); text=text[:i] if i>0 else text
    if len(text)<600: continue
    stars=len(d['star_glyphs'].replace('☆','')) if d.get('star_glyphs') else None
    rows.append(dict(source='independent',book_key=nt(t)+'|'+na(a),title=t,author=a,outlet='The Independent',critic=d.get('critic'),
        review_date=(d.get('date') or '')[:10],review_url=u,text=text,standfirst=(d.get('description') or '')[:300],stars=stars))
T=pd.DataFrame(rows).drop_duplicates('review_url'); print(len(T),T.book_key.nunique(),'with stars',T.stars.notna().sum())
print(T.review_date.str[:4].value_counts().sort_index().to_dict())
m=joblib.load('ft_guardian.joblib'); p,l=m.predict(T.text.values); T['pred']=p; T['rv']=l
# where the Independent printed stars, use them: 5/4 rave, 3 positive, 2 mixed, 1 pan
smap={5:4,4:4,3:3,2:2,1:1}
T['native_grade']=T.stars.map(lambda s: f'{int(s)}/5' if pd.notna(s) else None)
has=T.stars.notna()&T.stars.isin(smap.keys())
T.loc[has,'rv']=T.loc[has,'stars'].map(smap); T['rating_method']=np.where(has,'stars','model_fulltext')
T['uk']=T.review_url.map(norm_url)
ev=T.merge(bm[['uk','rating_value']].dropna().drop_duplicates('uk'),on='uk')
if len(ev): print('IND labeled',len(ev),'corr',np.corrcoef(ev.pred,ev.rating_value)[0,1],'exact',(ev.rv==ev.rating_value).mean(),'within1',(abs(ev.rv-ev.rating_value)<=1).mean())
print(T.sample(min(8,len(T)),random_state=1)[['title','author','critic','review_date','stars','rv']].to_string())
T.drop(columns=['text']).to_parquet('extra_independent.parquet')
