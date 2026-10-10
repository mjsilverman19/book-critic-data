import json,os,time,urllib.request
K=__import__('os').environ['NYT_API_KEY']
months=[(y,m) for y in range(2015,2027) for m in range(1,13) if (y,m)<=(2026,10)]+[(y,m) for y in range(2014,1989,-1) for m in range(1,13)]
for y,m in months:
    fn=f'nyt/{y}-{m:02d}.json'
    if os.path.exists(fn): continue
    for a in range(4):
        try:
            d=json.load(urllib.request.urlopen(f'https://api.nytimes.com/svc/archive/v1/{y}/{m}.json?api-key={K}',timeout=180))['response']['docs']; break
        except Exception as e:
            print('ERR',y,m,e,flush=True); time.sleep(30 if '429' in str(e) else 15); d=None
    if d is None: continue
    keep=[x for x in d if x.get('type_of_material')=='Review' and any(k['name']=='creative_works' and '(BOOK)' in k['value'].upper() for k in (x.get('keywords') or []))]
    keep2=[x for x in d if x.get('news_desk') in ('Book Review Desk','BookReview','Book Review') and x not in keep and x.get('type_of_material') in ('Review',)]
    json.dump(keep+keep2,open(fn,'w')); print(y,m,len(d),len(keep),len(keep2),flush=True)
    time.sleep(13)
print('DONE',flush=True)
