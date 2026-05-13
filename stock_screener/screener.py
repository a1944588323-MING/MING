"""
52 周高低点 + RSI + BB 股票筛选器
用法:
  1. 修改下方 SYMBOLS 列表
  2. python screener.py
  3. 输出: results.csv 和 控制台报告

依赖:
  pip install yfinance pandas numpy
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os

# ========== 配置 ==========

# 在这里填你想筛选的股票代码
# 美股: AAPL, TSLA, MSFT
# 港股: 0700.HK (腾讯), 9988.HK (阿里), 3690.HK (美团)
# A 股: 600519.SS (茅台), 000858.SZ (五粮液), 300750.SZ (宁德时代)
# ETF: QQQ, SPY, 510300.SS (沪深 300)
SYMBOLS = [
    # ===== 美股科技 =====
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "TSLA", "AMZN",
    # ===== 美股其他 =====
    "BRK-B", "JPM", "V", "JNJ", "WMT",
    # ===== 港股 =====
    "0700.HK", "9988.HK", "3690.HK", "1810.HK",
    # ===== ETF =====
    "QQQ", "SPY",
]

# 参数(可调)
LOOKBACK_DAYS = 252       # 52 周交易日 ≈ 252
ZONE_THRESHOLD_PCT = 20   # 危险区阈值(股票建议 20%,加密 30%)
RSI_PERIOD = 14
BB_LEN = 20
BB_MULT = 2.0
MIN_DATA_DAYS = 300       # 至少要有 300 天数据才能筛

# ========== 指标计算 ==========

def calc_rsi(s, n=14):
    delta = s.diff()
    up = delta.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = up / down.replace(0, np.nan)
    return 100 - 100 / (1 + rs)

def calc_atr(df, n=14):
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift()).abs(),
        (df["Low"]  - df["Close"].shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(n).mean()

# ========== 单只股票分析 ==========

def analyze(symbol):
    try:
        df = yf.download(symbol, period="2y", interval="1d",
                         progress=False, auto_adjust=True)
        if df is None or df.empty or len(df) < MIN_DATA_DAYS:
            return None

        # 兼容多列索引(yfinance 新版本可能返回 MultiIndex)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 取最近 LOOKBACK_DAYS 天计算 52 周高低
        recent = df.tail(LOOKBACK_DAYS)
        hi52 = float(recent["High"].max())
        lo52 = float(recent["Low"].min())

        last_close = float(df["Close"].iloc[-1])

        # 位置百分比: 0% = 在 52W 低, 100% = 在 52W 高
        position_pct = (last_close - lo52) / (hi52 - lo52) * 100 if hi52 > lo52 else 50

        # 网格区间(仅用于显示参考价位)
        danger_high_line = hi52 * (1 - ZONE_THRESHOLD_PCT / 100)
        danger_low_line  = lo52 * (1 + ZONE_THRESHOLD_PCT / 100)
        midline = (danger_high_line + danger_low_line) / 2

        # 区域判定 - 用 position_pct 划分,避免 52W 区间窄时 high/low 阈值翻转
        # < 20%: 低位危险区(抄底), 20-50%: 多网区, 50-80%: 空网区, > 80%: 高位危险区
        in_high_danger = position_pct >= 80
        in_low_danger  = position_pct <= 20
        in_short_zone  = 50 < position_pct < 80
        in_long_zone   = 20 < position_pct <= 50

        # RSI / BB
        rsi = float(calc_rsi(df["Close"], RSI_PERIOD).iloc[-1])
        ma  = df["Close"].rolling(BB_LEN).mean()
        std = df["Close"].rolling(BB_LEN).std()
        bb_upper = float((ma + BB_MULT * std).iloc[-1])
        bb_lower = float((ma - BB_MULT * std).iloc[-1])

        # ATR(用于建议网格步长)
        atr = float(calc_atr(df, 14).iloc[-1])
        atr_pct = atr / last_close * 100

        # 综合建议
        if in_high_danger:
            advice = "🚫 高点危险区 - 禁开多网,可能见顶"
            score = 1
        elif in_low_danger:
            advice = "🔥 低点危险区 - 抄底机会(也禁开空网)"
            score = 5
        elif in_long_zone:
            advice = "✅ 多单网格区 - 适合做多/网格做多"
            score = 4
        elif in_short_zone:
            advice = "⚠️ 空单网格区 - 偏高,可空单网格"
            score = 2
        else:
            advice = "➖ 中位附近 - 双向可布网"
            score = 3

        # RSI 加分
        if rsi < 30:
            advice += " | RSI 超卖"
            score += 1
        elif rsi > 70:
            advice += " | RSI 超买"
            score -= 1

        # 评级
        rating = "A+" if score >= 5 else "A" if score >= 4 else "B" if score >= 3 else "C" if score >= 2 else "D"

        return {
            "symbol": symbol,
            "price": round(last_close, 2),
            "52w_low": round(lo52, 2),
            "52w_high": round(hi52, 2),
            "position_pct": round(position_pct, 1),
            "long_zone_low": round(danger_low_line, 2),
            "long_zone_mid": round(midline, 2),
            "short_zone_high": round(danger_high_line, 2),
            "rsi": round(rsi, 1),
            "atr_pct": round(atr_pct, 2),
            "rating": rating,
            "score": score,
            "advice": advice,
        }
    except Exception as e:
        print(f"  ✗ {symbol} 失败: {e}")
        return None

# ========== 主流程 ==========

def main():
    print(f"分析 {len(SYMBOLS)} 只股票...")
    results = []
    for i, sym in enumerate(SYMBOLS, 1):
        print(f"  [{i}/{len(SYMBOLS)}] {sym}", end=" ... ", flush=True)
        r = analyze(sym)
        if r:
            results.append(r)
            print(f"{r['rating']} | {r['advice'][:30]}")
        else:
            print("跳过")

    if not results:
        print("没有可分析的股票")
        return

    df = pd.DataFrame(results).sort_values("score", ascending=False).reset_index(drop=True)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n完整结果已保存: {out}\n")

    # 打印漂亮的报告
    print("=" * 110)
    print(f"{'排名':<4} {'代码':<10} {'当前价':>10} {'52W高':>10} {'52W低':>10} {'位置%':>7} {'RSI':>6} {'评级':>4}  建议")
    print("=" * 110)
    for i, r in enumerate(results, 1):
        if not r:
            continue
        bar = "█" * int(r["position_pct"] / 5)  # 简易位置条
        print(f"{i:<4} {r['symbol']:<10} {r['price']:>10.2f} {r['52w_high']:>10.2f} {r['52w_low']:>10.2f} "
              f"{r['position_pct']:>6.1f}% {r['rsi']:>6.1f} {r['rating']:>4}  {r['advice']}")

    # 分组建议
    print("\n📋 推荐操作分组:\n")
    for grp_name, score_range in [
        ("🔥 抄底机会(接近 52W 低)", (5, 99)),
        ("✅ 适合做多/多单网格",      (4, 4)),
        ("➖ 中位震荡 双向可布网",    (3, 3)),
        ("⚠️ 偏高 谨慎",            (2, 2)),
        ("🚫 接近 52W 高 禁多",      (0, 1)),
    ]:
        sub = [r for r in results if score_range[0] <= r["score"] <= score_range[1]]
        if sub:
            print(f"  {grp_name}: {', '.join(s['symbol'] for s in sub)}")
    print()

if __name__ == "__main__":
    main()
