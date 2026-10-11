import json,os,time,urllib.request
K=__import__('os').environ['NYT_API_KEY']
import sys
Y0,Y1=int(sys.argv[1]),int(sys.argv[2])
months=[(y,m) for y in range(Y1,Y0-1,-1) for m in range(1,13)]
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
    keep3=[x for x in d if x not in keep and any(str(k.get('value','')).upper()=='BOOK REVIEWS' for k in (x.get('keywords') or []))]
    keep2=[x for x in d if x.get('news_desk') in ('Book Review Desk','BookReview','Book Review') and x not in keep and x.get('type_of_material') in ('Review',)]
    keep2=[x for x in keep2 if x not in keep3]
    json.dump(keep+keep2+keep3,open(fn,'w')); print(y,m,len(d),len(keep),len(keep2),len(keep3),flush=True)
    time.sleep(13)
print('DONE',flush=True)
