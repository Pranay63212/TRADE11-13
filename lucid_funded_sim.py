"""
Lucid 25K Pro FUNDED: chance of reaching the FIRST payout before the $1,000 max loss.
Rules from the user's screenshot (2026-11-24): payout profit target $250, max loss $1,000
(EOD trailing assumed, same as eval), DLL $600, 40% consistency, 3 days to payout.
Assumptions (not confirmed with Lucid): "3 days to payout" = at least 3 trading days with
a trade; consistency = best day <= 40% of total profit at payout time (keep trading until true).
Run: python3 lucid_funded_sim.py
"""
import numpy as np, pandas as pd
import lucid_sim as L
from variants import load_sets

def first_payout(daily, n=20000, max_days=120, seed=11, target=250.0, min_days=3, cons=0.4):
    rng = np.random.default_rng(seed); ok = 0; dd = []
    for _ in range(n):
        bal = peak = best = 0.0; traded = 0
        for k, (p, worst) in enumerate(daily[rng.integers(0, len(daily), max_days)], 1):
            if bal - min(worst, L.DLL) <= peak - L.START_DD: break
            p = max(p, -L.DLL); bal += p; peak = max(peak, bal); best = max(best, p)
            traded += p != 0
            if bal >= target and traded >= min_days and best <= cons * bal:
                ok += 1; dd.append(k); break
    return ok / n, (int(np.median(dd)) if dd else None)

if __name__ == "__main__":
    ins, oos = load_sets(); rows = []
    for period, sym, m5 in (("2025", "USATECHIDXUSD", dict(ins)["USATECHIDXUSD"]), ("2026", "NQ=F", dict(oos)["NQ=F"])):
        days = sorted({d for d in set(m5.index.normalize()) if d.dayofweek < 5})  # keep Sunday-evening bars (Monday's Asian range); count weekdays only
        for name, tr in (("ORB 3R", L.orb_trades(m5, 3)), ("ORB hold-to-close", L.orb_trades(m5, 10)),
                         ("AMD+IFVG 0.5R", L.amd_trades(m5, sym, "0.5R")), ("AMD+IFVG range", L.amd_trades(m5, sym, "range"))):
            for risk in (75, 100, 150, 200):
                pr, md = first_payout(L.day_pnl(tr, days, risk))
                base, _ = first_payout(L.day_pnl(tr, days, risk, zero_edge=True))
                rows.append(dict(period=period, strategy=name, risk=risk, first_payout=round(pr, 3),
                                 no_edge=round(base, 3), median_days=md))
    df = pd.DataFrame(rows); pd.set_option("display.width", 200)
    print(df.to_string(index=False)); df.to_csv("results/lucid_25k_funded_sim.csv", index=False)
