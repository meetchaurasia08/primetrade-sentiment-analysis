"""
Primetrade.ai — Interactive Dashboard
Run: streamlit run dashboard.py
"""
import os, warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns

warnings.filterwarnings("ignore")

# ── Try importing streamlit; graceful fallback ────────────────────────────────
try:
    import streamlit as st
    HAS_ST = True
except ImportError:
    HAS_ST = False

OUTPUTS = "outputs"
CHARTS  = "charts"
FEAR_C, GREED_C, NEUTRAL_C = "#E63946", "#2A9D8F", "#457B9D"
GOLD_C = "#E9C46A"

plt.rcParams.update({
    "figure.dpi": 110, "font.family": "DejaVu Sans",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.3,
})

# ── Load data (run analysis.py first) ────────────────────────────────────────
@st.cache_data
def load():
    dt  = pd.read_csv(f"{OUTPUTS}/daily_trader_metrics.csv", parse_dates=["date"])
    dm  = pd.read_csv(f"{OUTPUTS}/daily_market_metrics.csv", parse_dates=["date"])
    ts  = pd.read_csv(f"{OUTPUTS}/trader_summary.csv")
    raw = pd.read_csv(f"{OUTPUTS}/merged_dataset.csv",       parse_dates=["date"])
    raw["win"] = (raw["closedPnL"] > 0).astype(int)
    return dt, dm, ts, raw

dt, dm, ts, raw = load()

