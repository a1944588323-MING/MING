"""
Track Record Analysis for Active ETFs vs Passive Benchmarks
Compares manager-driven funds against their passive equivalents.
"""
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import numpy as np

# Active ETFs (and their relevant passive benchmarks)
ACTIVE_ETFS = {
    "UTES": "Virtus Reaves Utilities (Active)",        # vs XLU
    "VOLT": "Tema Electrification (Active)",            # vs AIPO/POWR
    "TSPA": "T.Rowe Price US Equity Research (Active)", # vs SPY
    "VCLN": "Virtus D&P Clean Energy (Active)",         # vs ICLN
    "ARKQ": "ARK Autonomous Tech & Robotics (Active)",  # vs QQQ
}
PASSIVE_BENCHMARKS = {
    "XLU": "XLU (Passive Utilities)",
    "AIPO": "AIPO (Passive AI Power)",
    "SPY": "SPY (Passive S&P 500)",
    "ICLN": "ICLN (Passive Clean Energy)",
    "QQQ": "QQQ (Passive Nasdaq 100)",
    "NLR": "NLR (Passive Nuclear)",
}

ALL_TICKERS = list(ACTIVE_ETFS.keys()) + list(PASSIVE_BENCHMARKS.keys())

print("Downloading data...")
data = yf.download(ALL_TICKERS, start="2014-01-01", end=None,
                   auto_adjust=True, progress=False)["Close"]
print(f"Latest available date: {data.index[-1].date()}")
print()

# ============================================================
# CALCULATE ANNUALIZED RETURNS (CAGR) AND VOLATILITY
# ============================================================
def cagr(series, years):
    series = series.dropna()
    if len(series) < 2:
        return None
    cutoff = series.index[-1] - pd.DateOffset(years=years)
    past = series.loc[series.index >= cutoff]
    if len(past) < 2:
        return None
    n_years = (past.index[-1] - past.index[0]).days / 365.25
    if n_years <= 0:
        return None
    return ((past.iloc[-1] / past.iloc[0]) ** (1 / n_years) - 1) * 100

def annual_vol(series, years):
    """Annualized volatility (std dev of daily returns * sqrt(252))"""
    series = series.dropna()
    cutoff = series.index[-1] - pd.DateOffset(years=years)
    past = series.loc[series.index >= cutoff]
    if len(past) < 30:
        return None
    daily_ret = past.pct_change().dropna()
    return daily_ret.std() * np.sqrt(252) * 100

def max_drawdown(series, years):
    series = series.dropna()
    cutoff = series.index[-1] - pd.DateOffset(years=years)
    past = series.loc[series.index >= cutoff]
    if len(past) < 10:
        return None
    cum_max = past.cummax()
    dd = (past / cum_max - 1) * 100
    return dd.min()

def total_return(series, years):
    series = series.dropna()
    cutoff = series.index[-1] - pd.DateOffset(years=years)
    past = series.loc[series.index >= cutoff]
    if len(past) < 2:
        return None
    return (past.iloc[-1] / past.iloc[0] - 1) * 100

rows = []
for ticker in ALL_TICKERS:
    if ticker not in data.columns:
        continue
    s = data[ticker].dropna()
    if len(s) < 2:
        continue
    name = ACTIVE_ETFS.get(ticker) or PASSIVE_BENCHMARKS.get(ticker, ticker)
    rows.append({
        "Ticker": ticker,
        "Name": name,
        "Active": "✅" if ticker in ACTIVE_ETFS else "—",
        "Inception in Data": s.index[0].strftime("%Y-%m-%d"),
        "1Y Return %": round(total_return(s, 1) or 0, 1),
        "3Y CAGR %": round(cagr(s, 3) or 0, 1) if cagr(s, 3) else None,
        "5Y CAGR %": round(cagr(s, 5) or 0, 1) if cagr(s, 5) else None,
        "3Y Vol %": round(annual_vol(s, 3) or 0, 1) if annual_vol(s, 3) else None,
        "Max DD 3Y %": round(max_drawdown(s, 3) or 0, 1) if max_drawdown(s, 3) else None,
    })

summary = pd.DataFrame(rows)
print("=" * 130)
print("ACTIVE vs PASSIVE ETF TRACK RECORD")
print("=" * 130)
print(summary.to_string(index=False))
print()

# ============================================================
# CHART 1: UTES vs XLU (longest active vs passive comparison)
# ============================================================
fig, axes = plt.subplots(2, 2, figsize=(16, 11))

