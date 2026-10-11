import json,os,time,urllib.request,gzip
UA={'User-Agent':'Mozilla/5.0 (compatible; book-critic-data/1.0; +https://github.com/mjsilverman19/book-critic-data)','Accept-Encoding':'gzip'}
for p in range(1,140):
    fn=f'lr/p{p:03d}.json'
    if os.path.exists(fn): continue
    for a in range(4):
        try:
            r=urllib.request.urlopen(urllib.request.Request(f'https://literaryreview.co.uk/wp-json/wp/v2/posts?per_page=100&page={p}&_fields=id,date,link,slug,title,content,class_list,categories,tags',headers=UA),timeout=120)
            d=r.read(); d=gzip.decompress(d) if r.headers.get('Content-Encoding')=='gzip' else d
            open(fn,'wb').write(d); break
        except Exception as e:
            if '400' in str(e): print('END',p,flush=True); raise SystemExit
            time.sleep(10)
    time.sleep(1.5)
    if p%25==0: print(p,flush=True)
print('DONE',flush=True)
