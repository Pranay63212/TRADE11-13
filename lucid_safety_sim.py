"""
Safety check for the Lucid 25K Pro eval (official rules): MNQ only vs MNQ + MES.
Reports pass %, BLOW % (hit the $1,000 MLL) and still-going % after 250 trading days.
MES: $5/point, cost 0.5 point per contract (as research.py). Daily P&L of both markets is summed.
Windows: overlap of both markets' data (2025 Dukascopy: Jan-Mar 2025; 2026 Yahoo: last ~60 days).
Run: python3 lucid_safety_sim.py
"""
import numpy as np, pandas as pd
import lucid_sim as L
from variants import load_sets

def daily(tr, days, risk, pv, cost):
    out = {}
    for d in days:
        if d in tr:
            pts, mae, rp = tr[d]; n = min(20, int(risk // ((rp + cost) * pv)))
            if n: out[d] = (n * pv * (pts - cost), n * pv * (mae + cost)); continue
        out[d] = (0.0, 0.0)
    return out

def mc(arr, n=20000, horizon=250, seed=4):
    rng = np.random.default_rng(seed); res = {"pass": 0, "blow": 0}
    for _ in range(n):
        bal = peak = 0.0
        for p, w in arr[rng.integers(0, len(arr), horizon)]:
            floor = 100.0 if peak > 1100 else peak - 1000
            if bal - w <= floor: res["blow"] += 1; break
            bal += p; peak = max(peak, bal)
            if bal >= 1250: res["pass"] += 1; break
    return res["pass"] / n, res["blow"] / n

if __name__ == "__main__":
    ins, oos = load_sets(); rows = []
    for period, (nq_sym, es_sym), sets in (("2025", ("USATECHIDXUSD", "USA500IDXUSD"), dict(ins)), ("2026", ("NQ=F", "ES=F"), dict(oos))):
        nq, es = sets[nq_sym], sets[es_sym]
        s, e = max(nq.index[0], es.index[0]), min(nq.index[-1], es.index[-1])
        nq, es = nq[(nq.index >= s) & (nq.index <= e)], es[(es.index >= s) & (es.index <= e)]
        days = sorted({d for d in set(nq.index.normalize()) if d.dayofweek < 5})
        L.COST = 1.0; tnq = L.amd_trades(nq, nq_sym, "0.5R")
        tes = L.amd_trades(es, es_sym, "0.5R")
        for label, rn, re_ in (("MNQ only $200", 200, 0), ("MNQ $200 + MES $200", 200, 200),
                               ("MNQ $100 + MES $100", 100, 100), ("MES only $200", 0, 200)):
            a = daily(tnq, days, rn, 2.0, 1.0) if rn else {d: (0.0, 0.0) for d in days}
            b = daily(tes, days, re_, 5.0, 0.5) if re_ else {d: (0.0, 0.0) for d in days}
            arr = np.array([(a[d][0] + b[d][0], a[d][1] + b[d][1]) for d in days])
            p, bl = mc(arr)
            rows.append(dict(period=period, setup=label, days=len(days), trades=int((arr[:, 1] > 0).sum()),
                             pass_=round(p, 2), blow=round(bl, 2), avg_day=round(arr[:, 0].mean(), 1)))
    df = pd.DataFrame(rows); print(df.to_string(index=False)); df.to_csv("results/lucid_safety_sim.csv", index=False)
