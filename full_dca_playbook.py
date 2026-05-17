"""
完整定投策略手册:
1) 60 个月月度执行表
2) 蒙特卡洛模拟（10000 次）+ 概率分布图
3) 熊市应急预案规则模拟
4) Roth IRA + 普通账户最优拆分
"""
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from datetime import datetime
import calendar

plt.rcParams['font.sans-serif'] = ['DejaVu Sans']

OUT = "/projects/sandbox/MING"
np.random.seed(42)

# ============================================================
# 0) GLOBAL PARAMETERS
# ============================================================
TICKERS = ["VOLT", "AIPO", "QQQ"]
BASE_MONTHLY = 1200            # $1,200/月
PER_ETF = BASE_MONTHLY / 3     # $400 each
DIP_BONUS = 0.50               # 跌后下月加 50%
N_MONTHS = 60                  # 5 年
DIP_FREQ_PER_ETF = 0.40        # 单只 ETF 每月有 40% 概率收阴

# ============================================================
# 1) 60 个月月度执行表
# ============================================================
print("="*80)
print("  1) 60 个月月度执行表 (基于历史回测真实价格)")
print("="*80)

print("Downloading...")
data = yf.download(TICKERS, start="2020-01-01", auto_adjust=True, progress=False)["Close"]
aipo_start = data["AIPO"].first_valid_index()
period = data.loc[aipo_start:].copy()

monthly_open  = period.resample('MS').apply(lambda s: s.dropna().iloc[0]  if len(s.dropna()) else np.nan)
monthly_close = period.resample('ME').apply(lambda s: s.dropna().iloc[-1] if len(s.dropna()) else np.nan)
monthly_high  = period.resample('ME').max()
monthly_low   = period.resample('ME').min()

# 用真实价格生成 11 个月 + 49 个月模拟，凑 60 个月
schedule = []
shares = {t:0.0 for t in TICKERS}
last_down = {t:False for t in TICKERS}
total_inv = 0.0

# 真实回测部分（10 个月）
for i, m in enumerate(monthly_open.index):
    row = {"month": m.strftime("%Y-%m")}
    monthly_total = 0
    for t in TICKERS:
        p_open = monthly_open.loc[m, t]
        if pd.isna(p_open):
            row[f"{t}_buy"] = 0
            continue
        bonus = PER_ETF * DIP_BONUS if last_down[t] else 0
        amount = PER_ETF + bonus
        sh = amount / p_open
        shares[t] += sh
        row[f"{t}_buy"] = amount
        row[f"{t}_price"] = round(p_open, 2)
        monthly_total += amount
    row["total"] = monthly_total
    total_inv += monthly_total
    row["cum_invested"] = total_inv
    
    # update last_down
    if i < len(monthly_close):
        for t in TICKERS:
            p_o = monthly_open.loc[m, t]
            p_c = monthly_close.iloc[i][t] if t in monthly_close.columns else np.nan
            if not pd.isna(p_o) and not pd.isna(p_c):
                last_down[t] = p_c < p_o
    
    # 当前组合价值
    latest = period.iloc[-1]
    cur_value = sum(shares[t] * latest[t] for t in TICKERS if not pd.isna(latest[t]))
    row["mtm_value"] = round(cur_value, 0)
    schedule.append(row)

real_months = len(schedule)
print(f"已经过去的真实月份: {real_months}")

# 模拟剩余月份
np.random.seed(123)
mu_m = (1 + 0.12) ** (1/12) - 1   # 12% 年化基准
vol_m = 0.06                      # 月波动 6%
last_prices = {t: period.iloc[-1][t] for t in TICKERS}
sim_prices = dict(last_prices)

