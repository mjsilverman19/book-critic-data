import pandas as pd, json, os, re, time, urllib.request, urllib.parse, threading
from concurrent.futures import ThreadPoolExecutor
exec(open('lang.py').read())
UA={'User-Agent':'book-critic-data/1.0 (https://github.com/mjsilverman19/book-critic-data)'}
B=pd.read_csv('out/backfill/books_backfill.csv')
B=B[B.bookmarks_slug.isna() & B.title.notna()]
out='ol_enrich.jsonl'; done=set()
if os.path.exists(out): done={json.loads(l)['book_key'] for l in open(out)}
lock=threading.Lock()
def get(u):
    for a in range(4):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=40))
        except Exception as e:
            if '404' in str(e): return None
            time.sleep(3+5*a)
    return None
def nt2(s): return re.sub(r'[^a-z0-9]','',re.sub(r'^(the|a|an) ','',str(s).lower().split(':')[0]))
def surname(a):
    a=str(a).split(',')[0].split(' and ')[0].strip().split(); return a[-1] if a else ''
def one(row):
    t,a=row.title,row.author if isinstance(row.author,str) else ''
    q={'title':t.split(':')[0],'limit':5,'fields':'key,title,author_name,cover_i,first_publish_year,publisher,isbn,subject,language'}
    sn=surname(a)
    if sn: q['author']=sn
    r=get('https://openlibrary.org/search.json?'+urllib.parse.urlencode(q)) or {}
    docs=r.get('docs',[])
    best=None
    for d in docs:
        if nt2(d.get('title',''))==nt2(t) and (not sn or any(sn.lower() in x.lower() for x in d.get('author_name',[]))): best=d; break
    if not best and docs and sn and any(sn.lower() in x.lower() for x in docs[0].get('author_name',[])): best=docs[0]
    rec=dict(book_key=row.book_key,matched=bool(best))
    if best:
        rec.update(ol_work=best['key'],ol_title=best.get('title'),ol_author='; '.join(best.get('author_name',[])[:3]),
            cover_url=f"https://covers.openlibrary.org/b/id/{best['cover_i']}-L.jpg" if best.get('cover_i') else None,
            first_publish_year=best.get('first_publish_year'),publisher=(best.get('publisher') or [None])[0],
            isbn=next((i for i in best.get('isbn',[]) if len(i)==13),None),subjects=best.get('subject',[])[:8])
        w=get('https://openlibrary.org'+best['key']+'.json') or {}
        d=w.get('description'); d=d.get('value') if isinstance(d,dict) else d
        if isinstance(d,str):
            d=re.split(r'\n\s*(?:-{3,}|\*{3,}|\(\[source\]|Source:|\[1\])',d)[0].strip()
            d=re.sub(r'\[([^\]]+)\]\([^)]+\)',r'\1',d)
        rec['description']=d if isinstance(d,str) and len(d)>40 else None
        if not rec.get('cover_url') and w.get('covers'): rec['cover_url']=f"https://covers.openlibrary.org/b/id/{w['covers'][0]}-L.jpg"
    with lock:
        with open(out,'a') as f: f.write(json.dumps(rec)+'\n')
todo=[r for r in B.itertuples() if r.book_key not in done]
print('todo',len(todo),flush=True)
with ThreadPoolExecutor(12) as ex:
    for i,_ in enumerate(ex.map(one,todo)):
        if i%500==0: print(i,flush=True)
print('DONE',flush=True)
