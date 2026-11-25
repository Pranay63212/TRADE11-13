"""
AMD+IFVG 0.5R on MNQ under Lucid 25K Pro rules, by entry window:
  both   = 02:00-05:00 and 08:30-11:00 (current strategy / automated + manual hybrid)
  ny     = 08:30-11:00 only (trade by hand)
  london = 02:00-05:00 only
Eval: $1,250 target, $1,000 EOD trailing DD, $600 DLL, 40% consistency (fails account; with
0.5R wins this never binds). Funded: first $250 payout, 3 trading days, 40% consistency.
Run: python3 lucid_windows.py
"""
import numpy as np, pandas as pd
import backtest as bt, lucid_sim as L
from lucid_funded_sim import first_payout
from variants import load_sets

WINDOWS = {"both": [(120, 300), (510, 660)], "ny": [(510, 660)], "london": [(120, 300)]}

def set_window(name):
    w = WINDOWS[name]
    bt.in_killzone = lambda ts: any(a <= ts.hour * 60 + ts.minute < b for a, b in w)

if __name__ == "__main__":
    ins, oos = load_sets(); rows = []
    for period, sym, m5 in (("2025", "USATECHIDXUSD", dict(ins)["USATECHIDXUSD"]), ("2026", "NQ=F", dict(oos)["NQ=F"])):
        days = sorted({d for d in set(m5.index.normalize()) if d.dayofweek < 5})  # keep Sunday-evening bars (Monday's Asian range); count weekdays only
        weeks = len(days) / 5
        for win in WINDOWS:
            set_window(win); tr = L.amd_trades(m5, sym, "0.5R")
            r = np.array([(p - L.COST) / rp for p, _, rp in tr.values()]); se = r.std(ddof=1) / np.sqrt(len(r))
            for risk in (150, 200, 250):
                dp, dz = L.day_pnl(tr, days, risk), L.day_pnl(tr, days, risk, zero_edge=True)
                ev, evd = L.eval_mc(dp, consistency=0.4); evz, _ = L.eval_mc(dz, consistency=0.4)
                fu, _ = first_payout(L.day_pnl(tr, days, 150))
                rows.append(dict(period=period, window=win, trades=len(r), per_week=round(len(r) / weeks, 1),
                                 win=f"{np.mean(r > 0):.0%}", avg_R=round(r.mean(), 3),
                                 ci=f"[{r.mean()-1.96*se:+.2f},{r.mean()+1.96*se:+.2f}]", risk=risk,
                                 eval_pass=round(ev, 2), no_edge=round(evz, 2), eval_days=evd, funded_payout_150=round(fu, 2)))
    df = pd.DataFrame(rows); pd.set_option("display.width", 250)
    print(df.to_string(index=False)); df.to_csv("results/lucid_windows.csv", index=False)
