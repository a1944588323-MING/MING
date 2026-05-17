"""
DCA + Buy-the-Dip Strategy Simulation
VOLT + AIPO + QQQ, $1200/month split 3 ways
Rule: if an ETF closes the month down, next month add 50% extra to that ETF
"""
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['DejaVu Sans']

# ============================================================
# 1) DOWNLOAD DATA
# ============================================================
TICKERS = ["VOLT", "AIPO", "QQQ"]
print("Downloading data...")
data = yf.download(TICKERS, start="2020-01-01", auto_adjust=True, progress=False)["Close"]

# ============================================================
# 2) BACKTEST: $1200/month split 3 ways with buy-the-dip rule
# ============================================================
def simulate_dca_with_dip(prices, base_monthly=1200, dip_bonus_pct=0.5):
    """
    Each month buy on the 1st (or first trading day).
    If a particular ETF closed the month DOWN (vs its month-start price),
    next month add 50% extra to THAT ETF.
    """
    base_per_etf = base_monthly / 3  # $400 each

    # Get first trading day of each month
    monthly_first = prices.resample('MS').apply(
        lambda x: x.dropna().iloc[0] if len(x.dropna()) > 0 else np.nan
    )
    monthly_last = prices.resample('M').apply(
        lambda x: x.dropna().iloc[-1] if len(x.dropna()) > 0 else np.nan
    )

    months = monthly_first.index
    results = []
    shares = {t: 0.0 for t in TICKERS}
    next_bonus = {t: 0.0 for t in TICKERS}  # extra $ for next month
    total_invested = 0.0
    total_dip_months = {t: 0 for t in TICKERS}

    for i, m in enumerate(months):
        for t in TICKERS:
            price_first = monthly_first.loc[m, t] if t in monthly_first.columns else np.nan
            if pd.isna(price_first):
                continue
            # Amount to buy: base + any bonus from previous month's dip
            buy_amount = base_per_etf + next_bonus[t]
            shares_bought = buy_amount / price_first
            shares[t] += shares_bought
            total_invested += buy_amount

        # After buying, determine if THIS month was down (close < open)
        # to decide bonus for NEXT month
        next_bonus = {t: 0.0 for t in TICKERS}  # reset
        if i < len(months):
            try:
                # Use month-end close
                month_end_idx = monthly_last.index[i] if i < len(monthly_last) else None
                if month_end_idx is not None:
                    for t in TICKERS:
                        p_first = monthly_first.loc[m, t] if t in monthly_first.columns else np.nan
                        p_last = monthly_last.iloc[i][t] if t in monthly_last.columns else np.nan
                        if not pd.isna(p_first) and not pd.isna(p_last):
                            if p_last < p_first:
                                next_bonus[t] = base_per_etf * dip_bonus_pct  # $200 extra next month
                                total_dip_months[t] += 1
            except Exception:
                pass

        # Current portfolio value (using latest close)
        latest_prices = prices.iloc[-1]
        value = sum(shares[t] * latest_prices[t] for t in TICKERS if t in latest_prices.index)
        results.append({
            'month': m,
            'invested_to_date': total_invested,
            'shares_VOLT': shares.get('VOLT', 0),
            'shares_AIPO': shares.get('AIPO', 0),
            'shares_QQQ':  shares.get('QQQ',  0),
        })

    df = pd.DataFrame(results).set_index('month')
    # Add daily portfolio value (mark-to-market with latest prices each day)
    return df, shares, total_invested, total_dip_months

# Use period since AIPO inception
aipo_start = data['AIPO'].first_valid_index()
period = data.loc[aipo_start:]
print(f"AIPO inception: {aipo_start.date()}")
print(f"Backtest period: {aipo_start.date()} to {period.index[-1].date()} "
      f"({(period.index[-1]-period.index[0]).days/30.44:.1f} months)\n")

df_bt, final_shares, total_inv, dip_counts = simulate_dca_with_dip(period)
final_value = sum(final_shares[t] * period.iloc[-1][t] for t in TICKERS)

print("=" * 80)
print(f"REAL BACKTEST: ${1200}/month with Buy-the-Dip 50% rule")
print(f"Period: {aipo_start.date()} to {period.index[-1].date()}")
print("=" * 80)
print(f"Total months invested:        {len(df_bt)}")
print(f"Total invested:               ${total_inv:>12,.2f}")
print(f"Final portfolio value:        ${final_value:>12,.2f}")
print(f"Profit:                       ${final_value-total_inv:>12,.2f}")
print(f"Total return:                 {(final_value/total_inv-1)*100:>12.2f}%")
months_real = len(df_bt)
years_real = months_real / 12
ann = ((final_value / total_inv) ** (1/years_real) - 1) * 100 if years_real > 0 else 0
print(f"Annualized return:            {ann:>12.2f}%")
print()
print("Months each ETF was DOWN (triggering dip-bonus next month):")
for t in TICKERS:
    print(f"  {t}: {dip_counts[t]} / {len(df_bt)} months ({dip_counts[t]/len(df_bt)*100:.0f}%)")
