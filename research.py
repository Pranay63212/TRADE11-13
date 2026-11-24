"""
Pre-registered refinements of AMD+Time+IFVG and CRT, tested in-sample (Dukascopy
CFDs, early 2025) and out-of-sample (Yahoo NQ/ES futures, last 60 days).

Variants were chosen from common ICT/CRT community refinements BEFORE looking at
results: closer targets (50% / 1R / 0.5R), SMT divergence (NQ vs ES), displacement
candle filter; CRT on the 1AM/5AM 4H grid with 50% target.

Run: python3 research.py
"""
import numpy as np
import pandas as pd

import backtest as bt
from variants import load_sets

NY = bt.NY
bt.COST_POINTS.update({"NQ=F": 1.0, "ES=F": 0.5})
PAIR = {"USATECHIDXUSD": "USA500IDXUSD", "USA500IDXUSD": "USATECHIDXUSD",
        "NQ=F": "ES=F", "ES=F": "NQ=F"}


def walk(m5, sym, entry_i, side, stop, target, end_i):
    """Same rules as backtest.simulate (stop first if both touched; costs in points)."""
    e = m5.Open.iat[entry_i]
    risk = (e - stop) * side
    if risk <= 0 or (target - e) * side <= 0:
        return None
    for i in range(entry_i, end_i + 1):
        h, l = m5.High.iat[i], m5.Low.iat[i]
        if (l <= stop) if side > 0 else (h >= stop):
            px = stop; break
        if (h >= target) if side > 0 else (l <= target):
            px = target; break
    else:
        px = m5.Close.iat[end_i]
    return ((px - e) * side - bt.COST_POINTS[sym]) / risk


def asia_levels(m5, d, hours=4):
    a = m5[(m5.index >= d - pd.Timedelta(hours=hours)) & (m5.index < d)]
    return (a.High.max(), a.Low.min()) if len(a) >= 6 * hours else (None, None)


def smt_ok(other, d, side, until):
    """SMT: the paired market did NOT sweep the same side of its own Asian range."""
    if other is None:
        return False
    hi, lo = asia_levels(other, d)
    if hi is None:
        return False
    s = other[(other.index >= d) & (other.index <= until)]
    return not (s.Low < lo).any() if side > 0 else not (s.High > hi).any()


def amd_variants(sym, m5, other):
    base = bt.amd_ifvg(sym, m5, "range", asia_hours=4)
    rng = (m5.High - m5.Low).values
    out = {k: [] for k in ["base", "mid50", "1R", "0.5R", "smt", "smt_1R", "displacement"]}
    for t in base:
        sig_i = m5.index.get_loc(pd.Timestamp(t.signal_time)); ei = sig_i + 1
        d = pd.Timestamp(t.signal_time).normalize()
        end = int(np.searchsorted(m5.index, d + pd.Timedelta(hours=16))) - 1
        e, s, side = m5.Open.iat[ei], t.stop, t.side
        hi, lo = asia_levels(m5, d)
        r = lambda tgt: walk(m5, sym, ei, side, s, tgt, end)
        out["base"].append((t.entry_time, t.r))
        x = r((hi + lo) / 2)
        if x is not None: out["mid50"].append((t.entry_time, x))
        out["1R"].append((t.entry_time, r(e + (e - s))))
        out["0.5R"].append((t.entry_time, r(e + 0.5 * (e - s))))
        smt = smt_ok(other, d, side, pd.Timestamp(t.signal_time))
        if smt:
            out["smt"].append((t.entry_time, t.r))
            out["smt_1R"].append((t.entry_time, r(e + (e - s))))
        if sig_i >= 12 and rng[sig_i] >= 1.5 * rng[sig_i - 12:sig_i].mean():
            out["displacement"].append((t.entry_time, t.r))
    return out


def h4_grid(h1, offset_h):
    loc = h1.copy(); loc.index = loc.index.tz_localize(None)
    key = (loc.index - pd.Timedelta(hours=offset_h)).floor("4h") + pd.Timedelta(hours=offset_h)
    g = loc.groupby(key)
    c4 = pd.DataFrame({"Open": g.Open.first(), "High": g.High.max(), "Low": g.Low.min(),
                       "Close": g.Close.last(), "last": g.apply(lambda x: x.index[-1]),
                       "n": g.size()})
    return c4[c4.n >= 2]


