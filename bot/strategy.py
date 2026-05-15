"""
双周期共振策略核心 (逆向+中性模式)
与 Pine 脚本 MA_BS_MultiTF_Resonance.pine 逻辑完全一致
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from dataclasses import dataclass


# ============ 指标计算 ============
def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([(h-l), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    up_move = h.diff()
    dn_move = -l.diff()
    plus_dm  = np.where((up_move > dn_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((dn_move > up_move) & (dn_move > 0), dn_move, 0.0)
    tr = pd.concat([(h-l), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    atr_ = tr.ewm(alpha=1/n, adjust=False).mean()
    plus_di  = 100 * pd.Series(plus_dm,  index=df.index).ewm(alpha=1/n, adjust=False).mean() / atr_
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1/n, adjust=False).mean() / atr_
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1/n, adjust=False).mean()


# ============ 信号数据类 ============
@dataclass
class Signal:
    side: str            # "long" / "short" / "none"
    entry: float
    sl: float
    tp: float
    reason: str
    daily_status: str    # "strong_bull" / "strong_bear" / "neutral"
    h4_trend: str        # "bull" / "bear" / "range"
    adx: float
    rsi: float
    atr: float


@dataclass
class StrategyConfig:
    # 4H 均线
    ema_fast: int = 20
    ema_mid: int = 50
    ema_slow: int = 200
    # 日线均线
    d_ema_fast: int = 30
    d_ema_slow: int = 200
    d_strong_pct: float = 5.0
    # 过滤器
    adx_min: float = 25.0
    rsi_long_min: float = 40
    rsi_long_max: float = 70
    rsi_short_min: float = 30
    rsi_short_max: float = 60
    touch_tol_pct: float = 0.5
    # 止损止盈
    sl_atr_mult: float = 3.0
    rr_mult: float = 1.67
    # 共振模式: reverse / pure / forward
    resonance_mode: str = "reverse"


# ============ 策略主函数 ============
def evaluate_signal(df_4h: pd.DataFrame, df_daily: pd.DataFrame,
                    cfg: StrategyConfig) -> Signal:
    """
    传入 4H 和日线数据,返回当前最后一根 K 线的信号.

    df_4h / df_daily: DataFrame(index=datetime, columns=[open,high,low,close,volume])
    """
    if len(df_4h) < max(cfg.ema_slow, 50) + 10:
        return Signal("none", 0, 0, 0, "数据不足", "neutral", "range", 0, 0, 0)

    # ---- 日线状态 ----
    d = df_daily.copy()
    d["d_ema_fast"] = ema(d["close"], cfg.d_ema_fast)
    d["d_ema_slow"] = ema(d["close"], cfg.d_ema_slow)
    d["d_spread"] = (d["d_ema_fast"] - d["d_ema_slow"]) / d["d_ema_slow"] * 100
    last_d = d.iloc[-1]
    d_spread = last_d["d_spread"]
    d_bull_strong = d_spread > cfg.d_strong_pct
    d_bear_strong = d_spread < -cfg.d_strong_pct
    d_neutral = abs(d_spread) <= cfg.d_strong_pct
    daily_status = ("strong_bull" if d_bull_strong else
                    "strong_bear" if d_bear_strong else "neutral")

    # ---- 4H 指标 ----
    f = df_4h.copy()
    f["ema_fast"] = ema(f["close"], cfg.ema_fast)
    f["ema_mid"]  = ema(f["close"], cfg.ema_mid)
    f["ema_slow"] = ema(f["close"], cfg.ema_slow)
    f["rsi"]      = rsi(f["close"])
    f["atr"]      = atr(f, 14)
    f["adx"]      = adx(f, 14)

    # 取最后一根已收盘K线 (倒数第二根才是已确认收盘)
    # 实盘中传入的数据最后一根通常已收盘,这里直接取 iloc[-1]
    cur = f.iloc[-1]
    prev = f.iloc[-2]

    ema_f, ema_m, ema_s = cur["ema_fast"], cur["ema_mid"], cur["ema_slow"]
    bull_trend = ema_f > ema_m > ema_s
    bear_trend = ema_f < ema_m < ema_s
    strong = cur["adx"] > cfg.adx_min
    h4_trend = ("bull" if bull_trend and strong else
                "bear" if bear_trend and strong else "range")

    # 回调触发 (针对 cur 这根 K 线)
    long_pb  = (cur["low"]  <= ema_f * (1 + cfg.touch_tol_pct/100)
                and cur["close"] > ema_f and cur["close"] > cur["open"])
    short_pb = (cur["high"] >= ema_f * (1 - cfg.touch_tol_pct/100)
                and cur["close"] < ema_f and cur["close"] < cur["open"])

    rsi_long_ok  = cfg.rsi_long_min  <= cur["rsi"] <= cfg.rsi_long_max
    rsi_short_ok = cfg.rsi_short_min <= cur["rsi"] <= cfg.rsi_short_max

    long_raw  = bull_trend and strong and long_pb  and rsi_long_ok
    short_raw = bear_trend and strong and short_pb and rsi_short_ok

    # ---- 共振过滤 ----
    mode = cfg.resonance_mode.lower()
    if mode == "pure":
        long_allow, short_allow = True, True
    elif mode == "reverse":   # 最优模式: 逆向+中性
        long_allow  = d_bear_strong or d_neutral
        short_allow = d_bull_strong or d_neutral
    elif mode == "forward":   # 传统顺向 (实测亏钱,不推荐)
        long_allow  = d_bull_strong
        short_allow = d_bear_strong
    else:
        long_allow = short_allow = False

    long_ok  = long_raw  and long_allow
    short_ok = short_raw and short_allow

    # ---- 生成信号 ----
    if long_ok:
        entry = float(cur["close"])
        sl_dist = cur["atr"] * cfg.sl_atr_mult
        sl = entry - sl_dist
        tp = entry + sl_dist * cfg.rr_mult
        return Signal("long", entry, sl, tp,
                      f"多单: 4H多头+回调+日线{daily_status}",
                      daily_status, h4_trend,
                      float(cur["adx"]), float(cur["rsi"]), float(cur["atr"]))
    if short_ok:
        entry = float(cur["close"])
        sl_dist = cur["atr"] * cfg.sl_atr_mult
        sl = entry + sl_dist
        tp = entry - sl_dist * cfg.rr_mult
        return Signal("short", entry, sl, tp,
                      f"空单: 4H空头+回调+日线{daily_status}",
                      daily_status, h4_trend,
                      float(cur["adx"]), float(cur["rsi"]), float(cur["atr"]))

    # 被过滤的信号
    reason = "无信号"
    if long_raw and not long_allow:
        reason = f"多信号被共振挡掉 (日线{daily_status})"
    elif short_raw and not short_allow:
        reason = f"空信号被共振挡掉 (日线{daily_status})"
    elif not strong:
        reason = f"ADX不够 ({cur['adx']:.1f}<{cfg.adx_min})"
    elif not (bull_trend or bear_trend):
        reason = "4H震荡,均线未排列"

    return Signal("none", float(cur["close"]), 0, 0, reason,
                  daily_status, h4_trend,
                  float(cur["adx"]), float(cur["rsi"]), float(cur["atr"]))
