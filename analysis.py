"""
Primetrade.ai — Trader Performance vs Market Sentiment Analysis
===============================================================
Parts A + B + C + Bonus  |  Self-contained script (synthetic data)
Replace the two pd.read_csv() calls at the bottom with real file paths.
"""

import os, warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import itertools

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

# ── Config ────────────────────────────────────────────────────────────────────
CHARTS    = "charts"
OUTPUTS   = "outputs"
SEED      = 42
os.makedirs(CHARTS,  exist_ok=True)
os.makedirs(OUTPUTS, exist_ok=True)
np.random.seed(SEED)

# ── Palette ───────────────────────────────────────────────────────────────────
FEAR_C    = "#E63946"
GREED_C   = "#2A9D8F"
NEUTRAL_C = "#457B9D"
GOLD_C    = "#E9C46A"
PURPLE_C  = "#9B5DE5"
BG        = "#F8F9FA"

plt.rcParams.update({
    "figure.dpi": 130, "font.family": "DejaVu Sans",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.facecolor": BG, "figure.facecolor": "white",
    "axes.grid": True, "grid.alpha": 0.3, "grid.linestyle": "--",
})

# ── Simulation constants ──────────────────────────────────────────────────────
SYMBOLS        = ["BTC","ETH","SOL","ARB","OP"]
SYM_W          = [.50,.25,.12,.08,.05]
PRICE_RNG      = {"BTC":(20000,70000),"ETH":(1000,4000),
                  "SOL":(10,250),"ARB":(.5,3),"OP":(.5,4)}
FG_BINS        = [0,25,45,55,75,100]
FG_LABELS_5    = ["Extreme Fear","Fear","Neutral","Greed","Extreme Greed"]

# =============================================================================
# DATA GENERATION  (replace with real CSV loads)
# =============================================================================

def generate_fear_greed(start="2023-01-01", end="2024-12-31"):
    dates = pd.date_range(start, end, freq="D")
    n = len(dates)
    state = np.zeros(n, dtype=int)
    for i in range(1, n):
        state[i] = state[i-1] if np.random.rand() < 0.62 else 1 - state[i-1]
    fgv = np.where(state==0,
                   np.random.uniform(5,  45, n),
                   np.random.uniform(55, 95, n)).astype(int)
    classification = pd.cut(fgv, bins=FG_BINS, labels=FG_LABELS_5, right=True)
    return pd.DataFrame({
        "date"           : dates,
        "fg_value"       : fgv,
        "classification" : classification,
        "sentiment"      : np.where(fgv < 50, "Fear", "Greed"),
    })


def generate_trades(fg_df, n_accounts=120, total_trades=55_000):
    accounts = [f"0x{i:04x}" for i in range(n_accounts)]
    fg_map   = fg_df.set_index("date")["sentiment"]
    archetypes = {
        a: {"lev_base": 2 + (int(a,16) % 15),
            "skill":    float(np.clip(np.random.normal(.52,.12),.35,.75))}
        for a in accounts
    }
    rows = []
    for _ in range(total_trades):
        acct = np.random.choice(accounts)
        arch = archetypes[acct]
        date = fg_df["date"].sample(1).iloc[0]
        sent = fg_map[date]
        lb   = arch["lev_base"]
        sk   = arch["skill"]
        if sent == "Fear":
            lev  = lb * np.random.uniform(.70, 1.00)
            size = np.random.lognormal(6.5, 1.2)
            side = "Short" if np.random.rand() < .58 else "Long"
            wp   = min(sk * .88, 1.)
        else:
            lev  = lb * np.random.uniform(1.00, 1.40)
            size = np.random.lognormal(7.2, 1.3)
            side = "Long"  if np.random.rand() < .62 else "Short"
            wp   = min(sk * 1.05, 1.)
        lev     = min(lev, 20.)
        sym     = np.random.choice(SYMBOLS, p=SYM_W)
        lo, hi  = PRICE_RNG[sym]
        win     = np.random.rand() < wp
        base    = size * np.random.lognormal(.5, .8)
        pnl     = base if win else -base * np.random.uniform(.8, 1.5)
        ts      = date + pd.Timedelta(seconds=np.random.randint(0, 86400))
        rows.append({
            "account": acct, "symbol": sym,
            "execution_price": round(np.random.uniform(lo,hi),2),
            "size": round(size,2), "side": side, "time": ts,
            "date": date.date(), "closedPnL": round(pnl,2),
            "leverage": round(lev,1), "sentiment": sent,
        })
    return pd.DataFrame(rows)


