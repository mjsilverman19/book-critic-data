import pandas as pd, numpy as np, joblib, re
exec(open(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)),'common.py')).read())
from fulltext import FullText
G=pd.read_parquet('guardian_reviews.parquet'); G=G[G.body.fillna('').str.len()>300].reset_index(drop=True)
F=np.load('gfeat.npy'); assert len(F)==len(G)
G['uk']=G.review_url.map(norm_url)
lab=G.merge(bm[['uk','rating_value']].dropna().drop_duplicates('uk'),on='uk',how='left')
li=np.where(lab.rating_value.notna())[0]
texts=(lab.body+' '+lab.standfirst.fillna('')).values
m=FullText().fit(texts[li],lab.rating_value.values[li],F[li]); print(m.metrics)
joblib.dump(m,'ft_guardian.joblib')