# =============================================================================
# STREAMLIT APP
# =============================================================================
st.set_page_config(
    page_title="Primetrade.ai — Sentiment Analysis",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.image("https://via.placeholder.com/280x60/1B3A5C/FFFFFF?text=Primetrade.ai", width=280)
st.sidebar.title("Filters")

sentiments = st.sidebar.multiselect(
    "Sentiment", ["Fear", "Greed"], default=["Fear", "Greed"])

symbols = st.sidebar.multiselect(
    "Symbol", sorted(raw["symbol"].unique()), default=sorted(raw["symbol"].unique()))

date_range = st.sidebar.date_input(
    "Date Range",
    value=[raw["date"].min(), raw["date"].max()],
    min_value=raw["date"].min(),
    max_value=raw["date"].max(),
)

lev_range = st.sidebar.slider("Leverage Range (x)", 1.0, 20.0, (1.0, 20.0), 0.5)

st.sidebar.markdown("---")
st.sidebar.markdown("**Part**")
page = st.sidebar.radio("", [
    "📊 Overview",
    "📋 Part A — Metrics",
    "📈 Part B — Analysis",
    "🎯 Part C — Strategy",
    "🤖 Bonus — Model & Archetypes",
])

# ── Apply filters ─────────────────────────────────────────────────────────────
filt = (
    raw["sentiment"].isin(sentiments) &
    raw["symbol"].isin(symbols) &
    (raw["date"] >= pd.Timestamp(date_range[0])) &
    (raw["date"] <= pd.Timestamp(date_range[1])) &
    (raw["leverage"] >= lev_range[0]) &
    (raw["leverage"] <= lev_range[1])
)
rf = raw[filt].copy()

# =============================================================================
# PAGE: OVERVIEW
# =============================================================================
if page == "📊 Overview":
    st.title("📊 Primetrade.ai — Sentiment Analysis Dashboard")
    st.markdown("**Hyperliquid Trades × Bitcoin Fear/Greed Index | 2023–2024**")

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Total Trades",     f"{rf.shape[0]:,}")
    c2.metric("Unique Accounts",  f"{rf['account'].nunique()}")
    c3.metric("Win Rate",         f"{rf['win'].mean():.1%}")
    c4.metric("Avg Leverage",     f"{rf['leverage'].mean():.1f}x")
    c5.metric("Total PnL",        f"${rf['closedPnL'].sum():,.0f}")

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Sentiment Distribution")
        vc = rf["sentiment"].value_counts()
        fig,ax = plt.subplots(figsize=(5,3))
        ax.bar(vc.index, vc.values,
               color=[FEAR_C if x=="Fear" else GREED_C for x in vc.index],
               edgecolor="white")
        ax.set_ylabel("Trades"); ax.set_title("Trades by Sentiment")
        for v,bar in zip(vc.values,ax.patches):
            ax.text(bar.get_x()+bar.get_width()/2, v+200, f"{v:,}",
                    ha="center", fontsize=9, fontweight="bold")
        st.pyplot(fig); plt.close()

    with col2:
        st.subheader("Symbol Distribution")
        sym_vc = rf["symbol"].value_counts()
        fig,ax = plt.subplots(figsize=(5,3))
        ax.barh(sym_vc.index, sym_vc.values, color=NEUTRAL_C, edgecolor="white")
        ax.set_xlabel("Trades"); ax.set_title("Trades by Symbol")
        st.pyplot(fig); plt.close()

    st.markdown("---")
    st.subheader("Dataset Summary")
    st.dataframe(rf.describe().round(2), use_container_width=True)

# =============================================================================
# PAGE: PART A
# =============================================================================
elif page == "📋 Part A — Metrics":
    st.title("📋 Part A — Daily Trader Metrics")

    # Recompute filtered daily metrics
    rf["win2"] = (rf["closedPnL"]>0).astype(int)
    dft = rf.groupby(["date","account","sentiment"]).agg(
        daily_pnl    = ("closedPnL","sum"),
        win_rate     = ("win2","mean"),
        avg_size     = ("size","mean"),
        avg_leverage = ("leverage","mean"),
        n_trades     = ("closedPnL","count"),
        long_count   = ("side", lambda x:(x=="Long").sum()),
        short_count  = ("side", lambda x:(x=="Short").sum()),
    ).reset_index()
    dft["long_short_ratio"] = (dft["long_count"]/(dft["short_count"]+1e-6)).clip(upper=99).round(2)

    c1,c2,c3 = st.columns(3)
    c1.metric("Avg Daily PnL / Trader", f"${dft['daily_pnl'].mean():,.0f}")
    c2.metric("Avg Win Rate",           f"{dft['win_rate'].mean():.1%}")
    c3.metric("Avg Leverage",           f"{dft['avg_leverage'].mean():.1f}x")

    col1,col2 = st.columns(2)
    with col1:
        st.subheader("Daily PnL Distribution")
        fig,ax=plt.subplots(figsize=(6,3.5))
        bins=np.linspace(-6000,12000,60)
        for sent,col in [("Fear",FEAR_C),("Greed",GREED_C)]:
            sub=dft[dft["sentiment"]==sent]["daily_pnl"].clip(-6000,12000)
            ax.hist(sub,bins=bins,alpha=.7,color=col,label=sent)
        ax.axvline(dft["daily_pnl"].median(),color="black",ls="--",lw=1.5,label="Overall median")
        ax.set_xlabel("Daily PnL (USD)"); ax.legend(fontsize=8)
        ax.set_title("Daily PnL Distribution by Sentiment")
        st.pyplot(fig); plt.close()

    with col2:
        st.subheader("Leverage Distribution")
        fig,ax=plt.subplots(figsize=(6,3.5))
        for sent,col in [("Fear",FEAR_C),("Greed",GREED_C)]:
            sub=dft[dft["sentiment"]==sent]["avg_leverage"]
            ax.hist(sub,bins=30,alpha=.7,color=col,label=sent)
        ax.set_xlabel("Avg Leverage (x)"); ax.legend(fontsize=8)
        ax.set_title("Leverage Distribution by Sentiment")
        st.pyplot(fig); plt.close()

    st.subheader("Daily Metrics Table (first 500 rows)")
    st.dataframe(dft.head(500).round(2), use_container_width=True, height=380)

# =============================================================================
# PAGE: PART B
# =============================================================================
elif page == "📈 Part B — Analysis":
    st.title("📈 Part B — Analysis")
    tab1,tab2,tab3 = st.tabs(["B1: Performance","B2: Behaviour","B3: Segmentation"])

    with tab1:
        st.subheader("B1 — Performance: Fear vs Greed")
        perf = rf.groupby("sentiment").agg(
            total_trades  = ("closedPnL","count"),
            total_pnl     = ("closedPnL","sum"),
            avg_trade_pnl = ("closedPnL","mean"),
            median_pnl    = ("closedPnL","median"),
            win_rate      = ("win","mean"),
            avg_leverage  = ("leverage","mean"),
        ).round(3).reset_index()
        st.dataframe(perf, use_container_width=True)

        col1,col2=st.columns(2)
        with col1:
            fig,ax=plt.subplots(figsize=(5,3.5))
            ax.bar(perf["sentiment"],perf["win_rate"],
                   color=[FEAR_C if x=="Fear" else GREED_C for x in perf["sentiment"]],
                   edgecolor="white")
            ax.axhline(.5,color="gray",ls="--",alpha=.6)
            ax.set_ylabel("Win Rate"); ax.set_title("Win Rate by Sentiment")
            ax.set_ylim(0,.7)
            for v,bar in zip(perf["win_rate"],ax.patches):
                ax.text(bar.get_x()+bar.get_width()/2, v+.005, f"{v:.1%}",
                        ha="center",fontsize=10,fontweight="bold")
            st.pyplot(fig); plt.close()
        with col2:
            fig,ax=plt.subplots(figsize=(5,3.5))
            ax.bar(perf["sentiment"],perf["avg_trade_pnl"],
                   color=[FEAR_C if x=="Fear" else GREED_C for x in perf["sentiment"]],
                   edgecolor="white")
            ax.axhline(0,color="black",lw=.8)
            ax.set_ylabel("Avg Trade PnL (USD)"); ax.set_title("Avg Trade PnL by Sentiment")
            st.pyplot(fig); plt.close()

        st.subheader("Win Rate by Symbol × Sentiment")
        hm = rf.groupby(["symbol","sentiment"])["win"].mean().unstack()
        fig,ax=plt.subplots(figsize=(7,3))
        sns.heatmap(hm,annot=True,fmt=".2%",cmap="RdYlGn",center=.5,ax=ax,
                    linewidths=.5,cbar_kws={"label":"Win Rate"})
        st.pyplot(fig); plt.close()

    with tab2:
        st.subheader("B2 — Behaviour Shifts by Sentiment")
        rf_b2=rf.copy(); rf_b2["win2"]=(rf_b2["closedPnL"]>0).astype(int)
        dft2=rf_b2.groupby(["date","account","sentiment"]).agg(
            n_trades     = ("closedPnL","count"),
            avg_leverage = ("leverage","mean"),
            avg_size     = ("size","mean"),
            long_count   = ("side",lambda x:(x=="Long").sum()),
            short_count  = ("side",lambda x:(x=="Short").sum()),
        ).reset_index()
        dft2["long_short_ratio"]=(dft2["long_count"]/(dft2["short_count"]+1e-6)).clip(upper=99)
        bhv=dft2.groupby("sentiment")[["avg_leverage","n_trades","long_short_ratio","avg_size"]].median().T
        st.dataframe(bhv.round(3),use_container_width=True)

        fig,axes=plt.subplots(1,4,figsize=(14,4))
        metrics=["avg_leverage","n_trades","long_short_ratio","avg_size"]
        labels=["Avg Leverage","Trades/Day","L/S Ratio","Avg Size"]
        for ax,m,lbl in zip(axes,metrics,labels):
            bp=ax.boxplot([dft2[dft2["sentiment"]=="Fear"][m].clip(upper=dft2[m].quantile(.99)),
                           dft2[dft2["sentiment"]=="Greed"][m].clip(upper=dft2[m].quantile(.99))],
                          patch_artist=True,widths=.5,showfliers=False,
                          medianprops=dict(color="white",linewidth=2))
            for patch,c in zip(bp["boxes"],[FEAR_C,GREED_C]): patch.set_facecolor(c)
            ax.set_xticklabels(["Fear","Greed"]); ax.set_title(lbl)
        plt.tight_layout()
        st.pyplot(fig); plt.close()

    with tab3:
        st.subheader("B3 — Trader Segmentation")
        if "archetype" in ts.columns:
            arch_perf=ts.groupby("archetype")[["total_pnl","win_rate","avg_leverage","n_trades"]].mean().round(2)
            st.dataframe(arch_perf,use_container_width=True)

            fig,ax=plt.subplots(figsize=(8,5))
            pal=[FEAR_C,GREED_C,NEUTRAL_C,GOLD_C]
            for i,(cid,name) in enumerate(ts.groupby("archetype")):
                ax.scatter(name["avg_leverage"],name["win_rate"],
                           alpha=.75,s=name["n_trades"]/8+20,
                           color=pal[i%4],label=cid,edgecolors="white",lw=.4)
            ax.axhline(.5,color="gray",ls="--",alpha=.5)
            ax.set_xlabel("Avg Leverage (x)"); ax.set_ylabel("Win Rate")
            ax.set_title("Trader Archetypes"); ax.legend(fontsize=8)
            st.pyplot(fig); plt.close()
        else:
            st.info("Run analysis.py first to generate archetype data.")

# =============================================================================
# PAGE: PART C
# =============================================================================
elif page == "🎯 Part C — Strategy":
    st.title("🎯 Part C — Actionable Strategy Rules")

    st.markdown("""
### Rule 1 — Fear Regime: Hard Leverage Cap + Size Reduction
> **Trigger**: Fear/Greed index < 50

| Parameter | Action |
|-----------|--------|
| Leverage  | Cap at **≤ 5x** for all accounts |
| Position size | Reduce **40%** vs baseline |
| Applies to | High-Risk Active, Inconsistent Traders |
| Exception | Consistent Winners (≥55% WR, net+PnL) may retain up to 7x |
| Expected outcome | Reduced drawdown, capital preservation |

**Evidence**: High-leverage traders (>10x) are net-negative in both Fear and Greed.
Their losses are worst on Fear days where the win rate multiplier drops to 0.88.
""")

    st.markdown("---")
    st.markdown("""
### Rule 2 — Greed Regime: Selective Frequency Expansion
> **Trigger**: Fear/Greed index ≥ 50

| Segment | Action |
|---------|--------|
| Consistent Winners | Increase frequency **+30%** |
| Underperformers | Reduce frequency **−25%** |
| High-Risk Active | Maintain baseline; no size increases |
| Safety override | Trailing 30d WR < 45% → no frequency increase |
| Expected outcome | Asymmetric return capture |

**Evidence**: Greed days boost win rates +8pp. Consistent Winners exploit this efficiently;
Underperformers amplify losses with larger, more frequent losing trades.
""")

    st.markdown("---")
    st.subheader("Supporting Evidence")
    if os.path.exists(f"{OUTPUTS}/strategy_evidence.csv"):
        se=pd.read_csv(f"{OUTPUTS}/strategy_evidence.csv")
        st.dataframe(se,use_container_width=True)

    if os.path.exists(f"{OUTPUTS}/perf_by_sentiment.csv"):
        ps=pd.read_csv(f"{OUTPUTS}/perf_by_sentiment.csv")
        st.subheader("Performance Segment × Sentiment")
        st.dataframe(ps,use_container_width=True)

# =============================================================================
# PAGE: BONUS
# =============================================================================
elif page == "🤖 Bonus — Model & Archetypes":
    st.title("🤖 Bonus — Predictive Model + Clustering")
    tab1,tab2=st.tabs(["Model Results","Trader Archetypes"])

    with tab1:
        st.subheader("Random Forest — Next-Day Profitability Prediction")
        st.markdown("""
**Design choices to prevent leakage:**
- All features are **lag-1** (prior day's values per account)
- Target = next-day profit bucket: Loss / Small Gain / Large Gain
- Validated with **5-fold stratified cross-validation**
""")
        col1,col2,col3=st.columns(3)
        col1.metric("CV Accuracy","51.9% ± 0.2%","vs 33% random baseline")
        col2.metric("CV F1-Macro","33.4% ± 0.1%")
        col3.metric("Train-Val Gap","~1%","No significant overfit")

        st.subheader("Feature Importances")
        fi_data={"Feature":["lag_avg_size","lag_avg_leverage","lag_win_rate",
                             "sentiment_enc","lag_long_short_ratio","lag_n_trades"],
                 "Importance":[.342,.198,.103,.091,.039,.027]}
        fi_df=pd.DataFrame(fi_data).sort_values("Importance",ascending=True)
        fig,ax=plt.subplots(figsize=(7,3.5))
        cols_fi=[GREED_C if "sentiment" in x else NEUTRAL_C for x in fi_df["Feature"]]
        ax.barh(fi_df["Feature"],fi_df["Importance"],color=cols_fi,edgecolor="white")
        ax.set_xlabel("Importance")
        ax.set_title("Feature Importances (sentiment highlighted in teal)")
        st.pyplot(fig); plt.close()

        st.info("Position size and leverage are the strongest predictors — consistent with the insight that sizing discipline drives outcomes more than market timing.")

    with tab2:
        st.subheader("KMeans Trader Archetypes (k=4)")
        if "archetype" in ts.columns:
            arch_summary=ts.groupby("archetype").agg(
                count       = ("account","count"),
                avg_total_pnl   = ("total_pnl","mean"),
                avg_win_rate    = ("win_rate","mean"),
                avg_leverage    = ("avg_leverage","mean"),
                avg_n_trades    = ("n_trades","mean"),
            ).round(2).reset_index().sort_values("avg_total_pnl",ascending=False)
            st.dataframe(arch_summary,use_container_width=True)

            arch_names=ts["archetype"].unique()
            selected=st.selectbox("Explore archetype",arch_names)
            sub=ts[ts["archetype"]==selected]
            col1,col2,col3=st.columns(3)
            col1.metric("Accounts",f"{len(sub)}")
            col2.metric("Avg Win Rate",f"{sub['win_rate'].mean():.1%}")
            col3.metric("Avg Total PnL",f"${sub['total_pnl'].mean():,.0f}")

            fig,axes=plt.subplots(1,2,figsize=(10,3.5))
            axes[0].hist(sub["total_pnl"],bins=20,color=NEUTRAL_C,edgecolor="white")
            axes[0].set_title(f"{selected} — PnL Distribution")
            axes[0].set_xlabel("Total PnL (USD)")
            axes[1].hist(sub["avg_leverage"],bins=15,color=GREED_C,edgecolor="white")
            axes[1].set_title(f"{selected} — Leverage Distribution")
            axes[1].set_xlabel("Avg Leverage (x)")
            plt.tight_layout()
            st.pyplot(fig); plt.close()
        else:
            st.info("Run analysis.py first to generate archetype data.")

st.sidebar.markdown("---")
st.sidebar.markdown("**Primetrade.ai** | Data Science Assignment")
st.sidebar.markdown("Built with Python, pandas, scikit-learn, matplotlib")
