"""
Live (bar-by-bar) version of the AMD strategies in backtest.py.

Feed it COMPLETED 5-minute bars in time order via on_bar(). It returns a Signal
when a setup triggers. The logic mirrors backtest.amd_ifvg / backtest.amd_only
exactly; tests/test_replay.py checks that both produce identical signals.

  Accumulation : Asian range = bars from (00:00 - asia_hours) to 00:00 NY.
  Manipulation : first sweep of the Asian high/low between 00:00 and 11:00 NY.
  Entry        : use_ifvg=True  -> close through the latest opposing FVG,
                                   only inside killzones (02:00-05:00, 08:30-11:00)
                 use_ifvg=False -> close back inside the Asian range (AMD only)
  Stop         : manipulation extreme.  Target: opposite Asian extreme or 2R.
  One signal per day at most.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Bar:
    ts: pd.Timestamp          # bar START time, tz-aware America/New_York
    open: float
    high: float
    low: float
    close: float


@dataclass
class Signal:
    signal_time: pd.Timestamp
    side: int                 # +1 long, -1 short
    stop: float
    target: float             # target for "range" mode; 2R is computed at entry
    day: pd.Timestamp


def in_killzone(ts: pd.Timestamp) -> bool:
    m = ts.hour * 60 + ts.minute
    return (2 * 60 <= m < 5 * 60) or (8 * 60 + 30 <= m < 11 * 60)


@dataclass
class _Day:
    asia: list = field(default_factory=list)       # (high, low)
    sess: list = field(default_factory=list)       # Bars since 00:00
    bias: int = 0
    run_lo: float = float("inf")
    run_hi: float = float("-inf")
    bear_fvg_top: float | None = None
    bull_fvg_bot: float | None = None
    done: bool = False


class AmdStrategy:
    def __init__(self, use_ifvg: bool = True, asia_hours: int = 4):
        self.use_ifvg = use_ifvg
        self.asia_hours = asia_hours
        self.days: dict[pd.Timestamp, _Day] = {}

    def _day(self, d: pd.Timestamp) -> _Day:
        if d not in self.days:
            self.days[d] = _Day()
            for k in [k for k in self.days if k < d - pd.Timedelta(days=3)]:
                del self.days[k]                       # keep memory bounded
        return self.days[d]

    def mark_done(self, day: pd.Timestamp):
        """Call when the trade for `day` was taken or rejected (no more signals)."""
        self._day(day).done = True

    def on_bar(self, b: Bar) -> Signal | None:
        midnight = b.ts.normalize()
        # Asian-range bar for the NEXT calendar day?
        nxt = midnight + pd.Timedelta(days=1)
        if b.ts >= nxt - pd.Timedelta(hours=self.asia_hours):
            self._day(nxt).asia.append((b.high, b.low))
            return None
        # Session bar (00:00-11:00) for today?
        if b.ts >= midnight + pd.Timedelta(hours=11):
            return None
        st = self._day(midnight)
        if st.done or len(st.asia) < 6 * self.asia_hours:
            st.sess.append(b)
            return None
        a_hi = max(h for h, _ in st.asia)
        a_lo = min(l for _, l in st.asia)
        st.sess.append(b)
        st.run_lo, st.run_hi = min(st.run_lo, b.low), max(st.run_hi, b.high)
        if self.use_ifvg and len(st.sess) >= 3:
            c1 = st.sess[-3]
            if b.high < c1.low:
                st.bear_fvg_top = c1.low
            if b.low > c1.high:
                st.bull_fvg_bot = c1.high
        if st.bias == 0:
            if b.low < a_lo:
                st.bias = 1
            elif b.high > a_hi:
                st.bias = -1
            return None
        side = 0
        if self.use_ifvg:
            if not in_killzone(b.ts):
                return None
            if st.bias == 1 and st.bear_fvg_top is not None and b.close > st.bear_fvg_top:
                side, stop, tgt = 1, st.run_lo, a_hi
            elif st.bias == -1 and st.bull_fvg_bot is not None and b.close < st.bull_fvg_bot:
                side, stop, tgt = -1, st.run_hi, a_lo
        else:
            if a_lo < b.close < a_hi:
                side = st.bias
                stop = st.run_lo if side == 1 else st.run_hi
                tgt = a_hi if side == 1 else a_lo
        if not side:
            return None
        st.done = True
        return Signal(b.ts, side, stop, tgt, midnight)
