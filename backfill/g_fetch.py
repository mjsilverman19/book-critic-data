import json, os, time, urllib.request, urllib.parse
K=__import__('os').environ['GUARDIAN_API_KEY']
def get(p):
    q=urllib.parse.urlencode(dict(**{'api-key':K,'section':'books','tag':'tone/reviews','page-size':200,'page':p,'order-by':'oldest',
      'show-fields':'headline,standfirst,trailText,byline,bodyText,starRating,wordcount,publication,isbn','show-tags':'keyword,contributor'}))
    return json.load(urllib.request.urlopen('https://content.guardianapis.com/search?'+q,timeout=60))['response']
p=1
while True:
    fn=f'guardian/p{p:04d}.json'
    if not os.path.exists(fn):
        for a in range(4):
            try: r=get(p); break
            except Exception as e: print('ERR',p,e,flush=True); time.sleep(10)
        json.dump(r,open(fn,'w'))
        time.sleep(1.2)
    else: r=json.load(open(fn))
    if p%20==0: print(p,r['pages'],flush=True)
    if p>=r['pages']: break
    p+=1
print('DONE',flush=True)
