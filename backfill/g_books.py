import pandas as pd, re
d=pd.read_parquet('guardian_reviews.parquet').drop(columns=['book_src','book_title','book_author','y'],errors='ignore')
AU=r"(?P<author>[A-ZÀ-Þ][\w.’'\-]*(?:\s+(?:[A-ZÀ-Þ][\w.’'\-]*|de|van|von|der|di|da|du|le|la|and|&|with|ed\.?|edited by|trans(?:lated)?\.?(?: by)?))*?)"
TI=r"(?P<title>[A-Z0-9\"“‘'][^•\n]{1,140}?)"
pats=[('order',re.compile(r"To order "+TI+r"(?: by "+AU+r")?,? (?:for|at|\()\s*£")),
      ('pubby',re.compile(TI+r" by "+AU+r",? (?:is|are) (?:published|out) (?:by|from|in)")),
      ('head',re.compile(r"^\s*"+TI+r" by "+AU+r"\s*(?:\(|[,.]?\s*\d+pp|[,.]?\s*pp|\s+[A-Z][\w&’' ,]{1,50}?,?\s*(?:£|\$)\d)")),
      ('pub_noauth',re.compile(r"(?:•\s*|\.\s+)"+TI+r" (?:is|are) published by"))]
out=[]
for r in d.itertuples():
    b=(r.body or '')
    res=None
    h=re.sub(r'\s*[–\-:|]\s*reviews?\b.*$','',(r.headline or '').strip())
    mh=re.match(r'^(?P<t>.{2,140}?) by (?P<a>[A-ZÀ-Þ][^,;:]{2,60})$',h)
    if mh and not re.search(r'roundup|round-up|books of the year',r.headline or '',re.I):
        res=('headline',mh.group('t').strip(' "“”‘’'),mh.group('a').strip())
    for name,p in ([] if res else pats):
        seg=b[:400] if name=='head' else b[-600:]
        m=None
        for m in p.finditer(seg): pass
        if m:
            t=m.group('title').strip(' "“”‘’\'.,'); a=(m.groupdict().get('author') or '').strip(' .,')
            t=re.sub(r'^.*?(?:•|\. )\s*','',t) if name!='head' else t
            if name=='head':
                span=b[m.start('author'):m.start('author')+90]
                tags=[x for x in (r.person_tags or '').split('; ') if x and x not in (r.critic or '')]
                hit=[x for x in tags if span.startswith(x)]
                if hit: a=max(hit,key=len)
            if 1<=len(t)<=140: res=(name,t,a); break
    out.append(res or (None,None,None))
d[['book_src','book_title','book_author']]=pd.DataFrame(out,index=d.index)
d['y']=d.date.str[:4].astype(int)
print(d.groupby(d.y//5*5).book_src.apply(lambda s:s.notna().mean()).round(2).to_string())
print(d.book_src.value_counts())
print(d.dropna(subset=['book_src']).sample(15,random_state=2)[['book_src','book_title','book_author']].to_string())
d.to_parquet('guardian_reviews.parquet')
def clean_a(a,body,src):
    if not isinstance(a,str) or not a: return a
    a=re.split(r'\s+(?:review\b|[–—]\s|-\s)',a)[0].strip(' ,.')
    return a
d['book_author']=[clean_a(a,b,s) for a,b,s in zip(d.book_author,d.body,d.book_src)]
# single-token authors from 'head': extend with next capitalized token from body
def ext(a,b,s):
    if s=='head' and isinstance(a,str) and a and ' ' not in a and b:
        m=re.search(re.escape(a)+r"\s+([A-ZÀ-Þ][\w’'\-]+)",b[:400])
        if m: return a+' '+m.group(1)
    return a
d['book_author']=[ext(a,b,s) for a,b,s in zip(d.book_author,d.body,d.book_src)]
d.to_parquet('guardian_reviews.parquet')
print(d.dropna(subset=['book_src']).sample(15,random_state=7)[['book_src','book_title','book_author']].to_string())
