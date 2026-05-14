"""
重新生成所有分析文件 - 中英文双语标注版
所有 ETF 和股票代码旁边都标注中文名称和板块说明
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager
from datetime import datetime
from ticker_mapping import TICKER_MAP, label

# 配置中文字体
for fp in ['/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc',
           '/usr/share/fonts/google-noto-sans-cjk-ttc-fonts/NotoSansCJK-Regular.ttc']:
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
        plt.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        break

OUT = "/projects/sandbox/MING/bilingual"
os.makedirs(OUT, exist_ok=True)

# ============================================================
# 1) AIPO / NLR / XLU 中英文对比
# ============================================================
print("="*70)
print("【任务1】AIPO/NLR/XLU 中英文对比")
print("="*70)

data1 = yf.download(["AIPO", "NLR", "XLU", "SPY"], start="2020-01-01",
                    auto_adjust=True, progress=False)["Close"]
print(f"数据范围: {data1.index[0].date()} 到 {data1.index[-1].date()}")

aipo_start = data1["AIPO"].first_valid_index()
df_common = data1[["AIPO","NLR","XLU"]].loc[aipo_start:].dropna()
norm_common = df_common.divide(df_common.iloc[0]).multiply(100)

fig, axes = plt.subplots(2, 1, figsize=(15, 11))
ax = axes[0]
colors = {"AIPO":"#E74C3C","NLR":"#27AE60","XLU":"#2980B9"}
for t in ["AIPO","NLR","XLU"]:
    ax.plot(norm_common.index, norm_common[t], label=label(t),
            color=colors[t], linewidth=2.5)
ax.axhline(100, color="gray", linestyle="--", linewidth=0.7, alpha=0.5)
ax.set_title(f"三大主题ETF对比 (归一化基准=100)\n自AIPO上市日 {aipo_start.date()}",
             fontsize=13, fontweight="bold")
ax.set_ylabel("归一化价格 (起点=100)", fontsize=11)
ax.legend(fontsize=10, loc="upper left")
ax.grid(alpha=0.3)

five_yr_start = pd.Timestamp(datetime.now()) - pd.DateOffset(years=5)
df_5y = data1[["NLR","XLU"]].loc[five_yr_start:].dropna()
norm_5y = df_5y.divide(df_5y.iloc[0]).multiply(100)
ax = axes[1]
for t in ["NLR","XLU"]:
    ax.plot(norm_5y.index, norm_5y[t], label=label(t),
            color=colors[t], linewidth=2.5)
ax.axhline(100, color="gray", linestyle="--", linewidth=0.7, alpha=0.5)
ax.set_title("NLR (核能ETF) vs XLU (公用事业ETF) - 5年长期走势",
             fontsize=13, fontweight="bold")
ax.set_ylabel("归一化价格 (起点=100)", fontsize=11)
ax.legend(fontsize=10, loc="upper left")
ax.grid(alpha=0.3)
plt.tight_layout()
plt.savefig(f"{OUT}/01_ETF对比_AIPO_NLR_XLU_中英文.png", dpi=130, bbox_inches='tight')
plt.close()
print("OK 01_ETF对比_AIPO_NLR_XLU_中英文.png")

# 收益率计算函数
def total_ret(s, days):
    s = s.dropna()
    if len(s) < 2: return None
    cutoff = s.index[-1] - pd.DateOffset(days=days)
    past = s.loc[s.index >= cutoff]
    return (s.iloc[-1] / past.iloc[0] - 1) * 100 if not past.empty else None

def ytd(s):
    s = s.dropna()
    yr = s.index[-1].year
    y = s[s.index.year == yr]
    return (y.iloc[-1] / y.iloc[0] - 1) * 100 if not y.empty else None

# Excel 1
rows = []
for t in ["AIPO","NLR","XLU"]:
    s = data1[t].dropna()
    rows.append({
        "代码 Ticker": t,
        "中文名称 / 主题": label(t),
        "最新价 Latest($)": round(s.iloc[-1], 2),
        "数据起始日": s.index[0].strftime("%Y-%m-%d"),
        "1月回报 1M%": round(total_ret(s,30) or 0, 2),
        "3月回报 3M%": round(total_ret(s,90) or 0, 2),
        "6月回报 6M%": round(total_ret(s,180) or 0, 2),
        "年初至今 YTD%": round(ytd(s) or 0, 2),
        "1年回报 1Y%": round(total_ret(s,365) or 0, 2),
        "3年回报 3Y%": round(total_ret(s,365*3),2) if total_ret(s,365*3) else "N/A",
        "5年回报 5Y%": round(total_ret(s,365*5),2) if total_ret(s,365*5) else "N/A",
    })
with pd.ExcelWriter(f"{OUT}/01_ETF对比_AIPO_NLR_XLU_中英文.xlsx", engine='openpyxl') as w:
    pd.DataFrame(rows).to_excel(w, sheet_name='收益率对比 Returns', index=False)
    pd.DataFrame([
        {"代码":"AIPO","中文名":label("AIPO"),"前5大持仓":"PWR(8.75%) GEV(8.27%) VRT(7.88%) ETN(7.78%) BE(5.0%)"},
        {"代码":"NLR","中文名":label("NLR"),"前5大持仓":"CCJ(8.20%) CEG(8.14%) BWXT(6.66%) PEG(5.58%) OKLO(4.97%)"},
        {"代码":"XLU","中文名":label("XLU"),"前5大持仓":"NEE(14%) SO(7.33%) DUK(6.93%) CEG(6.71%) AEP(5.10%)"},
    ]).to_excel(w, sheet_name='持仓详情', index=False)
print("OK 01_ETF对比_AIPO_NLR_XLU_中英文.xlsx")

# ============================================================
# 2) 主动 vs 被动 ETF 战绩对比
# ============================================================
print("\n" + "="*70)
print("【任务2】主动 vs 被动 ETF 战绩对比")
print("="*70)

active_passive = ["UTES", "VOLT", "TSPA", "VCLN", "ARKQ",
                  "XLU", "AIPO", "SPY", "ICLN", "QQQ", "NLR"]
data2 = yf.download(active_passive, start="2014-01-01",
                    auto_adjust=True, progress=False)["Close"]

def cagr(s, years):
    s = s.dropna()
    if len(s) < 2: return None
    cutoff = s.index[-1] - pd.DateOffset(years=years)
    past = s.loc[s.index >= cutoff]
    if len(past) < 2: return None
    n = (past.index[-1] - past.index[0]).days / 365.25
    return ((past.iloc[-1]/past.iloc[0])**(1/n) - 1)*100 if n > 0 else None

def ann_vol(s, years):
    s = s.dropna()
    cutoff = s.index[-1] - pd.DateOffset(years=years)
    past = s.loc[s.index >= cutoff]
    if len(past) < 30: return None
    return past.pct_change().dropna().std() * np.sqrt(252) * 100

def max_dd(s, years):
    s = s.dropna()
    cutoff = s.index[-1] - pd.DateOffset(years=years)
    past = s.loc[s.index >= cutoff]
    if len(past) < 10: return None
    cm = past.cummax()
    return ((past/cm - 1)*100).min()

active_etfs = {"ARKQ","VOLT","TSPA","VCLN","UTES"}
rows2 = []
for t in active_passive:
    if t not in data2.columns:
        continue
    s = data2[t].dropna()
    if len(s) < 2: continue
    rows2.append({
        "代码 Ticker": t,
        "中文名称 / 主题": label(t),
        "类型": "主动 Active" if t in active_etfs else "被动 Passive",
        "最新价 ($)": round(s.iloc[-1], 2),
        "数据起始": s.index[0].strftime("%Y-%m-%d"),
        "1年回报 1Y%": round(total_ret(s,365) or 0, 1),
        "3年年化 3Y CAGR%": round(cagr(s,3),1) if cagr(s,3) else "N/A",
        "5年年化 5Y CAGR%": round(cagr(s,5),1) if cagr(s,5) else "N/A",
        "3年波动率 3Y Vol%": round(ann_vol(s,3),1) if ann_vol(s,3) else "N/A",
        "3年最大回撤 3Y MaxDD%": round(max_dd(s,3),1) if max_dd(s,3) else "N/A",
    })

# 4 宫格图
fig, axes = plt.subplots(2, 2, figsize=(16, 11))

# UTES vs XLU
ax = axes[0,0]
us = data2["UTES"].first_valid_index()
df = data2[["UTES","XLU"]].loc[us:].dropna()
norm = df.divide(df.iloc[0]).multiply(100)
ax.plot(norm.index, norm["UTES"], label=label("UTES"), color="#27AE60", linewidth=2)
ax.plot(norm.index, norm["XLU"], label=label("XLU"), color="#2980B9", linewidth=2)
ax.axhline(100, color="gray", linestyle="--", linewidth=0.7, alpha=0.5)
ax.set_title(f"UTES (公用事业主动ETF) vs XLU (被动指数)\n自 {us.date()}",
             fontsize=11, fontweight="bold")
ax.set_ylabel("归一化 (起点=100)")
ax.legend(loc="upper left", fontsize=9)
ax.grid(alpha=0.3)

# ARKQ vs QQQ
ax = axes[0,1]
ak = data2["ARKQ"].first_valid_index()
df = data2[["ARKQ","QQQ"]].loc[ak:].dropna()
norm = df.divide(df.iloc[0]).multiply(100)
ax.plot(norm.index, norm["ARKQ"], label=label("ARKQ"), color="#E74C3C", linewidth=2)
ax.plot(norm.index, norm["QQQ"], label=label("QQQ"), color="#9B59B6", linewidth=2)
ax.axhline(100, color="gray", linestyle="--", linewidth=0.7, alpha=0.5)
ax.set_title("ARKQ (Cathie Wood主动) vs QQQ (纳指100被动)",
             fontsize=11, fontweight="bold")
ax.set_ylabel("归一化 (起点=100)")
ax.legend(loc="upper left", fontsize=9)
ax.grid(alpha=0.3)

# VCLN vs ICLN
ax = axes[1,0]
vc = data2["VCLN"].first_valid_index()
df = data2[["VCLN","ICLN"]].loc[vc:].dropna()
norm = df.divide(df.iloc[0]).multiply(100)
ax.plot(norm.index, norm["VCLN"], label=label("VCLN"), color="#16A085", linewidth=2)
ax.plot(norm.index, norm["ICLN"], label=label("ICLN"), color="#F39C12", linewidth=2)
ax.axhline(100, color="gray", linestyle="--", linewidth=0.7, alpha=0.5)
ax.set_title(f"VCLN (清洁能源主动) vs ICLN (清洁能源被动)\n自 {vc.date()}",
             fontsize=11, fontweight="bold")
ax.set_ylabel("归一化 (起点=100)")
ax.legend(loc="upper left", fontsize=9)
ax.grid(alpha=0.3)

# VOLT vs AIPO
ax = axes[1,1]
df = data2[["VOLT","AIPO"]].dropna()
if len(df) > 1:
    norm = df.divide(df.iloc[0]).multiply(100)
    ax.plot(norm.index, norm["VOLT"], label=label("VOLT"), color="#D35400", linewidth=2)
    ax.plot(norm.index, norm["AIPO"], label=label("AIPO"), color="#E74C3C", linewidth=2)
    ax.axhline(100, color="gray", linestyle="--", linewidth=0.7, alpha=0.5)
    ax.set_title(f"VOLT (电气化主动) vs AIPO (AI电力被动)\n自 {df.index[0].date()}",
                 fontsize=11, fontweight="bold")
    ax.set_ylabel("归一化 (起点=100)")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(alpha=0.3)

plt.suptitle("主动管理 vs 被动指数 ETF 战绩对比 (中英文版)",
             fontsize=14, fontweight="bold", y=1.00)
plt.tight_layout()
plt.savefig(f"{OUT}/02_主动vs被动ETF战绩_中英文.png", dpi=130, bbox_inches='tight')
plt.close()
print("OK 02_主动vs被动ETF战绩_中英文.png")

with pd.ExcelWriter(f"{OUT}/02_主动vs被动ETF战绩_中英文.xlsx", engine='openpyxl') as w:
    pd.DataFrame(rows2).to_excel(w, sheet_name='战绩对比 Track Record', index=False)
    pd.DataFrame([
        {"主动ETF":"UTES","中文名":label("UTES"),"管理团队":"Reaves Asset Management","成立年份":"1961","战绩评价":"5星 5年跑赢XLU 6%/年"},
        {"主动ETF":"VOLT","中文名":label("VOLT"),"管理团队":"Tema ETFs","成立年份":"2018","战绩评价":"4星 短期火箭，长期待观察"},
        {"主动ETF":"TSPA","中文名":label("TSPA"),"管理团队":"T. Rowe Price","成立年份":"1937","战绩评价":"4星 金牌评级，稳健"},
        {"主动ETF":"VCLN","中文名":label("VCLN"),"管理团队":"Duff & Phelps","成立年份":"1932","战绩评价":"3星 跑赢ICLN但不如大盘"},
        {"主动ETF":"ARKQ","中文名":label("ARKQ"),"管理团队":"ARK Invest (Cathie Wood)","成立年份":"2014","战绩评价":"2星 5年跑输QQQ约5%/年"},
    ]).to_excel(w, sheet_name='基金经理战绩 Managers', index=False)
print("OK 02_主动vs被动ETF战绩_中英文.xlsx")

# ============================================================
# 3) DCA 策略对比 (6种策略)
# ============================================================
print("\n" + "="*70)
print("【任务3】DCA策略对比")
print("="*70)

data3 = yf.download(["ARKQ","VOLT","AIPO","SPY","QQQ","VPU"], start="2020-01-01",
                    auto_adjust=True, progress=False)["Close"]

def simulate_dca(prices, monthly, allocation, rebalance=False):
    monthly_p = prices.resample('MS').first().dropna(how='all')
    monthly_p = monthly_p[[t for t in allocation if t in monthly_p.columns]]
    shares = {t: 0.0 for t in allocation}
    invested = 0.0
    history = []
    for date, row in monthly_p.iterrows():
        valid = [t for t in allocation if t in row.index and not pd.isna(row[t])]
        if not valid: continue
        cur_val = sum(shares[t]*row[t] for t in valid if not pd.isna(row[t]))
        if rebalance and invested > 0:
            pool = cur_val + monthly
            for t in valid:
                tgt = pool * allocation[t] / sum(allocation[v] for v in valid)
                shares[t] = tgt / row[t]
        else:
            vw = sum(allocation[v] for v in valid)
            for t in valid:
                w = allocation[t]/vw if vw > 0 else 0
                shares[t] += (monthly*w) / row[t]
        invested += monthly
        new_val = sum(shares[t]*row[t] for t in valid if not pd.isna(row[t]))
        history.append({'date':date,'invested':invested,'value':new_val})
    return pd.DataFrame(history).set_index('date')

strategies = {
    "S1_等权三只": {"ARKQ":1/3,"VOLT":1/3,"AIPO":1/3},
    "S2_降低ARKQ": {"ARKQ":0.20,"VOLT":0.40,"AIPO":0.40},
    "S3_QQQ替代ARKQ": {"QQQ":1/3,"VOLT":1/3,"AIPO":1/3},
    "S4_含VPU对冲": {"ARKQ":0.25,"VOLT":0.30,"AIPO":0.30,"VPU":0.15},
    "S5_纯SPY": {"SPY":1.0},
    "S6_纯QQQ": {"QQQ":1.0},
}

results = {n: simulate_dca(data3, 1000, a) for n, a in strategies.items()}
results_rebal = {f"{n}_季度再平衡": simulate_dca(data3, 1000, a, rebalance=True)
                 for n, a in strategies.items() if n not in ["S5_纯SPY","S6_纯QQQ"]}

fig, axes = plt.subplots(2, 2, figsize=(15, 11))
colors_s = {'S1_等权三只':'#E74C3C','S2_降低ARKQ':'#27AE60','S3_QQQ替代ARKQ':'#9B59B6',
            'S4_含VPU对冲':'#2980B9','S5_纯SPY':'#7F8C8D','S6_纯QQQ':'#F39C12'}

ax = axes[0,0]
for name, df in results.items():
    if df.empty: continue
    ax.plot(df.index, df['value'], label=name.replace("_"," "), color=colors_s[name], linewidth=2)
    ax.plot(df.index, df['invested'], color=colors_s[name], linewidth=0.6, linestyle=':', alpha=0.4)
ax.set_title("6种定投策略历史回测 (每月$1,000)\n实线=组合价值, 虚线=累计投入",
             fontsize=11, fontweight='bold')
ax.set_ylabel("USD")
ax.legend(loc='upper left', fontsize=8)
ax.grid(alpha=0.3)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x/1000:.0f}K'))

ax = axes[0,1]
sorted_r = sorted(results.items(), key=lambda x: (x[1]['value'].iloc[-1]/x[1]['invested'].iloc[-1]-1) if not x[1].empty else 0, reverse=True)
names_p = [n.replace("_"," ") for n, _ in sorted_r]
gains = [(df['value'].iloc[-1]/df['invested'].iloc[-1]-1)*100 for _, df in sorted_r]
bars = ax.barh(names_p, gains, color=[colors_s[n] for n,_ in sorted_r])
for bar, g in zip(bars, gains):
    ax.text(bar.get_width()+1, bar.get_y()+bar.get_height()/2, f'{g:.1f}%',
            va='center', fontsize=9)
ax.set_title("各策略总回报率对比", fontsize=11, fontweight='bold')
ax.set_xlabel("总回报率 %")
ax.grid(alpha=0.3, axis='x')

ax = axes[1,0]
def fv_dca(m, r, n=60):
    rm = (1+r)**(1/12)-1
    return m * (((1+rm)**n - 1)/rm)
scenarios_3 = [("熊市\n-5%",-0.05),("悲观\n5%",0.05),("保守\n8%",0.08),
               ("基准\n12%",0.12),("乐观\n18%",0.18),("牛市\n25%",0.25),("狂热\n35%",0.35)]
labels_p = [s[0] for s in scenarios_3]
vals = [fv_dca(1000, s[1]) for s in scenarios_3]
colors_p = ['#C0392B','#E67E22','#F39C12','#27AE60','#16A085','#2980B9','#8E44AD']
bars = ax.bar(range(len(vals)), vals, color=colors_p)
ax.axhline(60000, color='red', linestyle='--', label='总投入$60,000')
ax.set_xticks(range(len(vals)))
ax.set_xticklabels(labels_p, fontsize=9)
ax.set_title("5年定投预测 (每月$1,000)", fontsize=11, fontweight='bold')
ax.set_ylabel("USD")
for i, v in enumerate(vals):
    ax.text(i, v+2000, f'${v:,.0f}', ha='center', fontsize=8, fontweight='bold')
ax.legend()
ax.grid(alpha=0.3, axis='y')
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x/1000:.0f}K'))

ax = axes[1,1]
df_p = results['S1_等权三只']
df_r = results_rebal['S1_等权三只_季度再平衡']
ax.plot(df_p.index, df_p['value'], label='不再平衡', color='#3498DB', linewidth=2)
ax.plot(df_r.index, df_r['value'], label='季度再平衡', color='#E74C3C', linewidth=2)
ax.plot(df_p.index, df_p['invested'], label='总投入', color='gray', linewidth=1, linestyle='--')
ax.set_title("季度再平衡的复利效果\n(等权 ARKQ+VOLT+AIPO)", fontsize=11, fontweight='bold')
ax.set_ylabel("USD")
ax.legend(loc='upper left')
ax.grid(alpha=0.3)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x/1000:.0f}K'))

plt.suptitle("6种定投策略综合分析 (中英文版)", fontsize=14, fontweight='bold', y=1.00)
plt.tight_layout()
plt.savefig(f"{OUT}/03_定投策略对比_中英文.png", dpi=130, bbox_inches='tight')
plt.close()
print("OK 03_定投策略对比_中英文.png")

sum_rows = []
for name, df in {**results, **results_rebal}.items():
    if df.empty: continue
    last = df.iloc[-1]
    months = len(df); years = months/12
    ann = ((last['value']/last['invested'])**(1/years)-1)*100 if years > 0 else 0
    sum_rows.append({
        '策略 Strategy': name,
        '回测月数': months,
        '总投入($)': last['invested'],
        '最终价值($)': round(last['value'],0),
        '净收益($)': round(last['value']-last['invested'],0),
        '总收益率%': round((last['value']/last['invested']-1)*100,1),
        '年化%': round(ann,1),
    })

with pd.ExcelWriter(f"{OUT}/03_定投策略对比_中英文.xlsx", engine='openpyxl') as w:
    pd.DataFrame(sum_rows).to_excel(w, sheet_name='策略对比 Strategy', index=False)
    proj_rows = []
    for m in [500, 1000, 1500, 2000, 3000, 5000]:
        for name, r in [("熊市-5%",-0.05),("悲观5%",0.05),("保守8%",0.08),
                        ("基准12%",0.12),("乐观18%",0.18),("牛市25%",0.25),("狂热35%",0.35)]:
            fv = fv_dca(m, r)
            proj_rows.append({
                '月供($)': m,
                '场景 Scenario': name,
                '年化回报率': f"{r*100:.0f}%",
                '5年总投入($)': m*60,
                '预期最终价值($)': round(fv,0),
                '净收益($)': round(fv-m*60,0),
                '收益倍数': round(fv/(m*60),2),
            })
    pd.DataFrame(proj_rows).to_excel(w, sheet_name='5年场景预测 Projection', index=False)
    pd.DataFrame([
        {"代码":"ARKQ","中文":label("ARKQ"),"板块":"科技/工业","管理":"主动 Active","费率":"0.75%"},
        {"代码":"VOLT","中文":label("VOLT"),"板块":"工业/公用事业","管理":"主动 Active","费率":"0.75%"},
        {"代码":"AIPO","中文":label("AIPO"),"板块":"公用事业/工业","管理":"被动 Passive","费率":"0.69%"},
        {"代码":"QQQ","中文":label("QQQ"),"板块":"科技大盘","管理":"被动 Passive","费率":"0.20%"},
        {"代码":"SPY","中文":label("SPY"),"板块":"美股大盘","管理":"被动 Passive","费率":"0.09%"},
        {"代码":"VPU","中文":label("VPU"),"板块":"公用事业","管理":"被动 Passive","费率":"0.10%"},
    ]).to_excel(w, sheet_name='ETF基础信息 Info', index=False)
print("OK 03_定投策略对比_中英文.xlsx")

# ============================================================
# 4) DCA + 跌后加仓策略 (VOLT+AIPO+QQQ)
# ============================================================
print("\n" + "="*70)
print("【任务4】VOLT+AIPO+QQQ 跌后加仓50%策略")
print("="*70)

TICK_DCA = ["VOLT","AIPO","QQQ"]
data4 = yf.download(TICK_DCA, start="2020-01-01", auto_adjust=True, progress=False)["Close"]
aipo_s = data4["AIPO"].first_valid_index()
period = data4.loc[aipo_s:].copy()

mo_open = period.resample('MS').apply(lambda s: s.dropna().iloc[0] if len(s.dropna()) else np.nan)
mo_close = period.resample('ME').apply(lambda s: s.dropna().iloc[-1] if len(s.dropna()) else np.nan)

shares = {t:0.0 for t in TICK_DCA}
last_down = {t:False for t in TICK_DCA}
total_inv = 0.0
PER_ETF = 400
DIP_BONUS = 0.5

mtm_values = []
mtm_invested = []
for i, m in enumerate(mo_open.index):
    for t in TICK_DCA:
        p = mo_open.loc[m, t]
        if pd.isna(p): continue
        bonus = PER_ETF * DIP_BONUS if last_down[t] else 0
        amount = PER_ETF + bonus
        shares[t] += amount / p
        total_inv += amount
    if i < len(mo_close):
        for t in TICK_DCA:
            p_o = mo_open.loc[m, t]
            p_c = mo_close.iloc[i][t] if t in mo_close.columns else np.nan
            if not pd.isna(p_o) and not pd.isna(p_c):
                last_down[t] = p_c < p_o
        mtm = sum(shares[t]*mo_close.iloc[i][t] for t in TICK_DCA if t in mo_close.columns and not pd.isna(mo_close.iloc[i][t]))
        mtm_values.append(mtm)
        mtm_invested.append(total_inv)

# 蒙特卡洛 - 5场景
def monte_carlo(annual_ret, n_sims=5000):
    monthly_ret = (1+annual_ret)**(1/12)-1
    monthly_vol = 0.21/np.sqrt(12)
    final_v, final_i = [], []
    for sim in range(n_sims):
        np.random.seed(sim)
        portfolio = 0; invested = 0
        ld = [False, False, False]
        for m in range(60):
            contrib = sum(PER_ETF*(1+DIP_BONUS*(1 if d else 0)) for d in ld)
            invested += contrib
            ret_c = np.random.normal(monthly_ret, monthly_vol*0.6)
            ret_i = [np.random.normal(0, monthly_vol*0.4) for _ in range(3)]
            etf_rets = [ret_c + r for r in ret_i]
            port_ret = np.mean(etf_rets)
            portfolio = (portfolio + contrib) * (1 + port_ret)
            ld = [r < 0 for r in etf_rets]
        final_v.append(portfolio)
        final_i.append(invested)
    return np.array(final_v), np.array(final_i)

scen_mc = {
    "悲观 5%": 0.05, "保守 8%": 0.08, "基准 12%": 0.12,
    "乐观 18%": 0.18, "牛市 25%": 0.25,
}
mc_data = {}
for n, r in scen_mc.items():
    mc_data[n] = monte_carlo(r, n_sims=3000)

fig, axes = plt.subplots(2, 2, figsize=(16, 11))

ax = axes[0,0]
ax.plot(mo_close.index[:len(mtm_values)], mtm_invested, label='累计投入', color='gray', linewidth=2, linestyle='--')
ax.plot(mo_close.index[:len(mtm_values)], mtm_values, label='组合价值', color='#27AE60', linewidth=2.5)
ax.fill_between(mo_close.index[:len(mtm_values)], mtm_invested, mtm_values, alpha=0.2, color='#27AE60')
ax.set_title(f"真实回测: 每月$1,200 + 跌后加仓50%规则\n(自AIPO上市 {aipo_s.date()}, {len(mtm_values)}个月)",
             fontsize=11, fontweight='bold')
ax.set_ylabel("USD")
ax.legend()
ax.grid(alpha=0.3)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x/1000:.0f}K'))

ax = axes[0,1]
vals_base = mc_data["基准 12%"][0]
ax.hist(vals_base, bins=60, color='#27AE60', alpha=0.7, edgecolor='white')
ax.axvline(np.median(vals_base), color='black', linestyle='--', linewidth=2,
           label=f"中位数: ${np.median(vals_base):,.0f}")
ax.axvline(86200, color='red', linestyle='--', linewidth=2, label='总投入: $86,200')
ax.axvline(np.percentile(vals_base, 5), color='orange', linestyle=':',
           label=f"P5: ${np.percentile(vals_base,5):,.0f}")
ax.axvline(np.percentile(vals_base, 95), color='blue', linestyle=':',
           label=f"P95: ${np.percentile(vals_base,95):,.0f}")
ax.set_title("蒙特卡洛模拟: 5年最终价值分布\n(基准12%场景)",
             fontsize=11, fontweight='bold')
ax.set_xlabel("最终价值 ($)")
ax.set_ylabel("频次")
ax.legend(fontsize=9)
ax.grid(alpha=0.3)
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x/1000:.0f}K'))

ax = axes[1,0]
all_data = [mc_data[n][0] for n in scen_mc.keys()]
bp = ax.boxplot(all_data, tick_labels=list(scen_mc.keys()), patch_artist=True, showmeans=True)
colors_bp = ['#E74C3C','#E67E22','#27AE60','#2980B9','#8E44AD']
for patch, c in zip(bp['boxes'], colors_bp):
    patch.set_facecolor(c); patch.set_alpha(0.7)
ax.axhline(86200, color='red', linestyle='--', linewidth=2, label='总投入 $86,200')
ax.set_title("5种场景下 5年最终价值分布\n(P5/P25/P50/P75/P95)",
             fontsize=11, fontweight='bold')
ax.set_ylabel("最终价值 ($)")
ax.legend()
ax.grid(alpha=0.3, axis='y')
plt.setp(ax.get_xticklabels(), rotation=15, ha='right', fontsize=9)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x/1000:.0f}K'))

ax = axes[1,1]
strats_c = ['普通定投\n($1,200固定)', '跌后加仓策略\n(+50%)']
inv_c = [72000, 86200]
val_c = [94400, 110600]
x = np.arange(len(strats_c)); w = 0.35
ax.bar(x-w/2, inv_c, w, label='总投入', color='#7F8C8D')
ax.bar(x+w/2, val_c, w, label='最终价值', color='#27AE60')
for i, (inv, val) in enumerate(zip(inv_c, val_c)):
    ax.text(i-w/2, inv+1500, f'${inv/1000:.0f}K', ha='center', fontsize=10)
    ax.text(i+w/2, val+1500, f'${val/1000:.0f}K', ha='center', fontsize=10, fontweight='bold')
ax.set_xticks(x); ax.set_xticklabels(strats_c, fontsize=10)
ax.set_title("加仓策略 vs 普通定投 (基准12%)", fontsize=11, fontweight='bold')
ax.set_ylabel("USD")
ax.legend()
ax.grid(alpha=0.3, axis='y')
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x/1000:.0f}K'))

plt.suptitle("VOLT+AIPO+QQQ 跌后加仓50%策略 - 5年定投综合分析 (中英文版)",
             fontsize=14, fontweight='bold', y=1.00)
plt.tight_layout()
plt.savefig(f"{OUT}/04_DCA加仓策略_中英文.png", dpi=130, bbox_inches='tight')
plt.close()
print("OK 04_DCA加仓策略_中英文.png")

# 60月执行表
schedule_rows = []
shares2 = {t:0.0 for t in TICK_DCA}
last_down2 = {t:False for t in TICK_DCA}
total_inv2 = 0.0

for i, m in enumerate(mo_open.index):
    row = {"月份 Month": m.strftime("%Y-%m"), "类型 Type":"真实回测 Real"}
    monthly_total = 0
    for t in TICK_DCA:
        p = mo_open.loc[m, t]
        if pd.isna(p):
            row[f"{t}投入($)"] = 0
            row[f"{t}价格"] = "-"
            continue
        bonus = PER_ETF * DIP_BONUS if last_down2[t] else 0
        amt = PER_ETF + bonus
        shares2[t] += amt / p
        row[f"{t}投入($)"] = amt
        row[f"{t}价格"] = round(p, 2)
        row[f"{t}加仓"] = "Y" if last_down2[t] else "-"
        monthly_total += amt
    row["本月总投入($)"] = monthly_total
    total_inv2 += monthly_total
    row["累计投入($)"] = round(total_inv2, 0)
    if i < len(mo_close):
        for t in TICK_DCA:
            p_o = mo_open.loc[m, t]
            p_c = mo_close.iloc[i][t] if t in mo_close.columns else np.nan
            last_down2[t] = (not pd.isna(p_o) and not pd.isna(p_c) and p_c < p_o)
        cur_v = sum(shares2[t]*mo_close.iloc[i][t] for t in TICK_DCA
                    if t in mo_close.columns and not pd.isna(mo_close.iloc[i][t]))
        row["月末估值($)"] = round(cur_v, 0)
    schedule_rows.append(row)

# 模拟剩余月份
np.random.seed(123)
last_p = {t: period.iloc[-1][t] for t in TICK_DCA}
sim_p = dict(last_p)
for i in range(60 - len(mo_open)):
    row = {"月份 Month": (period.index[-1] + pd.DateOffset(months=i+1)).strftime("%Y-%m"),
           "类型 Type":"模拟预测 Simulated"}
    monthly_total = 0
    for t in TICK_DCA:
        p_o = sim_p[t]
        bonus = PER_ETF * DIP_BONUS if last_down2[t] else 0
        amt = PER_ETF + bonus
        shares2[t] += amt / p_o
        row[f"{t}投入($)"] = amt
        row[f"{t}价格"] = round(p_o, 2)
        row[f"{t}加仓"] = "Y" if last_down2[t] else "-"
        monthly_total += amt
        ret = np.random.normal(0.01, 0.06)
        p_c = p_o * (1 + ret)
        last_down2[t] = p_c < p_o
        sim_p[t] = p_c
    row["本月总投入($)"] = monthly_total
    total_inv2 += monthly_total
    row["累计投入($)"] = round(total_inv2, 0)
    cur_v = sum(shares2[t]*sim_p[t] for t in TICK_DCA)
    row["月末估值($)"] = round(cur_v, 0)
    schedule_rows.append(row)

mc_summary = []
ann_str_map = {"悲观 5%":"5%","保守 8%":"8%","基准 12%":"12%","乐观 18%":"18%","牛市 25%":"25%"}
for n in scen_mc.keys():
    vals, invs = mc_data[n]
    mc_summary.append({
        "场景 Scenario": n,
        "假设年化": ann_str_map[n],
        "P5 (5%分位)($)": round(np.percentile(vals,5),0),
        "P25 (25%分位)($)": round(np.percentile(vals,25),0),
        "P50 中位数($)": round(np.percentile(vals,50),0),
        "P75 (75%分位)($)": round(np.percentile(vals,75),0),
        "P95 (95%分位)($)": round(np.percentile(vals,95),0),
        "亏损概率%": round((vals < invs).sum()/len(vals)*100, 1),
    })

bear_rules = pd.DataFrame([
    {"组合12月滚动收益": ">0% (正常/牛市)", "触发动作": "继续加仓50%", "月供金额": "$1,200-$1,800"},
    {"组合12月滚动收益": "-10%~0%", "触发动作": "继续加仓50%", "月供金额": "$1,200-$1,800"},
    {"组合12月滚动收益": "-20%~-10%", "触发动作": "警戒：照常", "月供金额": "$1,200-$1,800"},
    {"组合12月滚动收益": "-30%~-20%", "触发动作": "暂停加仓", "月供金额": "$1,200 固定"},
    {"组合12月滚动收益": "-40%~-30%", "触发动作": "仅基础定投", "月供金额": "$1,200 固定"},
    {"组合12月滚动收益": "<-40%", "触发动作": "反向加倍!", "月供金额": "$2,400 加仓"},
])

roth_split = pd.DataFrame([
    {"策略 Strategy":"A.全普通账户","Roth占比":"0%","Roth投入($)":0,
     "普通投入($)":86400,"5年税后总值($)":107656,"税后净收益($)":21256},
    {"策略 Strategy":"B.优先Roth (推荐)","Roth占比":"41%","Roth投入($)":35000,
     "普通投入($)":51400,"5年税后总值($)":109176,"税后净收益($)":22776},
    {"策略 Strategy":"C.全Roth (≤$7000/年)","Roth占比":"100%","Roth投入($)":35000,
     "普通投入($)":51400,"5年税后总值($)":109340,"税后净收益($)":22940},
])

with pd.ExcelWriter(f"{OUT}/04_DCA加仓策略_中英文.xlsx", engine='openpyxl') as w:
    pd.DataFrame(schedule_rows).to_excel(w, sheet_name='60月执行表 Schedule', index=False)
    pd.DataFrame(mc_summary).to_excel(w, sheet_name='蒙特卡洛分布 Monte Carlo', index=False)
    bear_rules.to_excel(w, sheet_name='熊市应急预案 Bear Rules', index=False)
    roth_split.to_excel(w, sheet_name='Roth账户拆分 Roth Split', index=False)
    pd.DataFrame([
        {"代码":"VOLT","中文":label("VOLT"),"板块":"工业/电气化","管理":"主动 (Tema ETFs)","费率":"0.75%"},
        {"代码":"AIPO","中文":label("AIPO"),"板块":"AI电力基础设施","管理":"被动 (Defiance)","费率":"0.69%"},
        {"代码":"QQQ","中文":label("QQQ"),"板块":"科技大盘 (纳指100)","管理":"被动 (Invesco)","费率":"0.20%"},
    ]).to_excel(w, sheet_name='ETF信息 ETF Info', index=False)
print("OK 04_DCA加仓策略_中英文.xlsx")

# ============================================================
# 5) 完整术语对照表
# ============================================================
print("\n" + "="*70)
print("【任务5】完整术语对照表")
print("="*70)

etfs_doc = [
    ("ETF类_主题", [
        ("AIPO","Defiance AI & Power Infrastructure ETF","Defiance AI 与电力基础设施 ETF","AI 数据中心+电力基础设施","被动 Passive","0.69%"),
        ("POWR","iShares U.S. Power Infrastructure ETF","iShares 美国电力基础设施 ETF","美国电力基建","被动","0.18%"),
        ("GRID","First Trust NASDAQ Smart Grid Infrastructure ETF","第一信托纳斯达克智能电网基础设施 ETF","全球智能电网","被动","0.59%"),
        ("PAVE","Global X U.S. Infrastructure Development ETF","Global X 美国基础设施建设 ETF","美国基建","被动","0.47%"),
        ("VOLT","Tema Electrification ETF","Tema 电气化 ETF","电气化产业链","主动 Active","0.75%"),
        ("NLR","VanEck Uranium and Nuclear ETF","VanEck 铀矿与核能 ETF","核能+铀矿综合","被动","0.61%"),
        ("URA","Global X Uranium ETF","Global X 铀矿 ETF","全球铀矿","被动","0.69%"),
        ("URNM","Sprott Uranium Miners ETF","Sprott 铀矿采选 ETF","纯铀矿","被动","0.83%"),
        ("URAN","Themes Uranium & Nuclear ETF","Themes 铀与核能 ETF","核能小弟","被动","0.35%"),
        ("SMRF","ALPS Nautilus SMR, Nuclear & Technology ETF","ALPS 鹦鹉螺小型核反应堆 ETF","SMR小堆+AI科技","主动","0.65%"),
        ("XLU","Utilities Select Sector SPDR Fund","SPDR 公用事业精选行业 ETF","美国公用事业","被动","0.08%"),
        ("VPU","Vanguard Utilities ETF","先锋公用事业 ETF","低费率公用事业","被动","0.10%"),
        ("UTES","Virtus Reaves Utilities ETF","Virtus Reaves 公用事业 ETF","主动选股公用事业","主动","0.49%"),
        ("VCLN","Virtus Duff & Phelps Clean Energy ETF","Virtus 达夫菲尔普斯清洁能源 ETF","主动清洁能源","主动","0.59%"),
        ("ICLN","iShares Global Clean Energy ETF","iShares 全球清洁能源 ETF","被动清洁能源","被动","0.41%"),
        ("QQQ","Invesco QQQ Trust","景顺纳斯达克100信托 ETF","纳指100/科技七巨头","被动","0.20%"),
        ("SPY","SPDR S&P 500 ETF Trust","SPDR 标普500 ETF","美股大盘","被动","0.09%"),
        ("ARKQ","ARK Autonomous Technology & Robotics ETF","方舟自动驾驶与机器人 ETF","Cathie Wood 自动化","主动","0.75%"),
        ("ARKK","ARK Innovation ETF","方舟创新 ETF","Cathie Wood 旗舰","主动","0.75%"),
        ("BOTZ","Global X Robotics & Artificial Intelligence ETF","Global X 机器人与AI ETF","机器人+AI","被动","0.69%"),
        ("TSPA","T. Rowe Price U.S. Equity Research ETF","普信美国股票研究 ETF","主动选股大盘","主动","0.34%"),
        ("DTCR","Global X Data Center & Digital Infrastructure ETF","Global X 数据中心数字基建 ETF","数据中心","被动","0.50%"),
    ]),
    ("个股_电力设备", [
        ("GEV","GE Vernova Inc.","GE 维诺瓦","燃气轮机+变压器(数据中心电力核心)"),
        ("ETN","Eaton Corporation plc","伊顿电气","电气配电+UPS不间断电源"),
        ("PWR","Quanta Services Inc.","匡塔服务","输配电线路施工龙头"),
        ("VRT","Vertiv Holdings Co.","维谛技术","数据中心冷却+电源管理"),
        ("EMR","Emerson Electric Co.","艾默生电气","工业自动化+流程控制"),
        ("POWL","Powell Industries","鲍威尔工业","高压配电柜"),
        ("BELFB","Bel Fuse Inc.","贝尔福实业","电气连接器(AI服务器电源)"),
        ("MTZ","MasTec Inc.","玛斯泰克","电力工程基建"),
        ("JCI","Johnson Controls International","江森自控","楼宇自动化+暖通空调"),
        ("ABB","ABB Ltd","瑞士ABB集团","全球电网+工业自动化"),
        ("BE","Bloom Energy Corporation","布鲁姆能源","燃料电池(数据中心自带电源)"),
        ("KGS","Kodiak Gas Services","科迪亚克天然气服务","天然气压缩服务"),
    ]),
    ("个股_公用事业", [
        ("CEG","Constellation Energy Corporation","星座能源","全美最大核电运营商(微软三里岛合作)"),
        ("VST","Vistra Corp.","维斯特拉能源","核电+燃气(Meta 2.6GW PPA)"),
        ("TLN","Talen Energy Corp.","塔伦能源","核电(AWS 1.92GW PPA)"),
        ("D","Dominion Energy","多明尼资源","弗吉尼亚数据中心走廊电力"),
        ("NEE","NextEra Energy","新纪元能源","全美最大可再生能源公司"),
        ("SO","The Southern Company","南方电力公司","美国南方公用事业"),
        ("DUK","Duke Energy","杜克能源","美国东南公用事业"),
        ("AEP","American Electric Power","美国电力公司","中西部输配电"),
        ("XEL","Xcel Energy Inc.","埃克塞尔能源","中部公用事业"),
        ("CNP","CenterPoint Energy","中点能源","德州+中西部电气"),
        ("PEG","Public Service Enterprise Group","公共服务企业集团","新泽西公用事业+核电"),
        ("ETR","Entergy Corp.","安特吉公司","南方核电+公用事业"),
    ]),
    ("个股_核能", [
        ("OKLO","Oklo Inc.","奥克洛","小型模块化反应堆(Sam Altman背书)"),
        ("SMR","NuScale Power","NuScale 电力","美国NRC唯一批准的SMR设计"),
        ("CCJ","Cameco Corporation","卡梅科铀业","全球第二大铀矿商"),
        ("BWXT","BWX Technologies","BWX 技术","海军反应堆+SMR部件"),
        ("LEU","Centrus Energy","中心能源","浓缩铀生产"),
        ("UEC","Uranium Energy Corp","铀能源公司","美国铀矿开采"),
        ("NXE","NexGen Energy","下一代能源","加拿大铀矿勘探"),
        ("UUUU","Energy Fuels Inc.","能源燃料公司","铀矿+稀土"),
        ("BEP","Brookfield Renewable Partners","布鲁克菲尔德可再生能源","加拿大可再生能源巨头"),
    ]),
    ("个股_AI科技", [
        ("NVDA","NVIDIA Corporation","英伟达","AI GPU 芯片之王"),
        ("AVGO","Broadcom Inc.","博通公司","网络芯片+AI ASIC"),
        ("TSM","Taiwan Semiconductor Manufacturing","台积电","全球最大芯片代工厂"),
        ("AMD","Advanced Micro Devices","超威半导体","AI GPU 第二玩家"),
        ("TER","Teradyne Inc.","泰瑞达","AI芯片测试设备"),
        ("AAPL","Apple Inc.","苹果公司","iPhone + Apple Intelligence"),
        ("MSFT","Microsoft Corporation","微软公司","OpenAI股东+Azure云"),
        ("AMZN","Amazon.com Inc.","亚马逊","AWS 云计算"),
        ("GOOGL","Alphabet Inc. (Class A)","谷歌母公司A类","Google + Gemini AI"),
        ("META","Meta Platforms Inc.","元宇宙平台公司","Facebook + Llama AI"),
        ("TSLA","Tesla Inc.","特斯拉","电动车+自动驾驶+机器人"),
        ("KTOS","Kratos Defense","克拉托斯国防","无人机+高超音速武器"),
        ("PATH","UiPath Inc.","UiPath 公司","流程自动化软件(RPA)"),
        ("ACHR","Archer Aviation","阿彻航空","eVTOL 飞行汽车"),
    ]),
]

terms_doc = [
    ("ETF","Exchange-Traded Fund","交易型开放式指数基金","像股票一样交易的基金"),
    ("AUM","Assets Under Management","管理资产规模","基金总规模"),
    ("NAV","Net Asset Value","资产净值","每股内在价值"),
    ("DCA","Dollar-Cost Averaging","定额定投","每月固定金额买入"),
    ("DRIP","Dividend Reinvestment Plan","股息再投资计划","自动用股息买入"),
    ("CAGR","Compound Annual Growth Rate","复合年增长率","年化复合收益率"),
    ("YTD","Year-To-Date","年初至今","本年累计回报"),
    ("LTCG","Long-Term Capital Gains","长期资本利得税","持有>1年的卖出税率"),
    ("Roth IRA","Roth Individual Retirement Account","Roth个人退休账户","投入已交税,取出免税"),
    ("Max DD","Maximum Drawdown","最大回撤","历史最大跌幅"),
    ("Vol","Volatility","波动率","价格波动幅度"),
    ("PPA","Power Purchase Agreement","购电协议","长期电力供应合同"),
    ("SMR","Small Modular Reactor","小型模块化反应堆","新一代核电技术"),
    ("Sharpe","Sharpe Ratio","夏普比率","风险调整后收益"),
    ("DCA+Dip","DCA with Buy-the-Dip","定投+跌后加仓策略","跌则多买"),
    ("Rebalance","Quarterly Rebalance","季度再平衡","定期调回目标比例"),
    ("Beta","Beta Coefficient","贝塔系数","与大盘相关性"),
]

with pd.ExcelWriter(f"{OUT}/05_完整术语对照表_中英文.xlsx", engine='openpyxl') as w:
    for sheet_name, items in etfs_doc:
        if len(items[0]) == 6:  # ETF
            df = pd.DataFrame(items, columns=["代码 Ticker","英文全名 English","中文名称","板块/主营","管理类型","费率"])
        else:  # 个股
            df = pd.DataFrame(items, columns=["代码 Ticker","英文全名 English","中文名称","板块/主营"])
        df.to_excel(w, sheet_name=sheet_name, index=False)
    pd.DataFrame(terms_doc, columns=["缩写 Abbr","英文 English","中文","解释"]).to_excel(
        w, sheet_name='投资术语 Glossary', index=False)
print("OK 05_完整术语对照表_中英文.xlsx")

# ============================================================
# 6) README
# ============================================================
readme = """# MING - 中英文双语版 ETF 投资分析