for i in range(N_MONTHS - real_months):
    month_label = (period.index[-1] + pd.DateOffset(months=i+1)).strftime("%Y-%m") + " (模拟)"
    row = {"month": month_label}
    monthly_total = 0
    for t in TICKERS:
        # 月初价
        p_open = sim_prices[t]
        bonus = PER_ETF * DIP_BONUS if last_down[t] else 0
        amount = PER_ETF + bonus
        sh = amount / p_open
        shares[t] += sh
        row[f"{t}_buy"] = round(amount, 0)
        row[f"{t}_price"] = round(p_open, 2)
        monthly_total += amount
        # 月末价（随机生成）
        ret = np.random.normal(mu_m, vol_m)
        p_close = p_open * (1 + ret)
        last_down[t] = p_close < p_open
        sim_prices[t] = p_close
    row["total"] = monthly_total
    total_inv += monthly_total
    row["cum_invested"] = total_inv
    cur_value = sum(shares[t] * sim_prices[t] for t in TICKERS)
    row["mtm_value"] = round(cur_value, 0)
    schedule.append(row)

schedule_df = pd.DataFrame(schedule)
print(f"\n总投入 (60 个月): ${total_inv:,.0f}")
print(f"模拟最终价值: ${cur_value:,.0f}")
print(f"模拟净盈利: ${cur_value-total_inv:,.0f}")
print(f"模拟回报率: {(cur_value/total_inv-1)*100:.1f}%")

print("\n📋 前 12 个月示例:")
print(schedule_df.head(12).to_string(index=False))

# ============================================================
# 2) 蒙特卡洛模拟 - 10000 次
# ============================================================
print("\n" + "="*80)
print("  2) 蒙特卡洛模拟 10,000 次 - 5 年回报概率分布")
print("="*80)

def monte_carlo(annual_ret, annual_vol_etf=0.21, n_sims=10000, seed_offset=0):
    """蒙特卡洛模拟"""
    monthly_ret = (1 + annual_ret) ** (1/12) - 1
    monthly_vol = annual_vol_etf / np.sqrt(12)
    
    final_values = []
    final_invests = []
    
    for sim in range(n_sims):
        np.random.seed(sim + seed_offset)
        portfolio = 0.0
        invested = 0.0
        last_down_sim = [False, False, False]
        
        for m in range(N_MONTHS):
            # 该月投入（含加仓）
            month_contrib = sum(PER_ETF * (1 + DIP_BONUS * (1 if d else 0)) for d in last_down_sim)
            invested += month_contrib
            
            # 模拟该月组合回报（3 只 ETF 各自独立但相关性 0.6）
            ret_common = np.random.normal(monthly_ret, monthly_vol * 0.6)
            ret_idio = [np.random.normal(0, monthly_vol * 0.4) for _ in range(3)]
            etf_rets = [ret_common + r for r in ret_idio]
            
            # 组合等权回报
            port_ret = np.mean(etf_rets)
            portfolio = (portfolio + month_contrib) * (1 + port_ret)
            
            # 下月触发加仓的判断
            last_down_sim = [r < 0 for r in etf_rets]
        
        final_values.append(portfolio)
        final_invests.append(invested)
    
    return np.array(final_values), np.array(final_invests)

scenarios_mc = {
    "悲观 (5%)":    0.05,
    "保守 (8%)":    0.08,
    "基准 (12%)":   0.12,
    "乐观 (18%)":   0.18,
    "牛市 (25%)":   0.25,
}

mc_results = {}
print(f"{'场景':<15}{'P5':>10}{'P25':>10}{'P50':>11}{'P75':>11}{'P95':>11}{'破发概率':>14}")
print("-"*80)
for name, ret in scenarios_mc.items():
    vals, invs = monte_carlo(ret, n_sims=10000)
    profits = vals - invs
    p5, p25, p50, p75, p95 = np.percentile(vals, [5, 25, 50, 75, 95])
    loss_prob = (profits < 0).sum() / len(profits) * 100
    mc_results[name] = {'vals':vals, 'invs':invs, 'p5':p5, 'p25':p25, 'p50':p50, 'p75':p75, 'p95':p95, 'loss_prob':loss_prob}
    print(f"{name:<15}${p5:>9,.0f}${p25:>9,.0f}${p50:>10,.0f}${p75:>10,.0f}${p95:>10,.0f}{loss_prob:>13.1f}%")

# ============================================================
# 3) 熊市应急预案 - 多种规则对比
# ============================================================
print("\n" + "="*80)
print("  3) 熊市应急预案 - 6 种规则在熊市中的表现对比")
print("="*80)