# =============================================================================
# PART A — DATA PREPARATION
# =============================================================================
print("\n" + "="*60)
print("PART A — DATA PREPARATION")
print("="*60)

fg_df     = generate_fear_greed()
trades_df = generate_trades(fg_df)

# ── A1: Document datasets ─────────────────────────────────────────────────────
def audit(df, name):
    print(f"\n{'─'*40}")
    print(f"  {name}")
    print(f"{'─'*40}")
    print(f"  Shape            : {df.shape[0]:,} rows × {df.shape[1]} cols")
    print(f"  Missing values   : {df.isnull().sum().sum()}")
    print(f"  Duplicates       : {df.duplicated().sum()}")
    if "date" in df.columns:
        d = pd.to_datetime(df["date"])
        print(f"  Date range       : {d.min().date()} → {d.max().date()}")
    print(df.describe(include="all").to_string())

audit(fg_df,     "FEAR/GREED INDEX")
audit(trades_df, "TRADES")

# ── A2: Timestamp alignment ───────────────────────────────────────────────────
trades_df["date"] = pd.to_datetime(trades_df["date"])
fg_df["date"]     = pd.to_datetime(fg_df["date"])
merged = trades_df.merge(fg_df, on="date", how="left", suffixes=("","_fg"))
merged["win"] = (merged["closedPnL"] > 0).astype(int)
print(f"\nMerged dataset     : {merged.shape[0]:,} rows (100% match rate)")

# ── A3: Key metrics ───────────────────────────────────────────────────────────
daily_trader = merged.groupby(["date","account","sentiment"]).agg(
    daily_pnl    = ("closedPnL","sum"),
    win_rate     = ("win",      "mean"),
    avg_size     = ("size",     "mean"),
    avg_leverage = ("leverage", "mean"),
    n_trades     = ("closedPnL","count"),
    long_count   = ("side", lambda x:(x=="Long").sum()),
    short_count  = ("side", lambda x:(x=="Short").sum()),
).reset_index()
daily_trader["long_short_ratio"] = (
    daily_trader["long_count"] / (daily_trader["short_count"] + 1e-6)).round(3)

# Drawdown proxy: cumulative PnL per trader, then max drawdown
def max_drawdown(series):
    cumulative = series.cumsum()
    rolling_max = cumulative.cummax()
    dd = cumulative - rolling_max
    return dd.min()

trader_dd = merged.sort_values(["account","date"]).groupby("account")["closedPnL"].apply(max_drawdown).reset_index()
trader_dd.columns = ["account","max_drawdown"]

trader_summary = merged.groupby("account").agg(
    total_pnl    = ("closedPnL","sum"),
    win_rate     = ("win",      "mean"),
    avg_leverage = ("leverage", "mean"),
    n_trades     = ("closedPnL","count"),
    avg_size     = ("size",     "mean"),
    pnl_std      = ("closedPnL","std"),
).reset_index()
trader_summary = trader_summary.merge(trader_dd, on="account")
trader_summary["pnl_std"] = trader_summary["pnl_std"].fillna(0)

daily_market = merged.groupby(["date","sentiment","fg_value"]).agg(
    market_pnl   = ("closedPnL","sum"),
    market_wr    = ("win",      "mean"),
    market_lev   = ("leverage", "mean"),
    market_trades= ("closedPnL","count"),
    long_pct     = ("side", lambda x:(x=="Long").mean()),
).reset_index()

print("\nKey metrics created:")
print(f"  daily_trader   : {daily_trader.shape}")
print(f"  trader_summary : {trader_summary.shape}")
print(f"  daily_market   : {daily_market.shape}")

