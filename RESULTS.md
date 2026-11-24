# CRT vs AMD + Time + IFVG: backtest on free Yahoo data

Run: `pip install yfinance pandas numpy && python3 backtest.py`
(data is cached in `data/`; delete it to re-download). Trades are in `results/trades.csv` and the summary table is in `results/summary.csv`.

## Data (Yahoo Finance, NQ=F and ES=F continuous futures)
- 1h bars: 2024-06-24 to 2026-11-13 (about 2.4 years)
- 5m bars: 2026-09-04 to 2026-11-13 (60 days, Yahoo's limit for 5m)
- Caveats: Yahoo's continuous futures contain roll gaps, and the data is unaudited.

## Rules tested (my mechanical interpretation, not any educator's official rules)
**CRT (4H):** C1 = prior 4H candle, C2 = current one. If C2 trades beyond one side of C1 and closes back inside C1, enter at the next 1h open toward the other side.
Stop = C2's extreme. Target = C1's opposite side (or 2R). Exit after 2 more 4H candles if neither stop nor target is hit.

**AMD + Time + IFVG (5m):** The Asian range is 19:00 to 00:00 NY. The first sweep of the Asian high or low between 00:00 and 11:00 sets the bias.
Entry: a 5m close through the most recent opposing FVG (the IFVG), inside 02:00 to 05:00 or 08:30 to 11:00 NY, at the next bar open.
Stop = manipulation extreme. Target = the opposite side of the Asian range (or 2R). Exit at 16:00 NY. Max 1 trade per day.

**Both:** costs deducted (NQ 1.0 pt, ES 0.5 pt round trip). When the stop and target fall in the same bar, the stop is counted first.

## Results (NQ + ES combined)
| Test | Trades | Win % | Avg R | 95% CI avg R | Total R | PF | Max DD (R) | Prop pass* |
|---|---|---|---|---|---|---|---|---|
| CRT, opposite-side target, 2.4 yrs | 2085 | 48.2% | -0.04 | [-0.10, 0.02] | -81.6 | 0.92 | 102.6 | 22% |
| CRT, 2R target, 2.4 yrs | 2017 | 40.3% | -0.03 | [-0.08, 0.02] | -56.8 | 0.95 | 94.9 | 24% |
| CRT, opposite-side target, same 60 days | 171 | 48.0% | -0.11 | [-0.27, 0.04] | -19.4 | 0.77 | 26.4 | 6% |
| CRT, 2R target, same 60 days | 166 | 37.3% | -0.08 | [-0.26, 0.10] | -13.0 | 0.86 | 26.6 | 14% |
| AMD+Time+IFVG, Asian-range target, 60 days | 96 | 33.3% | +0.07 | [-0.29, 0.43] | +6.4 | 1.10 | 15.0 | 42% |
| AMD+Time+IFVG, 2R target, 60 days | 96 | 33.3% | -0.06 | [-0.34, 0.21] | -6.1 | 0.91 | 19.4 | 20% |

\*Bootstrap simulation of a generic $50k eval: +$3,000 target, $2,500 trailing drawdown, $250 risk per trade. It ignores daily loss limits, consistency rules and contract rounding.
**Baseline: a zero-edge strategy passes about 31% under these rules.**

## Reading it
- Every confidence interval includes 0. No version shows a statistically demonstrated edge.
- CRT has a large sample (2,000+ trades) and is slightly negative after costs. Under these rules, its eval pass rate is below the zero-edge baseline.
- AMD+Time+IFVG with the Asian-range target was slightly positive. But it has only 96 trades over 60 days, and its CI runs from -0.29R to +0.43R, which is too wide to conclude anything. The 2R version of the same entries was negative.
- These results apply only to these exact rules. Other definitions of CRT or IFVG could give different results.

## Bot strategy (AMD + Time + IFVG, Asia 20:00-00:00 ET, range target), run 2026-11-24
| Data | Symbol | Period | Trades | Win % | Avg R | 95% CI | Total R | Max DD (R) | Worst losing streak |
|---|---|---|---|---|---|---|---|---|---|
| Dukascopy CFD | Nasdaq 100 | 2025-01-01 to 2025-05-01 | 83 | 39.8% | +0.17 | [-0.20, 0.53] | +13.8 | 7.6 | 5 |
| Dukascopy CFD | S&P 500 | 2025-01-01 to 2025-03-02 | 41 | 31.7% | -0.26 | [-0.68, 0.16] | -10.8 | 11.5 | 5 |
| Yahoo futures | NQ | 2026-09-16 to 2026-11-24 | 49 | 32.7% | +0.06 | [-0.44, 0.57] | +3.0 | 9.3 | 10 |
| Yahoo futures | ES | 2026-09-16 to 2026-11-24 | 49 | 34.7% | +0.02 | [-0.44, 0.49] | +1.0 | 10.5 | 10 |
| **All** | | | **222** | **35.6%** | **+0.03** | **[-0.19, 0.25]** | **+7.1** | **18.1** | **11** |

Avg win +1.97R, avg loss -1.04R. Prop-eval bootstrap pass rate 38% (zero-edge baseline ~31%).
Sizing illustration on the combined trade list: 1% risk/trade $25,000 -> $26,044 (max DD 18%);
10% risk/trade $25,000 -> $3,543 (max DD 96%).
Conclusion: slightly positive but NOT statistically distinguishable from zero.
