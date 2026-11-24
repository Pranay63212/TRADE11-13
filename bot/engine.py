"""
Trading loop: builds 5-minute bars from 1-minute bars, runs the strategy,
sizes and places trades, manages stop / target / time exit, enforces risk limits.

Risk controls (all in config):
  * risk_per_trade   : $ lost if the stop is hit (position size = risk / stop distance)
  * max_daily_loss   : stop trading for the day after this realized loss
  * max_position_value: cap on position $ size
  * one trade per symbol per day (strategy rule)
  * kill switch: create a file named STOP in the working directory -> the bot
    flattens positions and exits.
"""
from __future__ import annotations

import csv
import os
import time
from dataclasses import dataclass, field

import pandas as pd

from .broker import NY, Broker
from .strategy import AmdStrategy, Bar, Signal


@dataclass
class Config:
    symbols: list = field(default_factory=lambda: ["QQQ"])
    use_ifvg: bool = True
    asia_hours: int = 4                 # 20:00-00:00 ET (Alpaca overnight opens 20:00)
    target_mode: str = "range"          # "range" or "2R"
    risk_per_trade: float = 50.0
    max_daily_loss: float = 150.0
    max_position_value: float = 20000.0
    risk_pct: float | None = None            # if set: risk = this % of account equity per trade
    max_position_pct: float | None = None    # if set: position value capped at this % of equity
    poll_seconds: int = 20
    exit_time: str = "15:58"            # flatten before 16:00 ET (backtest exits at 16:00)
    log_dir: str = "logs"


@dataclass
class Position:
    symbol: str
    side: int
    qty: int
    entry: float
    stop: float
    target: float
    entry_time: pd.Timestamp
    entry_bar_ts: pd.Timestamp      # only bars AFTER this one can trigger stop/target


