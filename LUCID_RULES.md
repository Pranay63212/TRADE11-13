# Lucid Trading 25K LucidPro: what you can and can't use
Source: Lucid's official help center, support.lucidtrading.com, read 2026-11-25. Rules can change, so re-check before buying.

## Allowed
| Item | Official rule | Article |
|---|---|---|
| Automated strategies / bots | "Automated trading systems and trade copiers are permitted" (you are responsible for errors) | /articles/11404728-other-trading-activities |
| News trading | Allowed on Pro (not on LucidDaily) | same |
| Scaling in | Allowed (martingale discouraged) | same |
| Platforms (CQG) | NinjaTrader, Tradovate, TradingView | /articles/11404614-lucid-trading-supported-platforms |
| Platforms (Rithmic) | Quantower, Tradesea, MotiveWave, Sierra Chart, Jigsaw, Bookmap, ATAS, R\|Trader Pro, MultiCharts | same |
| MNQ | Approved; commission $0.50 per side | /articles/11508978-approved-products-and-commissions |

## Not allowed
| Item | Official rule | Article |
|---|---|---|
| High-frequency trading | Warning, then profits removed and ban | /articles/11404736-prohibited-high-frequency-trading |
| Microscalping | Flagged if >50% of profit comes from trades held <= 5 seconds | /articles/11404742-prohibited-microscalping |
| Hedging | Prohibited | /articles/11404734-prohibited-hedging (title only, not read) |
| Exploiting sim fills or platform errors | Prohibited | /articles/11404732-trade-with-integrity |
| Holding past 4:45 PM ET | Auto-closed at 4:45 PM ET; holding past that does not fail the account | /articles/11404729-allowed-trading-times |
| Not trading for 30 days | The account is deleted if it has under $1 of net P&L in 30 calendar days | /articles/11404632-inactivity-policy |

## 25K LucidPro evaluation
- Profit target $1,250. Max Loss Limit $1,000, trailing on end-of-day balance. It locks at $25,100 once the balance exceeds $26,100.
- Daily loss limit: **none** on 25K. Your screenshot shows an optional $600 setting. DLLs are "soft": you stop for the day, but the account doesn't fail.
- **No consistency rule in the evaluation.** You can pass in 1 day, and there's no time limit.
- One-time fee, no monthly billing, no activation fee. A reset has to be bought.

## 25K LucidPro funded account
- Same $1,000 MLL, which locks at $25,100.
- **40% consistency:** your largest day must be no more than 40% of profit before you can request a payout. If it's over, "you would need to continue trading". It does **not** fail the account.
- To get paid you need all of: at least $250 profit, a balance above the $26,100 buffer, and a **minimum request of $500**. So the first payout is possible at a balance of **$26,600 or more**. The first payout is capped at $1,000. Lucid's split is 90% to you, 10% to them.

## Can't verify / ask Lucid
- Whether Lucid provides a **free NinjaTrader license that allows automated NinjaScript strategies**. The help center doesn't say.
- Whether TradingView-connected accounts can auto-execute Pine strategies without a webhook service. [Unverified] TradingView itself does not auto-trade strategies.

## Things that can't be used
- **Tradovate API (our own Python bot to Tradovate):** Tradovate says prop and evaluation accounts can't get API access. https://support.tradovate.com/s/article/Tradovate-API-Access
