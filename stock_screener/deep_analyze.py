"""
单股深度分析: 技术面 + 关键指标快照
用法:
  python deep_analyze.py 600519.SS
  python deep_analyze.py AAPL
  python deep_analyze.py 0700.HK
  python deep_analyze.py 600519.SS 000858.SZ 002230.SZ   # 多只一起分析
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime


def calc_rsi(s, n=14):
    delta = s.diff()
    up = delta.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = up / down.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def calc_macd(s, fast=12, slow=26, signal=9):
    ema_fast = s.ewm(span=fast, adjust=False).mean()
    ema_slow = s.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    sig_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - sig_line
    return macd_line, sig_line, hist


def calc_atr(df, n=14):
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift()).abs(),
        (df["Low"]  - df["Close"].shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def deep_analyze(symbol):
    print(f"\n{'='*80}")
    print(f"📊 深度分析: {symbol}")
    print(f"{'='*80}")

    df = yf.download(symbol, period="2y", interval="1d", progress=False, auto_adjust=True)
    if df is None or df.empty or len(df) < 60:
        print(f"  ✗ 数据不足或代码错误")
        return

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 基本信息
    last_close = float(df["Close"].iloc[-1])
    prev_close = float(df["Close"].iloc[-2])
    daily_chg = (last_close - prev_close) / prev_close * 100

    week_close = float(df["Close"].iloc[-5]) if len(df) > 5 else last_close
    week_chg = (last_close - week_close) / week_close * 100
    month_close = float(df["Close"].iloc[-20]) if len(df) > 20 else last_close
    month_chg = (last_close - month_close) / month_close * 100

    # 52 周高低
    recent = df.tail(252)
    hi52 = float(recent["High"].max())
    lo52 = float(recent["Low"].min())
    pos_pct = (last_close - lo52) / (hi52 - lo52) * 100 if hi52 > lo52 else 50

    # 均线
    ma5 = float(df["Close"].rolling(5).mean().iloc[-1])
    ma10 = float(df["Close"].rolling(10).mean().iloc[-1])
    ma20 = float(df["Close"].rolling(20).mean().iloc[-1])
    ma60 = float(df["Close"].rolling(60).mean().iloc[-1])
    ma200 = float(df["Close"].rolling(200).mean().iloc[-1]) if len(df) > 200 else float("nan")

    # RSI
    rsi6 = float(calc_rsi(df["Close"], 6).iloc[-1])
    rsi14 = float(calc_rsi(df["Close"], 14).iloc[-1])

    # MACD
    macd_line, sig_line, hist = calc_macd(df["Close"])
    macd_v = float(macd_line.iloc[-1])
    sig_v = float(sig_line.iloc[-1])
    hist_v = float(hist.iloc[-1])
    hist_prev = float(hist.iloc[-2])

    # 布林带
    ma20_s = df["Close"].rolling(20).mean()
    std20 = df["Close"].rolling(20).std()
    bb_up = float((ma20_s + 2 * std20).iloc[-1])
    bb_low = float((ma20_s - 2 * std20).iloc[-1])
    bb_pct = (last_close - bb_low) / (bb_up - bb_low) * 100

    # 成交量
    vol_avg20 = float(df["Volume"].rolling(20).mean().iloc[-1])
    vol_today = float(df["Volume"].iloc[-1])
    vol_ratio = vol_today / vol_avg20 if vol_avg20 > 0 else 0

    # ATR & 波动率
    atr = float(calc_atr(df, 14).iloc[-1])
    atr_pct = atr / last_close * 100

    # 1 年回报
    if len(df) > 252:
        year_close = float(df["Close"].iloc[-252])
        year_chg = (last_close - year_close) / year_close * 100
    else:
        year_chg = float("nan")

    # ============ 输出 ============
    print(f"\n【价格信息】")
    print(f"  当前价     : {last_close:>10.2f}    今日涨跌    : {daily_chg:>+6.2f}%")
    print(f"  近 5 日涨跌 : {week_chg:>+9.2f}%   近 20 日涨跌  : {month_chg:>+6.2f}%")
    if not pd.isna(year_chg):
        print(f"  近 1 年涨跌 : {year_chg:>+9.2f}%")

    print(f"\n【52 周区间】")
    print(f"  52W 高     : {hi52:>10.2f}    52W 低      : {lo52:>10.2f}")
    print(f"  当前位置   : {pos_pct:>9.1f}%   ", end="")
    if pos_pct < 20:
        print("🔥 极度低位 - 抄底区")
    elif pos_pct < 50:
        print("✅ 低位/中下 - 适合做多")
    elif pos_pct < 80:
        print("⚠️  中高位 - 谨慎追入")
    else:
        print("🚫 极度高位 - 慎入(可能见顶)")

    bar = "█" * int(pos_pct / 2.5)
    space = "·" * (40 - int(pos_pct / 2.5))
    print(f"  位置可视化: [{bar}{space}] {pos_pct:.1f}%")

    print(f"\n【均线系统】")
    print(f"  MA5  : {ma5:>10.2f}   MA10 : {ma10:>10.2f}")
    print(f"  MA20 : {ma20:>10.2f}   MA60 : {ma60:>10.2f}")
    if not pd.isna(ma200):
        print(f"  MA200: {ma200:>10.2f}")
    # 多空排列
    if last_close > ma5 > ma20 > ma60:
        ma_state = "✅ 多头排列"
    elif last_close < ma5 < ma20 < ma60:
        ma_state = "🔻 空头排列"
    else:
        ma_state = "⚖️  纠缠/震荡"
    print(f"  趋势状态: {ma_state}")

    print(f"\n【RSI 摆动】")
    print(f"  RSI(6)  : {rsi6:>5.1f}   ", end="")
    if rsi6 > 80: print("🚫 严重超买")
    elif rsi6 > 70: print("⚠️  超买")
    elif rsi6 < 20: print("🔥 严重超卖")
    elif rsi6 < 30: print("✅ 超卖")
    else: print("⚖️  中性")
    print(f"  RSI(14) : {rsi14:>5.1f}   ", end="")
    if rsi14 > 70: print("⚠️  超买")
    elif rsi14 < 30: print("✅ 超卖")
    else: print("⚖️  中性")

    print(f"\n【MACD】")
    print(f"  DIF       : {macd_v:>+8.3f}    DEA: {sig_v:>+8.3f}    Histogram: {hist_v:>+8.3f}")
    if hist_v > 0 and hist_prev <= 0:
        print(f"  状态: 🔥 金叉(刚发生),多头信号")
    elif hist_v < 0 and hist_prev >= 0:
        print(f"  状态: 🔻 死叉(刚发生),空头信号")
    elif hist_v > 0 and hist_v > hist_prev:
        print(f"  状态: ✅ 多头放大,趋势加强")
    elif hist_v > 0 and hist_v < hist_prev:
        print(f"  状态: ⚠️  多头衰减,警惕")
    elif hist_v < 0 and hist_v < hist_prev:
        print(f"  状态: 🔻 空头放大,趋势加强")
    else:
        print(f"  状态: ⚖️  空头衰减,可能反弹")

    print(f"\n【布林带】")
    print(f"  上轨: {bb_up:>10.2f}    中轨: {ma20:>10.2f}    下轨: {bb_low:>10.2f}")
    print(f"  位置: {bb_pct:>9.1f}%   ", end="")
    if bb_pct > 95: print("🚫 触及上轨,超买")
    elif bb_pct > 75: print("⚠️  接近上轨")
    elif bb_pct < 5: print("🔥 触及下轨,超卖")
    elif bb_pct < 25: print("✅ 接近下轨")
    else: print("⚖️  正常区间")

    print(f"\n【成交量】")
    print(f"  今日成交  : {vol_today:>15,.0f}")
    print(f"  20 日均量 : {vol_avg20:>15,.0f}")
    print(f"  量比     : {vol_ratio:>5.2f}    ", end="")
    if vol_ratio > 2.5: print("🔥 异常放量")
    elif vol_ratio > 1.5: print("✅ 放量")
    elif vol_ratio < 0.5: print("⚠️  缩量明显")
    else: print("⚖️  正常")

    print(f"\n【波动率(ATR)】")
    print(f"  ATR(14): {atr:>8.3f}    日波幅: {atr_pct:>5.2f}%")

    # ============ 综合结论 ============
    print(f"\n{'─'*80}")
    print(f"📋 综合评估")
    print(f"{'─'*80}")
    score = 0
    bullets = []
    if pos_pct < 20:
        score += 2; bullets.append("✅ 处于 52 周低位 (抄底机会)")
    elif pos_pct < 50:
        score += 1; bullets.append("✅ 低位区间")
    elif pos_pct > 90:
        score -= 2; bullets.append("🚫 极度高位 (回调风险大)")
    elif pos_pct > 75:
        score -= 1; bullets.append("⚠️  偏高位")

    if rsi14 < 30:
        score += 2; bullets.append("✅ RSI 超卖 (有反弹潜力)")
    elif rsi14 > 70:
        score -= 2; bullets.append("🚫 RSI 超买 (短期回调风险)")

    if hist_v > 0 and hist_v > hist_prev:
        score += 1; bullets.append("✅ MACD 多头加强")
    elif hist_v < 0 and hist_v < hist_prev:
        score -= 1; bullets.append("🔻 MACD 空头加强")

    if last_close > ma5 > ma20 > ma60:
        score += 1; bullets.append("✅ 均线多头排列")
    elif last_close < ma5 < ma20 < ma60:
        score -= 1; bullets.append("🔻 均线空头排列")

    if vol_ratio > 1.5 and daily_chg > 0:
        score += 1; bullets.append("✅ 放量上涨")
    elif vol_ratio > 1.5 and daily_chg < 0:
        score -= 1; bullets.append("🔻 放量下跌")

    for b in bullets:
        print(f"  {b}")

    print()
    if score >= 3:
        print(f"  🌟 综合评分: {score}  评级: A+ (强烈推荐研究)")
    elif score >= 1:
        print(f"  ✅ 综合评分: {score}  评级: A   (可关注)")
    elif score >= -1:
        print(f"  ⚖️  综合评分: {score}  评级: B   (中性)")
    elif score >= -3:
        print(f"  ⚠️  综合评分: {score}  评级: C   (谨慎)")
    else:
        print(f"  🚫 综合评分: {score}  评级: D   (回避)")

    print(f"\n  ⚠️  以上仅为技术面快照,不构成投资建议。请结合基本面、行业景气度自行判断。")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    for symbol in sys.argv[1:]:
        deep_analyze(symbol)


if __name__ == "__main__":
    main()
