import re, html, os, json, sys
import pandas as pd
def txt(s): return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',s))).strip()
def field(t,name):
    m=re.search(r'>\s*'+name+r':?\s*(?:</a>)?\s*</font>\s*</td>\s*<td[^>]*>(.*?)</td>',t,re.S|re.I)
    return txt(m.group(1)) if m else None
books=[];revs=[]
for fn in sorted(os.listdir('cr_html')):
    raw=open('cr_html/'+fn,'rb').read()
    try: t=raw.decode('utf-8')
    except UnicodeDecodeError: t=raw.decode('cp1252',errors='replace')
    url='https://www.complete-review.com/'+fn.replace('__','/')
    title=field(t,'Title'); author=field(t,'Author')
    if not title:
        m=re.search(r'<title>(.*?)</title>',t,re.S); 
        if m and ' - ' in txt(m.group(1)): title,author=[x.strip() for x in txt(m.group(1)).rsplit(' - ',1)]
    oa=re.search(r'Our Assessment:\s*</font>.*?<b>\s*([A-F][+-]?)\s*</b>',t,re.S)
    if not oa: oa=re.search(r'Our Assessment:.*?>\s*([A-F][+-]?)\s*<',t,re.S)
    sec=re.search(r'name="summaries">Review Summaries.*?</table>',t,re.S)
    rows=[]
    if sec:
        for tr in re.findall(r'<tr>(.*?)</tr>',sec.group(0),re.S):
            tds=re.findall(r'<td[^>]*>(.*?)</td>',tr,re.S)
            if len(tds)>=3:
                lk=re.search(r'href="([^"]+)"',tds[0])
                rows.append(dict(source=txt(tds[0]),source_url=lk.group(1) if lk else None,grade=txt(tds[1]),date=txt(tds[2]),reviewer=txt(tds[3]) if len(tds)>3 else None))
    # quotes
    fr=re.search(r'From the Reviews(?:</font>)?:(.*?)(?:Please note that these ratings|</table>|<hr)',t,re.S)
    quotes=[]
    if fr:
        for q in re.split(r'<li>',fr.group(1)):
            q=txt(q)
            m=re.match(r'^"(.*)"\s*-\s*(.+)$',q,re.S)
            if m: quotes.append((m.group(1).strip(),m.group(2).strip()))
    for r in rows:
        qs=[q for q,a in quotes if (r['reviewer'] and r['reviewer'] in a) or (not r['reviewer'] and r['source'].lower()[:10] in a.lower())]
        if not qs:
            qs=[q for q,a in quotes if r['source'].replace('The ','').lower()[:8] in a.lower() and (not r['reviewer'] or r['reviewer'].split()[-1] in a)]
        r['pull_quote']=' '.join(qs) if qs else None
        r['cr_url']=url
    books.append(dict(cr_url=url,title=title,author=author,genre=field(t,'Genre'),written=field(t,'Written'),
        original_in=field(t,'Original in'),translated_by=field(t,'Translated by'),cr_grade=oa.group(1) if oa else None,
        n_review_rows=len(rows),n_quotes=len(quotes)))
    revs+=rows
B=pd.DataFrame(books); R=pd.DataFrame(revs)
B.to_csv('cr_books.csv',index=False); R.to_csv('cr_reviews.csv',index=False)
print(len(B),len(R)); print(B.head(3).T); print(R.grade.value_counts().head(20)); print('quote match rate',R.pull_quote.notna().mean())
