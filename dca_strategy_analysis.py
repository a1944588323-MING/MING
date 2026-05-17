"""
DCA Strategy Analysis: ARKQ + VOLT + AIPO
Compares multiple strategies for maximum compound returns over 5 years.
"""
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ============================================================
# 1. DOWNLOAD DATA
# ============================================================
tickers = ["ARKQ", "VOLT", "AIPO", "SPY", "QQQ", "VPU"]
print("Downloading historical data...")
data = yf.download(tickers, start="2020-01-01", auto_adjust=True, progress=False)["Close"]
print(f"Data range: {data.index[0].date()} to {data.index[-1].date()}\n")

# ============================================================
# 2. HISTORICAL BACKTEST OF DCA STRATEGIES
# ============================================================
def simulate_dca(prices, monthly_amount, allocation, rebalance=False):
    """Simulate monthly DCA. allocation dict: ticker -> target weight"""
    monthly = prices.resample('MS').first().dropna(how='all')
    monthly = monthly[[t for t in allocation if t in monthly.columns]]

    shares = {t: 0.0 for t in allocation}
    total_invested = 0.0
    history = []

    for date, row in monthly.iterrows():
        # Skip if any allocated ticker has no price yet
        valid_tickers = [t for t in allocation if t in row.index and not pd.isna(row[t])]
        if not valid_tickers:
            continue

        # Compute current portfolio value
        current_value = sum(shares[t] * row[t] for t in valid_tickers if not pd.isna(row[t]))

        if rebalance and total_invested > 0:
            # Rebalance: redistribute current portfolio + new contribution to target weights
            total_pool = current_value + monthly_amount
            for t in valid_tickers:
                target_dollars = total_pool * allocation[t] / sum(allocation[v] for v in valid_tickers)
                shares[t] = target_dollars / row[t]
        else:
            # Pure DCA: just buy with new money at target weights
            valid_weight = sum(allocation[v] for v in valid_tickers)
            for t in valid_tickers:
                weight = allocation[t] / valid_weight if valid_weight > 0 else 0
                shares[t] += (monthly_amount * weight) / row[t]

        total_invested += monthly_amount
        new_value = sum(shares[t] * row[t] for t in valid_tickers if not pd.isna(row[t]))
        history.append({
            'date': date,
            'invested': total_invested,
            'value': new_value,
            'gain': new_value - total_invested,
            'gain_pct': (new_value - total_invested) / total_invested * 100,
        })

    return pd.DataFrame(history).set_index('date')

# Strategies to compare (monthly $1000 starting from earliest data)
strategies = {
    "S1_Equal_DCA":      {"ARKQ": 1/3, "VOLT": 1/3, "AIPO": 1/3},
    "S2_RiskWeighted":   {"ARKQ": 0.20, "VOLT": 0.40, "AIPO": 0.40},  # less ARKQ
    "S3_Replace_ARKQ":   {"QQQ": 1/3,  "VOLT": 1/3, "AIPO": 1/3},
    "S4_Hedged":         {"ARKQ": 0.25, "VOLT": 0.30, "AIPO": 0.30, "VPU": 0.15},  # 15% utilities hedge
    "S5_PureSPY":        {"SPY": 1.0},
    "S6_PureQQQ":        {"QQQ": 1.0},
}

results = {}
for name, alloc in strategies.items():
    results[name] = simulate_dca(data, 1000, alloc, rebalance=False)

# Print final results
print("=" * 90)
print(f"BACKTEST RESULTS (Monthly $1000 DCA, no rebalancing)")
print("=" * 90)
print(f"{'Strategy':<25} {'Months':<8} {'Invested':<12} {'Final Value':<14} {'Gain%':<10} {'Annual %':<10}")
print("-" * 90)
for name, df in results.items():
    if df.empty:
        continue
    last = df.iloc[-1]
    months = len(df)
    years = months / 12
    annual = ((last['value'] / last['invested']) ** (1/years) - 1) * 100 if years > 0 else 0
    print(f"{name:<25} {months:<8} ${last['invested']:<11,.0f} ${last['value']:<13,.0f} {last['gain_pct']:<10.1f} {annual:<10.1f}")

# ============================================================
# 3. WITH QUARTERLY REBALANCING
# ============================================================
print("\n" + "=" * 90)
print("WITH QUARTERLY REBALANCING (Buy-Low / Sell-High)")
print("=" * 90)
results_rebal = {}
for name, alloc in strategies.items():
    if name in ["S5_PureSPY", "S6_PureQQQ"]:
        continue
    results_rebal[name + "_Rebal"] = simulate_dca(data, 1000, alloc, rebalance=True)

