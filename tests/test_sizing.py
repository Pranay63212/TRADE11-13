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


def test_capped_by_buying_power():
    class Low(B):
        def buying_power(self): return 50883.24
    b = Low()
    e = Engine(b, Config(symbols=["QQQ"], log_dir=tempfile.mkdtemp(), risk_pct=10,
                         max_position_value=100000), log=lambda *_: None)
    e.last_bar_ts["QQQ"] = pd.Timestamp("2026-11-24 03:00", tz="America/New_York")
    sig = Signal(e.last_bar_ts["QQQ"], 1, 658.0, 670.0, e.last_bar_ts["QQQ"].normalize())
    e._enter("QQQ", sig, 660.0)
    assert b.orders[0] * 660.0 <= 50883.24 * 0.9          # 69 shares, ~$45.5k


def test_rejected_order_is_reported_not_crashed():
    class Rej(B):
        def buy_sell(self, s, q, side, p): return Fill(False, 0, 0.0, "insufficient buying power")
    e = Engine(Rej(), Config(symbols=["QQQ"], log_dir=tempfile.mkdtemp()), log=lambda *_: None)
    e.last_bar_ts["QQQ"] = pd.Timestamp("2026-11-24 03:00", tz="America/New_York")
    e._enter("QQQ", Signal(e.last_bar_ts["QQQ"], 1, 658.0, 670.0,
                           e.last_bar_ts["QQQ"].normalize()), 660.0)
    assert "QQQ" not in e.pos


def test_half_r_target():
    b = B()
    e = Engine(b, Config(symbols=["QQQ"], log_dir=tempfile.mkdtemp(), target_mode="0.5R"),
               log=lambda *_: None)
    e.last_bar_ts["QQQ"] = pd.Timestamp("2026-11-24 03:00", tz="America/New_York")
    e._enter("QQQ", Signal(e.last_bar_ts["QQQ"], 1, 658.0, 670.0,
                           e.last_bar_ts["QQQ"].normalize()), 660.0)
    assert e.pos["QQQ"].target == 661.0                    # entry + 0.5 * $2 risk
