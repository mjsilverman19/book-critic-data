import pandas as pd, json, os, re, time, urllib.request
K=os.environ.get('HARDCOVER_TOKEN') or None
ol={}
for l in open('ol_enrich.jsonl'):
    d=json.loads(l); ol[d['book_key']]=d
B=pd.read_csv('out/backfill/books_backfill.csv'); B=B[B.bookmarks_slug.isna()&B.title.notna()]
done=set()
if os.path.exists('hc_enrich.jsonl'): done={json.loads(l)['book_key'] for l in open('hc_enrich.jsonl')}
todo=[r for r in B.itertuples() if r.book_key not in done and not (ol.get(r.book_key,{}).get('description') and ol.get(r.book_key,{}).get('cover_url'))]
print('todo',len(todo),flush=True)
def nt2(s): return re.sub(r'[^a-z0-9]','',re.sub(r'^(the|a|an) ','',str(s).lower().split(':')[0]))
def sn(a): a=str(a or '').split(',')[0].split(' and ')[0].split(); return re.sub(r'[^a-z]','',a[-1].lower()) if a else ''
def variants(t):
    v={t.strip(), t.split(':')[0].strip()}
    v|={x.title() for x in v}|{re.sub(r"[’]","'",x) for x in v}
    return [x for x in v if x]
Q='query($t:[String!]) { books(where: {title: {_in: $t}}, limit: 2000, order_by: {users_count: desc}) { id slug title release_year description image { url } contributions(limit: 4) { author { name } } } }'
def call(titles):
    for a in range(6):
        try:
            req=urllib.request.Request('https://api.hardcover.app/v1/graphql',data=json.dumps({'query':Q,'variables':{'t':titles}}).encode(),
                headers={'content-type':'application/json','authorization':'Bearer '+K,'user-agent':'book-critic-data (github.com/mjsilverman19/book-critic-data)'})
            d=json.load(urllib.request.urlopen(req,timeout=120))
            if 'data' in d: return d['data']['books']
            print('ERR',str(d)[:200],flush=True); time.sleep(10)
        except Exception as e: print('ERR',e,flush=True); time.sleep(10*(a+1))
    return None
recs={}
for i in range(0,len(todo),40):
    chunk=todo[i:i+40]
    bs=call(sorted({v for r in chunk for v in variants(r.title)}))
    if bs is None: continue
    idx={}
    for b in bs: idx.setdefault(nt2(b['title']),[]).append(b)
    for r in chunk:
        s=sn(r.author); best=None
        for b in idx.get(nt2(r.title),[]):
            names=' '.join(c['author']['name'] for c in b['contributions'] if c.get('author')).lower()
            if s and s in re.sub(r'[^a-z ]','',names):
                if best is None or (not best['description'] and b['description']) or (not best['image'] and b['image']): best=b if best is None or b['description'] else best
                if best['description'] and best['image']: break
        rec=dict(book_key=r.book_key,matched=bool(best))
        if best: rec.update(hc_id=best['id'],hc_slug=best['slug'],description=best['description'],cover_url=(best['image'] or {}).get('url'),release_year=best['release_year'])
        recs[r.book_key]=rec
    with open('hc_enrich.jsonl','a') as f:
        for r in chunk:
            if r.book_key in recs: f.write(json.dumps(recs[r.book_key])+'\n')
    if i%2000==0: print(i,len(recs),flush=True)
    time.sleep(1.05)
print('DONE',flush=True)
