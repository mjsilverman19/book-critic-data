import pandas as pd, json, os, re, time, urllib.request, urllib.parse, threading
from concurrent.futures import ThreadPoolExecutor
UA={'User-Agent':'book-critic-data/1.0 (https://github.com/mjsilverman19/book-critic-data)'}
B=pd.read_csv('out/backfill/books_backfill.csv'); B=B[B.bookmarks_slug.isna() & B.title.notna()]
out='wp_enrich.jsonl'; done=set()
if os.path.exists(out): done={json.loads(l)['book_key'] for l in open(out)}
lock=threading.Lock()
def nt2(s): return re.sub(r'[^a-z0-9]','',re.sub(r'^(the|a|an) ','',str(s).lower().split(':')[0]))
def get(u):
    for a in range(4):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=40))
        except Exception: time.sleep(10+20*a)
def one(row):
    t=row.title.split(':')[0]; a=row.author if isinstance(row.author,str) else ''
    sn=(a.split(',')[0].split(' and ')[0].split() or [''])[-1]
    q={'action':'query','format':'json','generator':'search','gsrsearch':f'"{t}" {sn}','gsrlimit':5,'prop':'extracts','exintro':1,'explaintext':1,'redirects':1}
    time.sleep(0.6)
    r=get('https://en.wikipedia.org/w/api.php?'+urllib.parse.urlencode(q)) or {}
    rec=dict(book_key=row.book_key)
    for p in sorted((r.get('query') or {}).get('pages',{}).values(),key=lambda p:p.get('index',9)):
        title=re.sub(r'\s*\(.*\)$','',p['title'])
        ex=p.get('extract') or ''
        if nt2(title)==nt2(t) and sn and sn.lower() in ex.lower()[:600]:
            rec.update(wp_title=p['title'],wp_url='https://en.wikipedia.org/wiki/'+urllib.parse.quote(p['title'].replace(' ','_')),wp_extract=ex.strip()); break
    with lock:
        with open(out,'a') as f: f.write(json.dumps(rec)+'\n')
ol={}
for l in open('ol_enrich.jsonl'):
    d=json.loads(l); ol[d['book_key']]=d.get('description')
todo=[r for r in B.itertuples() if r.book_key not in done and not ol.get(r.book_key)]; print('todo',len(todo),flush=True)
with ThreadPoolExecutor(2) as ex:
    for i,_ in enumerate(ex.map(one,todo)):
        if i%1000==0: print(i,flush=True)
print('DONE',flush=True)
