"""TLS reviews -> backfill rows. Only articles whose URL marks them as a book review are used, and the book
(or books) under review come from the URL slug, which TLS writes as <title>-<author>[-<title>-<author>]-[book-]review-<reviewer>.
Italic titles in the text only confirm where each title ends; nothing is matched from mentions in the body."""
import json,glob,re,joblib,numpy as np,pandas as pd,html
exec(open(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)),'catalog.py')).read())
from fulltext import FullText
A={int(k):v for k,v in json.load(open('tls_authors.json')).items()}
D=[d for f in sorted(glob.glob('tls/p*.json')) for d in json.load(open(f))]
def slugify(s): return re.sub(r'[^a-z0-9]+','-',asc(s)).strip('-')
SKIP=re.compile(r'/(arts|regular-features/(?:letters-to-the-editor|nb|poem-of-the-week|mary-beard|footnotes-to-plato|commentary|letter-from|freelance))/|theatre-review|film-review|exhibition-review|arts-review|opera-review|blog-post')
rows=[]; skipped=0
for d in D:
    slug=d['slug']; link=d['link']
    m=re.match(r'^(.*?)-(?:book-)?review-[a-z0-9-]+$',slug)
    if not m or SKIP.search(link): skipped+=1; continue
    pre=m.group(1); h=html.unescape(d['content']['rendered']); text=plain(h)
    if len(text)<1200: continue
    tit=sorted({slugify(t):t for t in italics(h) if len(slugify(t))>2}.items(),key=lambda x:-len(x[0]))
    books=[]; rest=pre
    while rest:
        hit=next(((s,t) for s,t in tit if rest==s or rest.startswith(s+'-')),None)
        if not hit: break
        s,t=hit; rest=rest[len(s)+1:] if rest!=s else ''
        # author words run until the next italic title begins (or the slug ends)
        words=rest.split('-') if rest else []; au=[]
        while words:
            r='-'.join(words)
            if any(r==s2 or r.startswith(s2+'-') for s2,_ in tit): break
            au.append(words.pop(0))
        rest='-'.join(words)
        if 1<=len(au)<=4:
            name=' '.join(au); mm=re.search(r'\b'+r'[\s.]*'.join(map(re.escape,au))+r'\b',text,re.I)
            books.append((t,mm.group(0) if mm else name.title()))
    if not books: skipped+=1; continue
    critic='; '.join(A.get(i,'') for i in (d.get('article_author') or []) if A.get(i))
    for t,a in books[:4]:
        rows.append(dict(source='tls',book_key=nt(t)+'|'+na(a),title=t,author=a,outlet='The Times Literary Supplement',critic=critic or None,
            review_date=d['date'][:10],review_url=link,text=text,standfirst=plain(html.unescape(d.get('excerpt',{}).get('rendered','')))[:300],n_books=len(books)))
T=pd.DataFrame(rows); print('rows',len(T),'reviews',T.review_url.nunique(),'books',T.book_key.nunique(),'skipped articles',skipped)
c=T.groupby('book_key').review_url.nunique(); print('books with 2+ TLS reviews',(c>1).sum()); print(c.sort_values(ascending=False).head(8).to_dict())
m=joblib.load('ft_guardian.joblib'); U=T.drop_duplicates('review_url'); p,l=m.predict(U.text.values)
T=T.merge(U.assign(pred=p,rv=l)[['review_url','pred','rv']],on='review_url'); T['uk']=T.review_url.map(norm_url)
ev=T.merge(bm[['uk','rating_value']].dropna().drop_duplicates('uk'),on='uk')
print('TLS labeled',len(ev),'corr',round(np.corrcoef(ev.pred,ev.rating_value)[0,1],3))
print(T.sample(10,random_state=5)[['title','author','review_date']].to_string())
T.drop(columns=['text']).to_parquet('extra_tls.parquet')
