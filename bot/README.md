# AMD trading bot (Alpaca)

Command-window bot that trades the AMD strategies from `backtest.py` on Alpaca.
**Default is PAPER trading.** The strategy has NOT shown a proven edge yet; do
not use `--live` until the full backtest and several weeks of paper trading agree.

## What it does
- Polls Alpaca every 20 s for the latest 1-minute bar, builds 5-minute bars.
- Strategy (same code path verified against the backtest by `tests/`):
  - Asian range 20:00-00:00 ET (Alpaca's overnight session opens 20:00)
  - First sweep of the range high/low between 00:00 and 11:00 ET sets the bias
  - Entry: IFVG inside killzones 02:00-05:00 / 08:30-11:00 ET (default),
    or `--amd-only`: close back inside the range
  - Stop: sweep extreme. Target: other side of the range (or `--target 2R`)
  - Flat by 15:58 ET. One trade per symbol per day.
- Sizing: shares = risk per trade / stop distance, capped by `--max-position`.
- Stops are watched **by the bot** (overnight sessions only accept limit
  orders). **If the bot or your PC stops, open trades have no stop.**

## Setup (Windows)
1. Install Python 3.11+ from python.org (tick "Add Python to PATH").
2. Open Command Prompt in this folder and install packages:
   ```
   pip install -r requirements.txt
   ```
3. Create a free Alpaca account, switch to **Paper Trading**, generate API keys.
4. Set the keys (Command Prompt; reopen the window afterwards):
   ```
   setx APCA_API_KEY_ID "your-paper-key-id"
   setx APCA_API_SECRET_KEY "your-paper-secret"
   ```
   Never paste keys into code, chat, or GitHub.
5. Test the connection (sends no orders):
   ```
   python -m bot check
   ```

## Run
```
python -m bot run --dry-run          # live data, no orders, just logs signals
python -m bot run                    # paper trading, QQQ, $50 risk/trade
python -m bot run --symbols QQQ SPY --risk 25 --max-daily-loss 75
```
Start it **before 8 PM ET** so it records the whole Asian range; otherwise
that day is skipped. Leave the window open (and the PC awake) while it runs.

**Stop safely:** create a file called `STOP` in this folder (the bot closes
positions and exits). Ctrl+C stops the bot but leaves positions open.

Logs: `logs/bot_YYYYMMDD.log` and every closed trade in `logs/trades.csv`.

## Known limitations
- Free Alpaca data uses IEX (04:00-20:00) and the "overnight" feed (20:00-04:00);
  prices can differ slightly from the CFD data used in the backtest.
- Exits are marketable limit orders at the current price, so fills will be
  worse than the exact stop/target prices assumed in the backtest.
- Alpaca does not offer futures; the bot trades SPY/QQQ, not ES/NQ.
- A broker adapter for a futures prop firm (e.g. Tradovate for Lucid) is not
  written yet - `bot/broker.py` defines the interface it would implement.
