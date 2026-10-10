import os, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
B="https://www.complete-review.com"
UA={'User-Agent':'Mozilla/5.0 (compatible; book-critic-data/1.0; +https://github.com/mjsilverman19/book-critic-data)'}
urls=[u for u in open('cr_urls.txt').read().split() if not os.path.exists('cr_html/'+u.strip('/').replace('/','__'))]
print('todo',len(urls),flush=True)
def get(u):
    fn='cr_html/'+u.strip('/').replace('/','__')
    for a in range(4):
        try:
            d=urllib.request.urlopen(urllib.request.Request(B+u,headers=UA),timeout=30).read(); open(fn,'wb').write(d); break
        except Exception as e: time.sleep(3+a*3)
    else: print('FAIL',u,flush=True)
    time.sleep(1)
with ThreadPoolExecutor(3) as ex: list(ex.map(get,urls))
print('DONE',flush=True)
