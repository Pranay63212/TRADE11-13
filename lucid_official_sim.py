"""
Lucid 25K LucidPro, rules from Lucid's OFFICIAL help center (support.lucidtrading.com, read 2026-11-25):
  Eval   : target $1,250; MLL $1,000 EOD trailing, locks at $25,100 once balance > $26,100;
           DLL none on 25K (optional $600 if chosen at purchase - soft, not a fail); NO consistency rule.
  Funded : same MLL/lock; 40% consistency = must keep trading until best day <= 40% of profit
           (does NOT fail the account); payout needs >= $250 profit goal AND balance above the
           $26,100 buffer with a $500 minimum request -> first payout possible at balance >= $26,600.
  Commission MNQ $0.50/side ($1 round trip) - our 1-point cost ($2/contract) is more conservative.
Strategy: AMD+IFVG 0.5R, both killzones (the TradingView script). Run: python3 lucid_official_sim.py
"""
import numpy as np, pandas as pd
import lucid_sim as L
from variants import load_sets

LOCK_AT, LOCK_FLOOR = 1100.0, 100.0          # relative to starting balance

def run(daily, target, n=20000, max_days=250, seed=5, cons=None, min_goal=0.0):
    rng = np.random.default_rng(seed); ok = 0; days = []
    for _ in range(n):
        bal = peak = best = 0.0
        for k, (p, worst) in enumerate(daily[rng.integers(0, len(daily), max_days)], 1):
            floor = LOCK_FLOOR if peak > LOCK_AT else peak - L.START_DD
            if bal - worst <= floor: break
            bal += p; peak = max(peak, bal); best = max(best, p)
            if bal >= max(target, min_goal) and (cons is None or best <= cons * bal):
                ok += 1; days.append(k); break
    return ok / n, (int(np.median(days)) if days else None)

if __name__ == "__main__":
    ins, oos = load_sets(); rows = []
    for period, sym, m5 in (("2025", "USATECHIDXUSD", dict(ins)["USATECHIDXUSD"]), ("2026", "NQ=F", dict(oos)["NQ=F"])):
        days = sorted({d for d in set(m5.index.normalize()) if d.dayofweek < 5})  # keep Sunday-evening bars (Monday's Asian range); count weekdays only
        tr = L.amd_trades(m5, sym, "0.5R")
        for risk in (150, 200, 250):
            dp, dz = L.day_pnl(tr, days, risk), L.day_pnl(tr, days, risk, zero_edge=True)
            ev, evd = run(dp, 1250); evz, _ = run(dz, 1250)
            fu, fud = run(dp, 1600, cons=0.4, min_goal=250); fuz, _ = run(dz, 1600, cons=0.4, min_goal=250)
            rows.append(dict(period=period, risk=risk, eval_pass=round(ev, 2), eval_no_edge=round(evz, 2),
                             eval_days=evd, funded_first_500_payout=round(fu, 2), funded_no_edge=round(fuz, 2),
                             funded_days=fud))
    df = pd.DataFrame(rows); print(df.to_string(index=False)); df.to_csv("results/lucid_official_sim.csv", index=False)
