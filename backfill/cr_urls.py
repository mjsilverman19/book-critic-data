import re, time, urllib.request
B="https://www.complete-review.com"
idx=urllib.request.urlopen(B+"/maindex/maindex.html",timeout=30).read().decode('latin-1')
pages=sorted(set(re.findall(r'href="(/maindex/alphat/[^"#]+)"',idx)))
urls=set()
for p in pages:
    t=urllib.request.urlopen(B+p,timeout=30).read().decode('latin-1')
    for u in re.findall(r'href="(/reviews/[^"#]+\.html?)"',t): urls.add(u)
    time.sleep(1)
open('cr_urls.txt','w').write('\n'.join(sorted(urls)))
print(len(pages),len(urls))
