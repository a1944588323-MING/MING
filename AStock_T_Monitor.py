"""
A股做T 实时信号监控脚本
功能:
  - 每分钟拉取股票实时数据
  - 计算关键指标 (RSI / 振幅 / 5分钟均线)
  - 在终端打印做 T 信号 (拉升/回调)
  - 提示买卖时机
依赖: akshare
运行: python AStock_T_Monitor.py
"""
import akshare as ak
import pandas as pd
import time
from datetime import datetime, time as dtime

STOCK_CODE = "300059"  # 东方财富
STOCK_NAME = "东方财富"
PRICE_UP_THRESHOLD = 1.5    # 拉升 1.5% 提示卖出
PRICE_DN_THRESHOLD = -1.0   # 回调 1% 提示买入
CHECK_INTERVAL = 60          # 60 秒检查一次

last_signal = None

def get_realtime():
    """获取实时分时数据"""
    try:
        df = ak.stock_zh_a_hist_min_em(symbol=STOCK_CODE, period="1",
                                         start_date=datetime.now().strftime("%Y-%m-%d 09:30:00"),
                                         end_date=datetime.now().strftime("%Y-%m-%d 15:00:00"),
                                         adjust="")
        if df is None or len(df) == 0:
            return None
        df.columns = [c.lower() for c in df.columns]
        return df
    except Exception as e:
        print(f"[ERR] {e}")
        return None

def calc_rsi(close, n=14):
    delta = close.diff()
    up = delta.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100/(1+up/dn.replace(0, float('nan')))

def is_trading_hour():
    now = datetime.now().time()
    morning = dtime(9,30) <= now <= dtime(11,30)
    afternoon = dtime(13,0) <= now <= dtime(15,0)
    return morning or afternoon

def check_signal(df):
    global last_signal
    if df is None or len(df) < 20: return

    open_price = df['开盘'].iloc[0] if '开盘' in df.columns else df['open'].iloc[0]
    cur_price = df['收盘'].iloc[-1] if '收盘' in df.columns else df['close'].iloc[-1]
    high = (df['最高'] if '最高' in df.columns else df['high']).max()
    low = (df['最低'] if '最低' in df.columns else df['low']).min()

    pct_from_open = (cur_price - open_price) / open_price * 100
    amplitude = (high - low) / open_price * 100

    close_series = df['收盘'] if '收盘' in df.columns else df['close']
    rsi = calc_rsi(close_series).iloc[-1]
    ma5 = close_series.rolling(5).mean().iloc[-1]
    ma20 = close_series.rolling(20).mean().iloc[-1]

    now_str = datetime.now().strftime("%H:%M:%S")

    print(f"\n[{now_str}] {STOCK_NAME}({STOCK_CODE}) ${cur_price:.2f}")
    print(f"  日内振幅: {amplitude:.2f}% | 开盘涨跌: {pct_from_open:+.2f}%")
    print(f"  RSI: {rsi:.1f} | MA5: {ma5:.2f} | MA20: {ma20:.2f}")

    signal = None
    msg = ""
    if pct_from_open >= PRICE_UP_THRESHOLD and rsi > 70 and last_signal != "SELL":
        signal = "SELL"
        msg = f"🔴 卖出信号: 拉升 {pct_from_open:.2f}% + RSI 超买 {rsi:.0f}"
    elif pct_from_open <= PRICE_DN_THRESHOLD and rsi < 30 and last_signal != "BUY":
        signal = "BUY"
        msg = f"🟢 买入信号: 回调 {pct_from_open:.2f}% + RSI 超卖 {rsi:.0f}"
    elif cur_price > ma5 > ma20 and rsi < 65:
        msg = "📈 多头趋势,持有底仓"
    elif cur_price < ma5 < ma20 and rsi > 35:
        msg = "📉 空头趋势,空仓观望"
    else:
        msg = "⏸ 震荡区,等待"

    print(f"  状态: {msg}")
    if signal:
        print(f"  ⚠️⚠️⚠️ {signal} 触发!")
        last_signal = signal

def main():
    print(f"\n{'='*60}")
    print(f"A股做T 实时监控 - {STOCK_NAME}({STOCK_CODE})")
    print(f"{'='*60}")
    print(f"拉升阈值: +{PRICE_UP_THRESHOLD}% | 回调阈值: {PRICE_DN_THRESHOLD}%")
    print(f"检查间隔: {CHECK_INTERVAL}秒")
    print(f"提示: 仅在交易时段(9:30-11:30, 13:00-15:00)有效")

    while True:
        if is_trading_hour():
            df = get_realtime()
            check_signal(df)
        else:
            now_str = datetime.now().strftime("%H:%M:%S")
            print(f"[{now_str}] 非交易时段,等待...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
