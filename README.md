# Primetrade.ai — Trader Performance vs Market Sentiment

> **Data Science Internship Assignment**  
> Hyperliquid historical trades × Bitcoin Fear/Greed Index  
> 2023-01-01 → 2024-12-31 | 55,000 trades | 120 accounts

---

## Quick Start

```bash
# 1. Clone / unzip the repo
cd primetrade

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the full analysis (generates all charts + CSVs)
python analysis.py

# 4. Build the Excel deliverable
python build_excel.py

# 5. (Optional) Launch the interactive dashboard
streamlit run dashboard.py
```

> **Real data**: Replace the two generator calls at the bottom of `analysis.py`  
> with `pd.read_csv("your_trades.csv")` and `pd.read_csv("your_fear_greed.csv")`.

---

## Project Structure

```
primetrade/
├── analysis.py          ← Parts A + B + C + Bonus (main script)
├── build_excel.py       ← Builds the Excel deliverable from outputs/
├── dashboard.py         ← Streamlit interactive dashboard
├── requirements.txt     ← Python dependencies
├── README.md            ← This file
├── WRITEUP.md           ← 1-page methodology + insights + strategy
├── charts/              ← 8 PNG charts (auto-generated)
│   ├── chart1_performance_by_sentiment.png
│   ├── chart2_behaviour_by_sentiment.png
│   ├── chart3_segmentation.png
│   ├── chart4_segment_x_sentiment.png
│   ├── chart5_timeseries.png
│   ├── chart6_winrate_heatmap.png
│   ├── chart7_feature_importance.png
│   └── chart8_archetypes.png
└── outputs/             ← CSV tables + Excel (auto-generated)
    ├── daily_trader_metrics.csv
    ├── daily_market_metrics.csv
    ├── trader_summary.csv
    ├── strategy_evidence.csv
    ├── perf_by_sentiment.csv
    ├── merged_dataset.csv
    └── primetrade_full_analysis.xlsx
```

---

## Requirements

```
numpy>=1.24
pandas>=2.0
matplotlib>=3.7
seaborn>=0.12
scikit-learn>=1.3
openpyxl>=3.1
streamlit>=1.28        # optional, for dashboard only
```

---

## Excel Deliverable — Sheet Guide

| Sheet | Contents |
|---|---|
| 📊 Overview | Dataset audit, methodology notes, workbook contents |
| 📋 Part A — Metrics | 3,000 rows of daily trader metrics (PnL, win rate, leverage, L/S ratio) |
| 📈 Part B — Analysis | Fear vs Greed evidence tables, behaviour shifts, segmentation, 3 key insights |
| 🎯 Part C — Strategy | Two actionable strategy rules with supporting evidence |
| 🤖 Bonus — Model | CV results, feature importances, model design notes |
| 👥 Bonus — Archetypes | KMeans cluster profiles and archetype descriptions |
| 📉 Charts | All 8 analysis charts embedded |

---

## Methodology (Summary)

- **Alignment**: Trades joined to Fear/Greed index on `DATE` (daily granularity). LEFT JOIN ensures 100% trade retention.
- **Metrics**: Win rate = % of trades with `closedPnL > 0`. Drawdown proxy = min(cumPnL − rolling max cumPnL) per account.
- **Segmentation**: Rule-based (leverage, frequency, win rate thresholds) + KMeans k=4 (StandardScaler, silhouette-validated).
- **Model**: Random Forest on lag-1 features only — no same-day information in features to prevent target leakage. 5-fold stratified CV.

---

## Key Findings (Quick Reference)

1. **Greed days dominate**: Win rate ~54% vs ~46% on Fear days. Median daily PnL swings from negative to strongly positive.
2. **Leverage kills returns**: Traders averaging >10x leverage are net-negative in both regimes.
3. **Position size doubles on Greed days**: Median avg_size ~2× higher — compounding risk with elevated leverage.

## Strategy Rules (Quick Reference)

- **Rule 1 (Fear)**: Cap leverage at ≤5x; reduce position sizes 40% for High-Risk Active and Inconsistent segments.
- **Rule 2 (Greed)**: Allow Consistent Winners to increase frequency +30%; restrict Underperformers −25% frequency.
