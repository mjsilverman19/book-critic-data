import json,glob,re,joblib,numpy as np,pandas as pd,html
exec(open(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)),'catalog.py')).read())
from fulltext import FullText, sent_feats
C=catalog(); A={int(k):v for k,v in json.load(open('tls_authors.json')).items()}
D=[d for f in sorted(glob.glob('tls/p*.json')) for d in json.load(open(f))]
rows=[]
def slugify(s): return re.sub(r'[^a-z0-9]+','-',asc(s)).strip('-')
for d in D:
    h=d['content']['rendered']; text=plain(html.unescape(h))
    if len(text)<1500: continue
    critic='; '.join(A.get(i,'') for i in (d.get('article_author') or []) if A.get(i))
    books=match_books(html.unescape(h),C,text)
    slug=d['slug']; m=re.match(r'^(.*?)-(?:book-)?review-[a-z-]+$',slug)
    if m and not books:
        pre=m.group(1)
        for it in italics(html.unescape(h)):
            s=slugify(it)
            if len(s)>3 and pre.startswith(s) and len(pre)>len(s)+2:
                au=pre[len(s)+1:].split('-')
                au=' '.join(au[:3]).title() if len(au)<=4 else None
                if au: books=[(nt(it)+'|'+na(au),it,au)]
                break
    if not books: continue
    for bk,t,a in books[:3]:
        rows.append(dict(source='tls',book_key=bk,title=t,author=a,outlet='The Times Literary Supplement',critic=critic or None,
            review_date=d['date'][:10],review_url=d['link'],text=text,standfirst=plain(html.unescape(d.get('excerpt',{}).get('rendered','')))[:300],n_books=len(books)))
T=pd.DataFrame(rows); print(len(T),T.review_url.nunique(),T.book_key.nunique())
m=joblib.load('ft_guardian.joblib')
U=T.drop_duplicates('review_url'); p,l=m.predict(U.text.values)
U=U.assign(pred=p,rv=l); T=T.merge(U[['review_url','pred','rv']],on='review_url')
T['uk']=T.review_url.map(norm_url)
ev=T.merge(bm[['uk','rating_value']].dropna().drop_duplicates('uk'),on='uk')
print('TLS labeled',len(ev),'corr',np.corrcoef(ev.pred,ev.rating_value)[0,1],'exact',(ev.rv==ev.rating_value).mean(),'within1',(abs(ev.rv-ev.rating_value)<=1).mean())
T.drop(columns=['text']).to_parquet('tls_backfill.parquet')
