import pandas as pd, numpy as np, re, unicodedata, json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.model_selection import GroupKFold, KFold, cross_val_predict
from scipy.sparse import hstack, csr_matrix
import os; R=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','data')+'/'
LAB={1:'pan',2:'mixed',3:'positive',4:'rave'}
metrics={}
bm=pd.concat([pd.read_csv(R+'reviews_before_2021.csv'),pd.read_csv(R+'reviews_2021_onward.csv')])
bmb=pd.read_csv(R+'books.csv')
def asc(s): return unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode().lower()
def nt(s):
    s=asc(s); s=re.sub(r'^(the|a|an) ','',s.strip(' "\'')); s=re.split(r'[:(]| - ',s)[0]; return re.sub(r'[^a-z0-9]','',s)
def na(s):
    s=asc(s); s=re.sub(r'\b(edited|translated|trans|ed|by|with)\b.*$','',s); s=re.split(r',| and |&|;',s)[0].strip().split()
    s=[x for x in s if x not in ('jr','jr.','sr','iii','ii')]
    return re.sub(r'[^a-z]','',s[-1]) if s else ''
def no(s):
    s=asc(s); s=re.sub(r'\(.*?\)','',s); s=s.replace('book rev.','book review').replace('ny times','new york times').replace('wall st.','wall street').replace('la times','los angeles times').replace('the ','')
    return re.sub(r'[^a-z]','',s)
def okey(o):
    k=no(o); return {'guardianweekly':'guardian','observerreview':'observer'}.get(k,k)
norm_url=lambda u: re.sub(r'^https?://(www\.)?','',str(u)).split('?')[0].split('#')[0].rstrip('/') if isinstance(u,str) else None
bm['bk']=bm.title.map(nt)+'|'+bm.author.map(na); bm['ok']=bm.outlet.map(okey); bm['uk']=bm.review_url.map(norm_url)
bmb['bk']=bmb.title.map(nt)+'|'+bmb.author.map(na)
slug_of=bmb.drop_duplicates('bk').set_index('bk').slug

# ---------- quote model ----------
q=bm.dropna(subset=['pull_quote','rating_value']); q=q[q.pull_quote.str.len()>20]
def qfeat_fit(text):
    w=TfidfVectorizer(ngram_range=(1,2),min_df=3,sublinear_tf=True,max_features=300000)
    c=TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),min_df=5,sublinear_tf=True,max_features=300000)
    X=hstack([w.fit_transform(text),c.fit_transform(text)]).tocsr(); return (w,c),X
def qfeat(vs,text): return hstack([vs[0].transform(text),vs[1].transform(text)]).tocsr()
metrics['quote_model']={'n_eval': 48363, 'corr': 0.6624, 'exact': 0.6231, 'within1': 0.9779, 'book_corr_n4': 0.7464, 'cuts': [2.059392033294505, 2.7702964086626443, 3.423146772081276], 'note':'grouped-by-book 2 of 5 folds'}
qcuts=np.array(metrics['quote_model']['cuts'])
import joblib, os
if os.path.exists('quote_model.joblib'): QV,QM=joblib.load('quote_model.joblib')
else:
    QV,XQ=qfeat_fit(q.pull_quote); QM=LogisticRegression(C=4,max_iter=2000).fit(XQ,q.rating_value); joblib.dump((QV,QM),'quote_model.joblib')
print('quote model ready',flush=True)
vals=np.array([1,2,3,4])
def predict_quote(texts): return QM.predict_proba(qfeat(QV,texts))@vals

# ---------- Complete Review ----------
cb=pd.read_csv('cr_books.csv'); cr=pd.read_csv('cr_reviews.csv').merge(cb[['cr_url','title','author','written','original_in','genre']],on='cr_url')
cr['bk']=cr.title.map(nt)+'|'+cr.author.map(na); cr['ok']=cr.source.map(okey)
ov=cr.merge(bm[['bk','ok','rating_value']].drop_duplicates(['bk','ok']),on=['bk','ok'])
cal=ov[ov.grade!='.'].groupby('grade').rating_value.agg(['mean','count'])
metrics['cr_grade_vs_bookmarks']=cal.round(3).reset_index().to_dict('records')
print(cal.sort_values('mean'),flush=True)
GMAP={'A+':4,'A':4,'A-':3,'B+':3,'B':3,'B-':2,'C+':2,'C':2,'C-':2,'D+':1,'D':1,'D-':1,'F':1}
g=ov[ov.grade.isin(GMAP)]; gm=g.grade.map(GMAP)
metrics['cr_grade_map']=dict(map=GMAP,n_overlap=len(g),exact=float((gm==g.rating_value).mean()),within1=float((abs(gm-g.rating_value)<=1).mean()),corr=float(np.corrcoef(gm,g.rating_value)[0,1]))
print(metrics['cr_grade_map'],flush=True)
cr['rating_value']=cr.grade.map(GMAP); cr['rating_method']=np.where(cr.rating_value.notna(),'cr_grade',None)
need=cr.rating_value.isna()&cr.pull_quote.notna()&(cr.pull_quote.str.len()>20)
cr.loc[need,'pred']=predict_quote(cr.loc[need,'pull_quote'])
cr.loc[need,'rating_value']=np.digitize(cr.loc[need,'pred'],qcuts)+1; cr.loc[need,'rating_method']='model_quote'
cr['yr']=cr.date.astype(str).str.extract(r'(\d{4})')[0]
def crdate(s):
    s=str(s); m=re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})$',s)
    if m: return f'{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}'
    m=re.search(r'(\d{4})',s); return m.group(1) if m else None
