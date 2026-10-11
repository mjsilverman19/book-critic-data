import pandas as pd, re, collections
exec(open(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)),'common.py')).read())
def catalog():
    """title key -> list of (book_key, author surname, display title, author) for every known book"""
    C=collections.defaultdict(list)
    for t,a in zip(bmb.title,bmb.author):
        if isinstance(t,str): C[nt(t)].append((nt(t)+'|'+na(a),na(a),t,a))
    bf=pd.read_csv('out/backfill/books_backfill.csv')
    for k,t,a in zip(bf.book_key,bf.title,bf.author):
        if isinstance(k,str) and isinstance(t,str): C[nt(t)].append((k,k.split('|')[1],t,a))
    return C
def italics(h): return [re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',x)).strip(' ,.;:') for x in re.findall(r'<(?:i|em)>(.*?)</(?:i|em)>',h,re.S)]
def plain(h): return re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',h)).strip()
def match_books(h,C,text=None):
    text=(text or plain(h)).lower(); out=[]; seen=set()
    for it in italics(h):
        k=nt(it)
        if len(k)<4: continue
        for bk,sn,t,a in C.get(k,[]):
            if sn and len(sn)>2 and re.search(r'\b'+re.escape(sn)+r'\b',re.sub(r'[^a-z ]',' ',text)) and bk not in seen:
                out.append((bk,t,a)); seen.add(bk)
    return out
