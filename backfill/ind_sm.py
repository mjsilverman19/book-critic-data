import re,os,time,urllib.request,gzip
from concurrent.futures import ThreadPoolExecutor
UA={'User-Agent':'Mozilla/5.0 (compatible; book-critic-data/1.0; +https://github.com/mjsilverman19/book-critic-data)','Accept-Encoding':'gzip'}
sms=[u.replace('www.independent.co.uk','www.the-independent.com') for u in open('ind_sitemaps.txt').read().split() if 'sitemap-articles-' in u]
done=set(open('ind_sm_done.txt').read().split()) if os.path.exists('ind_sm_done.txt') else set()
todo=[u for u in sms if u not in done]; print('todo',len(todo),flush=True)
def get(u):
    for a in range(4):
        try:
            r=urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=60); d=r.read()
            if r.headers.get('Content-Encoding')=='gzip': d=gzip.decompress(d)
            return d.decode('utf-8','replace')
        except Exception as e: time.sleep(5+5*a)
    return None
def one(u):
    t=get(u); time.sleep(0.5)
    if t is None: return u,None
    return u,[x for x in re.findall(r'<loc>([^<]+)</loc>',t) if '/books/' in x and ('/reviews/' in x or 'review' in x.rsplit('/',1)[-1])]
with ThreadPoolExecutor(3) as ex, open('ind_review_urls.txt','a') as f, open('ind_sm_done.txt','a') as g:
    for i,(u,urls) in enumerate(ex.map(one,todo)):
        if urls is None: continue
        for x in urls: f.write(x+'\n')
        g.write(u+'\n')
        if i%500==0: f.flush(); g.flush(); print(i,flush=True)
print('DONE',flush=True)