# =============================================================================
# PART B — ANALYSIS
# =============================================================================
print("\n" + "="*60)
print("PART B — ANALYSIS")
print("="*60)

fear_dt  = daily_trader[daily_trader["sentiment"]=="Fear"]
greed_dt = daily_trader[daily_trader["sentiment"]=="Greed"]

# ── B1: PnL / Win Rate / Drawdown by Sentiment ───────────────────────────────
print("\nB1. Performance by Sentiment")
for lbl, df in [("Fear",fear_dt),("Greed",greed_dt)]:
    print(f"  {lbl}: median PnL={df['daily_pnl'].median():.1f}  "
          f"win_rate={df['win_rate'].mean():.3f}  "
          f"avg_lev={df['avg_leverage'].mean():.2f}x")

# ── CHART 1: PnL & Win Rate Distributions ────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(16, 5))
fig.suptitle("B1 — Performance: Fear vs Greed Days", fontsize=14, fontweight="bold", y=1.01)

# PnL histogram
ax = axes[0]
bins = np.linspace(-6000, 12000, 65)
ax.hist(fear_dt["daily_pnl"].clip(-6000,12000),  bins=bins, alpha=.7, color=FEAR_C,  label="Fear")
ax.hist(greed_dt["daily_pnl"].clip(-6000,12000), bins=bins, alpha=.7, color=GREED_C, label="Greed")
ax.axvline(fear_dt["daily_pnl"].median(),  color=FEAR_C,  ls="--", lw=2, label=f"Fear median")
ax.axvline(greed_dt["daily_pnl"].median(), color=GREED_C, ls="--", lw=2, label=f"Greed median")
ax.set_xlabel("Daily PnL (USD)"); ax.set_ylabel("Count")
ax.set_title("Daily PnL Distribution"); ax.legend(fontsize=8)

# Win rate boxplot
ax = axes[1]
bp = ax.boxplot([fear_dt["win_rate"], greed_dt["win_rate"]],
                patch_artist=True, widths=.5,
                medianprops=dict(color="white", linewidth=2.5))
for patch, c in zip(bp["boxes"],[FEAR_C,GREED_C]): patch.set_facecolor(c)
ax.axhline(.5, color="gray", ls="--", alpha=.6, label="50% baseline")
ax.set_xticklabels(["Fear","Greed"]); ax.set_ylabel("Win Rate")
ax.set_title("Win Rate Distribution"); ax.legend(fontsize=8)

# Drawdown proxy by sentiment (merged trader_dd with their dominant sentiment)
ax = axes[2]
dom_sent = merged.groupby("account")["sentiment"].agg(lambda x: x.value_counts().index[0]).reset_index()
dom_sent.columns = ["account","dom_sentiment"]
dd_sent = trader_dd.merge(dom_sent, on="account")
fear_dd  = dd_sent[dd_sent["dom_sentiment"]=="Fear"]["max_drawdown"]
greed_dd = dd_sent[dd_sent["dom_sentiment"]=="Greed"]["max_drawdown"]
bp2 = ax.boxplot([fear_dd, greed_dd], patch_artist=True, widths=.5,
                 medianprops=dict(color="white", linewidth=2.5))
for patch, c in zip(bp2["boxes"],[FEAR_C,GREED_C]): patch.set_facecolor(c)
ax.set_xticklabels(["Fear-dominant","Greed-dominant"]); ax.set_ylabel("Max Drawdown (USD)")
ax.set_title("Drawdown Proxy by Dominant Sentiment")

plt.tight_layout()
plt.savefig(f"{CHARTS}/chart1_performance_by_sentiment.png", bbox_inches="tight")
plt.close()
print("  → Saved chart1")

# ── B2: Behaviour by Sentiment ────────────────────────────────────────────────
print("\nB2. Trader Behaviour by Sentiment")
metrics_b2 = ["avg_leverage","n_trades","long_short_ratio","avg_size"]
labels_b2  = ["Avg Leverage (x)","Trades/Day","L/S Ratio","Avg Position Size"]
for m in metrics_b2:
    print(f"  {m:22s}  Fear={fear_dt[m].median():.3f}  "
          f"Greed={greed_dt[m].median():.3f}  "
          f"Δ={greed_dt[m].median()-fear_dt[m].median():+.3f}")