def simulate_with_rules(rule_name, n_sims=5000, ann_ret=0.06, ann_vol=0.25):
    """模拟 5 年（含某段熊市），不同规则"""
    monthly_ret = (1 + ann_ret) ** (1/12) - 1
    monthly_vol = ann_vol / np.sqrt(12)
    
    final_vals = []
    final_invs = []
    
    for sim in range(n_sims):
        np.random.seed(sim + 1000)
        portfolio = 0.0
        invested = 0.0
        last_down = [False, False, False]
        rolling_returns = []  # 12 个月滚动收益
        
        for m in range(N_MONTHS):
            # 计算 12 个月回撤
            twelve_month_ret = np.prod([1+r for r in rolling_returns[-12:]]) - 1 if len(rolling_returns) >= 12 else 0
            
            # 应用规则
            if rule_name == "基础策略":
                contrib = sum(PER_ETF * (1 + DIP_BONUS * d) for d in last_down)
            elif rule_name == "梯度加仓":
                contrib = sum(PER_ETF * (1 + DIP_BONUS * d) for d in last_down)
            elif rule_name == "停止加仓-12M-30%":
                if twelve_month_ret < -0.30:
                    contrib = BASE_MONTHLY  # 暂停加仓，恢复基础
                else:
                    contrib = sum(PER_ETF * (1 + DIP_BONUS * d) for d in last_down)
            elif rule_name == "反向加倍-12M-40%":
                if twelve_month_ret < -0.40:
                    contrib = BASE_MONTHLY * 2  # 反向加倍
                else:
                    contrib = sum(PER_ETF * (1 + DIP_BONUS * d) for d in last_down)
            elif rule_name == "组合规则":
                if twelve_month_ret < -0.40:
                    contrib = BASE_MONTHLY * 2
                elif twelve_month_ret < -0.20:
                    contrib = BASE_MONTHLY  # 暂停加仓
                else:
                    contrib = sum(PER_ETF * (1 + DIP_BONUS * d) for d in last_down)
            elif rule_name == "纯定投":
                contrib = BASE_MONTHLY
            
            invested += contrib
            ret_common = np.random.normal(monthly_ret, monthly_vol * 0.6)
            ret_idio = [np.random.normal(0, monthly_vol * 0.4) for _ in range(3)]
            etf_rets = [ret_common + r for r in ret_idio]
            port_ret = np.mean(etf_rets)
            portfolio = (portfolio + contrib) * (1 + port_ret)
            rolling_returns.append(port_ret)
            last_down = [r < 0 for r in etf_rets]
        
        final_vals.append(portfolio)
        final_invs.append(invested)
    
    return np.array(final_vals), np.array(final_invs)

rules_to_test = [
    "纯定投",
    "基础策略",
    "停止加仓-12M-30%",
    "反向加倍-12M-40%",
    "组合规则",
]

print(f"\n场景: 平均 6% 年化 + 25% 波动率（含熊市）")
print(f"{'规则':<22}{'总投入(中位数)':>16}{'最终值(中位数)':>17}{'净收益':>13}{'破发概率':>11}")
print("-"*82)
rule_results = {}
for rule in rules_to_test:
    vals, invs = simulate_with_rules(rule, n_sims=3000, ann_ret=0.06, ann_vol=0.25)
    profits = vals - invs
    rule_results[rule] = {
        'invs': invs, 'vals': vals,
        'med_inv': np.median(invs),
        'med_val': np.median(vals),
        'med_profit': np.median(profits),
        'loss_prob': (profits < 0).sum() / len(profits) * 100,
    }
    r = rule_results[rule]
    print(f"{rule:<22}${r['med_inv']:>15,.0f}${r['med_val']:>16,.0f}${r['med_profit']:>12,.0f}{r['loss_prob']:>10.1f}%")

# ============================================================
# 4) Roth IRA + 普通账户最优拆分
# ============================================================
print("\n" + "="*80)
print("  4) Roth IRA + 普通账户最优拆分 - 5 年税后回报对比")
print("="*80)

