import json,urllib.request,gzip,time
UA={'User-Agent':'Mozilla/5.0 (compatible; book-critic-data/1.0; +https://github.com/mjsilverman19/book-critic-data)','Accept-Encoding':'gzip'}
out={}
for tax in ['article_author']:
    p=1
    while True:
        try:
            r=urllib.request.urlopen(urllib.request.Request(f'https://www.the-tls.com/wp-json/wp/v2/{tax}?per_page=100&page={p}&_fields=id,name,slug',headers=UA),timeout=60)
        except Exception as e:
            print(tax,p,e); break
        b=r.read(); d=json.loads(gzip.decompress(b) if r.headers.get('Content-Encoding')=='gzip' else b)
        if not d: break
        for x in d: out[x['id']]=x['name']
        p+=1; time.sleep(1)
json.dump(out,open('tls_authors.json','w')); print(len(out))