print()

# ============================================================
# 3) FORWARD 5-YEAR PROJECTION (60 months) — multiple scenarios
# ============================================================
print("=" * 80)
print("5-YEAR FORWARD PROJECTION (60 months)")
print("=" * 80)

# Historical "dip frequency" — fraction of months a stock fund closes down
# QQQ historical: ~40% of months are down
DIP_FREQ = 0.40
N_MONTHS = 60
BASE_PER_MONTH = 1200
PER_ETF = BASE_PER_MONTH / 3  # $400

# Average extra investment per month from dip-bonus rule:
# Each ETF independently has 40% chance of being down → triggers $200 next month
# Expected extra per month = 3 ETFs × 0.40 × $200 = $240
expected_total_invested = (BASE_PER_MONTH + 3 * DIP_FREQ * PER_ETF * 0.5) * N_MONTHS

print(f"Base monthly: ${BASE_PER_MONTH} ($400 per ETF × 3 ETFs)")
print(f"Dip bonus: 50% extra to any ETF that closed down last month")
print(f"Assuming ~40% of months an ETF is down (historical avg)")
print(f"Expected avg monthly investment: ${BASE_PER_MONTH + 3*DIP_FREQ*PER_ETF*0.5:.0f}")
print(f"Expected TOTAL invested over 60 months: ${expected_total_invested:>11,.0f}")
print()

# DCA future-value formula with variable contributions is complex,
# so we use a simulation with fixed average annual return per scenario
def simulate_forward(monthly_base, n_months, annual_ret, dip_freq=0.40):
    """Simulate forward DCA with random monthly returns."""
    np.random.seed(42)
    monthly_ret = (1 + annual_ret) ** (1/12) - 1
    monthly_vol = 0.06  # ~21% annual vol assumption per ETF
    portfolio = 0.0
    invested = 0.0
    per_etf = monthly_base / 3
    last_month_down = [False, False, False]
    n_down_months = [0, 0, 0]

    for m in range(n_months):
        # Determine this month's contribution based on last month's signal
        contribution = 0
        for i in range(3):
            bonus = per_etf * 0.5 if last_month_down[i] else 0
            contribution += per_etf + bonus

        invested += contribution
        # Apply this month's random return to existing portfolio + new contribution
        ret = np.random.normal(monthly_ret, monthly_vol)
        portfolio = (portfolio + contribution) * (1 + ret)

        # Determine if "down" this month for each ETF (independent draws)
        last_month_down = [np.random.rand() < dip_freq for _ in range(3)]
        for i in range(3):
            if last_month_down[i]:
                n_down_months[i] += 1
    return invested, portfolio, sum(n_down_months) / 3

scenarios = {
    "Bear (-5%/year)":          -0.05,
    "Pessimistic (5%)":          0.05,
    "Conservative (8%)":         0.08,
    "Base case (12%)":           0.12,
    "Optimistic (18%)":          0.18,
    "Bull (25%)":                0.25,
    "Mania (35%, recent VOLT)":  0.35,
}

# Run Monte Carlo for stable results
N_SIMS = 1000
forward_results = []
print(f"{'Scenario':<28}{'Total Invested':>16}{'Final Value (median)':>22}{'Profit':>14}{'Multiple':>11}")
print("-" * 95)
for name, ann_ret in scenarios.items():
    invs, vals = [], []
    for sim in range(N_SIMS):
        np.random.seed(sim)
        monthly_ret = (1 + ann_ret) ** (1/12) - 1
        monthly_vol = 0.06
        portfolio = 0.0
        invested = 0.0
        per_etf = BASE_PER_MONTH / 3
        last_down = [False, False, False]
        for m in range(N_MONTHS):
            contribution = sum((per_etf + per_etf * 0.5 * (1 if d else 0)) for d in last_down)
            invested += contribution
            ret = np.random.normal(monthly_ret, monthly_vol)
            portfolio = (portfolio + contribution) * (1 + ret)
            last_down = [np.random.rand() < DIP_FREQ for _ in range(3)]
        invs.append(invested)
        vals.append(portfolio)
    med_inv = np.median(invs)
    med_val = np.median(vals)
    profit = med_val - med_inv
    mult = med_val / med_inv if med_inv > 0 else 0
    forward_results.append({
        'Scenario': name, 'Annual': ann_ret,
        'Total Invested': med_inv, 'Final Value': med_val,
        'Profit': profit, 'Multiple': mult,
        'P10 Value': np.percentile(vals, 10), 'P90 Value': np.percentile(vals, 90),
    })
    print(f"{name:<28}${med_inv:>15,.0f}${med_val:>21,.0f}${profit:>13,.0f}{mult:>11.2f}x")