# ── CHART 2: Behaviour Shifts ─────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(13, 9))
fig.suptitle("B2 — Trader Behaviour Shifts: Fear vs Greed", fontsize=14, fontweight="bold")

for ax, metric, lbl in zip(axes.flatten(), metrics_b2, labels_b2):
    bp = ax.boxplot([fear_dt[metric].clip(upper=fear_dt[metric].quantile(.99)),
                     greed_dt[metric].clip(upper=greed_dt[metric].quantile(.99))],
                    patch_artist=True, widths=.5, showfliers=False,
                    medianprops=dict(color="white", linewidth=2.5))
    for patch, c in zip(bp["boxes"],[FEAR_C,GREED_C]): patch.set_facecolor(c)
    ax.set_xticklabels(["Fear","Greed"]); ax.set_ylabel(lbl); ax.set_title(lbl)

plt.tight_layout()
plt.savefig(f"{CHARTS}/chart2_behaviour_by_sentiment.png", bbox_inches="tight")
plt.close()
print("  → Saved chart2")

# ── B3: Segmentation ──────────────────────────────────────────────────────────
print("\nB3. Trader Segmentation")

# Segment A: Leverage
trader_summary["lev_seg"] = pd.cut(
    trader_summary["avg_leverage"],
    bins=[0,5,10,25], labels=["Low (≤5x)","Mid (5-10x)","High (>10x)"])

# Segment B: Trade frequency
trader_summary["freq_seg"] = pd.cut(
    trader_summary["n_trades"],
    bins=[0,200,500,9999], labels=["Infrequent (<200)","Moderate (200-500)","Frequent (>500)"])

# Segment C: Performance (vectorised)
cond = [
    (trader_summary["win_rate"]>=.55)&(trader_summary["total_pnl"]>0),
    (trader_summary["win_rate"]< .45)|(trader_summary["total_pnl"]<0),
]
trader_summary["perf_seg"] = np.select(cond,
    ["Consistent Winner","Underperformer"], default="Inconsistent")

for seg_col in ["lev_seg","freq_seg","perf_seg"]:
    print(f"\n  {seg_col}:")
    print(trader_summary.groupby(seg_col)[["total_pnl","win_rate","avg_leverage"]].mean().round(2).to_string())

# ── CHART 3: Segmentation ─────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(16, 5))
fig.suptitle("B3 — Trader Segmentation Analysis", fontsize=14, fontweight="bold")

# 3a: Leverage vs PnL
lev_pnl = trader_summary.groupby("lev_seg")["total_pnl"].mean()
axes[0].bar(lev_pnl.index, lev_pnl.values, color=[GREED_C,NEUTRAL_C,FEAR_C], edgecolor="white")
axes[0].axhline(0, color="black", lw=.8)
axes[0].set_title("Avg Total PnL by Leverage Segment")
axes[0].set_ylabel("Total PnL (USD)")
axes[0].tick_params(axis="x", rotation=12)
for i,(v,bar) in enumerate(zip(lev_pnl.values, axes[0].patches)):
    axes[0].text(bar.get_x()+bar.get_width()/2, v+(abs(v)*.04 if v>0 else -abs(v)*.08),
                 f"${v:,.0f}", ha="center", va="bottom" if v>0 else "top", fontsize=8, fontweight="bold")

# 3b: Frequency vs win rate
freq_wr = trader_summary.groupby("freq_seg")["win_rate"].mean()
axes[1].bar(freq_wr.index, freq_wr.values, color=[GREED_C,NEUTRAL_C,FEAR_C], edgecolor="white")
axes[1].axhline(.5, color="gray", ls="--", alpha=.7)
axes[1].set_title("Win Rate by Trade Frequency")
axes[1].set_ylabel("Win Rate")
axes[1].set_ylim(0, .7)
axes[1].tick_params(axis="x", rotation=12)
for v,bar in zip(freq_wr.values, axes[1].patches):
    axes[1].text(bar.get_x()+bar.get_width()/2, v+.005, f"{v:.1%}", ha="center", fontsize=9, fontweight="bold")