# 假设
LTCG = 0.15            # 长期资本利得税率（多数中产）
DIVIDEND_TAX = 0.15    # 合格股息税率
ROTH_LIMIT_2026 = 7000 # Roth IRA 2026 年度上限

# 4 种策略
def split_scenarios(annual_ret=0.12, n_sims=5000):
    monthly_ret = (1+annual_ret)**(1/12)-1
    monthly_vol = 0.06
    
    # 平均每月预期投入（含加仓）
    avg_monthly = BASE_MONTHLY + 3 * DIP_FREQ_PER_ETF * PER_ETF * DIP_BONUS  # ~$1440
    annual_total = avg_monthly * 12  # ~$17280
    
    strategies = {}
    
    # 策略 A: 全部放普通账户
    strategies['A_全普通'] = {
        'roth_share': 0.0,
        'desc': '简单粗暴，全在普通券商账户',
    }
    # 策略 B: 优先填满 Roth，剩下放普通
    strategies['B_优先Roth'] = {
        'roth_share': ROTH_LIMIT_2026 / annual_total,  # 约 40%
        'desc': '每年先放满 Roth IRA $7000，剩下放普通',
    }
    # 策略 C: 全部 Roth（仅当年投入 < $7000 时可行）
    strategies['C_全Roth'] = {
        'roth_share': 1.0,
        'desc': '全部塞进 Roth（前提：你年度总额 ≤ $7000）',
    }
    
    results = {}
    for name, cfg in strategies.items():
        roth_pct = cfg['roth_share']
        roth_finals = []
        taxable_finals = []
        roth_invs = []
        taxable_invs = []
        
        for sim in range(n_sims):
            np.random.seed(sim + 5000)
            roth_port = 0
            tax_port = 0
            roth_inv = 0
            tax_inv = 0
            tax_basis = 0  # 普通账户的成本基础
            
            for m in range(N_MONTHS):
                contrib_total = avg_monthly  # 简化：用平均月投入
                roth_part = contrib_total * roth_pct
                tax_part = contrib_total * (1 - roth_pct)
                
                # 注意 Roth 年度上限（每 12 个月重置）
                if m % 12 == 0:
                    roth_year_used = 0
                year_remaining = max(0, ROTH_LIMIT_2026 - roth_year_used)
                roth_part = min(roth_part, year_remaining)
                roth_year_used += roth_part
                tax_part = contrib_total - roth_part  # 超额部分进普通
                
                roth_inv += roth_part
                tax_inv += tax_part
                tax_basis += tax_part
                
                ret = np.random.normal(monthly_ret, monthly_vol)
                roth_port = (roth_port + roth_part) * (1 + ret)
                tax_port = (tax_port + tax_part) * (1 + ret)
            
            # Roth 取出免税
            # 普通账户卖出要交资本利得税
            tax_gain = tax_port - tax_basis
            tax_owed = tax_gain * LTCG if tax_gain > 0 else 0
            tax_after = tax_port - tax_owed
            
            roth_finals.append(roth_port)
            taxable_finals.append(tax_after)
            roth_invs.append(roth_inv)
            taxable_invs.append(tax_inv)
        
        roth_finals = np.array(roth_finals)
        taxable_finals = np.array(taxable_finals)
        total_after_tax = roth_finals + taxable_finals
        total_inv = np.array(roth_invs) + np.array(taxable_invs)
        
        results[name] = {
            'desc': cfg['desc'],
            'roth_share': roth_pct,
            'med_roth_inv': np.median(roth_invs),
            'med_tax_inv': np.median(taxable_invs),
            'med_total_inv': np.median(total_inv),
            'med_roth_final': np.median(roth_finals),
            'med_tax_final_after_tax': np.median(taxable_finals),
            'med_total_after_tax': np.median(total_after_tax),
            'med_profit_after_tax': np.median(total_after_tax - total_inv),
        }
    
    return results

split_res = split_scenarios(annual_ret=0.12)