# 1) UTES vs XLU since UTES inception (2015)
ax = axes[0, 0]
utes_start = data["UTES"].first_valid_index()
df = data[["UTES", "XLU"]].loc[utes_start:].dropna()
norm = df.divide(df.iloc[0]).multiply(100)
ax.plot(norm.index, norm["UTES"], label="UTES (Active, Reaves)", color="#27AE60", linewidth=2)
ax.plot(norm.index, norm["XLU"], label="XLU (Passive)", color="#2980B9", linewidth=2)
ax.axhline(100, color="gray", linestyle="--", linewidth=0.7, alpha=0.5)
ax.set_title(f"UTES vs XLU: Active Manager (Reaves, founded 1961) vs Passive Index\nSince UTES inception {utes_start.date()}",
             fontsize=11, fontweight="bold")
ax.set_ylabel("Normalized (start=100)")
ax.legend(loc="upper left")
ax.grid(alpha=0.3)

# 2) ARKQ vs QQQ (active vs passive)
ax = axes[0, 1]
arkq_start = data["ARKQ"].first_valid_index()
df = data[["ARKQ", "QQQ"]].loc[arkq_start:].dropna()
norm = df.divide(df.iloc[0]).multiply(100)
ax.plot(norm.index, norm["ARKQ"], label="ARKQ (Active, Cathie Wood)", color="#E74C3C", linewidth=2)
ax.plot(norm.index, norm["QQQ"], label="QQQ (Passive Nasdaq-100)", color="#9B59B6", linewidth=2)
ax.axhline(100, color="gray", linestyle="--", linewidth=0.7, alpha=0.5)
ax.set_title("ARKQ vs QQQ: Cathie Wood Active vs Passive Nasdaq",
             fontsize=11, fontweight="bold")
ax.set_ylabel("Normalized (start=100)")
ax.legend(loc="upper left")
ax.grid(alpha=0.3)

# 3) VCLN vs ICLN (clean energy active vs passive)
ax = axes[1, 0]
try:
    vcln_start = data["VCLN"].first_valid_index()
    df = data[["VCLN", "ICLN"]].loc[vcln_start:].dropna()
    norm = df.divide(df.iloc[0]).multiply(100)
    ax.plot(norm.index, norm["VCLN"], label="VCLN (Active, Duff & Phelps)", color="#16A085", linewidth=2)
    ax.plot(norm.index, norm["ICLN"], label="ICLN (Passive Clean Energy)", color="#F39C12", linewidth=2)
    ax.axhline(100, color="gray", linestyle="--", linewidth=0.7, alpha=0.5)
    ax.set_title(f"VCLN vs ICLN: Duff & Phelps Active vs Passive\nSince VCLN inception {vcln_start.date()}",
                 fontsize=11, fontweight="bold")
    ax.set_ylabel("Normalized (start=100)")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)
except Exception as e:
    ax.text(0.5, 0.5, f"VCLN data not available", ha="center", va="center")

# 4) VOLT vs AIPO (electrification active vs passive AI power)
ax = axes[1, 1]
volt_start = data["VOLT"].first_valid_index()
df = data[["VOLT", "AIPO"]].dropna()
if len(df) > 1:
    norm = df.divide(df.iloc[0]).multiply(100)
    ax.plot(norm.index, norm["VOLT"], label="VOLT (Active, Tema)", color="#D35400", linewidth=2)
    ax.plot(norm.index, norm["AIPO"], label="AIPO (Passive AI Power)", color="#E74C3C", linewidth=2)
    ax.axhline(100, color="gray", linestyle="--", linewidth=0.7, alpha=0.5)
    ax.set_title(f"VOLT vs AIPO: Tema Active vs Passive AI Power\nSince common date {df.index[0].date()}",
                 fontsize=11, fontweight="bold")
    ax.set_ylabel("Normalized (start=100)")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig("/projects/sandbox/MING/active_vs_passive_comparison.png", dpi=130)
plt.close()
print("Saved: active_vs_passive_comparison.png")

# ============================================================
# Save summary to Excel (append to existing if exists)
# ============================================================
out_path = "/projects/sandbox/MING/Active_ETF_Track_Record.xlsx"
with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
    summary.to_excel(writer, sheet_name="Track Record Summary", index=False)
    data.round(2).to_excel(writer, sheet_name="Raw Adjusted Close")
print(f"Saved: {out_path}")