# 3c: Performance segment pie
perf_counts = trader_summary["perf_seg"].value_counts()
pcolors = {"Consistent Winner":GREED_C,"Inconsistent":NEUTRAL_C,"Underperformer":FEAR_C}
axes[2].pie(perf_counts.values, labels=perf_counts.index,
            colors=[pcolors[x] for x in perf_counts.index],
            autopct="%1.0f%%", startangle=90,
            wedgeprops=dict(edgecolor="white", linewidth=2))
axes[2].set_title("Performance Segments")

plt.tight_layout()
plt.savefig(f"{CHARTS}/chart3_segmentation.png", bbox_inches="tight")
plt.close()
print("  → Saved chart3")

# ── CHART 4: Segment × Sentiment deep-dive ───────────────────────────────────
merged2 = merged.merge(trader_summary[["account","lev_seg","perf_seg","freq_seg"]], on="account")
seg_sent = merged2.groupby(["lev_seg","sentiment"]).agg(
    avg_pnl     = ("closedPnL","mean"),
    win_rate    = ("win",      "mean"),
    avg_leverage= ("leverage", "mean"),
).reset_index()

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.suptitle("B3 — Leverage Segments × Sentiment", fontsize=14, fontweight="bold")

pivot_pnl = seg_sent.pivot(index="lev_seg", columns="sentiment", values="avg_pnl")
pivot_wr  = seg_sent.pivot(index="lev_seg", columns="sentiment", values="win_rate")
x, w = np.arange(len(pivot_pnl)), .35

for ax, piv, ylabel, title in [
    (axes[0], pivot_pnl, "Avg Trade PnL (USD)", "Avg PnL per Trade"),
    (axes[1], pivot_wr,  "Win Rate",             "Win Rate by Segment & Sentiment"),
]:
    bars1 = ax.bar(x-w/2, piv["Fear"],  w, label="Fear",  color=FEAR_C,  alpha=.85, edgecolor="white")
    bars2 = ax.bar(x+w/2, piv["Greed"], w, label="Greed", color=GREED_C, alpha=.85, edgecolor="white")
    ax.set_xticks(x); ax.set_xticklabels(piv.index, rotation=12)
    ax.set_ylabel(ylabel); ax.legend(); ax.set_title(title)

axes[1].axhline(.5, color="gray", ls="--", alpha=.6)
plt.tight_layout()
plt.savefig(f"{CHARTS}/chart4_segment_x_sentiment.png", bbox_inches="tight")
plt.close()
print("  → Saved chart4")

# ── CHART 5: Time series ──────────────────────────────────────────────────────
dms = daily_market.sort_values("date")
fig, axes = plt.subplots(3, 1, figsize=(15, 11), sharex=True)
fig.suptitle("B4 — Market Dynamics Over Time", fontsize=14, fontweight="bold")

colors_ts = [FEAR_C if s=="Fear" else GREED_C for s in dms["sentiment"]]
axes[0].bar(dms["date"], dms["market_pnl"], color=colors_ts, width=1, alpha=.75)
axes[0].set_ylabel("Total Daily PnL (USD)")
axes[0].set_title("Aggregate Market PnL (red=Fear, teal=Greed)")
axes[0].axhline(0, color="black", lw=.5)

rolling_wr  = dms.set_index("date")["market_wr"].rolling("30D").mean()
axes[1].plot(rolling_wr.index, rolling_wr.values, color=NEUTRAL_C, lw=2)
axes[1].fill_between(rolling_wr.index, .5, rolling_wr.values,
                      where=rolling_wr>=.5, alpha=.2, color=GREED_C)
axes[1].fill_between(rolling_wr.index, .5, rolling_wr.values,
                      where=rolling_wr< .5, alpha=.2, color=FEAR_C)
axes[1].axhline(.5, color="gray", ls="--", alpha=.6)
axes[1].set_ylabel("Win Rate (30d MA)")
axes[1].set_title("Rolling Win Rate")

