"""
End-to-end test of the trading engine with a fake broker that replays historical
1-minute bars minute by minute (as the live bot would see them).
Checks the engine opens the same trades (day + side) as the backtest.
"""
import os
import shutil
import sys
import tempfile

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import backtest as bt                                    # noqa: E402
from bot.broker import Broker, Fill                      # noqa: E402
from bot.engine import Config, Engine                    # noqa: E402

SYM = "USATECHIDXUSD"
PATH = os.path.join(bt.DATA_DIR, f"{SYM}_1m.csv.gz")


class ReplayBroker(Broker):
    def __init__(self, m1):
        self.m1, self.i = m1, 0

    def latest_minute_bar(self, symbol):
        ts = self.m1.index[self.i]
        r = self.m1.iloc[self.i]
        return ts, r.Open, r.High, r.Low, r.Close

    def equity(self):
        return 25000.0

    def position_qty(self, symbol):
        return 0

    def buy_sell(self, symbol, qty, side, ref_price):
        return Fill(True, qty, ref_price)


@pytest.mark.skipif(not os.path.exists(PATH), reason="no data")
def test_engine_matches_backtest_entries():
    m1 = pd.read_csv(PATH, index_col=0)
    m1.index = pd.to_datetime(m1.index, utc=True).tz_convert(bt.NY)
    m5, _ = bt.load_duka(SYM)
    expected = {(t.signal_time[:10], t.side)
                for t in bt.amd_ifvg(SYM, m5, "range", asia_hours=4)}
    logdir = tempfile.mkdtemp()
    try:
        broker = ReplayBroker(m1)
        eng = Engine(broker, Config(symbols=[SYM], max_position_value=1e9, risk_per_trade=1000,
                                    max_daily_loss=1e9, log_dir=logdir), log=lambda *_: None)
        for i in range(len(m1)):
            broker.i = i
            eng.step(now=m1.index[i] + pd.Timedelta(seconds=65))
        trades = pd.read_csv(os.path.join(logdir, "trades.csv"))
    finally:
        shutil.rmtree(logdir)
    got = {(str(t)[:10], int(s)) for t, s in zip(trades.entry_time, trades.side)}
    # every engine trade must be a backtest trade, and nearly all backtest trades appear
    assert got <= expected, got - expected
    assert len(got) >= 0.9 * len(expected), (len(got), len(expected))
    assert set(trades.reason) <= {"stop", "target", "time"}
