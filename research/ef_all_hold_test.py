"""+-7 fixed-hold event study, 20 non-cross markets (USD majors, indices, metals, energy, BTC). RESULT 2026-10-27: overall <= random; REGIME FLIP 2019-23 t-4.0 vs 2024-26 t+5.0 (indices 77% won +2.7% vs rnd +0.7%) = momentum in trend years, not usable.
"""
import numpy as np, pandas as pd
LD="/Users/Niklas/supply_demand_intraday/data_cache/lse_daily/"; BB="/Users/Niklas/bias-board/data/history/lse/"
M={ # replica symbol: (file, group)
 'EURUSD':(LD+'EURUSD.csv','USD majors'),'GBPUSD':(LD+'GBPUSD.csv','USD majors'),'AUDUSD':(LD+'AUDUSD.csv','USD majors'),
 'NZDUSD':(LD+'NZDUSD.csv','USD majors'),'USDCAD':(LD+'USDCAD.csv','USD majors'),'USDCHF':(LD+'USDCHF.csv','USD majors'),
 'USDJPY':(LD+'USDJPY.csv','USD majors'),'USDZAR':(LD+'USDZAR.csv','USD majors'),
 'SPX500':(LD+'SP500.csv','Indices'),'NASDAQ':(LD+'NAS100.csv','Indices'),'DOW':(LD+'DOW.csv','Indices'),
 'RUSSELL':(LD+'RUSSELL.csv','Indices'),'DAX':(LD+'DAX.csv','Indices'),
 'GOLD':(LD+'GOLD.csv','Metals'),'SILVER':(LD+'SILVER.csv','Metals'),'PLATINUM':(BB+'PL.csv.gz','Metals'),'COPPER':(LD+'COPPER.csv','Metals'),
 'USOIL':(LD+'USOIL.csv','Energy'),'NATGAS':(BB+'NG.csv.gz','Energy'),'BITCOIN':(LD+'BITCOIN.csv','Crypto')}
def load(sym):
    f,_=M[sym]; df=pd.read_csv(f,parse_dates=["ts"]).rename(columns={"open":"o","high":"h","low":"l","close":"c"}).set_index("ts").sort_index()
    df=df[(df.index.dayofweek<5)|(sym=='BITCOIN')]; df=df[df.index>="2014-01-01"]
    if sym=='DAX': df=df[df.c>5000]
    med=df.c.rolling(5,center=True,min_periods=3).median(); lim=10*np.log(df.c).diff().abs().median()
    bad=(np.log(df.c/med)).abs()>lim
    for c in "ohl": bad|=(np.log(df[c]/med)).abs()>2*lim
    df=df[~bad]; df=df[(df.h>=df.l)&(df.o>0)]
    return df
ef=pd.read_csv("/Users/Niklas/Downloads/scores_taeglich_gesamt_und_macro.csv",usecols=["date","symbol","ef_score"],parse_dates=["date"])
TH=7; H=[1,2,4,8]; rng=np.random.default_rng(3); rows=[]
for p,(f,grp) in M.items():
    px=load(p); n5=7 if p=='BITCOIN' else 5
    s=ef[ef.symbol==p].set_index("date").ef_score.sort_index()
    side=np.where(s>=TH,1,np.where(s<=-TH,-1,0)); prev=np.r_[0,side[:-1]]
    O,Hh,L=px.o.values,px.h.values,px.l.values
    wk=(np.log(px.c).diff().rolling(260).std()*np.sqrt(n5)).values*100
    ev=(side!=0)&(side!=prev)
    for d,sd in zip(s.index[ev],side[ev]):
        a=px.index.searchsorted(d+pd.Timedelta(days=1))
        if a<260: continue
        for h in H:
            n=n5*h
            if a+n>=len(px): continue
            def m(k):
                e=O[k]; end=sd*100*(O[k+n]/e-1)
                mfe=100*(Hh[k:k+n].max()/e-1) if sd>0 else 100*(1-L[k:k+n].min()/e)
                return end,mfe
            end,mfe=m(a); rs=rng.choice(np.arange(260,len(px)-n-1),100); R=np.array([m(k) for k in rs])
            rows.append(dict(sym=p,grp=grp,d=px.index[a],side=sd,h=h,end=end,mfe=mfe,wk=wk[a],rend=R[:,0].mean(),rmfe=R[:,1].mean(),rwin=(R[:,0]>0).mean()))
T=pd.DataFrame(rows); T=T[T.d>="2015-06"]; T.to_csv("ef_hz_all.csv",index=False)
def st(g,lab):
    x=(g.end-g.rend)/g.wk; t=x.mean()/x.std()*np.sqrt(len(x))
    print(f"{lab:16s} n{len(g):4d} won{100*(g.end>0).mean():5.1f}% (rnd{100*g.rwin.mean():5.1f}) end{g.end.mean():+6.2f}% rnd{g.rend.mean():+6.2f} | MFE{g.mfe.mean():6.2f} rnd{g.rmfe.mean():6.2f} | edge/wk{x.mean():+5.2f} t{t:+5.2f}")
for h in H:
    g=T[T.h==h]; print(f"=== hold {h}w"); st(g,"ALL"); st(g[g.d<"2019"],"2015-18"); st(g[(g.d>="2019")&(g.d<"2024")],"2019-23"); st(g[g.d>="2024"],"2024-26")
    for k,gg in g.groupby("grp"): st(gg,"  "+k)
    for k,gg in g.groupby("grp"): st(gg[gg.d>="2024"],"  "+k+" 24+")
    st(g[g.side>0],"long"); st(g[g.side<0],"short")
print(); g=T[T.h==4]
for k,gg in g.groupby("sym"): st(gg,k)