# ============================================================
# 4) Compare with simple DCA (no dip-bonus rule)
# ============================================================
print()
print("=" * 80)
print("COMPARISON: With Dip-Bonus vs. Simple DCA (12% annual scenario)")
print("=" * 80)
def simple_dca(monthly, n_months, ann_ret, vol=0.06):
    np.random.seed(7)
    invs, vals = [], []
    monthly_ret = (1 + ann_ret) ** (1/12) - 1
    for sim in range(N_SIMS):
        np.random.seed(sim)
        portfolio = 0
        invested = 0
        for m in range(n_months):
            invested += monthly
            ret = np.random.normal(monthly_ret, vol)
            portfolio = (portfolio + monthly) * (1 + ret)
        invs.append(invested)
        vals.append(portfolio)
    return np.median(invs), np.median(vals)

inv_simple, val_simple = simple_dca(BASE_PER_MONTH, N_MONTHS, 0.12)
print(f"Simple DCA ($1200/m fixed):    invested ${inv_simple:>10,.0f}  →  ${val_simple:>10,.0f}  "
      f"(profit ${val_simple-inv_simple:,.0f})")
dip_inv = forward_results[3]['Total Invested']
dip_val = forward_results[3]['Final Value']
print(f"With Dip-Bonus rule (avg+):   invested ${dip_inv:>10,.0f}  →  ${dip_val:>10,.0f}  "
      f"(profit ${dip_val-dip_inv:,.0f})")
print()
print(f"Extra capital deployed: ${dip_inv - inv_simple:,.0f}")
print(f"Extra profit generated: ${(dip_val - val_simple):,.0f}")
print(f"ROI on extra capital:   {(dip_val-val_simple)/(dip_inv-inv_simple)*100:.1f}%")

# ============================================================
# 5) PLOTS
# ============================================================
fig, axes = plt.subplots(2, 2, figsize=(15, 10))

# Plot 1: Backtest portfolio value vs invested
ax = axes[0, 0]
months_axis = df_bt.index
# Recompute mark-to-market portfolio value over time
mtm_values = []
mtm_invested = []
shares_iter = {t: 0.0 for t in TICKERS}
inv_iter = 0.0
next_bonus = {t: 0.0 for t in TICKERS}
monthly_first = period.resample('MS').apply(lambda x: x.dropna().iloc[0] if len(x.dropna()) else np.nan)
monthly_last  = period.resample('M').apply(lambda x: x.dropna().iloc[-1] if len(x.dropna()) else np.nan)
for i, m in enumerate(monthly_first.index):
    for t in TICKERS:
        p = monthly_first.loc[m, t]
        if not pd.isna(p):
            buy_amt = PER_ETF + next_bonus[t]
            shares_iter[t] += buy_amt / p
            inv_iter += buy_amt
    # Compute next month's bonus (based on this month's performance)
    next_bonus = {t: 0.0 for t in TICKERS}
    if i < len(monthly_last):
        for t in TICKERS:
            p_first = monthly_first.loc[m, t]
            p_last = monthly_last.iloc[i][t] if i < len(monthly_last) else np.nan
            if not pd.isna(p_first) and not pd.isna(p_last) and p_last < p_first:
                next_bonus[t] = PER_ETF * 0.5
    # Mark to market at end of month
    if i < len(monthly_last):
        mtm = sum(shares_iter[t] * monthly_last.iloc[i][t] for t in TICKERS if t in monthly_last.columns and not pd.isna(monthly_last.iloc[i][t]))
        mtm_values.append(mtm)
        mtm_invested.append(inv_iter)

ax.plot(monthly_last.index[:len(mtm_values)], mtm_invested, label='Total Invested', color='gray', linewidth=2, linestyle='--')
ax.plot(monthly_last.index[:len(mtm_values)], mtm_values, label='Portfolio Value', color='#27AE60', linewidth=2.5)
ax.fill_between(monthly_last.index[:len(mtm_values)], mtm_invested, mtm_values, alpha=0.2, color='#27AE60')
ax.set_title(f'Backtest: $1200/month + Dip-Bonus 50% Rule\n'
             f'(Since AIPO inception, {(period.index[-1]-aipo_start).days/30.44:.0f} months)',
             fontsize=11, fontweight='bold')
