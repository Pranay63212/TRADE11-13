"""
Compare Lucid 25K plans for AMD+IFVG 0.5R (MNQ) from purchase to FIRST payout ($500+).
Official rules (support.lucidtrading.com, read 2026-11-25):
  Pro   : eval $1,250 (no consistency) -> funded: balance >= $26,600 (buffer $26,100 + $500 min),
          >= $250 profit goal, best day <= 40% of profit (keep trading if not).
  Flex  : eval $1,250 with best day <= 40% (keep trading if not) -> funded: no consistency, no buffer,
          5 days each with >= $100 profit, payout max 50% of profit so $500 needs >= $1,000 profit.
  Direct: no eval. Funded: profit >= $1,500 and best day <= 20%.
  Daily : not simulated - U.S. high-impact news is a HARD breach in funded and our entries run 8:30-11 AM.
All: $1,000 EOD trailing MLL that locks at +$100 once balance > +$1,100.
Run: python3 lucid_plans_sim.py
"""
import numpy as np, pandas as pd
import lucid_sim as L
from variants import load_sets

def phase(seq, i, target, cons=None, days_needed=0, day_min=0.0):
    """Walk days from index i. Returns (passed, next_index)."""
    bal = peak = best = 0.0; good = 0
    while i < len(seq):
        p, w = seq[i]; i += 1
        floor = 100.0 if peak > 1100.0 else peak - 1000.0
        if bal - w <= floor: return False, i
        bal += p; peak = max(peak, bal); best = max(best, p); good += p >= day_min and p > 0
        if bal >= target and (cons is None or best <= cons * bal) and good >= days_needed:
            return True, i
    return False, i

def plan_mc(daily_eval, daily_fund, plan, n=20000, horizon=500, seed=9):
    rng = np.random.default_rng(seed); ok = 0; t = []
    for _ in range(n):
        idx = rng.integers(0, len(daily_eval), horizon); se, sf = daily_eval[idx], daily_fund[idx]
        if plan == "Pro":
            p1, i = phase(se, 0, 1250)
            p2, j = phase(sf, i, 1600, cons=0.4) if p1 else (False, i)
        elif plan == "Flex":
            p1, i = phase(se, 0, 1250, cons=0.4)
            p2, j = phase(sf, i, 1000, days_needed=5, day_min=100) if p1 else (False, i)
        else:  # Direct
            p2, j = phase(sf, 0, 1500, cons=0.2)
        if p2: ok += 1; t.append(j)
    return ok / n, (int(np.median(t)) if t else None)

if __name__ == "__main__":
    ins, oos = load_sets(); rows = []
    for period, sym, m5 in (("2025", "USATECHIDXUSD", dict(ins)["USATECHIDXUSD"]), ("2026", "NQ=F", dict(oos)["NQ=F"])):
        m5 = m5[m5.index.dayofweek < 5]; days = sorted(set(m5.index.normalize()))
        tr = L.amd_trades(m5, sym, "0.5R")
        for plan in ("Pro", "Flex", "Direct"):
            for fund_risk in (150, 200, 300):
                de, df_ = L.day_pnl(tr, days, 200), L.day_pnl(tr, days, fund_risk)
                p, d = plan_mc(de, df_, plan)
                ze, zf = L.day_pnl(tr, days, 200, zero_edge=True), L.day_pnl(tr, days, fund_risk, zero_edge=True)
                pz, _ = plan_mc(ze, zf, plan)
                rows.append(dict(period=period, plan=plan, eval_risk=200 if plan != "Direct" else None,
                                 funded_risk=fund_risk, first_payout=round(p, 2), no_edge=round(pz, 2),
                                 median_trading_days=d))
    out = pd.DataFrame(rows); print(out.to_string(index=False)); out.to_csv("results/lucid_plans_sim.csv", index=False)
