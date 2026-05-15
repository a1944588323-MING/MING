"""
把回测最好的策略组合起来看能不能更强
从上面的数据最好的几个:
  1. 4h Wyckoff 放量突破: 胜率 53.5%, PnL 147%, PF 1.28
  2. 1d 布林均值回归: 胜率 50%, PnL 83%, PF 1.27
  3. 1d SMC BOS+EMA: 胜率 50%, PnL 48%, PF 1.30

组合思路:
  A. 在 4h 图上跑 Wyckoff,用 1d 趋势(EMA 20>50)做顺势过滤
  B. 在 4h 图上跑 Wyckoff + SuperTrend 双确认
  C. 同时在 4h 和 1d 跑,只有两边方向一致才入场
"""
import pandas as pd
import numpy as np
import os
from backtest import ema, atr, run_backtest, sig_wyckoff, sig_supertrend, sig_smc_bos, sig_bb_meanrev

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

def load(tf):
    df = pd.read_csv(os.path.join(DATA_DIR, f"ethusdt_{tf}.csv"))
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

def resample_higher(df_4h):
    """从 4h 数据聚合出 1d 数据"""
    d = df_4h.set_index("timestamp")
    dd = d.resample("1D").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
    return dd.reset_index()

# ==================== 组合 A: Wyckoff(4h) + 1d 趋势过滤 ====================
def combo_wyckoff_with_daily_trend():
    df4 = load("4h")
    df1d = load("1d")
    # 为 4h 每根 K 算出当时的 1d 趋势
    df1d["ema20"] = ema(df1d["close"], 20)
    df1d["ema50"] = ema(df1d["close"], 50)
    df1d["trend_up"] = (df1d["ema20"] > df1d["ema50"]) & (df1d["close"] > df1d["ema20"])
    df1d["trend_dn"] = (df1d["ema20"] < df1d["ema50"]) & (df1d["close"] < df1d["ema20"])

    # 把 1d 趋势映射回 4h
    df1d_small = df1d[["timestamp","trend_up","trend_dn"]].copy()
    df1d_small["timestamp"] = df1d_small["timestamp"].dt.floor("D")
    merged = df4.copy()
    merged["date"] = merged["timestamp"].dt.floor("D")
    merged = merged.merge(df1d_small, left_on="date", right_on="timestamp", how="left", suffixes=("","_d"))
    merged["trend_up"] = merged["trend_up"].ffill().fillna(False)
    merged["trend_dn"] = merged["trend_dn"].ffill().fillna(False)

    sigs_raw = sig_wyckoff(df4)
    sigs = pd.Series(0, index=df4.index)
    sigs[(sigs_raw == 1) & merged["trend_up"].values] = 1
    sigs[(sigs_raw == -1) & merged["trend_dn"].values] = -1
    a = atr(df4, 14)
    return run_backtest(df4, sigs, "Wyckoff(4h) + 1d 趋势", "4h", a)

# ==================== 组合 B: Wyckoff + SuperTrend 同向 ====================
def combo_wyckoff_supertrend():
    df = load("4h")
    s1 = sig_wyckoff(df)
    # SuperTrend 当前方向
    a_st = atr(df, 10)
    hl2 = (df["high"] + df["low"]) / 2
    upper = hl2 + 3.0 * a_st
    lower = hl2 - 3.0 * a_st
    st_dir = pd.Series(1, index=df.index)
    for i in range(1, len(df)):
        prev_st = upper.iloc[i-1] if st_dir.iloc[i-1] == -1 else lower.iloc[i-1]
        if df["close"].iloc[i-1] > prev_st:
            st_dir.iloc[i] = 1
        else:
            st_dir.iloc[i] = -1
    sigs = pd.Series(0, index=df.index)
    sigs[(s1 == 1) & (st_dir == 1)] = 1
    sigs[(s1 == -1) & (st_dir == -1)] = -1
    a = atr(df, 14)
    return run_backtest(df, sigs, "Wyckoff + SuperTrend", "4h", a)

# ==================== 组合 C: SMC BOS + 1d 趋势 (4h) ====================
def combo_smc_with_daily_trend():
    df4 = load("4h")
    df1d = load("1d")
    df1d["ema20"] = ema(df1d["close"], 20)
    df1d["ema50"] = ema(df1d["close"], 50)
    df1d["trend_up"] = (df1d["ema20"] > df1d["ema50"]) & (df1d["close"] > df1d["ema20"])
    df1d["trend_dn"] = (df1d["ema20"] < df1d["ema50"]) & (df1d["close"] < df1d["ema20"])
    df1d_small = df1d[["timestamp","trend_up","trend_dn"]].copy()
    df1d_small["timestamp"] = df1d_small["timestamp"].dt.floor("D")
    merged = df4.copy()
    merged["date"] = merged["timestamp"].dt.floor("D")
    merged = merged.merge(df1d_small, left_on="date", right_on="timestamp", how="left", suffixes=("","_d"))
    merged["trend_up"] = merged["trend_up"].ffill().fillna(False)
    merged["trend_dn"] = merged["trend_dn"].ffill().fillna(False)

    sigs_raw = sig_smc_bos(df4)
    sigs = pd.Series(0, index=df4.index)
    sigs[(sigs_raw == 1) & merged["trend_up"].values] = 1
    sigs[(sigs_raw == -1) & merged["trend_dn"].values] = -1
    a = atr(df4, 14)
    return run_backtest(df4, sigs, "SMC BOS(4h) + 1d 趋势", "4h", a)

# ==================== 组合 D: 只做多(币圈长牛偏好) ====================
def combo_wyckoff_long_only():
    df = load("4h")
    s = sig_wyckoff(df)
    s[s < 0] = 0   # 只保留做多信号
    a = atr(df, 14)
    return run_backtest(df, s, "Wyckoff 只做多", "4h", a)

# ==================== 组合 E: 布林回归(1d)只做多 ====================
def combo_bb_long_only():
    df = load("1d")
    s = sig_bb_meanrev(df)
    s[s < 0] = 0
    a = atr(df, 14)
    return run_backtest(df, s, "布林回归 只做多", "1d", a)

if __name__ == "__main__":
    print("\n========== 组合策略回测 ==========")
    results = [
        combo_wyckoff_with_daily_trend(),
        combo_wyckoff_supertrend(),
        combo_smc_with_daily_trend(),
        combo_wyckoff_long_only(),
        combo_bb_long_only(),
    ]
    for r in results:
        print(f"  [{r.tf:>2}] {r.strategy:<26} trades={r.trades:>3}  "
              f"win={r.win_rate:>5.1f}%  PnL={r.net_pnl_pct:>7.2f}%  PF={r.profit_factor:.2f}  MDD={r.max_drawdown_pct:.1f}%")
