"""
ETF Historical Performance Comparison: AIPO vs NLR vs XLU
Pulls historical prices via yfinance and generates comparison charts + Excel summary.
"""
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

# AIPO inception was 2025-07-24, so common start date is set to inception of AIPO
# We will produce two charts: (1) common period since AIPO inception, (2) longer 5y view of NLR & XLU
TICKERS = ["AIPO", "NLR", "XLU"]
COLORS = {"AIPO": "#E74C3C", "NLR": "#27AE60", "XLU": "#2980B9"}

print("Downloading data ...")
# Daily adjusted close from a wide range; yfinance auto-handles short history for AIPO
data = yf.download(TICKERS, start="2020-01-01", end=None, auto_adjust=True, progress=False)["Close"]
data = data.dropna(how="all")
print("Latest dates:")
print(data.tail(3))

# ============================================================
# CHART 1: Normalized total return since AIPO inception (Jul 24, 2025)
# ============================================================
common_start = data["AIPO"].first_valid_index()
print(f"\nAIPO first available date: {common_start}")
df_common = data.loc[common_start:].dropna()
norm_common = df_common.divide(df_common.iloc[0]).multiply(100)

fig, ax = plt.subplots(figsize=(12, 6))
for t in TICKERS:
    ax.plot(norm_common.index, norm_common[t], label=t, color=COLORS[t], linewidth=2)
ax.axhline(100, color="gray", linestyle="--", linewidth=0.7, alpha=0.7)
ax.set_title(f"AIPO vs NLR vs XLU - Normalized Total Return (Base = 100)\nSince AIPO Inception: {common_start.date()}",
             fontsize=13, fontweight="bold")
ax.set_ylabel("Normalized Price (start = 100)")
ax.set_xlabel("Date")
ax.legend(fontsize=11, loc="upper left")
ax.grid(alpha=0.3)
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig("/projects/sandbox/MING/etf_compare_since_aipo.png", dpi=130)
plt.close()
print("Saved: etf_compare_since_aipo.png")

# ============================================================
# CHART 2: 5-year normalized comparison for NLR & XLU
# ============================================================
five_yr_start = pd.Timestamp(datetime.now()) - pd.DateOffset(years=5)
df_5y = data[["NLR", "XLU"]].loc[five_yr_start:].dropna()
norm_5y = df_5y.divide(df_5y.iloc[0]).multiply(100)

fig, ax = plt.subplots(figsize=(12, 6))
for t in ["NLR", "XLU"]:
    ax.plot(norm_5y.index, norm_5y[t], label=t, color=COLORS[t], linewidth=2)
ax.axhline(100, color="gray", linestyle="--", linewidth=0.7, alpha=0.7)
ax.set_title("NLR vs XLU - 5-Year Normalized Total Return (Base = 100)\n(AIPO not included - inception was 2025-07-24)",
             fontsize=13, fontweight="bold")
ax.set_ylabel("Normalized Price (start = 100)")
ax.set_xlabel("Date")
ax.legend(fontsize=11, loc="upper left")
ax.grid(alpha=0.3)
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig("/projects/sandbox/MING/etf_compare_5y.png", dpi=130)
plt.close()
print("Saved: etf_compare_5y.png")

# ============================================================
# Performance summary table (multiple time horizons)
# ============================================================
def total_ret_pct(series, days):
    series = series.dropna()
    if len(series) < 2:
        return None
    end = series.iloc[-1]
    cutoff = series.index[-1] - pd.DateOffset(days=days)
    past = series.loc[series.index >= cutoff]
    if past.empty:
        return None
    start = past.iloc[0]
    return (end / start - 1) * 100

def ytd_pct(series):
    series = series.dropna()
    if series.empty:
        return None
    year = series.index[-1].year
    ytd_ser = series[series.index.year == year]
    if ytd_ser.empty:
        return None
    return (ytd_ser.iloc[-1] / ytd_ser.iloc[0] - 1) * 100

def inception_pct(series):
    series = series.dropna()
    if len(series) < 2:
        return None
    return (series.iloc[-1] / series.iloc[0] - 1) * 100

rows = []
for t in TICKERS:
    s = data[t].dropna()
    rows.append({
        "Ticker": t,
        "Latest Price": round(s.iloc[-1], 2),
        "Latest Date": s.index[-1].strftime("%Y-%m-%d"),
        "1M Return %": round(total_ret_pct(s, 30) or 0, 2),
        "3M Return %": round(total_ret_pct(s, 90) or 0, 2),
        "6M Return %": round(total_ret_pct(s, 180) or 0, 2),
        "YTD %": round(ytd_pct(s) or 0, 2),
        "1Y %": round(total_ret_pct(s, 365) or 0, 2),
        "3Y %": round(total_ret_pct(s, 365 * 3) or 0, 2),
        "5Y %": round(total_ret_pct(s, 365 * 5) or 0, 2),
        "Since data start %": round(inception_pct(s), 2),
        "First Available": s.index[0].strftime("%Y-%m-%d"),
    })

summary = pd.DataFrame(rows)
print("\n" + "=" * 100)
print("PERFORMANCE SUMMARY (price-only, dividends not reinvested)")
print("=" * 100)
print(summary.to_string(index=False))

# Save to Excel
out_path = "/projects/sandbox/MING/ETF对比_AIPO_NLR_XLU.xlsx"
with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
    summary.to_excel(writer, sheet_name="Performance Summary", index=False)
    norm_common.round(2).to_excel(writer, sheet_name="Since AIPO Inception (Norm)")
    norm_5y.round(2).to_excel(writer, sheet_name="5-Year NLR vs XLU (Norm)")
    data.round(2).to_excel(writer, sheet_name="Raw Adjusted Close")
print(f"\nSaved Excel: {out_path}")
