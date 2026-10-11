import json,glob,re,html,joblib,numpy as np,pandas as pd,datetime
exec(open(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)),'catalog.py')).read())
cats={int(k):v for k,v in json.load(open('lr_cats.json')).items()}
B={json.loads(l)['link']:json.loads(l) for l in open('lr_books.jsonl')}
D=[d for f in sorted(glob.glob('lr/p*.json')) for d in json.load(open(f))]
def name_from_slug(sl,text):
    words=sl.split('-'); pat=r'\b'+r'[\s.]*'.join(re.escape(w) for w in words)+r'\b'
    m=re.search(pat,text,re.I)
    return m.group(0) if m else ' '.join(w.capitalize() for w in words)
def issue_year(n):
    try: n=int(n)
    except: return None
    if n<1 or n>700: return None
    return round(2026+7/12-(554-n)/11.0,2)
rows=[]
for d in D:
    b=B.get(d['link']); 
    if not b or not b.get('book'): continue
    text=plain(html.unescape(d['content']['rendered']))
    if len(text)<800: continue
    cl=d.get('class_list') or []
    au=[c[10:] for c in cl if c.startswith('author_tx-')]; cr=[c[15:] for c in cl if c.startswith('contributor_tx-')]
    if not au: continue
    author=name_from_slug(au[0],text); critic=name_from_slug(cr[0],text) if cr else None
    yr=None
    for c in d.get('categories') or []:
        yr=issue_year(cats.get(c)) or yr
    date=d['date'][:10]
    # the 2014 bulk import carries upload dates; the issue number gives the print date for those
    if date.startswith('2014') and yr and 2005<=yr<2014.5: date=f"{int(yr)}-{int((yr%1)*12)+1:02d}"
    t=b['book']
    rows.append(dict(source='literary_review',book_key=nt(t)+'|'+na(author),title=t,author=author,outlet='Literary Review',critic=critic,
        review_date=date,review_url=d['link'],text=text,standfirst=plain(html.unescape(d['title']['rendered']))))
T=pd.DataFrame(rows); print(len(T),T.book_key.nunique()); print(T.review_date.str[:4].value_counts().sort_index().to_dict())
m=joblib.load('ft_guardian.joblib'); p,l=m.predict(T.text.values); T['pred']=p; T['rv']=l
T['uk']=T.review_url.map(norm_url); ev=T.merge(bm[['bk','ok','rating_value']].drop_duplicates(['bk','ok']).rename(columns={'bk':'book_key'}).query("ok=='literaryreview'"),on='book_key')
if len(ev): print('LR labeled',len(ev),'corr',np.corrcoef(ev.pred,ev.rating_value)[0,1],'within1',(abs(ev.rv-ev.rating_value)<=1).mean())
T.drop(columns=['text']).to_parquet('extra_literary_review.parquet')
