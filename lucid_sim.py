"""
Lucid 25K Pro Eval simulator (rules from the user's screenshot, 2026-11-24):
  profit target $1,250 | daily loss limit $600 | max loss $1,000, EOD trailing drawdown
  max size 2 mini / 20 micro.  Traded here with MNQ micros ($2 per NQ point).
Model assumptions (NOT confirmed with Lucid):
  * floor = highest end-of-day balance - $1,000; breached if live equity (closed balance
    minus the trade's worst open loss) touches the floor intraday.
  * no lock of the floor, no minimum days. 40% consistency (user, 2026-11-24): best day
    <= 40% of total profit before passing; assumed to delay passing, not fail.
  * costs: 1 NQ point per contract round trip (as in research.py).
Bootstrap: resample whole trading days (including no-trade days) with replacement.
Run: python3 lucid_sim.py
"""
import numpy as np, pandas as pd
import backtest as bt
from variants import load_sets

PV, COST = 2.0, 1.0                       # MNQ $/point, cost points per contract
START_DD, TARGET, DLL, MAXC = 1000.0, 1250.0, 600.0, 20

def walk(m5, ei, side, stop, tgt, end):
    e = m5.Open.iat[ei]; mae = 0.0
    for i in range(ei, end + 1):
        h, l = m5.High.iat[i], m5.Low.iat[i]
        if (l <= stop) if side > 0 else (h >= stop):
            return (stop - e) * side, abs(e - stop)
        mae = max(mae, (e - l) if side > 0 else (h - e))
        if (h >= tgt) if side > 0 else (l <= tgt):
            return (tgt - e) * side, mae
    return (m5.Close.iat[end] - e) * side, mae

def end_idx(m5, d):
    return int(np.searchsorted(m5.index, d + pd.Timedelta(hours=16))) - 1

def orb_trades(m5, mult):
    out = {}
    for d, day in m5.groupby(m5.index.normalize()):
        o = day[day.index == d + pd.Timedelta(hours=9, minutes=30)]
        if o.empty: continue
        c = o.iloc[0]; side = int(np.sign(c.Close - c.Open))
        if not side: continue
        ei = m5.index.get_loc(o.index[0]) + 1; end = end_idx(m5, d)
        if ei > end: continue
        e = m5.Open.iat[ei]; stop = c.Low if side > 0 else c.High
        rp = (e - stop) * side
        if rp <= 0: continue
        pts, mae = walk(m5, ei, side, stop, e + mult * rp * side, end)
        out[d] = (pts, mae, rp)
    return out

def amd_trades(m5, sym, mode):
    out = {}
    for t in bt.amd_ifvg(sym, m5, "range", asia_hours=4):
        d = pd.Timestamp(t.entry_time).normalize(); ei = m5.index.get_loc(pd.Timestamp(t.entry_time))
        e = m5.Open.iat[ei]; rp = (e - t.stop) * t.side
        if rp <= 0: continue
        tgt = t.target if mode == "range" else e + float(mode[:-1]) * rp * t.side
        pts, mae = walk(m5, ei, t.side, t.stop, tgt, end_idx(m5, d))
        out[d] = (pts, mae, rp)
    return out

def day_pnl(trades, days, risk_usd, zero_edge=False):
    """Per-day (pnl$, worst open loss$) for a $ risk budget per trade."""
    if zero_edge:                               # remove the average edge (in R) -> no-skill baseline
        mr = np.mean([(p - COST) / rp for p, _, rp in trades.values()])
    res = []
    for d in days:
        if d not in trades: res.append((0.0, 0.0)); continue
        pts, mae, rp = trades[d]
        n = min(MAXC, int(risk_usd // ((rp + COST) * PV)))
        if n == 0: res.append((0.0, 0.0)); continue
        if zero_edge: pts = pts - mr * rp
        res.append((n * PV * (pts - COST), n * PV * (mae + COST)))
    return np.array(res)

def eval_mc(daily, n=20000, max_days=120, seed=7, consistency=None):
    """consistency=0.4: may only pass once best single day <= 40% of total profit
    (assumed: you keep trading until it holds; it does not fail the account)."""
    rng = np.random.default_rng(seed); passed = 0; days_to = []
    for _ in range(n):
        bal = peak = best = 0.0
        for k, (p, worst) in enumerate(daily[rng.integers(0, len(daily), max_days)], 1):
            if bal - min(worst, DLL) <= peak - START_DD: break        # intraday breach
            p = max(p, -DLL); bal += p; peak = max(peak, bal); best = max(best, p)
            if bal >= TARGET and (consistency is None or best <= consistency * bal):
                passed += 1; days_to.append(k); break
    return passed / n, (int(np.median(days_to)) if days_to else None)

if __name__ == "__main__":
    ins, oos = load_sets()
    sets = {"2025 in-sample": dict(ins)["USATECHIDXUSD"], "2026 out-of-sample": dict(oos)["NQ=F"]}
    strategies = {"ORB hold-to-close": lambda m, s: orb_trades(m, 10),
                  "ORB 3R": lambda m, s: orb_trades(m, 3),
                  "ORB 2R": lambda m, s: orb_trades(m, 2),
                  "AMD+IFVG range (bot)": lambda m, s: amd_trades(m, s, "range"),
                  "AMD+IFVG 0.5R": lambda m, s: amd_trades(m, s, "0.5R")}
    rows = []
    for period, m5 in sets.items():
        sym = "USATECHIDXUSD" if period.startswith("2025") else "NQ=F"
        m5 = m5[m5.index.dayofweek < 5]
        days = sorted({d for d in m5.index.normalize()
                       if not m5[(m5.index >= d + pd.Timedelta(hours=9, minutes=30)) &
                                 (m5.index < d + pd.Timedelta(hours=9, minutes=35))].empty})
        for name, fn in strategies.items():
            tr = fn(m5, sym)
            for risk in (100, 150, 200, 250, 300):
                dp, dz = day_pnl(tr, days, risk), day_pnl(tr, days, risk, zero_edge=True)
                pr, med = eval_mc(dp); pc, medc = eval_mc(dp, consistency=0.4)
                base, _ = eval_mc(dz, consistency=0.4)
                rows.append(dict(period=period, strategy=name, trades=len(tr), days=len(days),
                                 risk=risk, pass_no_rule=round(pr, 3), pass_40pct=round(pc, 3),
                                 no_edge_40pct=round(base, 3), median_days_40pct=medc))
            print(period, name, "done", flush=True)
    df = pd.DataFrame(rows); pd.set_option("display.width", 250)
    print(df.to_string(index=False)); df.to_csv("results/lucid_25k_sim.csv", index=False)