ax.set_ylabel('USD')
ax.legend()
ax.grid(alpha=0.3)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x/1000:.0f}K'))

# Plot 2: 5-year forward scenarios
ax = axes[0, 1]
names = [r['Scenario'].split(' (')[0] for r in forward_results]
invested_arr = [r['Total Invested'] for r in forward_results]
values_arr = [r['Final Value'] for r in forward_results]
x = np.arange(len(names))
ax.bar(x, invested_arr, label='Total Invested', color='#7F8C8D', alpha=0.7)
ax.bar(x, [v - i for v, i in zip(values_arr, invested_arr)], bottom=invested_arr,
       label='Profit', color='#27AE60', alpha=0.85)
for i, (inv, val) in enumerate(zip(invested_arr, values_arr)):
    ax.text(i, val + 3000, f'${val/1000:.0f}K', ha='center', fontsize=9, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(names, rotation=30, ha='right', fontsize=9)
ax.set_title('5-Year Forward Projection (Monte Carlo, 1000 sims, median)',
             fontsize=11, fontweight='bold')
ax.set_ylabel('USD')
ax.legend()
ax.grid(alpha=0.3, axis='y')
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x/1000:.0f}K'))

# Plot 3: Confidence interval (P10/P50/P90) at 12% scenario
ax = axes[1, 0]
labels_ci = ['P10\n(Bad luck)', 'P50\n(Median)', 'P90\n(Good luck)']
base_ci = [forward_results[3]['P10 Value'], forward_results[3]['Final Value'], forward_results[3]['P90 Value']]
colors_ci = ['#C0392B', '#27AE60', '#2980B9']
bars = ax.bar(labels_ci, base_ci, color=colors_ci)
ax.axhline(forward_results[3]['Total Invested'], color='red', linestyle='--', label=f'Invested ~${forward_results[3]["Total Invested"]/1000:.1f}K')
for bar, v in zip(bars, base_ci):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2000,
            f'${v:,.0f}', ha='center', fontsize=10, fontweight='bold')
ax.set_title('5-Year Projection Range at 12% Base Case\n(spread reflects volatility)',
             fontsize=11, fontweight='bold')
ax.set_ylabel('Final Value (USD)')
ax.legend()
ax.grid(alpha=0.3, axis='y')
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x/1000:.0f}K'))

# Plot 4: Comparison Dip vs Simple DCA
ax = axes[1, 1]
strategies_compare = ['Simple DCA\n($1,200 fixed)', 'With Dip-Bonus\n(+50% after dip)']
inv_vals = [inv_simple, dip_inv]
final_vals = [val_simple, dip_val]
profit_vals = [v - i for v, i in zip(final_vals, inv_vals)]
x = np.arange(len(strategies_compare))
w = 0.35
ax.bar(x - w/2, inv_vals, w, label='Invested', color='#7F8C8D')
ax.bar(x + w/2, final_vals, w, label='Final Value', color='#27AE60')
for i, (inv, val) in enumerate(zip(inv_vals, final_vals)):
    ax.text(i - w/2, inv + 1500, f'${inv/1000:.0f}K', ha='center', fontsize=9)
    ax.text(i + w/2, val + 1500, f'${val/1000:.0f}K', ha='center', fontsize=9, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(strategies_compare)
ax.set_title('Strategy Comparison @ 12% scenario',
             fontsize=11, fontweight='bold')
ax.set_ylabel('USD')
ax.legend()
ax.grid(alpha=0.3, axis='y')
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x/1000:.0f}K'))

plt.tight_layout()
plt.savefig("/projects/sandbox/MING/dca_dip_strategy.png", dpi=130)
plt.close()
print("\nSaved chart: dca_dip_strategy.png")

# ============================================================
# 6) EXPORT
# ============================================================
out_path = "/projects/sandbox/MING/DCA_Dip_Strategy.xlsx"
with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
    pd.DataFrame(forward_results).to_excel(writer, sheet_name='5Y Forward Projection', index=False)
    summary = pd.DataFrame([{
        'Strategy': 'VOLT+AIPO+QQQ DCA + Dip 50%',
        'Period (real backtest)': f'{aipo_start.date()} to {period.index[-1].date()}',
        'Months': len(df_bt),
        'Total Invested': total_inv,
        'Final Value': final_value,
        'Profit': final_value - total_inv,
        'Total Return %': (final_value/total_inv-1)*100,
        'Annualized %': ann,
    }])
    summary.to_excel(writer, sheet_name='Real Backtest', index=False)
print(f"Saved Excel: {out_path}")
