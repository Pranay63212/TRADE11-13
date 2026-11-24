"""Position sizing: fixed $ risk, % of equity risk, and % of equity position cap."""
import os, sys, tempfile
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bot.broker import Broker, Fill          # noqa: E402
from bot.engine import Config, Engine        # noqa: E402
from bot.strategy import Signal              # noqa: E402


class B(Broker):
    def __init__(self): self.orders = []
    def equity(self): return 25000.0
    def buy_sell(self, s, q, side, p): self.orders.append(q); return Fill(True, q, p)


def qty(**cfg):
    b = B()
    e = Engine(b, Config(symbols=["QQQ"], log_dir=tempfile.mkdtemp(), **cfg), log=lambda *_: None)
    e.last_bar_ts["QQQ"] = pd.Timestamp("2026-11-24 03:00", tz="America/New_York")
    sig = Signal(e.last_bar_ts["QQQ"], 1, 658.0, 670.0, e.last_bar_ts["QQQ"].normalize())
    e._enter("QQQ", sig, 660.0)          # $2 risk per share
    return b.orders[0]


def test_fixed_dollar_risk():
    assert qty(risk_per_trade=50, max_position_value=1e9) == 25          # $50 / $2


def test_risk_pct_of_equity():
    assert qty(risk_pct=10, max_position_value=1e9) == 1250              # $2,500 / $2


def test_max_position_pct_caps_size():
    assert qty(risk_per_trade=50, max_position_pct=10) == 3              # $2,500 / $660
