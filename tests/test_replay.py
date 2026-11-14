"""
Replays historical 5m bars through the live strategy and checks it produces the
SAME signals (time, side, stop, target) as the backtest functions.

Run: python3 -m pytest -q tests/test_replay.py      (needs data/*_1m.csv.gz)
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import backtest as bt                                    # noqa: E402
from bot.strategy import AmdStrategy, Bar                # noqa: E402

SYMS = [s for s in bt.DUKA_SYMBOLS
        if os.path.exists(os.path.join(bt.DATA_DIR, f"{s}_1m.csv.gz"))]


def live_signals(m5, use_ifvg, asia_hours):
    strat, out = AmdStrategy(use_ifvg=use_ifvg, asia_hours=asia_hours), []
    for ts, r in m5.iterrows():
        s = strat.on_bar(Bar(ts, r.Open, r.High, r.Low, r.Close))
        if s:
            out.append((str(s.signal_time), s.side, round(s.stop, 4), round(s.target, 4)))
    return out


@pytest.mark.skipif(not SYMS, reason="no Dukascopy data downloaded")
@pytest.mark.parametrize("sym", SYMS)
@pytest.mark.parametrize("use_ifvg", [True, False])
@pytest.mark.parametrize("asia_hours", [4, 5])
def test_live_matches_backtest(sym, use_ifvg, asia_hours):
    m5, _ = bt.load_duka(sym)
    fn = bt.amd_ifvg if use_ifvg else bt.amd_only
    trades = fn(sym, m5, "range", asia_hours=asia_hours)
    expected = {(t.signal_time, t.side, round(t.stop, 4), round(t.target, 4)) for t in trades}
    got = set(live_signals(m5, use_ifvg, asia_hours))
    # Backtest also drops signals whose next-bar entry is invalid; live does that at
    # entry time. So every backtest trade must be a live signal:
    missing = expected - got
    assert not missing, f"{len(missing)} backtest trades not produced live, e.g. {sorted(missing)[:3]}"
    assert len(got) >= len(expected)
