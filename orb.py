"""
Opening Range Breakout (ORB), pre-registered BEFORE seeing results.
Rules (5-minute ORB in the style of Zarattini & Aziz 2023):
  * Opening range = the 09:30-09:35 ET 5-minute candle.
  * Direction = the colour of that candle (green -> long, red -> short, doji -> skip).
  * Entry at the 09:35 bar open. Stop = the opposite side of the opening candle.
  * Targets tested: 10R (effectively hold to close, as in the paper), 2R, 1R. Flat at 16:00.
Same stop-first convention and point costs as research.py.
Run: python3 orb.py
"""
import numpy as np, pandas as pd
import backtest as bt
from research import walk, summarize
from variants import load_sets

def orb(sym, m5, mult):
    out = []
    for d, day in m5.groupby(m5.index.normalize()):
        o = day[day.index == d + pd.Timedelta(hours=9, minutes=30)]
        if o.empty: continue
        c = o.iloc[0]
        side = 1 if c.Close > c.Open else -1 if c.Close < c.Open else 0
        if not side: continue
        i0 = m5.index.get_loc(o.index[0]); ei = i0 + 1
        end = int(np.searchsorted(m5.index, d + pd.Timedelta(hours=16))) - 1
        if ei > end: continue
        e = m5.Open.iat[ei]; stop = c.Low if side > 0 else c.High
        r = walk(m5, sym, ei, side, stop, e + mult * (e - stop), end)
        if r is not None: out.append((m5.index[ei], r))
    return out

class T:  # tiny adapter for bt.prop_mc
    def __init__(s, r): s.r = r

if __name__ == "__main__":
    ins, oos = load_sets(); rows = []
    for period, sets in (("2025 in-sample", ins), ("2026 out-of-sample", oos)):
        for mult in (10, 2, 1):
            pairs = []; weeks = 0
            for sym, m5 in sets:
                pairs += orb(sym, m5, mult); weeks = max(weeks, (m5.index[-1] - m5.index[0]).days / 7)
            rs = [x for _, x in pairs]
            rows.append(dict(period=period, variant=f"ORB {mult}R", **summarize(pairs, weeks),
                             prop_pass=bt.prop_mc([T(x) for x in rs])))
    df = pd.DataFrame(rows); pd.set_option("display.width", 250)
    print(df.to_string(index=False)); df.to_csv("results/orb.csv", index=False)