print(f"\n基准 12% 年化场景，每月平均投入 ~$1,440 (含加仓)，5 年共 ~$86,400")
print(f"假设 LTCG 税率: 15%, Roth IRA 年度上限: $7,000\n")
print(f"{'策略':<18}{'Roth占比':>10}{'Roth投入':>11}{'普通投入':>11}{'总税后':>14}{'净收益(税后)':>15}")
print("-"*80)
for name, r in split_res.items():
    print(f"{name:<18}{r['roth_share']*100:>9.0f}%${r['med_roth_inv']:>10,.0f}${r['med_tax_inv']:>10,.0f}${r['med_total_after_tax']:>13,.0f}${r['med_profit_after_tax']:>14,.0f}")

# 计算优先 Roth 节省的税
extra_after_tax = split_res['B_优先Roth']['med_total_after_tax'] - split_res['A_全普通']['med_total_after_tax']
print(f"\n💰 优先 Roth 比纯普通账户多赚: ${extra_after_tax:,.0f} (税后)")

# ============================================================
# 5) 大图：4 宫格综合
# ============================================================
fig = plt.figure(figsize=(16, 11))
gs = fig.add_gridspec(2, 2, hspace=0.35, wspace=0.28)

# Plot 1: 蒙特卡洛分布 - 12% 基准场景
ax1 = fig.add_subplot(gs[0, 0])
vals_base = mc_results['基准 (12%)']['vals']
ax1.hist(vals_base, bins=60, color='#27AE60', alpha=0.7, edgecolor='white')
ax1.axvline(np.median(vals_base), color='black', linestyle='--', linewidth=2, label=f"Median: ${np.median(vals_base):,.0f}")
ax1.axvline(86200, color='red', linestyle='--', linewidth=2, label='Total Invested: $86,200')
ax1.axvline(np.percentile(vals_base, 5), color='orange', linestyle=':', label=f"P5: ${np.percentile(vals_base,5):,.0f}")
ax1.axvline(np.percentile(vals_base, 95), color='blue', linestyle=':', label=f"P95: ${np.percentile(vals_base,95):,.0f}")
ax1.set_title("Monte Carlo: 5Y Final Value @ 12% scenario\n(10,000 simulations)", fontsize=11, fontweight='bold')
ax1.set_xlabel("Final Portfolio Value ($)")
ax1.set_ylabel("Frequency")
ax1.legend(fontsize=9)
ax1.grid(alpha=0.3)
ax1.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x/1000:.0f}K'))

# Plot 2: 5 个场景的概率箱线图
ax2 = fig.add_subplot(gs[0, 1])
all_data = [mc_results[n]['vals'] for n in scenarios_mc.keys()]
bp = ax2.boxplot(all_data, labels=list(scenarios_mc.keys()), patch_artist=True, showmeans=True)
colors_bp = ['#E74C3C', '#E67E22', '#F1C40F', '#27AE60', '#2980B9']
for patch, c in zip(bp['boxes'], colors_bp):
    patch.set_facecolor(c)
    patch.set_alpha(0.7)
ax2.axhline(86200, color='red', linestyle='--', linewidth=2, label='Total Invested $86,200')
ax2.set_title("5Y Final Value Distribution by Scenario\n(P5/P25/P50/P75/P95 box)", fontsize=11, fontweight='bold')
ax2.set_ylabel("Final Value ($)")
ax2.legend()
ax2.grid(alpha=0.3, axis='y')
ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x/1000:.0f}K'))
plt.setp(ax2.get_xticklabels(), rotation=20, ha='right', fontsize=9)

# Plot 3: 6 种规则对比
ax3 = fig.add_subplot(gs[1, 0])
names_r = list(rule_results.keys())
profits_med = [rule_results[r]['med_profit'] for r in names_r]
loss_probs = [rule_results[r]['loss_prob'] for r in names_r]
colors_r = ['#95A5A6', '#3498DB', '#F39C12', '#E74C3C', '#27AE60']
y_pos = np.arange(len(names_r))
bars = ax3.barh(y_pos, profits_med, color=colors_r)
for bar, p, lp in zip(bars, profits_med, loss_probs):
    ax3.text(bar.get_width() + 500, bar.get_y() + bar.get_height()/2,
             f"${p:,.0f} (loss={lp:.1f}%)", va='center', fontsize=9)