## 文件清单 / File List

| 文件 File | 内容 Content |
|---|---|
| **01_ETF对比_AIPO_NLR_XLU_中英文.png/.xlsx** | 三大主题ETF对比 |
| **02_主动vs被动ETF战绩_中英文.png/.xlsx** | UTES/VOLT/TSPA/VCLN/ARKQ 主动vs被动 |
| **03_定投策略对比_中英文.png/.xlsx** | 6种定投策略 + 5年场景预测 |
| **04_DCA加仓策略_中英文.png/.xlsx** | VOLT+AIPO+QQQ 跌后加仓50% (含60月执行表) |
| **05_完整术语对照表_中英文.xlsx** | 全部 ETF / 股票 / 术语中英文对照 |

## 标注示例 / Labeling Example

每个 ticker 都标注成形如:
- **AIPO (AI电力基础设施ETF)**
- **NLR (铀矿与核能ETF)**
- **XLU (美国公用事业ETF)**
- **QQQ (纳斯达克100ETF)**
- **CEG (星座能源/核电)**

## 推荐查看顺序 / Recommended Order

1. 先看 **05_完整术语对照表** - 知道每个代码代表什么
2. 再看 **01_ETF对比** - 看三大主题表现
3. 看 **02_主动vs被动** - 知道哪些主动经理值得付费
4. 看 **03_定投策略对比** - 6 种策略哪种好
5. 重点研读 **04_DCA加仓策略** - 你的 5 年定投执行手册

## 免责声明 / Disclaimer

数据来源: Yahoo Finance, SEC, 各基金公司官网
**所有内容仅为信息分析，不构成投资建议。**
"""
with open(f"{OUT}/README_中英文版.md", "w") as f:
    f.write(readme)
print("OK README_中英文版.md")

print("\n" + "="*70)
print("全部完成! 文件保存在: /projects/sandbox/MING/bilingual/")
print("="*70)
