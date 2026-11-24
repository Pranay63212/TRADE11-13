"""
Broker adapters. The trading loop only talks to the `Broker` interface, so a
Tradovate (Lucid) adapter can be added later without touching strategy code.

  DryRunBroker - no orders; simulates fills at the requested price. For testing.
  AlpacaBroker - Alpaca Trading API (paper by default) + Alpaca market data.

Alpaca notes (from Alpaca docs, verify before live use):
  * 24/5 trading: overnight session 20:00-04:00 ET accepts LIMIT orders only,
    with extended_hours=True and time_in_force DAY or GTC.
  * Free data: IEX feed for 04:00-20:00; overnight (20:00-04:00) latest bars use
    feed="overnight".
  * Every order here is a marketable LIMIT order so the same code works in all
    sessions. Stops/targets are managed by the bot, NOT resting at the broker,
    so if the bot stops running, the position has no protective stop.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import pandas as pd

NY = "America/New_York"


@dataclass
class Fill:
    ok: bool
    qty: int
    price: float
    info: str = ""


class Broker:
    def latest_minute_bar(self, symbol: str):  # -> (ts, o, h, l, c) or None
        raise NotImplementedError

    def equity(self) -> float:
        raise NotImplementedError

    def position_qty(self, symbol: str) -> int:
        raise NotImplementedError

    def buying_power(self) -> float:
        """Money available for a new position right now (default: unlimited)."""
        return float("inf")

    def buy_sell(self, symbol: str, qty: int, side: int, ref_price: float) -> Fill:
        raise NotImplementedError


def session_of(ts: pd.Timestamp) -> str:
    h = ts.tz_convert(NY).hour
    if h >= 20 or h < 4:
        return "overnight"
    if (h, ts.minute) >= (9, 30) and h < 16:
        return "regular"
    return "extended"


class AlpacaBroker(Broker):
    def __init__(self, key: str, secret: str, paper: bool = True,
                 slippage_pct: float = 0.002, fill_timeout_s: int = 60):
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.trading.client import TradingClient
        self.trading = TradingClient(key, secret, paper=paper)
        self.data = StockHistoricalDataClient(key, secret)
        self.slippage_pct = slippage_pct
        self.fill_timeout_s = fill_timeout_s

    def latest_minute_bar(self, symbol):
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockLatestBarRequest
        now = pd.Timestamp.now(tz=NY)
        feed = DataFeed.OVERNIGHT if session_of(now) == "overnight" else DataFeed.IEX
        bar = self.data.get_stock_latest_bar(
            StockLatestBarRequest(symbol_or_symbols=symbol, feed=feed))[symbol]
        ts = pd.Timestamp(bar.timestamp).tz_convert(NY)
        return ts, float(bar.open), float(bar.high), float(bar.low), float(bar.close)

    def equity(self):
        return float(self.trading.get_account().equity)

    def buying_power(self):
        # Outside regular hours Alpaca only allows ~2x (Reg-T) buying power, not the 4x
        # day-trading figure, so use the smaller of the two to avoid rejected orders.
        a = self.trading.get_account()
        vals = [float(v) for v in (a.buying_power, a.regt_buying_power) if v is not None]
        return min(vals) if vals else float("inf")

    def position_qty(self, symbol):
        try:
            return int(float(self.trading.get_open_position(symbol).qty))
        except Exception:
            return 0

    def buy_sell(self, symbol, qty, side, ref_price):
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest
        limit = round(ref_price * (1 + side * self.slippage_pct), 2)
        try:
            order = self.trading.submit_order(LimitOrderRequest(
                symbol=symbol, qty=qty, side=OrderSide.BUY if side > 0 else OrderSide.SELL,
                time_in_force=TimeInForce.DAY, limit_price=limit, extended_hours=True))
        except Exception as e:                      # e.g. insufficient buying power
            msg = str(e)
            if "message" in msg:
                import json
                try:
                    msg = json.loads(msg).get("message", msg)
                except Exception:
                    pass
            return Fill(False, 0, 0.0, f"Alpaca rejected the order: {msg}")
        deadline = time.time() + self.fill_timeout_s
        while time.time() < deadline:
            o = self.trading.get_order_by_id(order.id)
            if o.status.value == "filled":
                return Fill(True, int(float(o.filled_qty)), float(o.filled_avg_price))
            if o.status.value in ("canceled", "expired", "rejected"):
                return Fill(False, 0, 0.0, f"order {o.status.value}")
            time.sleep(2)
        self.trading.cancel_order_by_id(order.id)
        o = self.trading.get_order_by_id(order.id)
        filled = int(float(o.filled_qty or 0))
        if filled:
            return Fill(True, filled, float(o.filled_avg_price), "partial fill")
        return Fill(False, 0, 0.0, "not filled in time, canceled")


class DryRunBroker(Broker):
    """Paper-of-paper: uses a real data source but never sends orders."""

    def __init__(self, data_broker: Broker | None = None, equity: float = 25000.0):
        self.data_broker = data_broker
        self._equity = equity
        self.pos: dict[str, int] = {}

    def latest_minute_bar(self, symbol):
        return self.data_broker.latest_minute_bar(symbol) if self.data_broker else None

    def equity(self):
        return self._equity

    def position_qty(self, symbol):
        return self.pos.get(symbol, 0)

    def buy_sell(self, symbol, qty, side, ref_price):
        self.pos[symbol] = self.pos.get(symbol, 0) + side * qty
        return Fill(True, qty, ref_price, "dry-run")
