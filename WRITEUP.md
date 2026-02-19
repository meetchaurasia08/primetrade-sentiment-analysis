# Primetrade.ai — Analysis Write-Up

## Methodology

**Datasets**: Hyperliquid historical trades (55,000 rows, 120 accounts, 2023–2024) aligned with the Bitcoin Fear/Greed Index (daily). Both are joined on date; every trade inherits the sentiment label of its day.

**Key metrics created**: daily PnL per trader, win rate (% trades closing positive), average trade size, leverage distribution, trade count per day, long/short ratio, and a drawdown proxy (min of cumulative PnL minus its rolling maximum per account).

**Segmentation**: Three rule-based segments (leverage buckets ≤5x / 5–10x / >10x; trade frequency <200 / 200–500 / >500; performance by win rate + total PnL) plus KMeans clustering (k=4, StandardScaler, silhouette-validated) yielding four archetypes: Consistent Winner, High-Risk Active, Moderate Trader, Passive/Occasional.

**Predictive model**: Random Forest Classifier predicting next-day profitability bucket (Loss / Small Gain / Large Gain) using six lag-1 features (prior-day win rate, leverage, trade count, L/S ratio, position size, sentiment encoding). No same-day features used — validated with 5-fold stratified cross-validation (accuracy ~52%, F1-macro ~33%).

---

## Insights

**Insight 1 — Sentiment materially shifts win rates and PnL.**
Win rate on Greed days is ~54% vs ~46% on Fear days — an 8-percentage-point gap that compounds across large position sizes. Median daily PnL flips from negative on Fear days to strongly positive on Greed days. This pattern is consistent across all leverage segments, confirming that sentiment is a genuine environmental factor, not just noise.

**Insight 2 — High leverage destroys returns regardless of sentiment.**
Traders averaging >10x leverage are net-negative in both Fear and Greed environments. Low-leverage traders (≤5x) are the only segment with consistently positive average PnL. The performance gap widens on Fear days, where high-leverage traders face compounding losses as adverse moves hit harder. Leverage is the single strongest modifiable driver of underperformance.

**Insight 3 — Position sizes expand ~2× on Greed days, amplifying tail risk.**
Median average position size nearly doubles when sentiment is Greed. Combined with the leverage increase that occurs simultaneously (avg_leverage rises from ~7.6x to ~10.8x on Greed days), this creates a regime where winners win large and losers lose large. The 30-day rolling leverage chart shows leverage drifting upward during sustained Greed periods — a risk that builds invisibly and reverses sharply when sentiment turns.

---

## Strategy Recommendations

**Rule 1 — Fear Regime: Hard Leverage Cap + Size Reduction**

*When FG index < 50 (Fear):* Cap leverage at 5x for all accounts. Reduce target position size by 40% relative to baseline. This applies most critically to the High-Risk Active archetype and the >10x leverage segment — the two groups with the worst Fear-day outcomes. Consistent Winners (≥55% win rate, net-positive PnL) may retain up to 7x as they demonstrate resilience. Expected outcome: reduced drawdown, fewer forced exits, capital preservation through adverse periods.

**Rule 2 — Greed Regime: Selective Frequency Expansion**

*When FG index ≥ 50 (Greed):* Consistent Winners may increase trade frequency by up to 30% to capture the elevated win-rate environment. Underperformers and High-Risk Active traders must reduce frequency by 25% — their Greed-day losses are larger in absolute terms (bigger sizing × lower win rate = amplified losses). Accounts with a trailing 30-day win rate below 45% are excluded from any frequency increase, regardless of market sentiment. Expected outcome: asymmetric return capture — winners compound gains; underperformers reduce loss magnitude. Net portfolio PnL improves via a selection effect.
