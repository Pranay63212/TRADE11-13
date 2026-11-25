# NinjaTrader 8: AMD+IFVG 0.5R strategy

## Install
1. Download and install NinjaTrader 8 (free) from ninjatrader.com.
2. Copy `AmdIfvgHalfR.cs` into `Documents\NinjaTrader 8\bin\Custom\Strategies\`.
3. In NinjaTrader: Control Center -> New -> NinjaScript Editor. Press **F5** to compile.
   If an error appears at the bottom, send a screenshot.

## Test (free, no money)
- Control Center -> New -> Strategy Analyzer. Strategy `AmdIfvgHalfR`, instrument MNQ (front month),
  type Minute, value 5, the last 1-2 months -> Run. Compare with the TradingView results.
- The Output window (New -> NinjaScript Output) prints each bias and entry.

## Run on Lucid
1. Connect NinjaTrader with your Lucid CQG/Tradovate login.
2. Open an MNQ 5-minute chart. Strategies (right-click chart) -> add `AmdIfvgHalfR`.
3. Set Account = your Lucid evaluation account, risk 200 (use 150 once funded), then Enabled -> OK.
4. Keep the laptop on, plugged in, with sleep off, and NinjaTrader open overnight (setups at 2-5 AM ET).