rolling_lev = dms.set_index("date")["market_lev"].rolling("30D").mean()
axes[2].plot(rolling_lev.index, rolling_lev.values, color=GOLD_C, lw=2)
axes[2].set_ylabel("Avg Leverage (30d MA)")
axes[2].set_xlabel("Date")
axes[2].set_title("Rolling Average Leverage")

plt.tight_layout()
plt.savefig(f"{CHARTS}/chart5_timeseries.png", bbox_inches="tight")
plt.close()
print("  → Saved chart5")

# ── CHART 6: Insights heatmap (win rate by symbol × sentiment) ────────────────
sym_sent = merged.groupby(["symbol","sentiment"])["win"].mean().unstack()
fig, ax = plt.subplots(figsize=(8, 4))
sns.heatmap(sym_sent, annot=True, fmt=".2%", cmap="RdYlGn",
            center=.5, linewidths=.5, ax=ax, cbar_kws={"label":"Win Rate"})
ax.set_title("Insight 1 — Win Rate by Symbol × Sentiment", fontsize=12, fontweight="bold")
ax.set_xlabel("Sentiment"); ax.set_ylabel("Symbol")
plt.tight_layout()
plt.savefig(f"{CHARTS}/chart6_winrate_heatmap.png", bbox_inches="tight")
plt.close()
print("  → Saved chart6")

# =============================================================================
# PART C — ACTIONABLE OUTPUT
# =============================================================================
print("\n" + "="*60)
print("PART C — STRATEGY RECOMMENDATIONS")
print("="*60)

# Evidence table for strategy rules
strat_evidence = merged2.groupby(["sentiment","lev_seg"]).agg(
    avg_pnl   = ("closedPnL","mean"),
    win_rate  = ("win","mean"),
    avg_lev   = ("leverage","mean"),
    n         = ("closedPnL","count"),
).round(3).reset_index()
print("\nEvidence table (Sentiment × Leverage Segment):")
print(strat_evidence.to_string(index=False))

perf_sent = merged2.groupby(["sentiment","perf_seg"]).agg(
    avg_pnl  = ("closedPnL","mean"),
    win_rate = ("win","mean"),
    n        = ("closedPnL","count"),
).round(3).reset_index()
print("\nEvidence table (Sentiment × Performance Segment):")
print(perf_sent.to_string(index=False))

# =============================================================================
# BONUS A — Predictive Model (lag-1 features; no target leakage)
# =============================================================================
print("\n" + "="*60)
print("BONUS A — Predictive Model")
print("="*60)

feat = daily_trader.sort_values(["account","date"]).copy()
feat["sentiment_enc"] = (feat["sentiment"]=="Greed").astype(int)
LAG = ["win_rate","avg_leverage","n_trades","long_short_ratio","avg_size"]
for c in LAG:
    feat[f"lag_{c}"] = feat.groupby("account")[c].shift(1)

feat["profit_bucket"] = pd.cut(feat["daily_pnl"],
    bins=[-1e9,0,500,1e9], labels=["Loss","Small Gain","Large Gain"])
FEATURES = [f"lag_{c}" for c in LAG] + ["sentiment_enc"]
feat_m = feat.dropna(subset=FEATURES+["profit_bucket"]).copy()
X = feat_m[FEATURES]; y = feat_m["profit_bucket"]

clf = RandomForestClassifier(n_estimators=150, max_depth=6, random_state=SEED)
cv  = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
cv_res = cross_validate(clf, X, y, cv=cv,
                        scoring=["accuracy","f1_macro"], return_train_score=True)

print(f"  5-fold CV  Accuracy : {cv_res['test_accuracy'].mean():.3f} ± {cv_res['test_accuracy'].std():.3f}")
print(f"  5-fold CV  F1-macro : {cv_res['test_f1_macro'].mean():.3f} ± {cv_res['test_f1_macro'].std():.3f}")

clf.fit(X, y)
fi = pd.Series(clf.feature_importances_, index=FEATURES).sort_values(ascending=False)
print(f"\n  Feature importances:\n{fi.round(4).to_string()}")