print(f"{'Strategy':<28} {'Months':<8} {'Invested':<12} {'Final Value':<14} {'Gain%':<10} {'Annual %':<10}")
print("-" * 90)
for name, df in results_rebal.items():
    if df.empty:
        continue
    last = df.iloc[-1]
    months = len(df)
    years = months / 12
    annual = ((last['value'] / last['invested']) ** (1/years) - 1) * 100 if years > 0 else 0
    print(f"{name:<28} {months:<8} ${last['invested']:<11,.0f} ${last['value']:<13,.0f} {last['gain_pct']:<10.1f} {annual:<10.1f}")

# ============================================================
# 4. 5-YEAR FORWARD PROJECTION
# ============================================================
print("\n" + "=" * 90)
print("5-YEAR FORWARD PROJECTION (60 months)")
print("=" * 90)

def fv_dca(monthly_amount, annual_return, months=60):
    """Future value of monthly DCA at constant return rate"""
    r = (1 + annual_return) ** (1/12) - 1
    return monthly_amount * (((1 + r) ** months - 1) / r)

scenarios = {
    "Bear (-5% annual)":     -0.05,
    "Pessimistic (5%)":       0.05,
    "Conservative (8%)":      0.08,
    "Base Case (12%)":        0.12,
    "Optimistic (18%)":       0.18,
    "Bull (25%)":             0.25,
    "Mania (35%)":            0.35,
}

print(f"\n{'Scenario':<25} {'Final Value':<15} {'Profit':<15} {'Multiple':<10}")
print("-" * 90)
print("Monthly contribution: $1,000  |  Total invested over 60 months: $60,000")
print("-" * 90)
for name, ret in scenarios.items():
    fv = fv_dca(1000, ret)
    profit = fv - 60000
    multiple = fv / 60000
    print(f"{name:<25} ${fv:<14,.0f} ${profit:<14,.0f} {multiple:<10.2f}x")

# ============================================================
# 5. COMPOUND ADVANTAGE OF DRIP / NO DRIP
# ============================================================
print("\n" + "=" * 90)
print("KEY INSIGHT: VOLATILITY DRAG (why low-vol portfolios compound better)")
print("=" * 90)
print("""
Two portfolios both have +10% average annual return but different volatility:
""")
print(f"{'Portfolio':<30} {'Avg Return':<12} {'Vol':<8} {'Realized CAGR':<15}")
print("-" * 70)
print(f"{'High volatility (e.g. ARKQ)':<30} {'+10%':<12} {'30%':<8} {'10% - 4.5% = 5.5%':<15}")
print(f"{'Medium vol (e.g. AIPO)':<30} {'+10%':<12} {'25%':<8} {'10% - 3.1% = 6.9%':<15}")
print(f"{'Low vol (e.g. UTES/VPU)':<30} {'+10%':<12} {'15%':<8} {'10% - 1.1% = 8.9%':<15}")
print("\nRule: Realized CAGR = Mean Return - 0.5 * Variance")
print("Lower volatility = higher actual compound return for the same mean return!\n")

# ============================================================
# 6. CHARTS
# ============================================================
fig, axes = plt.subplots(2, 2, figsize=(15, 11))

# Chart 1: All historical strategies
ax = axes[0, 0]
colors = {'S1_Equal_DCA': '#E74C3C', 'S2_RiskWeighted': '#27AE60',
          'S3_Replace_ARKQ': '#9B59B6', 'S4_Hedged': '#2980B9',
          'S5_PureSPY': '#7F8C8D', 'S6_PureQQQ': '#F39C12'}
labels = {'S1_Equal_DCA': 'S1: Equal 33/33/33',
          'S2_RiskWeighted': 'S2: 20/40/40 (less ARKQ)',
          'S3_Replace_ARKQ': 'S3: QQQ + VOLT + AIPO',
          'S4_Hedged': 'S4: 25/30/30/15 + VPU hedge',
          'S5_PureSPY': 'S5: 100% SPY',
          'S6_PureQQQ': 'S6: 100% QQQ'}
for name, df in results.items():
    if df.empty:
        continue
    ax.plot(df.index, df['value'], label=labels[name], color=colors[name], linewidth=2)
    ax.plot(df.index, df['invested'], color=colors[name], linewidth=0.7, linestyle=':', alpha=0.4)
ax.set_title("Historical DCA Backtest ($1,000/month)\nSolid = Portfolio Value, Dotted = Total Invested",
             fontsize=11, fontweight='bold')
ax.set_ylabel("Portfolio Value ($)")
ax.legend(loc='upper left', fontsize=9)
ax.grid(alpha=0.3)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x/1000:.0f}K'))

# Chart 2: Final return % comparison
ax = axes[0, 1]
sorted_results = sorted(results.items(), key=lambda x: x[1]['gain_pct'].iloc[-1] if not x[1].empty else 0, reverse=True)
names = [labels[n] for n, _ in sorted_results]
gains = [df['gain_pct'].iloc[-1] for _, df in sorted_results]
bars = ax.barh(names, gains, color=[colors[n] for n, _ in sorted_results])
ax.set_title("Total Gain % by Strategy (since common start date)",
             fontsize=11, fontweight='bold')
