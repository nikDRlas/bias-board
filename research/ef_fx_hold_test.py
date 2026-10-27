"""+-7 fixed-hold event study, 15 FX pairs (no CHF/JPY). RESULT 2026-10-27: negative at every hold (1w 50.6%/-0.04%, 8w 46.1%/-0.17%) vs random ~50%/0%.
"""
import numpy as np, pandas as pd, sys
src=open('/Users/Niklas/bias-board/research/ef_fx_flip_test.py').read(); exec(src[src.index('def load(p):'):src.index('ef = pd.read_csv')])
P=['EURUSD','GBPUSD','AUDUSD','NZDUSD','USDCAD','EURGBP','EURAUD','EURCAD','EURNZD','GBPAUD','GBPCAD','GBPNZD','AUDCAD','AUDNZD','NZDCAD']
ef=pd.read_csv("/Users/Niklas/Downloads/scores_taeglich_gesamt_und_macro.csv",usecols=["date","symbol","ef_score"],parse_dates=["date"])
TH=7; H=[1,2,4,8]; rng=np.random.default_rng(3); rows=[]
import contextlib, io
for p in P:
    with contextlib.redirect_stdout(io.StringIO()): px=load(p)
    s=ef[ef.symbol==p].set_index("date").ef_score.sort_index()
    side=np.where(s>=TH,1,np.where(s<=-TH,-1,0)); prev=np.r_[0,side[:-1]]
    O,Hh,L=px.o.values,px.h.values,px.l.values
    wk=(np.log(px.c).diff().rolling(260).std()*np.sqrt(5)).values*100
    for d,sd in zip(s.index[(side!=0)&(side!=prev)], side[(side!=0)&(side!=prev)]):   # first day it enters +7 / -7 zone
        a=px.index.searchsorted(d+pd.Timedelta(days=1))
        if a<260: continue
        for h in H:
            b=a+5*h
            if b>=len(px): continue
            def m(k):
                e=O[k]; end=sd*100*(O[k+5*h]/e-1)
                mfe=100*(Hh[k:k+5*h].max()/e-1) if sd>0 else 100*(1-L[k:k+5*h].min()/e)
                mae=100*(L[k:k+5*h].min()/e-1) if sd>0 else 100*(1-Hh[k:k+5*h].max()/e)
                return end,mfe,mae
            end,mfe,mae=m(a)
            rs=rng.choice(np.arange(260,len(px)-5*h-1),100); R=np.array([m(k) for k in rs])
            rows.append(dict(pair=p,d=px.index[a],side=sd,h=h,end=end,mfe=mfe,mae=mae,wk=wk[a],
                 rend=R[:,0].mean(),rmfe=R[:,1].mean(),rwin=(R[:,0]>0).mean()))
T=pd.DataFrame(rows); T=T[T.d>="2015-06"]
def st(g,lab):
    x=g.end-g.rend; t=x.mean()/x.std()*np.sqrt(len(x))
    print(f"{lab:14s} n{len(g):4d} won{100*(g.end>0).mean():5.1f}% (rnd{100*g.rwin.mean():5.1f}) end{g.end.mean():+6.2f}% rnd{g.rend.mean():+6.2f} edge{x.mean():+6.2f} t{t:+5.2f} | MFE{g.mfe.mean():5.2f} rnd{g.rmfe.mean():5.2f} MAE{g.mae.mean():+6.2f} | end/wk{(g.end/g.wk).mean():+5.2f}")
for h in H:
    g=T[T.h==h]; print(f"--- hold {h} week(s)")
    st(g,"all 2015-26"); st(g[g.d<"2019"],"2015-18"); st(g[(g.d>="2019")&(g.d<"2024")],"2019-23"); st(g[g.d>="2024"],"2024-26")
    st(g[g.side>0],"long"); st(g[g.side<0],"short")
