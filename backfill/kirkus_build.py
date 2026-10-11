"""Kirkus rows -> backfill reviews. Starred reviews are raves; others are rated from the closing sentence
with the quote model, using cut points calibrated on Kirkus reviews Book Marks has already labeled."""
import pandas as pd, numpy as np, joblib, re, os
exec(open(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)),'common.py')).read())
from scipy.sparse import hstack
QV,QM=joblib.load('quote_model.joblib'); V=np.array([1,2,3,4])
K=pd.read_csv(os.environ.get('REPO',os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))+'/data/backfill/kirkus/reviews.csv.gz')
K=K.drop_duplicates('url')
def title_case(t):
    t=str(t).strip('"')
    return re.sub(r"(\w)'(\w)",lambda m:m.group(1)+"'"+m.group(2).lower(),t.title()) if t.isupper() else t
K['title_c']=K.title.map(title_case)
K['pred']=QM.predict_proba(hstack([QV[0].transform(K.verdict.fillna('')),QV[1].transform(K.verdict.fillna(''))]).tocsr())@V
K['uk']=K.url.map(norm_url)
lab=K.merge(bm[['uk','rating_value']].dropna().drop_duplicates('uk'),on='uk')
if len(lab)>200:
    y=lab.rating_value.values; dist=pd.Series(y).value_counts(normalize=True).sort_index().reindex([1,2,3,4],fill_value=0).values
    cuts=np.quantile(lab.pred,np.cumsum(dist)[:-1])
else:
    cuts=np.array([2.059392033294505, 2.7702964086626443, 3.423146772081276])
K['rv']=np.digitize(K.pred,cuts)+1
K.loc[K.starred==1,'rv']=4
if len(lab):
    lab=lab.merge(K[['uk','rv']],on='uk')
    print('Kirkus labeled',len(lab),'corr',np.corrcoef(lab.pred,lab.rating_value)[0,1],'exact',(lab.rv==lab.rating_value).mean(),'within1',(abs(lab.rv-lab.rating_value)<=1).mean())
def pubdate(s):
    m=re.search(r'(\d{4})',str(s)); return m.group(1) if m else None
out=pd.DataFrame(dict(source='kirkus',book_key=K.title_c.map(nt)+'|'+K.author.map(na),title=K.title_c,author=K.author,outlet='Kirkus',critic=None,
    review_date=K.issue_date.where(K.issue_date.fillna('N/A')!='N/A',K.date_published),standfirst=K.verdict,review_url=K.url,pred=K.pred,rv=K.rv,
    native_grade=np.where(K.starred==1,'Kirkus Star',None),rating_method=np.where(K.starred==1,'kirkus_star','model_quote'),book_year=K.date_published.map(pubdate),
    publisher=K.publisher,isbn=K.isbn))
import datetime
def iso(s):
    s=str(s); m=re.match(r'(\w+)\.? (\d+)(?:st|nd|rd|th)?, (\d{4})',s)
    for f in ('%B %d %Y','%b %d %Y'):
        try: return datetime.datetime.strptime(f'{m.group(1)[:3] if f=="%b %d %Y" else m.group(1)} {m.group(2)} {m.group(3)}',f).strftime('%Y-%m-%d')
        except Exception: pass
    return pubdate(s)
out['review_date']=out.review_date.map(iso)
out.to_parquet('extra_kirkus.parquet'); print(len(out), out.rv.value_counts().sort_index().to_dict())