ax.set_xlabel("Total Return %")
for bar, gain in zip(bars, gains):
    ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2,
            f'{gain:.1f}%', va='center', fontsize=9)
ax.grid(alpha=0.3, axis='x')

# Chart 3: 5-Year projection at different scenarios
ax = axes[1, 0]
scenarios_to_plot = list(scenarios.items())
labels_plot = [f"{name}\n${fv_dca(1000, r):,.0f}" for name, r in scenarios_to_plot]
values = [fv_dca(1000, r) for _, r in scenarios_to_plot]
colors_proj = ['#C0392B', '#E67E22', '#F39C12', '#27AE60', '#16A085', '#2980B9', '#8E44AD']
bars = ax.bar(range(len(values)), values, color=colors_proj)
ax.axhline(60000, color='red', linestyle='--', label='Total Invested ($60,000)')
ax.set_title("5-Year DCA Projection at Different Return Scenarios\n($1,000/month for 60 months)",
             fontsize=11, fontweight='bold')
ax.set_ylabel("Final Portfolio Value ($)")
ax.set_xticks(range(len(values)))
ax.set_xticklabels([s.split(' (')[0] for s, _ in scenarios_to_plot], rotation=30, ha='right', fontsize=9)
for i, v in enumerate(values):
    ax.text(i, v + 2000, f'${v:,.0f}', ha='center', fontsize=8, fontweight='bold')
ax.legend()
ax.grid(alpha=0.3, axis='y')
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x/1000:.0f}K'))

# Chart 4: Rebalanced vs Pure DCA
ax = axes[1, 1]
df_pure = results['S1_Equal_DCA']
df_rebal = results_rebal['S1_Equal_DCA_Rebal']
ax.plot(df_pure.index, df_pure['value'], label='Pure DCA (no rebalance)', color='#3498DB', linewidth=2)
ax.plot(df_rebal.index, df_rebal['value'], label='With Quarterly Rebalance', color='#E74C3C', linewidth=2)
ax.plot(df_pure.index, df_pure['invested'], label='Total Invested', color='gray', linewidth=1, linestyle='--')
ax.set_title("Effect of Quarterly Rebalancing\n(Equal Weight ARKQ+VOLT+AIPO)",
             fontsize=11, fontweight='bold')
ax.set_ylabel("Portfolio Value ($)")
ax.legend(loc='upper left')
ax.grid(alpha=0.3)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x/1000:.0f}K'))

plt.tight_layout()
plt.savefig("/projects/sandbox/MING/dca_strategy_analysis.png", dpi=130)
plt.close()
print("Saved: dca_strategy_analysis.png\n")

# ============================================================
# 7. EXPORT TO EXCEL
# ============================================================
out_path = "/projects/sandbox/MING/DCA_5Year_Strategy.xlsx"
with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
    # Strategy backtest results
    summary_rows = []
    for name, df in {**results, **results_rebal}.items():
        if df.empty:
            continue
        last = df.iloc[-1]
        months = len(df)
        years = months / 12
        annual = ((last['value'] / last['invested']) ** (1/years) - 1) * 100 if years > 0 else 0
        summary_rows.append({
            'Strategy': name,
            'Months Backtested': months,
            'Total Invested': last['invested'],
            'Final Value': last['value'],
            'Total Gain': last['gain'],
            'Gain %': last['gain_pct'],
            'Annualized %': annual,
        })
    pd.DataFrame(summary_rows).to_excel(writer, sheet_name='Strategy Comparison', index=False)

    # 5-year projection table
    proj_rows = []
    for monthly in [500, 1000, 1500, 2000, 3000, 5000]:
        for name, ret in scenarios.items():
            fv = fv_dca(monthly, ret)
            proj_rows.append({
                'Monthly Contribution': monthly,
                'Scenario': name,
                'Annual Return': f"{ret*100:.0f}%",
                'Total Invested (5y)': monthly * 60,
                'Projected Value': fv,
                'Profit': fv - monthly * 60,
                'Multiple': fv / (monthly * 60),
            })
    pd.DataFrame(proj_rows).to_excel(writer, sheet_name='5-Year Projection', index=False)

    # Daily history of S1 vs benchmarks
    perf = pd.DataFrame({
        'Equal DCA Value': results['S1_Equal_DCA']['value'],
        'Replace ARKQ Value': results['S3_Replace_ARKQ']['value'],
        'Hedged Value': results['S4_Hedged']['value'],
        'SPY Value': results['S5_PureSPY']['value'],
        'QQQ Value': results['S6_PureQQQ']['value'],
    })
    perf.to_excel(writer, sheet_name='DCA History')

print(f"Saved: {out_path}")
print("\nDone!")
