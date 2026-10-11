"""Assign every book a set of categories from one taxonomy.

Facets, after bookseller practice (BISAC top levels, trimmed):
  form:      Fiction | Nonfiction | Poetry | Drama
  genre:     fiction genres or nonfiction subjects (below)
  attribute: In Translation, LGBTQ+
Marketing and seasonal tags from Book Marks (Hottest Books of the Season, Best Books, Lithub, ...) are dropped.
Signals: Book Marks tags, Complete Review form, Guardian section tags, NYT subjects, Open Library subjects, title words.
"""
import pandas as pd, json, re, glob, os, collections
ROOT=os.environ.get('REPO',os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
FICTION=['Literary Fiction','Historical Fiction','Mystery & Thriller','Science Fiction & Fantasy','Horror','Romance','Short Stories','Graphic Novels & Comics',"Children's & Young Adult"]
NONFICTION=['Biography & Memoir','History','Politics & Current Affairs','Society & Culture','Science & Nature','Technology','Business & Economics',
            'Health & Psychology','Philosophy & Religion','Arts & Entertainment','Essays & Criticism','True Crime & Investigative','Food & Cooking','Travel','Sports']
# Book Marks tag -> categories
BM={'Fiction':['Fiction'],'Non-Fiction':['Nonfiction'],'Literary':['Literary Fiction'],'History':['History'],'Memoir':['Biography & Memoir'],
 'Mystery, Crime, & Thriller':['Mystery & Thriller'],'Biography':['Biography & Memoir'],'Politics':['Politics & Current Affairs'],'Culture':['Society & Culture'],
 'Historical':['Historical Fiction'],'Literature in Translation':['In Translation'],'Lit in Translation':['In Translation'],
 'Investigative Journalism':['True Crime & Investigative'],'True Crime':['True Crime & Investigative'],'Essays':['Essays & Criticism'],'Criticism':['Essays & Criticism'],
 'Social Sciences':['Society & Culture'],'Story Collections':['Short Stories'],'Speculative':['Science Fiction & Fantasy'],'Fantasy':['Science Fiction & Fantasy'],
 'Sci-Fi and Fantasy':['Science Fiction & Fantasy'],'Science':['Science & Nature'],'Nature':['Science & Nature'],'LGBTQ Stories':['LGBTQ+'],'Music':['Arts & Entertainment'],
 'Film & TV':['Arts & Entertainment'],'Art':['Arts & Entertainment'],'Poetry':['Poetry'],'Romance':['Romance'],'Technology':['Technology'],'Horror':['Horror'],
 'Sports':['Sports'],'Travel':['Travel'],'Religion':['Philosophy & Religion'],'Graphic Novels':['Graphic Novels & Comics'],'Graphic Nonfiction':['Graphic Novels & Comics','Nonfiction'],
 'Health':['Health & Psychology'],'Business':['Business & Economics']}
# keyword rules over lowercased signal text (subjects/tags), applied to backfill books and as additions for all
RULES=[('Food & Cooking',r'\bcook(ing|ery|book)|\brecipes?\b|\bfood\b|gastronom|\bwine\b|\bbaking\b|\bkitchen'),
 ('Mystery & Thriller',r'mystery|detective|thriller|\bcrime fiction|suspense|books/crime|books/thrillers|espionage'),
 ('Science Fiction & Fantasy',r'science fiction|science-fiction|\bfantasy\b|dystopi|speculative'),
 ('Horror',r'\bhorror\b|ghost stories|books/horror'),('Romance',r'\bromance\b|love stories'),
 ('Short Stories',r'short stories|short-stories|\bstories\b'),('Graphic Novels & Comics',r'comic|graphic novel'),
 ("Children's & Young Adult",r'juvenile|children|teen-books|young-adult|young adult|picture-books'),
 ('Historical Fiction',r'fiction, historical|historical fiction'),
 ('Biography & Memoir',r'biograph|memoir|autobiograph'),('History',r'\bhistory\b|world war|civil war|books/history'),
 ('Politics & Current Affairs',r'politic|government|foreign relations|international relations|terrorism|defense and military|presiden'),
 ('Society & Culture',r'social|society|sociolog|anthropolog|race and ethnicity|women|immigration|discrimination|civilization|manners and customs'),
 ('Science & Nature',r'\bscience\b(?![ -]fiction)|scienceandnature|natural history|biology|physics|evolution|ecology|environment|nature'),
 ('Technology',r'technolog|computers and the internet|computingandthenet|\binternet\b'),
 ('Business & Economics',r'business|econom|finance'),('Health & Psychology',r'psycholog|medicine|health|mental|healthmindandbody'),
 ('Philosophy & Religion',r'philosoph|religio|christian|islam|judaism|\bgod\b|spiritual'),
 ('Arts & Entertainment',r'\bart\b|books/art|music|film|movies|motion pictures|television|tvandradio|theater|theatre|photograph|books/stage|dance'),
 ('Essays & Criticism',r'essays|criticism|literary-criticism|history and criticism'),('True Crime & Investigative',r'true crime|true-crime|journalism|investigative'),
 ('Travel',r'travel|description and travel'),('Sports',r'sport|baseball|football|basketball|boxing|golf|tennis|cricket'),
 ('In Translation',r'translat'),('LGBTQ+',r'\bgay\b|lesbian|lgbt|queer|transgender|homosexual')]
TITLE_FOOD=r'\b(cookbook|recipes|cooking|kitchen|cuisine)\b'
ATTR={'In Translation','LGBTQ+'}
def apply_rules(signals, top=3):
    # score each category by how many independent signals (sources) support it; keep the strongest few
    score=collections.Counter()
    for t in signals:
        for c,p in RULES:
            n=len(re.findall(p,t))
            if n: score[c]+=1+min(n,3)/10
    subj=[c for c,_ in score.most_common() if c not in ATTR][:top]
    return set(subj)|{c for c in score if c in ATTR}
def finish(cats,form_hint=None):
    cats=set(cats)
    if form_hint: cats.add(form_hint)
    if cats & set(FICTION) and 'Nonfiction' not in cats and 'Poetry' not in cats: cats.add('Fiction')
    if 'Fiction' in cats:
        cats-= {'Biography & Memoir'} if 'Fiction' in cats and form_hint!='Nonfiction' else set()
    if cats & set(NONFICTION) and not cats & {'Fiction','Poetry','Drama'}: cats.add('Nonfiction')
    if 'Fiction' in cats and 'Nonfiction' in cats:
        cats.discard('Nonfiction' if form_hint=='Fiction' or not form_hint else 'Fiction')
    order=['Fiction','Nonfiction','Poetry','Drama']+FICTION+NONFICTION+['In Translation','LGBTQ+']
    return [c for c in order if c in cats]

# ---- Book Marks books ----
books=pd.read_csv(f'{ROOT}/data/books.csv')
out={}
for b in books.itertuples():
    try: tags=json.loads(b.genres) if isinstance(b.genres,str) else []
    except Exception: tags=[]
    cats={c for t in tags for c in BM.get(t,[])}
    if re.search(TITLE_FOOD,str(b.title).lower()) and not cats & {'Fiction','Poetry'}: cats.add('Food & Cooking')
    hint='Fiction' if 'Fiction' in cats else 'Nonfiction' if 'Nonfiction' in cats else 'Poetry' if 'Poetry' in cats else None
    out[b.slug]=finish(cats,hint)

# ---- backfill books: gather signals by book_key ----
sig=collections.defaultdict(list); form=collections.defaultdict(collections.Counter); LRS={}
cb=pd.read_csv('cr_books.csv'); exec(open('common.py').read().split("R='")[0])  # pandas etc
import unicodedata
def asc(s): return unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode().lower()
def nt(s):
    s=asc(s); s=re.sub(r'^(the|a|an) ','',s.strip(' "\'')); s=re.split(r'[:(]| - ',s)[0]; return re.sub(r'[^a-z0-9]','',s)
def na(s):
    s=asc(s); s=re.sub(r'\b(edited|translated|trans|ed|by|with)\b.*$','',s); s=re.split(r',| and |&|;',s)[0].strip().split()
    s=[x for x in s if x not in ('jr','jr.','sr','iii','ii')]
    return re.sub(r'[^a-z]','',s[-1]) if s else ''
CRF={'novel':'Fiction','fiction':'Fiction','novella':'Fiction','novellas':'Fiction','stories':'Fiction','poetry':'Poetry','poems':'Poetry','drama':'Drama','play':'Drama','plays':'Drama',
     'non-fiction':'Nonfiction','memoir':'Nonfiction','biography':'Nonfiction','essays':'Nonfiction','history':'Nonfiction','science':'Nonfiction','travel':'Nonfiction','philosophy':'Nonfiction',
     'autobiography':'Nonfiction','autobiographical':'Fiction','biographical':'Nonfiction','interviews':'Nonfiction'}
for r in cb.itertuples():
    k=nt(r.title)+'|'+na(r.author); g=str(r.genre).lower()
    sig[k].append(g)
    if g in CRF: form[k][CRF[g]]+=3
    if isinstance(r.original_in,str) and r.original_in.strip() and 'english' not in r.original_in.lower(): sig[k].append('translated')
G=pd.read_parquet('guardian_reviews.parquet')
G['bk']=[(nt(t)+'|'+na(a)) if isinstance(t,str) else None for t,a in zip(G.book_title,G.book_author)]
for k,tags in zip(G.bk,G.keyword_tags):
    if not k or not isinstance(tags,str): continue
    bt=[t for t in tags.split('; ') if t.startswith('books/')]
    sig[k].append(' '.join(bt))
    if 'books/fiction' in bt or 'books/short-stories' in bt: form[k]['Fiction']+=2
    elif 'books/poetry' in bt: form[k]['Poetry']+=2
    elif any(t in bt for t in ['books/biography','books/history','books/politics','books/society','books/scienceandnature','books/autobiography-and-memoir']): form[k]['Nonfiction']+=1
N=pd.read_parquet('nyt_backfill.parquet'); url2k=dict(zip(N.review_url,N.book_key))
for f in glob.glob('nyt/*.json'):
    for x in json.load(open(f)):
        k=url2k.get(x.get('web_url'))
        if not k: continue
        subj=[kw['value'] for kw in (x.get('keywords') or []) if kw['name']=='subject' and kw['value'] not in ('Books and Literature','Reviews','BOOK REVIEWS','TERMS NOT AVAILABLE')]
        sig[k].append(' '.join(subj).lower()); ab=(x.get('abstract') or '').lower()
        if re.search(r'\b(novel|short stories|stories)\b',ab): form[k]['Fiction']+=1
        if re.search(r'\bpoems|poetry\b',ab): form[k]['Poetry']+=1
        if re.search(r'\b(biography|memoir|history of|account of|study of|examines)\b',ab): form[k]['Nonfiction']+=1
for l in open('ol_enrich.jsonl'):
    d=json.loads(l); s=[x.lower() for x in (d.get('subjects') or [])]
    if not s: continue
    sig[d['book_key']].append(' '.join(s))
    if any(x.startswith('fiction') or x.endswith(', fiction') or x=='fiction' for x in s): form[d['book_key']]['Fiction']+=2
    elif any(x in ('nonfiction','biography','history') for x in s): form[d['book_key']]['Nonfiction']+=1
# section paths and fields from the newer sources (TLS url sections, Literary Review sections, Kirkus genre)
import glob as _g
for p in _g.glob('extra_*.parquet'):
    X=pd.read_parquet(p)
    for k,u in zip(X.book_key,X.review_url):
        if not isinstance(u,str): continue
        path=' '.join(re.sub(r'https?://[^/]+/','',u).split('/')[:-1]).replace('-',' ')
        if path: sig[k].append(path)
        if 'the-tls.com' in u:
            if re.search(r'/(fiction|literature/(?:contemporary|modern|classics)|poetry)',u): form[k]['Fiction' if 'poetry' not in u else 'Poetry']+=1
            elif re.search(r'/(history|politics|science|philosophy|religion|arts|culture|economics|society|biography|memoir|world)',u): form[k]['Nonfiction']+=1
for l in open('lr/p001.json') if False else []: pass
for f in _g.glob('lr/p*.json'):
    for d in json.load(open(f)):
        secs=[c[20:].replace('-',' ') for c in (d.get('class_list') or []) if c.startswith('content_section_tx-')]
        au=[c[10:] for c in (d.get('class_list') or []) if c.startswith('author_tx-')]
        if secs: LRS[d['link']]=' '.join(secs)
LRX=pd.read_parquet('extra_literary_review.parquet') if os.path.exists('extra_literary_review.parquet') else None
if LRX is not None:
    for k,u in zip(LRX.book_key,LRX.review_url):
        s_=LRS.get(u)
        if s_:
            sig[k].append(s_)
            if re.search(r'fiction|poetry',s_): form[k]['Poetry' if 'poetry' in s_ else 'Fiction']+=2
            else: form[k]['Nonfiction']+=1
KX=pd.read_parquet('extra_kirkus.parquet') if os.path.exists('extra_kirkus.parquet') else None
kg=pd.read_csv(f'{ROOT}/data/backfill/kirkus/reviews.csv.gz') if os.path.exists(f'{ROOT}/data/backfill/kirkus/reviews.csv.gz') else None
if KX is not None and kg is not None:
    g2=dict(zip(kg.url,kg.genre.fillna('')))
    for k,u in zip(KX.book_key,KX.review_url):
        g=g2.get(u,'').lower()
        if 'nonfiction' in g: form[k]['Nonfiction']+=3
        elif 'fiction' in g: form[k]['Fiction']+=3
        if g: sig[k].append(g)
bf=pd.read_csv('out/backfill/books_backfill.csv'); bf=bf[bf.bookmarks_slug.isna()&bf.book_key.notna()]
for r in bf.itertuples():
    cats=apply_rules(sig.get(r.book_key,[]))
    t=str(r.title).lower()
    if re.search(TITLE_FOOD,t): cats.add('Food & Cooking')
    for pat,c,f in [(r'\b(a )?memoirs?\b','Biography & Memoir','Nonfiction'),(r'\b(a )?biography\b|\bthe life (and|of)\b','Biography & Memoir','Nonfiction'),
                    (r'\bhistory of\b','History','Nonfiction'),(r'\b(collected|selected|new) poems\b|\bpoems\b','Poetry','Poetry'),
                    (r'\ba novel\b','','Fiction'),(r'\b(and other )?stories\b','Short Stories','Fiction')]:
        if re.search(pat,t):
            if c: cats.add(c)
            form[r.book_key][f]+=4
    hint=form[r.book_key].most_common(1)[0][0] if form[r.book_key] else None
    fic=hint=='Fiction'
    if fic: cats-= {'History','Politics & Current Affairs','Society & Culture','Science & Nature','Business & Economics','Health & Psychology','Philosophy & Religion','Travel','Sports','Technology','Food & Cooking','True Crime & Investigative','Essays & Criticism','Arts & Entertainment','Biography & Memoir'}
    elif hint in ('Nonfiction',None): cats-= {'Literary Fiction','Mystery & Thriller','Science Fiction & Fantasy','Horror','Romance','Short Stories','Historical Fiction'} if hint=='Nonfiction' else set()
    if hint in ('Fiction','Poetry','Drama'): cats.discard('Food & Cooking')
    out['bf-'+re.sub(r'[^a-z0-9]+','-',r.book_key.lower()).strip('-')]=finish(cats,hint)
# books still without a form: classify Fiction / Nonfiction / Poetry from their review snippets and title,
# trained on books whose form is known; only confident predictions are kept
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    import glob as _g2
    R=pd.concat([pd.read_csv(f,usecols=['book_key','title','pull_quote','headline'],low_memory=False) for f in _g2.glob('out/backfill/reviews/*.csv')])
    R=R.dropna(subset=['book_key'])
    snip=R.assign(t=R.title.fillna('')+' . '+R.headline.fillna('')+' . '+R.pull_quote.fillna('')).groupby('book_key').t.apply(lambda x:' '.join(x)[:3000])
    slug2key={'bf-'+re.sub(r'[^a-z0-9]+','-',k.lower()).strip('-'):k for k in snip.index}
    lab={k:v for k,v in out.items() if k.startswith('bf-') and k in slug2key}
    y=[]; X=[]; U=[]
    for sl,v in lab.items():
        f=[x for x in v if x in ('Fiction','Nonfiction','Poetry')]
        if f: X.append(snip[slug2key[sl]]); y.append(f[0])
        elif not v or not set(v)&{'Fiction','Nonfiction','Poetry','Drama'}: U.append(sl)
    tv=TfidfVectorizer(ngram_range=(1,2),min_df=3,sublinear_tf=True,max_features=200000); Xm=tv.fit_transform(X)
    clf=LogisticRegression(C=4,max_iter=2000).fit(Xm,y)
    if U:
        P=clf.predict_proba(tv.transform([snip[slug2key[s_]] for s_ in U]))
        added=0
        for s_,p in zip(U,P):
            j=p.argmax()
            if p[j]>=0.8:
                out[s_]=finish(set(out[s_])|{clf.classes_[j]},clf.classes_[j]); added+=1
        print('form from snippets:',added,'of',len(U))
except Exception as e: print('snippet classifier skipped:',e)
rows=[dict(slug=k,genres=json.dumps(v)) for k,v in out.items()]
pd.DataFrame(rows).to_csv('out/backfill/book_genres.csv',index=False)
c=collections.Counter(x for v in out.values() for x in v)
bfv=[v for k,v in out.items() if k.startswith('bf-')]; bmv=[v for k,v in out.items() if not k.startswith('bf-')]
print('books',len(out),'bf with any',sum(bool(v) for v in bfv)/len(bfv),'bf with form',sum(bool(set(v)&{'Fiction','Nonfiction','Poetry','Drama'}) for v in bfv)/len(bfv))
print(c.most_common())