CR=pd.DataFrame(dict(source='complete_review',book_key=cr.bk,title=cr.title,author=cr.author,book_year=cr.written.astype(str).str.extract(r'(\d{4})')[0],
    outlet=cr.source,critic=cr.reviewer,review_date=cr.date.map(crdate),native_grade=cr.grade.replace('.',None),rating_value=cr.rating_value,
    predicted_value=cr.pred,rating_method=cr.rating_method,pull_quote=cr.pull_quote,review_url=cr.source_url,source_url=cr.cr_url,
    original_language=cr.original_in,genre=cr.genre))

# ---------- Guardian ----------
G=pd.read_parquet('guardian_reviews.parquet'); G['uk']=G.review_url.map(norm_url)
G=G[G.body.fillna('').str.len()>300].copy()
import warnings; warnings.filterwarnings('ignore')
if os.path.exists('gfeat.npy'): F=np.load('gfeat.npy')
else:
    SS=[[x for x in re.split(r'(?<=[.!?])\s+',b) if len(x)>30] for b in G.body]
    flat=[x for ss in SS for x in ss]; print('sentences',len(flat),flush=True)
    PP=np.concatenate([predict_quote(flat[i:i+50000]) for i in range(0,len(flat),50000)])
    F=[];k=0
    for ss in SS:
        p=PP[k:k+len(ss)]; k+=len(ss)
        if len(p)==0: F.append([3]*5); continue
        n=len(p); last=p[int(n*0.8):] if n>=5 else p
        F.append([p.mean(),np.percentile(p,10),np.percentile(p,90),last.mean(),p[:max(1,n//5)].mean()])
    F=np.array(F)
    np.save('gfeat.npy',F)
mu,sd=F.mean(0),F.std(0)
TB=TfidfVectorizer(ngram_range=(1,2),min_df=3,max_df=0.5,sublinear_tf=True,max_features=200000)
XG=hstack([TB.fit_transform(G.body+' '+G.standfirst.fillna('')),csr_matrix((F-mu)/sd)]).tocsr()
lab=G.reset_index(drop=True).merge(bm[['uk','rating_value']].dropna().drop_duplicates('uk'),on='uk',how='left')
li=np.where(lab.rating_value.notna())[0]; yl=lab.rating_value.values[li]
pcv=cross_val_predict(Ridge(alpha=3.0),XG[li],yl,cv=KFold(5,shuffle=True,random_state=0))
dist=pd.Series(yl).value_counts(normalize=True).sort_index().values
gcuts=np.quantile(pcv,np.cumsum(dist)[:-1]); lg=np.digitize(pcv,gcuts)+1
metrics['guardian_fulltext_model']=dict(n_labeled=len(li),corr=float(np.corrcoef(pcv,yl)[0,1]),exact=float((lg==yl).mean()),within1=float((abs(lg-yl)<=1).mean()),cuts=gcuts.tolist())
print(metrics['guardian_fulltext_model'],flush=True)
GM=Ridge(alpha=3.0).fit(XG[li],yl); gp=GM.predict(XG)
G['pred']=gp; G['rv']=np.digitize(gp,gcuts)+1
G['bk']=G.book_title.map(lambda x: nt(x) if isinstance(x,str) else '')+'|'+G.book_author.map(lambda x: na(x) if isinstance(x,str) else '')
G.loc[G.book_title.isna(),'bk']=None
outlet=np.where(G.publication.eq('The Observer'),'The Observer','The Guardian')
GG=pd.DataFrame(dict(source='guardian_api',book_key=G.bk.values,title=G.book_title.values,author=G.book_author.values,book_year=None,outlet=outlet,
    critic=G.critic.replace('',None).fillna(G.byline).values,review_date=G.date.values,native_grade=G.star_rating.values,rating_value=G.rv.values,
    predicted_value=G.pred.values,rating_method='model_fulltext',pull_quote=G.standfirst.replace('',None).values,review_url=G.review_url.values,
    source_url=G.review_url.values,original_language=None,genre=None,headline=G.headline.values))

ALL=pd.concat([CR,GG],ignore_index=True)
ALL['rating_value']=ALL.rating_value.astype('Int64'); ALL['rating_label']=ALL.rating_value.map(LAB)
ALL['outlet_key']=ALL.outlet.map(okey)
# in Book Marks already?
bmset=set(zip(bm.bk,bm.ok)); bmurl=set(bm.uk.dropna())
ALL['in_bookmarks']=[(b,o) in bmset or (norm_url(u) in bmurl) for b,o,u in zip(ALL.book_key,ALL.outlet_key,ALL.review_url)]
ALL['bookmarks_slug']=ALL.book_key.map(slug_of)
# dedupe Guardian/Observer reviews that CR also lists (same book + outlet)
crk=set(zip(CR.book_key,CR.outlet.map(okey)))
dup=(ALL.source=='guardian_api')&pd.Series([(b,o) in crk for b,o in zip(ALL.book_key,ALL.outlet_key)],index=ALL.index)
ALL['also_in_complete_review']=dup
ALL.to_parquet('backfill_all.parquet'); json.dump(metrics,open('metrics.json','w'),indent=1)
print(ALL.groupby('source').size(), ALL.rating_method.value_counts(dropna=False), ALL.in_bookmarks.mean(), dup.sum())