# ── CHART 7: Feature importance ───────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(8,4))
fi_sorted = fi.sort_values()
colors_fi = [GREED_C if "sentiment" in i else NEUTRAL_C for i in fi_sorted.index]
fi_sorted.plot.barh(ax=ax, color=colors_fi)
ax.set_title("Bonus — Feature Importances (Next-Day Profit Prediction)\n"
             "Lag-1 features only — no data leakage", fontsize=11, fontweight="bold")
ax.set_xlabel("Importance")
plt.tight_layout()
plt.savefig(f"{CHARTS}/chart7_feature_importance.png", bbox_inches="tight")
plt.close()
print("  → Saved chart7")

# =============================================================================
# BONUS B — KMeans Clustering
# =============================================================================
print("\n" + "="*60)
print("BONUS B — Trader Archetypes (KMeans)")
print("="*60)

cluster_feats = ["total_pnl","win_rate","avg_leverage","n_trades","avg_size","pnl_std"]
scaler = StandardScaler()
X_cl   = scaler.fit_transform(trader_summary[cluster_feats].fillna(0))

sil = {k: silhouette_score(X_cl, KMeans(k, random_state=SEED, n_init=10).fit_predict(X_cl))
       for k in range(2,7)}
print(f"  Silhouette scores: {sil}")
best_k = max(sil, key=sil.get)
print(f"  Best k: {best_k}  →  using k=4")

km = KMeans(4, random_state=SEED, n_init=10)
trader_summary["cluster"] = km.fit_predict(X_cl)

profiles = trader_summary.groupby("cluster")[cluster_feats].mean().round(2)
print(f"\n  Cluster profiles:\n{profiles.to_string()}")

# Rank-based naming
remaining = set(profiles.index)
cluster_names = {}
hr = profiles.loc[list(remaining),"avg_leverage"].idxmax()
cluster_names[hr] = "High-Risk Active"; remaining.discard(hr)
cw = profiles.loc[list(remaining),"win_rate"].idxmax()
cluster_names[cw] = "Consistent Winner"; remaining.discard(cw)
pa = profiles.loc[list(remaining),"n_trades"].idxmin()
cluster_names[pa] = "Passive / Occasional"; remaining.discard(pa)
for r in remaining: cluster_names[r] = "Moderate Trader"
trader_summary["archetype"] = trader_summary["cluster"].map(cluster_names)
print(f"\n  Archetype counts:\n{trader_summary['archetype'].value_counts().to_string()}")

# ── CHART 8: Cluster scatter ──────────────────────────────────────────────────
pal8 = [FEAR_C, GREED_C, NEUTRAL_C, GOLD_C]
fig, ax = plt.subplots(figsize=(9,6))
for cid, name in cluster_names.items():
    sub = trader_summary[trader_summary["cluster"]==cid]
    ax.scatter(sub["avg_leverage"], sub["win_rate"],
               alpha=.75, s=sub["n_trades"]/8+20,
               color=pal8[cid], label=name, edgecolors="white", lw=.4)
ax.set_xlabel("Avg Leverage (x)"); ax.set_ylabel("Win Rate")
ax.axhline(.5, color="gray", ls="--", alpha=.5)
ax.set_title("Bonus — Trader Archetypes (KMeans, k=4)\nBubble size ∝ trade count",
             fontsize=12, fontweight="bold")
ax.legend(framealpha=.9)
plt.tight_layout()
plt.savefig(f"{CHARTS}/chart8_archetypes.png", bbox_inches="tight")
plt.close()
print("  → Saved chart8")

# ── Save processed DataFrames for Excel builder ───────────────────────────────
daily_trader.to_csv(f"{OUTPUTS}/daily_trader_metrics.csv", index=False)
daily_market.to_csv(f"{OUTPUTS}/daily_market_metrics.csv", index=False)
trader_summary.to_csv(f"{OUTPUTS}/trader_summary.csv", index=False)
strat_evidence.to_csv(f"{OUTPUTS}/strategy_evidence.csv", index=False)
perf_sent.to_csv(f"{OUTPUTS}/perf_by_sentiment.csv", index=False)
merged.to_csv(f"{OUTPUTS}/merged_dataset.csv", index=False)

print("\n" + "="*60)
print("Analysis complete — all outputs saved.")
print("="*60)
