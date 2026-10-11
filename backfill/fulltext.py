"""Full-text review rating model: TF-IDF of the review plus quote-model sentence features, ridge regression.
Trained on reviews whose Book Marks label is known (matched by URL)."""
import numpy as np, re, joblib, pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold, cross_val_predict
from scipy.sparse import hstack, csr_matrix
QV,QM=joblib.load('quote_model.joblib'); VALS=np.array([1,2,3,4])
def pq(t): return QM.predict_proba(hstack([QV[0].transform(t),QV[1].transform(t)]).tocsr())@VALS
def sent_feats(bodies):
    SS=[[x for x in re.split(r'(?<=[.!?])\s+',b or '') if len(x)>30] for b in bodies]
    flat=[x for ss in SS for x in ss]
    PP=np.concatenate([pq(flat[i:i+50000]) for i in range(0,len(flat),50000)]) if flat else np.array([])
    F=[];k=0
    for ss in SS:
        p=PP[k:k+len(ss)]; k+=len(ss)
        if len(p)==0: F.append([3]*5); continue
        n=len(p); last=p[int(n*0.8):] if n>=5 else p
        F.append([p.mean(),np.percentile(p,10),np.percentile(p,90),last.mean(),p[:max(1,n//5)].mean()])
    return np.array(F)
class FullText:
    def fit(self,texts,y,F=None):
        F=sent_feats(texts) if F is None else F
        self.mu,self.sd=F.mean(0),F.std(0)
        self.tv=TfidfVectorizer(ngram_range=(1,2),min_df=3,max_df=0.5,sublinear_tf=True,max_features=200000)
        X=hstack([self.tv.fit_transform(texts),csr_matrix((F-self.mu)/self.sd)]).tocsr()
        p=cross_val_predict(Ridge(alpha=3.0),X,y,cv=KFold(5,shuffle=True,random_state=0))
        dist=pd.Series(y).value_counts(normalize=True).sort_index().values
        self.cuts=np.quantile(p,np.cumsum(dist)[:-1]); l=np.digitize(p,self.cuts)+1
        self.metrics=dict(n=len(y),corr=float(np.corrcoef(p,y)[0,1]),exact=float((l==y).mean()),within1=float((abs(l-y)<=1).mean()))
        self.m=Ridge(alpha=3.0).fit(X,y); return self
    def predict(self,texts,F=None):
        F=sent_feats(texts) if F is None else F
        X=hstack([self.tv.transform(texts),csr_matrix((F-self.mu)/self.sd)]).tocsr()
        p=self.m.predict(X); return p,np.digitize(p,self.cuts)+1
