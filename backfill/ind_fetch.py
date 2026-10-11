import re,json,os,time,html,urllib.request,gzip,threading
from concurrent.futures import ThreadPoolExecutor
UA={'User-Agent':'Mozilla/5.0 (compatible; book-critic-data/1.0; +https://github.com/mjsilverman19/book-critic-data)','Accept-Encoding':'gzip'}
out='ind_reviews.jsonl'; done=set()
if os.path.exists(out): done={json.loads(l)['url'] for l in open(out)}
lock=threading.Lock()
def one(u):
    u2=u.replace('www.independent.co.uk','www.the-independent.com')
    t=None
    for a in range(3):
        try:
            r=urllib.request.urlopen(urllib.request.Request(u2,headers=UA),timeout=60); b=r.read()
            t=(gzip.decompress(b) if r.headers.get('Content-Encoding')=='gzip' else b).decode('utf-8','replace'); break
        except Exception as e:
            if '404' in str(e): break
            time.sleep(5)
    rec={'url':u2}
    if t:
        for b in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',t,re.S):
            try: d=json.loads(b)
            except Exception: continue
            if isinstance(d,dict) and d.get('@type') in ('NewsArticle','Review','Article'):
                a=d.get('author'); a=a[0] if isinstance(a,list) and a else a
                rec.update(headline=d.get('headline'),date=d.get('datePublished'),critic=(a or {}).get('name') if isinstance(a,dict) else None,description=d.get('description'))
                rr=d.get('reviewRating') or {}
                if rr: rec['stars']=rr.get('ratingValue')
                break
        ps=[re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>','',p))).strip() for p in re.findall(r'<p[^>]*>(.*?)</p>',t,re.S)]
        rec['text']=' '.join(p for p in ps if len(p)>60)
        st=re.findall(r'(★+☆*)',t[:200000]); rec['star_glyphs']=st[0] if st else None
    with lock:
        with open(out,'a') as f: f.write(json.dumps(rec)+'\n')
    time.sleep(0.7)
urls=[u.strip() for u in open('ind_review_urls.txt') if u.strip()]
todo=sorted({u.replace('www.independent.co.uk','www.the-independent.com') for u in urls}-done)
print('todo',len(todo),flush=True)
with ThreadPoolExecutor(5) as ex:
    for i,_ in enumerate(ex.map(one,todo)):
        if i%1000==0: print(i,flush=True)
print('DONE',flush=True)
