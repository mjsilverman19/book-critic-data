import json,glob,os,re,time,html,urllib.request,gzip,threading
from concurrent.futures import ThreadPoolExecutor
UA={'User-Agent':'Mozilla/5.0 (compatible; book-critic-data/1.0; +https://github.com/mjsilverman19/book-critic-data)','Accept-Encoding':'gzip'}
out='lr_books.jsonl'; done=set()
if os.path.exists(out): done={json.loads(l)['link'] for l in open(out)}
lock=threading.Lock()
def links():
    for f in sorted(glob.glob('lr/p*.json')):
        for d in json.load(open(f)):
            if d['link'] not in done: yield d['link']
def one(u):
    for a in range(3):
        try:
            r=urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=60); b=r.read()
            t=(gzip.decompress(b) if r.headers.get('Content-Encoding')=='gzip' else b).decode('utf-8','replace'); break
        except Exception as e:
            t=None; time.sleep(5)
    rec={'link':u}
    if t:
        m=re.search(r'class="single-article-book"[^>]*>(.*?)</(?:div|h\d|p)>',t,re.S)
        rec['book']=re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',m.group(1)))).strip() if m else None
        mi=re.search(r'class="[^"]*issue[^"]*"[^>]*>(.*?)</',t,re.S)
        rec['issue']=re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',mi.group(1)))).strip() if mi else None
    with lock:
        with open(out,'a') as f: f.write(json.dumps(rec)+'\n')
    time.sleep(1)
while True:
    todo=list(links())
    if not todo:
        if os.path.exists('lr_fetch.log') and 'DONE' in open('lr_fetch.log').read() or 'END' in open('lr_fetch.log').read(): break
        time.sleep(30); continue
    with ThreadPoolExecutor(4) as ex: list(ex.map(one,todo))
    done|=set(todo)
print('DONE',flush=True)
