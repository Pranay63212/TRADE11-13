"""
Backtest of two ICT-style strategies on free Yahoo Finance data.

Strategy 1 - CRT (Candle Range Theory) on 4H candles built from 1h data.
Strategy 2 - AMD (Asian range accumulation -> sweep manipulation -> distribution)
             + time windows (killzones) + IFVG entry, on 5m data.

These rule sets are ONE mechanical interpretation of concepts that are taught
loosely on social media. They are not the "official" rules of any educator.

Conventions (applied to both strategies):
  * Entry at the OPEN of the bar after the signal bar (no look-ahead).
  * If stop and target are both touched inside the same bar, the STOP is assumed
    hit first (conservative).
  * A fixed round-trip cost in points is deducted from every trade.
  * Results are in R (1R = distance entry -> stop).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd
import yfinance as yf

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

# Assumed round-trip cost (spread + slippage + commission) in index points.
COST_POINTS = {"NQ=F": 1.0, "ES=F": 0.5}
SYMBOLS = ["NQ=F", "ES=F"]
NY = "America/New_York"


# ---------------------------------------------------------------- data
def load(symbol: str, interval: str, period: str) -> pd.DataFrame:
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, f"{symbol.replace('=', '_')}_{interval}.csv")
    if os.path.exists(path):
        df = pd.read_csv(path, index_col=0)
        df.index = pd.to_datetime(df.index, utc=True).tz_convert(NY)
        return df
    df = yf.download(symbol, interval=interval, period=period,
                     progress=False, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close"]].dropna()
    df.index = df.index.tz_convert(NY)
    df.to_csv(path)
    return df


# ---------------------------------------------------------------- trades
@dataclass
class Trade:
    symbol: str
    strategy: str
    signal_time: str
    entry_time: str
    exit_time: str
    side: int          # +1 long, -1 short
    entry: float
    stop: float
    target: float
    exit: float
    exit_reason: str
    r: float


def simulate(bars: pd.DataFrame, start_idx: int, side: int, stop: float,
             target: float, last_idx: int, cost: float):
    """Walk bars from start_idx (entry at its open) until stop/target/time exit."""
    entry = bars["Open"].iat[start_idx]
    risk = (entry - stop) * side
    if risk <= 0 or (target - entry) * side <= 0:
        return None
    exit_px, reason, exit_i = None, None, None
    last_idx = min(last_idx, len(bars) - 1)
    for i in range(start_idx, last_idx + 1):
        hi, lo = bars["High"].iat[i], bars["Low"].iat[i]
        hit_stop = lo <= stop if side == 1 else hi >= stop
        hit_tgt = hi >= target if side == 1 else lo <= target
        if hit_stop:                       # stop first if both
            exit_px, reason, exit_i = stop, "stop", i
            break
        if hit_tgt:
            exit_px, reason, exit_i = target, "target", i
            break
    if exit_px is None:
        exit_i = last_idx
        exit_px, reason = bars["Close"].iat[exit_i], "time"
    r = ((exit_px - entry) * side - cost) / risk
    return entry, exit_px, reason, exit_i, r


# ---------------------------------------------------------------- strategy 1: CRT
def resample_4h(h1: pd.DataFrame) -> pd.DataFrame:
    """4H candles aligned to the 18:00 NY futures session open
    (18-22, 22-02, 02-06, 06-10, 10-14, 14-17)."""
    local = h1.copy()
    local.index = local.index.tz_localize(None)
    key = (local.index - pd.Timedelta(hours=18)).floor("4h")
    g = local.groupby(key)
    out = pd.DataFrame({
        "Open": g["Open"].first(), "High": g["High"].max(),
        "Low": g["Low"].min(), "Close": g["Close"].last(),
        "last_h1": g.apply(lambda x: x.index[-1]),
        "n": g.size(),
    })
    return out[out["n"] >= 2]


def crt(symbol: str, h1: pd.DataFrame, target_mode: str = "range",
        hold_4h: int = 2, start: pd.Timestamp | None = None) -> list[Trade]:
    """C1 = reference 4H candle, C2 = sweep candle.
    Long:  C2.low < C1.low and C1.low < C2.close < C1.high -> buy next 1h open,
           stop = C2.low, target = C1.high (or 2R).
    Short: mirror. Time exit after `hold_4h` further 4H candles."""
    cost = COST_POINTS[symbol]
    c4 = resample_4h(h1)
    h1_naive_idx = h1.index.tz_localize(None)
    pos = {t: i for i, t in enumerate(h1_naive_idx)}
    trades, busy_until = [], -1
    for k in range(1, len(c4) - 1):
        c1, c2 = c4.iloc[k - 1], c4.iloc[k]
        side = 0
        if c2.Low < c1.Low and c1.Low < c2.Close < c1.High:
            side, stop, tgt = 1, c2.Low, c1.High
        elif c2.High > c1.High and c1.Low < c2.Close < c1.High:
            side, stop, tgt = -1, c2.High, c1.Low
        if not side:
            continue
        sig_i = pos[c2.last_h1]
        entry_i = sig_i + 1
        if entry_i >= len(h1) or entry_i <= busy_until:
            continue
        if start is not None and h1.index[entry_i] < start:
            continue
        if target_mode == "2R":
            e = h1["Open"].iat[entry_i]
            tgt = e + side * 2 * (e - stop) * side
        end_4h = min(k + hold_4h, len(c4) - 1)
        last_i = pos[c4.iloc[end_4h].last_h1]
        res = simulate(h1, entry_i, side, stop, tgt, last_i, cost)
        if res is None:
            continue
        entry, exit_px, reason, exit_i, r = res
        busy_until = exit_i
        trades.append(Trade(symbol, f"CRT-4H ({target_mode})",
                            str(h1.index[sig_i]), str(h1.index[entry_i]),
                            str(h1.index[exit_i]), side, entry, stop, tgt,
                            exit_px, reason, r))
    return trades


# ---------------------------------------------------------------- strategy 2: AMD + time + IFVG
def in_killzone(ts: pd.Timestamp) -> bool:
    m = ts.hour * 60 + ts.minute
    return (2 * 60 <= m < 5 * 60) or (8 * 60 + 30 <= m < 11 * 60)


def amd_ifvg(symbol: str, m5: pd.DataFrame, target_mode: str = "range",
             asia_hours: int = 5) -> list[Trade]:
    """Per NY calendar day D:
      Accumulation: Asian range = high/low of bars 19:00 (D-1) to 00:00 (D).
      Manipulation: between 00:00 and 11:00 price trades beyond one side.
                    The FIRST side swept sets the bias (sweep low -> long).
      Entry (IFVG): after the sweep, a 5m close through the far edge of the most
                    recent opposing FVG (for longs: close > top of a bearish FVG
                    formed since 00:00). Entry bar must be inside a killzone
                    (02:00-05:00 or 08:30-11:00 NY). Buy next bar open.
      Stop: extreme of the manipulation leg (lowest low since 00:00 for longs).
      Target: opposite side of the Asian range (distribution) or 2R.
      Time exit: 16:00 NY. Max one trade per day."""
    cost = COST_POINTS[symbol]
    df = m5
    idx = df.index
    H, L, C = df["High"].values, df["Low"].values, df["Close"].values
    trades = []
    days = sorted(set(idx.normalize()))
    for d in days:
        asia = df[(idx >= d - pd.Timedelta(hours=asia_hours)) & (idx < d)]
        if len(asia) < 6 * asia_hours:
            continue
        a_hi, a_lo = asia["High"].max(), asia["Low"].min()
        sess_mask = (idx >= d) & (idx < d + pd.Timedelta(hours=11))
        sess_pos = np.flatnonzero(sess_mask)
        if len(sess_pos) < 10:
            continue
        bias, bear_fvg_top, bull_fvg_bot = 0, None, None
        run_lo, run_hi = np.inf, -np.inf
        for i in sess_pos:
            run_lo, run_hi = min(run_lo, L[i]), max(run_hi, H[i])
            # FVGs formed since 00:00 (3-candle pattern ending at bar i)
            if i - 2 >= sess_pos[0]:
                if H[i] < L[i - 2]:          # bearish FVG: gap = [H[i], L[i-2]]
                    bear_fvg_top = L[i - 2]
                if L[i] > H[i - 2]:          # bullish FVG: gap = [H[i-2], L[i]]
                    bull_fvg_bot = H[i - 2]
            if bias == 0:
                if L[i] < a_lo:
                    bias = 1
                elif H[i] > a_hi:
                    bias = -1
                continue
            if not in_killzone(idx[i]) or i + 1 >= len(df):
                continue
            side = 0
            if bias == 1 and bear_fvg_top is not None and C[i] > bear_fvg_top:
                side, stop, tgt = 1, run_lo, a_hi
            elif bias == -1 and bull_fvg_bot is not None and C[i] < bull_fvg_bot:
                side, stop, tgt = -1, run_hi, a_lo
            if not side:
                continue
            entry_i = i + 1
            if target_mode == "2R":
                e = df["Open"].iat[entry_i]
                tgt = e + 2 * (e - stop)
            close_t = d + pd.Timedelta(hours=16)
            last_i = int(np.searchsorted(idx, close_t)) - 1
            res = simulate(df, entry_i, side, stop, tgt, last_i, cost)
            if res is None:
                break                         # setup invalid (e.g. target already hit)
            entry, exit_px, reason, exit_i, r = res
            trades.append(Trade(symbol, f"AMD+Time+IFVG-5m ({target_mode})",
                                str(idx[i]), str(idx[entry_i]), str(idx[exit_i]),
                                side, entry, stop, tgt, exit_px, reason, r))
            break                             # one trade per day
    return trades


def amd_only(symbol: str, m5: pd.DataFrame, target_mode: str = "range",
             asia_hours: int = 5) -> list[Trade]:
    """Plain AMD, no killzone filter and no IFVG:
      Accumulation: Asian range 19:00 (D-1) to 00:00 (D) NY.
      Manipulation: first sweep of the Asian high/low between 00:00 and 11:00.
      Entry: first 5m close back INSIDE the Asian range after the sweep
             (still before 11:00). Buy/sell next bar open.
      Stop: manipulation extreme. Target: opposite Asian extreme (or 2R).
      Time exit 16:00 NY. Max one trade per day."""
    cost = COST_POINTS[symbol]
    df, idx = m5, m5.index
    H, L, C = df["High"].values, df["Low"].values, df["Close"].values
    trades = []
    for d in sorted(set(idx.normalize())):
        asia = df[(idx >= d - pd.Timedelta(hours=asia_hours)) & (idx < d)]
        if len(asia) < 6 * asia_hours:
            continue
        a_hi, a_lo = asia["High"].max(), asia["Low"].min()
        sess_pos = np.flatnonzero((idx >= d) & (idx < d + pd.Timedelta(hours=11)))
        if len(sess_pos) < 10:
            continue
        bias, run_lo, run_hi = 0, np.inf, -np.inf
        for i in sess_pos:
            run_lo, run_hi = min(run_lo, L[i]), max(run_hi, H[i])
            if bias == 0:
                if L[i] < a_lo:
                    bias = 1
                elif H[i] > a_hi:
                    bias = -1
                continue
            if i + 1 >= len(df):
                break
            side = 0
            if bias == 1 and a_lo < C[i] < a_hi:
                side, stop, tgt = 1, run_lo, a_hi
            elif bias == -1 and a_lo < C[i] < a_hi:
                side, stop, tgt = -1, run_hi, a_lo
            if not side:
                continue
            entry_i = i + 1
            if target_mode == "2R":
                e = df["Open"].iat[entry_i]
                tgt = e + 2 * (e - stop)
            last_i = int(np.searchsorted(idx, d + pd.Timedelta(hours=16))) - 1
            res = simulate(df, entry_i, side, stop, tgt, last_i, cost)
            if res is not None:
                entry, exit_px, reason, exit_i, r = res
                trades.append(Trade(symbol, f"AMD-only-5m ({target_mode})",
                                    str(idx[i]), str(idx[entry_i]), str(idx[exit_i]),
                                    side, entry, stop, tgt, exit_px, reason, r))
            break
    return trades


# ---------------------------------------------------------------- stats
def stats(trades: list[Trade]) -> dict:
    if not trades:
        return {"trades": 0}
    r = np.array([t.r for t in trades])
    eq = np.cumsum(r)
    dd = (np.maximum.accumulate(np.concatenate([[0], eq]))[1:] - eq).max()
    streak = cur = 0
    for x in r:
        cur = cur + 1 if x < 0 else 0
        streak = max(streak, cur)
    wins, losses = r[r > 0].sum(), -r[r < 0].sum()
    se = r.std(ddof=1) / np.sqrt(len(r)) if len(r) > 1 else np.nan
    return {
        "trades": len(r),
        "win_rate": round(float((r > 0).mean()), 3),
        "avg_R": round(float(r.mean()), 3),
        "avg_R_95ci": f"[{r.mean() - 1.96 * se:.2f}, {r.mean() + 1.96 * se:.2f}]",
        "total_R": round(float(r.sum()), 1),
        "profit_factor": round(float(wins / losses), 2) if losses else np.inf,
        "max_dd_R": round(float(dd), 1),
        "max_loss_streak": streak,
    }


def prop_mc(trades: list[Trade], risk=250.0, target=3000.0, max_dd=2500.0,
            n=10000, max_trades=500, seed=1) -> float | None:
    """Bootstrap pass rate for a generic $50k eval: +$3,000 target,
    $2,500 trailing drawdown (on closed balance), $250 risk per trade (1R).
    Ignores daily loss limits, consistency rules and contract rounding."""
    if len(trades) < 10:
        return None
    rng = np.random.default_rng(seed)
    r = np.array([t.r for t in trades]) * risk
    passed = 0
    for _ in range(n):
        bal = peak = 0.0
        for x in rng.choice(r, size=max_trades):
            bal += x
            peak = max(peak, bal)
            if bal >= target:
                passed += 1
                break
            if peak - bal >= max_dd:
                break
    return round(passed / n, 3)


# ---------------------------------------------------------------- dukascopy run
COST_POINTS.update({"USA500IDXUSD": 0.5, "USATECHIDXUSD": 1.0})
DUKA_SYMBOLS = ["USA500IDXUSD", "USATECHIDXUSD"]


def load_duka(sym: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(os.path.join(DATA_DIR, f"{sym}_1m.csv.gz"), index_col=0)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert(NY)
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    m5 = df.resample("5min", label="left", closed="left").agg(agg).dropna()
    h1 = df.resample("1h", label="left", closed="left").agg(agg).dropna()
    return m5, h1


def report(groups: dict, symbols: list[str], tag: str):
    rows, all_trades = [], []
    for name in sorted(groups):
        tr = groups[name]
        for t in tr:                 # label each trade with its test variant
            t.strategy = name
        all_trades.extend(tr)
        for sym in symbols + ["ALL"]:
            sub = tr if sym == "ALL" else [t for t in tr if t.symbol == sym]
            row = {"test": name, "symbol": sym, **stats(sub)}
            if sym == "ALL":
                row["prop_pass_rate_mc"] = prop_mc(sub)
            rows.append(row)
    table = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 20)
    print(table.to_string(index=False))
    table.to_csv(os.path.join(RESULTS_DIR, f"summary{tag}.csv"), index=False)
    trades = pd.DataFrame([asdict(t) for t in all_trades])
    trades.to_csv(os.path.join(RESULTS_DIR, f"trades{tag}.csv"), index=False)
    # per-year stability (avg R per year, both symbols combined)
    trades["year"] = trades["entry_time"].str[:4]
    yearly = trades.pivot_table(index="strategy", columns="year", values="r",
                                aggfunc="mean").round(3)
    print("\nAverage R by year:\n", yearly.to_string())
    yearly.to_csv(os.path.join(RESULTS_DIR, f"yearly{tag}.csv"))


def main_duka():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    groups: dict[str, list[Trade]] = {}
    for sym in DUKA_SYMBOLS:
        m5, h1 = load_duka(sym)
        print(f"{sym}: {m5.index[0]} -> {m5.index[-1]}")
        for tm in ("range", "2R"):
            groups.setdefault(f"1. CRT-4H ({tm})", []).extend(crt(sym, h1, tm))
            groups.setdefault(f"2. AMD only ({tm})", []).extend(amd_only(sym, m5, tm))
            groups.setdefault(f"3. AMD+Time+IFVG ({tm})", []).extend(amd_ifvg(sym, m5, tm))
            # Alpaca's overnight session opens 20:00 ET -> Asian range 20:00-00:00
            groups.setdefault(f"2b. AMD only, Asia from 8PM ({tm})", []).extend(
                amd_only(sym, m5, tm, asia_hours=4))
            groups.setdefault(f"3b. AMD+Time+IFVG, Asia from 8PM ({tm})", []).extend(
                amd_ifvg(sym, m5, tm, asia_hours=4))
    report(groups, DUKA_SYMBOLS, "_dukascopy")


# ---------------------------------------------------------------- main
def main():
    if "--source" in sys.argv and sys.argv[sys.argv.index("--source") + 1] == "dukascopy":
        return main_duka()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    groups: dict[str, list[Trade]] = {}
    for sym in SYMBOLS:
        h1 = load(sym, "1h", "730d")
        m5 = load(sym, "5m", "60d")
        m5_start = m5.index[0] + pd.Timedelta(days=1)
        for tm in ("range", "2R"):
            groups.setdefault(f"A. CRT-4H ({tm}) | 1h data, full history", []) \
                .extend(crt(sym, h1, tm))
            groups.setdefault(f"B. CRT-4H ({tm}) | same 60-day window as AMD", []) \
                .extend(crt(sym, h1, tm, start=m5_start))
            groups.setdefault(f"C. AMD+Time+IFVG ({tm}) | 5m data, 60 days", []) \
                .extend(amd_ifvg(sym, m5, tm))
        print(f"{sym}: 1h {h1.index[0]} -> {h1.index[-1]} ({len(h1)} bars); "
              f"5m {m5.index[0]} -> {m5.index[-1]} ({len(m5)} bars)")

    rows, all_trades = [], []
    for name in sorted(groups):
        tr = groups[name]
        all_trades.extend(tr)
        for sym in SYMBOLS + ["ALL"]:
            sub = tr if sym == "ALL" else [t for t in tr if t.symbol == sym]
            row = {"test": name, "symbol": sym, **stats(sub)}
            if sym == "ALL":
                row["prop_pass_rate_mc"] = prop_mc(sub)
            rows.append(row)
    table = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 20)
    print(table.to_string(index=False))
    table.to_csv(os.path.join(RESULTS_DIR, "summary.csv"), index=False)
    pd.DataFrame([asdict(t) for t in all_trades]).to_csv(
        os.path.join(RESULTS_DIR, "trades.csv"), index=False)


if __name__ == "__main__":
    sys.exit(main())
