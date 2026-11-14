"""
Command-line entry point.

  python -m bot check                 # test the Alpaca connection (no orders)
  python -m bot run                   # PAPER trading (default) - QQQ, AMD+Time+IFVG
  python -m bot run --dry-run         # live data, NO orders at all (logs only)
  python -m bot run --symbols QQQ SPY --amd-only --target 2R --risk 25
  python -m bot run --live            # REAL MONEY - asks for typed confirmation

API keys come from environment variables (never put them in code):
  APCA_API_KEY_ID, APCA_API_SECRET_KEY
"""
import argparse
import os
import sys
from datetime import datetime

from .broker import AlpacaBroker, DryRunBroker
from .engine import Config, Engine
from .notify import Ntfy


def make_logger(log_dir):
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, f"bot_{datetime.now():%Y%m%d}.log")

    def log(msg):
        line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
        print(line, flush=True)
        with open(path, "a") as f:
            f.write(line + "\n")
    return log


def main():
    ap = argparse.ArgumentParser(prog="python -m bot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="test Alpaca connection + ntfy, no orders")
    c.add_argument("--live", action="store_true")
    r = sub.add_parser("run", help="run the trading loop")
    r.add_argument("--symbols", nargs="+", default=["QQQ"])
    r.add_argument("--amd-only", action="store_true", help="AMD without killzones/IFVG")
    r.add_argument("--asia-hours", type=int, default=4, help="4 = 20:00-00:00 ET")
    r.add_argument("--target", choices=["range", "2R"], default="range")
    r.add_argument("--risk", type=float, default=50.0, help="$ risk per trade")
    r.add_argument("--max-daily-loss", type=float, default=150.0)
    r.add_argument("--max-position", type=float, default=20000.0)
    r.add_argument("--dry-run", action="store_true", help="no orders, log only")
    r.add_argument("--live", action="store_true", help="REAL MONEY account")
    ap.add_argument("--ntfy-topic", default=os.environ.get("NTFY_TOPIC"),
                    help="ntfy topic for phone alerts (or set NTFY_TOPIC)")
    a = ap.parse_args()

    key, secret = os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY")
    if not key or not secret:
        sys.exit("Set APCA_API_KEY_ID and APCA_API_SECRET_KEY first (see bot/README.md).")

    paper = not getattr(a, "live", False)
    if not paper:
        print("!!! LIVE MODE: this trades REAL MONEY. The strategy has NOT shown a proven edge.")
        if input("Type 'I ACCEPT THE RISK' to continue: ") != "I ACCEPT THE RISK":
            sys.exit("Aborted.")
    alpaca = AlpacaBroker(key, secret, paper=paper)

    if a.cmd == "check":
        acct = alpaca.trading.get_account()
        clock = alpaca.trading.get_clock()
        print(f"Connected ({'PAPER' if paper else 'LIVE'}). Equity ${float(acct.equity):,.2f}, "
              f"buying power ${float(acct.buying_power):,.2f}")
        print(f"Market open now: {clock.is_open}. Next open {clock.next_open}")
        if a.ntfy_topic:
            Ntfy(a.ntfy_topic)("Bot test", "ntfy is working - you will get trade alerts here.",
                               tags="white_check_mark")
            print(f"Sent a test notification to ntfy topic '{a.ntfy_topic}'. Check your phone.")
        else:
            print("No ntfy topic set (NTFY_TOPIC) - phone alerts are off.")
        for s in ("QQQ", "SPY"):
            try:
                print(s, "latest 1m bar:", alpaca.latest_minute_bar(s))
            except Exception as e:
                print(s, "data error:", e)
        return

    cfg = Config(symbols=a.symbols, use_ifvg=not a.amd_only, asia_hours=a.asia_hours,
                 target_mode=a.target, risk_per_trade=a.risk, max_daily_loss=a.max_daily_loss,
                 max_position_value=a.max_position)
    broker = DryRunBroker(alpaca) if a.dry_run else alpaca
    log = make_logger(cfg.log_dir)
    log(f"Mode: {'DRY-RUN (no orders)' if a.dry_run else ('PAPER' if paper else 'LIVE')}")
    try:
        Engine(broker, cfg, log, notify=Ntfy(a.ntfy_topic, log=log)).run()
    except KeyboardInterrupt:
        log("Stopped by user (Ctrl+C). Open positions are NOT closed automatically - "
            "check your Alpaca dashboard, or create a STOP file next time to flatten on exit.")
        Ntfy(a.ntfy_topic)("Bot stopped (Ctrl+C)", "Open positions were NOT closed - check Alpaca.",
                           priority="high", tags="warning")
    except Exception as e:
        log(f"CRASH: {e!r}")
        Ntfy(a.ntfy_topic)("BOT CRASHED", f"{e!r}"[:300] + "\nOpen positions have NO stop - check Alpaca.",
                           priority="urgent", tags="rotating_light")
        raise


if __name__ == "__main__":
    main()
