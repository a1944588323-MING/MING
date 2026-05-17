"""
月度报表自动生成
运行: python monthly_report.py 2026-05
"""
import pandas as pd
import sys
import os
from datetime import datetime

month = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m")
log_file = f"logs/orders_{month.replace('-','')}.csv"

if not os.path.exists(log_file):
    print(f"❌ 找不到 {log_file}")
    sys.exit(1)

df = pd.read_csv(log_file)
df["金额"] = df["金额"].astype(float)
df["时间"] = pd.to_datetime(df["时间"])
df["日期"] = df["时间"].dt.date

print(f"\n{'='*60}")
print(f"📊 {month} 月度交易报表")
print(f"{'='*60}\n")

# 配对买卖单 (FIFO)
sells = df[df["方向"] == "SELL"].copy().reset_index(drop=True)
buys = df[df["方向"] == "BUY"].copy().reset_index(drop=True)

paired = []
b_idx = 0
for _, s in sells.iterrows():
    while b_idx < len(buys) and buys.iloc[b_idx]["时间"] <= s["时间"]:
        b_idx += 1
    if b_idx > 0:
        b = buys.iloc[b_idx - 1]
        pnl_pct = (s["价格"] - b["价格"]) / b["价格"] * 100
        paired.append({
            "卖时间": s["时间"], "买时间": b["时间"],
            "卖价": s["价格"], "买价": b["价格"],
            "数量": min(s["数量"], b["数量"]),
            "盈亏%": pnl_pct
        })

if paired:
    pdf = pd.DataFrame(paired)
    n = len(pdf)
    win = (pdf["盈亏%"] > 0).sum()
    wr = win / n
    print(f"【交易统计】")
    print(f"  完整 T 单: {n} 笔")
    print(f"  胜率: {wr*100:.1f}% ({win}赢/{n-win}亏)")
    print(f"  平均盈亏: {pdf['盈亏%'].mean():+.2f}%")
    print(f"  最大盈利: {pdf['盈亏%'].max():+.2f}%")
    print(f"  最大亏损: {pdf['盈亏%'].min():+.2f}%")

print(f"\n【按日明细】")
print(f"  {'日期':<12} {'买入':>4} {'卖出':>4} {'净盈亏':>10}")
for d in sorted(df["日期"].unique()):
    sub = df[df["日期"] == d]
    n_buy = (sub["方向"]=="BUY").sum()
    n_sell = (sub["方向"]=="SELL").sum()
    net = sub.loc[sub["方向"]=="SELL","金额"].sum() - sub.loc[sub["方向"]=="BUY","金额"].sum()
    print(f"  {str(d):<12} {n_buy:>4} {n_sell:>4} {net:>+9.2f}")

out_file = f"logs/月度报表_{month}.xlsx"
with pd.ExcelWriter(out_file) as w:
    df.to_excel(w, sheet_name="原始交易", index=False)
    if paired:
        pd.DataFrame(paired).to_excel(w, sheet_name="T单配对", index=False)
print(f"\n✅ 已生成: {out_file}")
