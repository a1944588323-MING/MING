"""
A股做T 真实回测 - 东方财富 (300059) 最近1年
"""
import akshare as ak
import pandas as pd
import numpy as np

print("加载东方财富日线数据...")
df = ak.stock_zh_a_hist(symbol="300059", period="daily",
                         start_date="20240517", end_date="20260517", adjust="qfq")
df.columns = ['date','code','open','close','high','low','volume','amount','amplitude','pct_change','change','turnover']
df['date'] = pd.to_datetime(df['date'])
df = df.set_index('date')
print(f"数据: {len(df)} 个交易日")
print(f"区间: {df.index[0].date()} -> {df.index[-1].date()}")

capital = 10000
position_pct = 0.7
btc_qty = (capital * position_pct) / df['close'].iloc[0]

cash = capital * 0.3
shares = btc_qty
trades = []
daily_log = []

for date, row in df.iterrows():
    o, h, l, c = row['open'], row['high'], row['low'], row['close']
    daily_amp = (h - l) / o * 100

    if daily_amp > 2.0:
        capture_rate = 0.30
        t_profit_pct = daily_amp * capture_rate / 100
        t_profit = shares * o * t_profit_pct
        t_profit -= shares * o * 0.0005 * 2

        cash += t_profit
        trades.append({'date':date,'amp':daily_amp,'t_profit':t_profit,'price':c})

    total_value = cash + shares * c
    daily_log.append({'date':date,'close':c,'total':total_value})

t_df = pd.DataFrame(trades)
log_df = pd.DataFrame(daily_log).set_index('date')

final_value = log_df['total'].iloc[-1]
ret = (final_value - capital) / capital
days = (log_df.index[-1] - log_df.index[0]).days
annual = ret / days * 365

bh_value = capital + btc_qty * (df['close'].iloc[-1] - df['close'].iloc[0])
bh_ret = (bh_value - capital) / capital

log_df['dd'] = (log_df['total'].cummax() - log_df['total']) / log_df['total'].cummax()
max_dd = log_df['dd'].max()

total_t = len(t_df)
total_t_profit = t_df['t_profit'].sum()
avg_t = t_df['t_profit'].mean()
win = (t_df['t_profit'] > 0).sum()
wr = win / total_t

print(f"\n{'='*70}")
print(f"📊 东方财富 (300059) 1年做T回测")
print(f"{'='*70}")
print(f"\n【期间】 {days}天 | 涨跌: {(df['close'].iloc[-1]/df['close'].iloc[0]-1)*100:+.1f}%")
print(f"\n【做T统计】")
print(f"  做T次数: {total_t} 天 (振幅>2%的天数)")
print(f"  胜率: {wr*100:.1f}%")
print(f"  单次平均: ${avg_t:.2f}")
print(f"  总利润: ${total_t_profit:.2f}")

print(f"\n【资金】 起始 ${capital} → 末值 ${final_value:.0f}")
print(f"  总收益: {ret*100:+.2f}%")
print(f"  年化:   {annual*100:+.2f}%")
print(f"  回撤:   {max_dd*100:.2f}%")
print(f"  vs BH:  {bh_ret*100:+.2f}% → 超额 {(ret-bh_ret)*100:+.2f}%")

print(f"\n💡 不同水平做T手 (1年):")
total_amp_money = sum(shares * row['open'] * (row['high']-row['low'])/row['open']
                      for _, row in df.iterrows() if (row['high']-row['low'])/row['open']>0.02)
for rate, desc in [(0.10,"新手抓10%"),(0.20,"进阶20%"),(0.30,"熟练30%"),
                   (0.50,"高手50%"),(0.70,"顶级70%")]:
    profit = total_amp_money * rate * 0.7
    profit -= total_amp_money * rate * 0.001
    print(f"  {desc:<12} → ${profit:>7.0f} ({profit/capital*100:>+5.1f}%/年)")

print(f"\n📅 月度细分:")
log_df['m'] = log_df.index.to_period('M')
mf = log_df.groupby('m')['total'].first()
ml = log_df.groupby('m')['total'].last()
for m in mf.index:
    t_n = sum(1 for d in t_df['date'] if d.to_period('M')==m) if not t_df.empty else 0
    r = (ml[m]/mf[m]-1)*100
    print(f"  {str(m):<10} 做T {t_n:>3}次 | 月收益 {r:>+6.2f}% | ${mf[m]:>5.0f} → ${ml[m]:>5.0f}")
