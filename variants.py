import sys; sys.path.insert(0,"/home/user/TRADE11-13")
import pandas as pd, numpy as np, yfinance as yf
import backtest as bt
NY=bt.NY; bt.COST_POINTS.update({"NQ=F":1.0,"ES=F":0.5})
def load_sets():
    ins,oos=[],[]
    for sym in ["USATECHIDXUSD","USA500IDXUSD"]:
        m5,_=bt.load_duka(sym); ins.append((sym,m5[m5.index<"2026-01-01"]))
    for sym in ["NQ=F","ES=F"]:
        df=yf.download(sym,interval="5m",period="60d",progress=False,auto_adjust=False)
        if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.get_level_values(0)
        df.index=df.index.tz_convert(NY); oos.append((sym,df[["Open","High","Low","Close"]]))
    return ins,oos

def resim(sym,m5,t,be=False):
    """Re-walk a trade; be=True moves stop to entry once price reaches +1R."""
    idx=m5.index; i0=idx.get_loc(pd.Timestamp(t.entry_time)); i1=idx.get_loc(pd.Timestamp(t.exit_time))
    end=int(np.searchsorted(idx,pd.Timestamp(t.entry_time).normalize()+pd.Timedelta(hours=16)))-1
    e,s,tg,side=t.entry,t.stop,t.target,t.side; risk=(e-s)*side; stop=s
    for i in range(i0,end+1):
        h,l=m5.High.iat[i],m5.Low.iat[i]
        if (l<=stop if side>0 else h>=stop): px=stop; break
        if (h>=tg if side>0 else l<=tg): px=tg; break
        if be and ((h>=e+risk) if side>0 else (l<=e-risk)): stop=e
    else: px=m5.Close.iat[end]
    return ((px-e)*side-bt.COST_POINTS[sym])/risk

def features(sym,m5,trades):
    daily=m5.Close.resample("1D").last().dropna()
    out=[]
    for t in trades:
        et=pd.Timestamp(t.entry_time); d=et.normalize()
        prev=daily[daily.index<d-pd.Timedelta(hours=4)]
        trend=np.sign(prev.iloc[-1]-prev.iloc[-6]) if len(prev)>=6 else 0   # 5-day trend
        rr=abs(t.target-t.entry)/abs(t.entry-t.stop)
        out.append(dict(sym=sym,r=t.r,r_be=resim(sym,m5,t,True),rr=rr,ny=et.hour>=8,
                        with_trend=(trend==t.side)))
    return out

if __name__=="__main__":
    ins,oos=load_sets(); res={}
    for name,sets in (("2025 (in-sample)",ins),("2026 (out-of-sample)",oos)):
        rows=[]
        for sym,m5 in sets: rows+=features(sym,m5,bt.amd_ifvg(sym,m5,"range",asia_hours=4))
        res[name]=pd.DataFrame(rows)
    def summ(d,col="r"):
        r=d[col]; n=len(r)
        if n<2: return f"{n:>4} trades"
        se=r.std(ddof=1)/np.sqrt(n)
        return f"{n:>4} trades  win {np.mean(r>0)*100:4.0f}%  avg {r.mean():+.2f}R  [{r.mean()-1.96*se:+.2f},{r.mean()+1.96*se:+.2f}]  total {r.sum():+6.1f}R"
    tests=[("0. Current rules",lambda d:d,"r"),
           ("1. Breakeven stop at +1R",lambda d:d,"r_be"),
           ("2. Skip if reward:risk < 1.5",lambda d:d[d.rr>=1.5],"r"),
           ("3. Only with 5-day trend",lambda d:d[d.with_trend],"r"),
           ("4. NY window only (8:30-11)",lambda d:d[d.ny],"r"),
           ("5. London window only (2-5)",lambda d:d[~d.ny],"r"),
           ("6. Nasdaq only",lambda d:d[d.sym.isin(["USATECHIDXUSD","NQ=F"])],"r")]
    for label,f,col in tests:
        print(label)
        for name,d in res.items(): print(f"   {name:22s} {summ(f(d),col)}")