def crt_variants(sym, m5, other):
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    h1 = m5.resample("1h", label="left", closed="left").agg(agg).dropna()
    oh1 = other.resample("1h", label="left", closed="left").agg(agg).dropna() if other is not None else None
    pos = {t: i for i, t in enumerate(h1.index.tz_localize(None))}
    out = {k: [] for k in ["base", "1am5am", "mid50", "1am5am_mid50", "smt"]}
    for grid, offset in (("std", 18), ("fx", 17)):          # 18:00 grid vs 17:00 (1/5/9 AM) grid
        c4 = h4_grid(h1, offset)
        oc4 = h4_grid(oh1, offset) if oh1 is not None else None
        busy = -1
        for k in range(1, len(c4) - 2):
            c1, c2 = c4.iloc[k - 1], c4.iloc[k]
            side = 0
            if c2.Low < c1.Low and c1.Low < c2.Close < c1.High:
                side, stop, tgt = 1, c2.Low, c1.High
            elif c2.High > c1.High and c1.Low < c2.Close < c1.High:
                side, stop, tgt = -1, c2.High, c1.Low
            if not side:
                continue
            ei = pos[c2["last"]] + 1
            if ei >= len(h1) or ei <= busy:
                continue
            last_i = pos[c4.iloc[min(k + 2, len(c4) - 1)]["last"]]
            mid = (c1.High + c1.Low) / 2
            is15 = c4.index[k - 1].hour == 1 and c4.index[k].hour == 5
            et = h1.index[ei]
            if grid == "std":
                x = walk(h1, sym, ei, side, stop, tgt, last_i)
                if x is not None:
                    out["base"].append((et, x)); busy = ei
                    y = walk(h1, sym, ei, side, stop, mid, last_i)
                    if y is not None: out["mid50"].append((et, y))
                    if oc4 is not None and c4.index[k] in oc4.index:
                        o1 = oc4.loc[c4.index[k - 1]] if c4.index[k - 1] in oc4.index else None
                        o2 = oc4.loc[c4.index[k]]
                        if o1 is not None:
                            swept = (o2.Low < o1.Low) if side > 0 else (o2.High > o1.High)
                            if not swept: out["smt"].append((et, x))
            elif is15:
                x = walk(h1, sym, ei, side, stop, tgt, last_i)
                if x is not None: out["1am5am"].append((et, x))
                y = walk(h1, sym, ei, side, stop, mid, last_i)
                if y is not None: out["1am5am_mid50"].append((et, y))
    return out


def summarize(pairs, weeks):
    r = np.array([x for _, x in pairs if x is not None]); n = len(r)
    if n < 2:
        return dict(trades=n)
    se = r.std(ddof=1) / np.sqrt(n)
    return dict(trades=n, per_week=round(n / weeks, 1), win=f"{np.mean(r > 0) * 100:.0f}%",
                avg_R=round(r.mean(), 3), ci=f"[{r.mean() - 1.96 * se:+.2f},{r.mean() + 1.96 * se:+.2f}]",
                total_R=round(r.sum(), 1))


if __name__ == "__main__":
    ins, oos = load_sets()
    rows = []
    for period, sets in (("2025 in-sample", ins), ("2026 out-of-sample", oos)):
        data = dict(sets)
        # overlap window so both markets of a pair exist (needed for SMT)
        start = max(m.index[0] for m in data.values()); end = min(m.index[-1] for m in data.values())
        weeks = (end - start).days / 7
        acc = {}
        for sym, m5 in data.items():
            m5 = m5[(m5.index >= start) & (m5.index <= end)]
            other = data[PAIR[sym]]; other = other[(other.index >= start) & (other.index <= end)]
            for fam, fn in (("AMD+IFVG", amd_variants), ("CRT", crt_variants)):
                for v, pairs in fn(sym, m5, other).items():
                    acc.setdefault((fam, v), []).extend(pairs)
        for (fam, v), pairs in acc.items():
            rows.append(dict(period=period, strategy=fam, variant=v, **summarize(pairs, weeks)))
        print(f"{period}: {start:%Y-%m-%d} -> {end:%Y-%m-%d} ({weeks:.1f} weeks, both markets combined)")
    df = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(df.sort_values(["strategy", "variant", "period"]).to_string(index=False))
    df.to_csv("results/research_variants.csv", index=False)