class Engine:
    def __init__(self, broker: Broker, cfg: Config, log=print, notify=None):
        self.b, self.cfg, self.log = broker, cfg, log
        self.notify = notify or (lambda *a, **k: None)
        self.strats = {s: AmdStrategy(cfg.use_ifvg, cfg.asia_hours) for s in cfg.symbols}
        self.minutes: dict[str, dict] = {s: {} for s in cfg.symbols}   # ts -> (o,h,l,c)
        self.last_5m: dict[str, pd.Timestamp] = {}
        self.pos: dict[str, Position] = {}
        self.realized: dict[pd.Timestamp, float] = {}
        os.makedirs(cfg.log_dir, exist_ok=True)
        self.trade_log = os.path.join(cfg.log_dir, "trades.csv")
        self.now = pd.Timestamp.now(tz=NY)
        self.last_bar_ts: dict[str, pd.Timestamp] = {}

    # ------------------------------------------------------------ helpers
    def _today(self, ts=None):
        return (ts or self.now).normalize()

    def _record(self, row: dict):
        new = not os.path.exists(self.trade_log)
        with open(self.trade_log, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(row))
            if new:
                w.writeheader()
            w.writerow(row)

    def _daily_loss_hit(self) -> bool:
        return self.realized.get(self._today(), 0.0) <= -abs(self.cfg.max_daily_loss)

    # ------------------------------------------------------------ bars
    def _completed_5m_bars(self, sym: str, now: pd.Timestamp) -> list[Bar]:
        """Aggregate stored 1m bars into 5m bars whose window has fully closed."""
        mins = self.minutes[sym]
        if not mins:
            return []
        last = self.last_5m.get(sym)
        ready = now - pd.Timedelta(seconds=30)
        buckets: dict = {}
        for ts in sorted(mins):                            # only minutes not yet processed
            start = ts.floor("5min")
            if last is not None and start <= last:
                continue
            if start + pd.Timedelta(minutes=5) > ready:
                break                                      # still forming
            buckets.setdefault(start, []).append(mins[ts])
        out = [Bar(s, v[0][0], max(x[1] for x in v), min(x[2] for x in v), v[-1][3])
               for s, v in buckets.items()]
        if out:
            self.last_5m[sym] = out[-1].ts
            for k in [k for k in mins if k.floor("5min") <= out[-1].ts]:
                del mins[k]                                # processed: free memory
        return out

    # ------------------------------------------------------------ trading
    def _enter(self, sym: str, sig: Signal, price: float):
        strat = self.strats[sym]
        target = sig.target
        if self.cfg.target_mode == "2R":
            target = price + 2 * (price - sig.stop)
        risk_ps = (price - sig.stop) * sig.side
        if risk_ps <= 0 or (target - price) * sig.side <= 0:
            self.log(f"{sym} signal rejected: price {price} already past stop/target")
            self.notify(f"{sym}: setup skipped", f"Price {price:.2f} already past stop/target. "
                        "No trade today.", tags="no_entry")
            strat.mark_done(sig.day)
            return
        if self._daily_loss_hit():
            self.log(f"{sym} signal skipped: daily loss limit reached")
            self.notify(f"{sym} skipped", "Daily loss limit reached - no more trades today", tags="no_entry")
            return
        risk_dollars, max_value = self.cfg.risk_per_trade, self.cfg.max_position_value
        if self.cfg.risk_pct or self.cfg.max_position_pct:
            eq = self.b.equity()
            if self.cfg.risk_pct:
                risk_dollars = eq * self.cfg.risk_pct / 100
            if self.cfg.max_position_pct:
                max_value = eq * self.cfg.max_position_pct / 100
        try:
            bp = self.b.buying_power() * 0.90       # keep 10% headroom for price/limit slippage
        except Exception:
            bp = float("inf")
        wanted = min(risk_dollars / risk_ps, max_value / price)
        qty = int(min(wanted, bp / price))
        if qty < int(wanted):
            self.log(f"{sym} size cut from {int(wanted)} to {qty} shares to fit buying power")
            self.notify(f"{sym}: size reduced", f"{int(wanted)} -> {qty} shares to fit available "
                        "buying power.", tags="warning")
        if qty < 1:
            self.log(f"{sym} signal skipped: stop too wide for risk_per_trade")
            self.notify(f"{sym}: setup skipped", "Stop too far away for your $ risk per trade.",
                        tags="no_entry")
            return
        fill = self.b.buy_sell(sym, qty, sig.side, price)
        if not fill.ok:
            self.log(f"{sym} entry failed: {fill.info}")
            self.notify(f"{sym} entry failed", fill.info, tags="warning")
            return
        self.pos[sym] = Position(sym, sig.side, fill.qty, fill.price, sig.stop, target,
                                 self.now, self.last_bar_ts[sym])
        self.log(f"{sym} ENTER {'LONG' if sig.side > 0 else 'SHORT'} {fill.qty} @ {fill.price:.2f} "
                 f"stop {sig.stop:.2f} target {target:.2f} (risk ${risk_ps * fill.qty:.0f})")
        self.notify(f"{sym} {'LONG' if sig.side > 0 else 'SHORT'} entered",
                    f"{fill.qty} @ {fill.price:.2f}\nStop {sig.stop:.2f}  Target {target:.2f}\n"
                    f"Risk ${risk_ps * fill.qty:.0f}", priority="high",
                    tags="chart_with_upwards_trend" if sig.side > 0 else "chart_with_downwards_trend")

    def _exit(self, sym: str, price: float, reason: str):
        p = self.pos[sym]
        fill = self.b.buy_sell(sym, p.qty, -p.side, price)
        if not fill.ok:
            self.log(f"{sym} EXIT FAILED ({fill.info}) - will retry next poll. CHECK BROKER.")
            self.notify(f"{sym} EXIT FAILED", f"{fill.info}. Bot will retry - CHECK ALPACA NOW.",
                        priority="urgent", tags="rotating_light", throttle_key=f"exitfail{sym}",
                        throttle_s=120)
            return
        pnl = (fill.price - p.entry) * p.side * p.qty
        r = pnl / max(abs(p.entry - p.stop) * p.qty, 1e-9)
        day = self._today()
        self.realized[day] = self.realized.get(day, 0.0) + pnl
        self.log(f"{sym} EXIT {reason} {fill.qty} @ {fill.price:.2f}  P&L ${pnl:.2f} ({r:+.2f}R)")
        self.notify(f"{sym} closed: {reason}",
                    f"{fill.qty} @ {fill.price:.2f}\nP&L ${pnl:.2f} ({r:+.2f}R)\n"
                    f"Today: ${self.realized[day]:.2f}", tags="moneybag" if pnl > 0 else "x")
        self._record({"symbol": sym, "side": p.side, "qty": fill.qty, "entry_time": p.entry_time,
                      "entry": p.entry, "stop": p.stop, "target": p.target,
                      "exit_time": self.now, "exit": fill.price,
                      "reason": reason, "pnl": round(pnl, 2), "r": round(r, 3)})
        del self.pos[sym]

    def _manage(self, sym: str, now: pd.Timestamp, ts, h: float, l: float, c: float):
        p = self.pos.get(sym)
        if not p or ts <= p.entry_bar_ts:
            return
        hit_stop = l <= p.stop if p.side > 0 else h >= p.stop
        hit_tgt = h >= p.target if p.side > 0 else l <= p.target
        hh, mm = map(int, self.cfg.exit_time.split(":"))
        if hit_stop:
            self._exit(sym, c, "stop")
        elif hit_tgt:
            self._exit(sym, c, "target")
        elif (now.hour, now.minute) >= (hh, mm) and now.hour < 20:
            self._exit(sym, c, "time")

    def flatten_all(self, reason="kill switch"):
        for sym in list(self.pos):
            bar = self.b.latest_minute_bar(sym)
            if bar:
                self._exit(sym, bar[4], reason)

    # ------------------------------------------------------------ main loop
    def step(self, now: pd.Timestamp | None = None):
        now = self.now = now or pd.Timestamp.now(tz=NY)
        for sym in self.cfg.symbols:
            try:
                bar = self.b.latest_minute_bar(sym)
            except Exception as e:
                self.log(f"{sym} data error: {e}")
                self.notify(f"{sym} data error", str(e)[:200], tags="warning",
                            throttle_key=f"data{sym}")
                continue
            if not bar:
                continue
            ts, o, h, l, c = bar
            self.minutes[sym][ts] = (o, h, l, c)
            self.last_bar_ts[sym] = ts
            self._manage(sym, now, ts, h, l, c)
            for b5 in self._completed_5m_bars(sym, now):
                sig = self.strats[sym].on_bar(b5)
                self._report_events(sym)
                if sig and sym not in self.pos:
                    self.log(f"{sym} SIGNAL {sig}")
                    self.notify(f"{sym} SIGNAL - entering {'LONG' if sig.side > 0 else 'SHORT'}",
                                f"Trigger candle {sig.signal_time:%H:%M} ET. Placing order now.",
                                priority="high", tags="bell")
                    self._enter(sym, sig, c)
            self._heartbeat(now)

    # ------------------------------------------------------------ status messages
    def _report_events(self, sym: str):
        strat = self.strats[sym]
        while strat.events:
            ev = strat.events.pop(0)
            kind, day = ev[0], ev[1]
            if kind == "asia":
                t, m = f"{sym}: Asian range set", (f"High {ev[2]:.2f} / Low {ev[3]:.2f}\n"
                       "Now watching for the first line to break (until 11:00 AM ET).")
            elif kind == "asia_short":
                t, m = (f"{sym}: no trade {day:%a %b %d}",
                        f"Only {ev[2]} of {ev[3]} Asian-range candles recorded "
                        "(bot started late or PC slept). Next chance: tomorrow.")
            elif kind == "bias":
                side = "LONGS" if ev[2] > 0 else "SHORTS"
                line = "LOW" if ev[2] > 0 else "HIGH"
                t, m = (f"{sym}: Asian {line} broken - {side} only",
                        f"Broke at {ev[3]:%H:%M} ET. Waiting for an IFVG trigger in "
                        "2-5 AM or 8:30-11 AM ET.")
            elif kind == "gap":
                word = "ABOVE" if ev[2] > 0 else "BELOW"
                t, m = (f"{sym}: watching gap {ev[3]:.2f}",
                        f"A 5-min candle closing {word} {ev[3]:.2f} inside the time windows "
                        f"= {'LONG' if ev[2] > 0 else 'SHORT'} entry.")
            elif kind == "no_trade":
                t, m = f"{sym}: no trade today", "No valid setup by 11:00 AM ET."
            else:
                continue
            self.log(f"{t} | {m}".replace("\n", " "))
            self.notify(t, m, priority="low" if kind == "gap" else "default", tags="eyes")

    def _heartbeat(self, now: pd.Timestamp):
        """Hourly 'still running' log line, plus one phone alert each evening at 8 PM ET."""
        hour = now.floor("h")
        if getattr(self, "_last_hb", None) != hour:
            self._last_hb = hour
            self.log(f"still running - {now:%a %H:%M} ET, open positions: {list(self.pos) or 'none'}")
            if now.hour == 20:
                self.notify("Bot still running",
                            "Recording tonight's Asian range (8 PM - midnight ET).", tags="robot")

    def run(self):
        self.log(f"Bot started: {self.cfg}")
        self.notify("Bot started", f"Symbols: {', '.join(self.cfg.symbols)}", tags="robot")
        self.log("Warm-up: the strategy needs the Asian range (from "
                 f"{24 - self.cfg.asia_hours}:00 ET) before it can signal.")
        while True:
            if os.path.exists("STOP"):
                self.log("STOP file found - flattening and exiting.")
                self.notify("Bot stopping", "STOP file found - closing positions", tags="stop_sign")
                self.flatten_all()
                return
            try:
                self.step()
            except Exception as e:                          # keep running; alert the user
                self.log(f"ERROR in trading loop: {e!r}")
                self.notify("Bot error", f"{e!r}"[:300] + "\nBot is still running - check Alpaca.",
                            priority="high", tags="warning", throttle_key="loop", throttle_s=300)
            time.sleep(self.cfg.poll_seconds)