ax3.set_yticks(y_pos)
ax3.set_yticklabels(names_r)
ax3.set_xlabel("5Y Median Net Profit ($)")
ax3.set_title("Bear Market Rules Compared\n(@ 6% avg + 25% vol scenario)", fontsize=11, fontweight='bold')
ax3.grid(alpha=0.3, axis='x')
ax3.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x/1000:.0f}K'))

# Plot 4: Roth vs 普通账户
ax4 = fig.add_subplot(gs[1, 1])
strats = list(split_res.keys())
totals = [split_res[s]['med_total_after_tax'] for s in strats]
profits_split = [split_res[s]['med_profit_after_tax'] for s in strats]
invs_split = [split_res[s]['med_total_inv'] for s in strats]
x = np.arange(len(strats))
w = 0.35
ax4.bar(x - w/2, invs_split, w, label='Total Invested', color='#7F8C8D')
ax4.bar(x + w/2, totals, w, label='Final After-Tax', color='#9B59B6')
for i, (inv, tot) in enumerate(zip(invs_split, totals)):
    ax4.text(i - w/2, inv + 1500, f'${inv/1000:.0f}K', ha='center', fontsize=9)
    ax4.text(i + w/2, tot + 1500, f'${tot/1000:.0f}K', ha='center', fontsize=9, fontweight='bold')
ax4.set_xticks(x)
ax4.set_xticklabels(['全普通账户', '优先 Roth', '全 Roth'], fontsize=10)
ax4.set_title("Roth vs Taxable Account Split (12% scenario, after tax)", fontsize=11, fontweight='bold')
ax4.set_ylabel("USD")
ax4.legend()
ax4.grid(alpha=0.3, axis='y')
ax4.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x/1000:.0f}K'))

plt.suptitle("VOLT + AIPO + QQQ 5-Year DCA + Dip-Bonus Strategy: Full Analysis",
             fontsize=14, fontweight='bold', y=1.00)
plt.savefig(f"{OUT}/dca_full_playbook.png", dpi=130, bbox_inches='tight')
plt.close()
print(f"\n✅ Saved: {OUT}/dca_full_playbook.png")

# ============================================================
# 6) 导出 Excel - 月度执行表
# ============================================================
out_path = f"{OUT}/DCA_5Year_Playbook.xlsx"
with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
    # Sheet 1: 60 个月执行表
    schedule_df.to_excel(writer, sheet_name='60-Month Schedule', index=False)
    
    # Sheet 2: 蒙特卡洛分布
    mc_summary = []
    for name, r in mc_results.items():
        mc_summary.append({
            'Scenario': name,
            'P5': r['p5'], 'P25': r['p25'], 'P50_Median': r['p50'], 'P75': r['p75'], 'P95': r['p95'],
            'Loss_Probability_%': r['loss_prob'],
        })
    pd.DataFrame(mc_summary).to_excel(writer, sheet_name='Monte Carlo Distribution', index=False)
    
    # Sheet 3: 熊市应急规则对比
    rule_summary = pd.DataFrame([{
        'Rule': r,
        'Median_Invested': rule_results[r]['med_inv'],
        'Median_Final_Value': rule_results[r]['med_val'],
        'Median_Net_Profit': rule_results[r]['med_profit'],
        'Loss_Probability_%': rule_results[r]['loss_prob'],
    } for r in rule_results])
    rule_summary.to_excel(writer, sheet_name='Bear Market Rules', index=False)
    
    # Sheet 4: Roth vs 普通账户
    split_summary = pd.DataFrame([{
        'Strategy': k,
        'Description': v['desc'],
        'Roth_Share_%': v['roth_share']*100,
        'Roth_Invested': v['med_roth_inv'],
        'Taxable_Invested': v['med_tax_inv'],
        'Total_Invested': v['med_total_inv'],
        'Final_After_Tax': v['med_total_after_tax'],
        'Net_Profit_After_Tax': v['med_profit_after_tax'],
    } for k, v in split_res.items()])
    split_summary.to_excel(writer, sheet_name='Roth vs Taxable', index=False)

print(f"✅ Saved Excel: {out_path}")
print("\n🎉 全部完成!")
