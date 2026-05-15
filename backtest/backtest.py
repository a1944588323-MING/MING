"""
ETH 多策略回测对比
数据源: OKX (ETH-USDT)
周期: 1h / 4h / 1d

策略列表(9 个):
  1. EMA 交叉        - 最经典的趋势跟踪
  2. MACD           - 趋势动量
  3. RSI 反转       - 超买超卖反转
  4. 布林带均值回归  - 震荡市
  5. 布林带突破     - 波动率突破
  6. Donchian 突破  - 海龟交易法
  7. SuperTrend     - ATR 趋势跟踪
  8. SMC(BOS)     - 结构突破 + EMA 过滤
  9. Wyckoff 模拟   - 吸筹/派发区 + 突破

统一使用:
  - 初始资金 10000 USDT
  - 每笔仓位 10% 权益
  - 止损: 2×ATR
  - 止盈: 3×ATR(1.5 RR)
  - 手续费 0.05% + 滑点 0.05%
"""

import pandas as pd
import numpy as np
import os
import json
from dataclasses import dataclass, asdict
from typing import List, Dict

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# ==================== 工具函数 ====================

def ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False).mean()

def sma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n).mean()

def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"]  - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def rsi(series: pd.Series, n: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    rs = up.ewm(alpha=1/n, adjust=False).mean() / down.ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100/(1+rs)

def macd(series: pd.Series, fast=12, slow=26, signal=9):
    m = ema(series, fast) - ema(series, slow)
    s = ema(m, signal)
    return m, s, m - s

def bbands(series: pd.Series, n=20, k=2.0):
    mid = sma(series, n)
    std = series.rolling(n).std()
    return mid, mid + k*std, mid - k*std

# ==================== 回测引擎 ====================

@dataclass
class BTResult:
    strategy: str
    tf: str
    trades: int
    wins: int
    losses: int
    win_rate: float
    net_pnl: float
    net_pnl_pct: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    max_drawdown_pct: float
    expectancy_per_trade: float

def run_backtest(df: pd.DataFrame, signals: pd.Series, name: str, tf: str,
                  atr_series: pd.Series, sl_mult=2.0, tp_mult=3.0,
                  initial=10000.0, risk_pct=0.10, fee=0.0005, slip=0.0005) -> BTResult:
    """
    signals: +1 = 开多, -1 = 开空, 0 = 不动
    使用 下一根 K 的 open 入场(避免未来函数)
    止损止盈用当根 K 的 high/low 检测
    """
    equity = initial
    peak = initial
    max_dd = 0.0
    trades = []
    position = 0   # 0 = 无, 1 = 多, -1 = 空
    entry = sl = tp = 0.0
    qty = 0.0

    opens  = df["open"].values
    highs  = df["high"].values
    lows   = df["low"].values
    closes = df["close"].values
    sigs   = signals.values
    atrs   = atr_series.values
    n = len(df)

    for i in range(n - 1):
        # 持仓中:先检查止损止盈
        if position != 0:
            hit_sl = lows[i] <= sl if position == 1 else highs[i] >= sl
            hit_tp = highs[i] >= tp if position == 1 else lows[i] <= tp
            exit_price = None
            result = None
            if hit_sl and hit_tp:
                # 保守:按止损算
                exit_price = sl
                result = "loss"
            elif hit_sl:
                exit_price = sl
                result = "loss"
            elif hit_tp:
                exit_price = tp
                result = "win"

            if exit_price is not None:
                # 扣手续费+滑点
                if position == 1:
                    gross = (exit_price - entry) * qty
                else:
                    gross = (entry - exit_price) * qty
                cost = (entry + exit_price) * qty * (fee + slip)
                pnl = gross - cost
                equity += pnl
                trades.append({"pnl": pnl, "result": result})
                position = 0

                if equity > peak:
                    peak = equity
                dd = (peak - equity) / peak * 100
                if dd > max_dd:
                    max_dd = dd

        # 检查信号(用 i 根的信号,i+1 根 open 入场)
        if position == 0 and sigs[i] != 0 and not np.isnan(atrs[i]) and atrs[i] > 0:
            direction = int(sigs[i])
            entry = opens[i+1]
            a = atrs[i]
            if direction == 1:
                sl = entry - sl_mult * a
                tp = entry + tp_mult * a
            else:
                sl = entry + sl_mult * a
                tp = entry - tp_mult * a
            risk_usd = equity * risk_pct
            stop_dist = abs(entry - sl)
            if stop_dist > 0:
                qty = risk_usd / stop_dist
                position = direction

    # 未平仓按最后一根 close 结算
    if position != 0:
        exit_price = closes[-1]
        if position == 1:
            gross = (exit_price - entry) * qty
        else:
            gross = (entry - exit_price) * qty
        cost = (entry + exit_price) * qty * (fee + slip)
        pnl = gross - cost
        equity += pnl
        trades.append({"pnl": pnl, "result": "win" if pnl > 0 else "loss"})

    # 统计
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = -sum(t["pnl"] for t in losses) or 1e-9
    pf = gross_win / gross_loss if gross_loss > 0 else 0
    win_rate = len(wins) / len(trades) * 100 if trades else 0
    avg_win = gross_win / len(wins) if wins else 0
    avg_loss = -gross_loss / len(losses) if losses else 0
    expectancy = (equity - initial) / len(trades) if trades else 0

    return BTResult(
        strategy=name, tf=tf,
        trades=len(trades), wins=len(wins), losses=len(losses),
        win_rate=round(win_rate, 2),
        net_pnl=round(equity - initial, 2),
        net_pnl_pct=round((equity - initial) / initial * 100, 2),
        profit_factor=round(pf, 3),
        avg_win=round(avg_win, 2),
        avg_loss=round(avg_loss, 2),
        max_drawdown_pct=round(max_dd, 2),
        expectancy_per_trade=round(expectancy, 2),
    )

# ==================== 策略信号生成 ====================

def sig_ema_cross(df, fast=20, slow=50):
    ef = ema(df["close"], fast)
    es = ema(df["close"], slow)
    s = pd.Series(0, index=df.index)
    # 金叉做多
    s[(ef > es) & (ef.shift() <= es.shift())] = 1
    # 死叉做空
    s[(ef < es) & (ef.shift() >= es.shift())] = -1
    return s

def sig_macd(df):
    m, sl, h = macd(df["close"])
    s = pd.Series(0, index=df.index)
    s[(m > sl) & (m.shift() <= sl.shift()) & (m > 0)] = 1
    s[(m < sl) & (m.shift() >= sl.shift()) & (m < 0)] = -1
    return s

def sig_rsi_reversal(df, n=14, ob=70, os=30):
    r = rsi(df["close"], n)
    s = pd.Series(0, index=df.index)
    # 从超卖回升
    s[(r > os) & (r.shift() <= os)] = 1
    s[(r < ob) & (r.shift() >= ob)] = -1
    return s

def sig_bb_meanrev(df, n=20, k=2.0):
    mid, ub, lb = bbands(df["close"], n, k)
    s = pd.Series(0, index=df.index)
    # 触下轨后收回做多
    s[(df["close"] > lb) & (df["close"].shift() <= lb.shift())] = 1
    s[(df["close"] < ub) & (df["close"].shift() >= ub.shift())] = -1
    return s

def sig_bb_breakout(df, n=20, k=2.0):
    mid, ub, lb = bbands(df["close"], n, k)
    s = pd.Series(0, index=df.index)
    s[(df["close"] > ub) & (df["close"].shift() <= ub.shift())] = 1
    s[(df["close"] < lb) & (df["close"].shift() >= lb.shift())] = -1
    return s

def sig_donchian(df, n=20):
    upper = df["high"].rolling(n).max().shift(1)
    lower = df["low"].rolling(n).min().shift(1)
    s = pd.Series(0, index=df.index)
    s[df["close"] > upper] = 1
    s[df["close"] < lower] = -1
    # 每根只触发一次
    s = s.where(s != s.shift(), 0)
    return s

def sig_supertrend(df, n=10, mult=3.0):
    a = atr(df, n)
    hl2 = (df["high"] + df["low"]) / 2
    upper = hl2 + mult * a
    lower = hl2 - mult * a
    st = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(1, index=df.index)
    for i in range(len(df)):
        if i == 0:
            st.iloc[i] = lower.iloc[i]
            continue
        prev_st = st.iloc[i-1]
        if df["close"].iloc[i-1] > prev_st:
            direction.iloc[i] = 1
            st.iloc[i] = max(lower.iloc[i], prev_st)
        else:
            direction.iloc[i] = -1
            st.iloc[i] = min(upper.iloc[i], prev_st)
        if direction.iloc[i] != direction.iloc[i-1]:
            st.iloc[i] = lower.iloc[i] if direction.iloc[i] == 1 else upper.iloc[i]
    s = pd.Series(0, index=df.index)
    s[(direction == 1) & (direction.shift() == -1)] = 1
    s[(direction == -1) & (direction.shift() == 1)] = -1
    return s

def sig_smc_bos(df, swing=10, ema_fast=21, ema_slow=50):
    """SMC: 结构突破 BOS + EMA 趋势过滤"""
    ef = ema(df["close"], ema_fast)
    es = ema(df["close"], ema_slow)
    trend_up = (ef > es) & (df["close"] > ef)
    trend_dn = (ef < es) & (df["close"] < ef)

    # 摆动高低点(简化: 过去 swing 根的 high/low)
    ph = df["high"].rolling(swing*2+1, center=True).max() == df["high"]
    pl = df["low"].rolling(swing*2+1, center=True).min() == df["low"]

    last_ph = pd.Series(np.nan, index=df.index)
    last_pl = pd.Series(np.nan, index=df.index)
    v_ph = np.nan
    v_pl = np.nan
    for i in range(len(df)):
        if ph.iloc[i] and not pd.isna(df["high"].iloc[i]):
            v_ph = df["high"].iloc[i]
        if pl.iloc[i] and not pd.isna(df["low"].iloc[i]):
            v_pl = df["low"].iloc[i]
        last_ph.iloc[i] = v_ph
        last_pl.iloc[i] = v_pl

    # BOS up: close 突破 last_ph
    bos_up = (df["close"] > last_ph.shift(swing)) & (df["close"].shift() <= last_ph.shift(swing+1))
    bos_dn = (df["close"] < last_pl.shift(swing)) & (df["close"].shift() >= last_pl.shift(swing+1))

    s = pd.Series(0, index=df.index)
    s[bos_up & trend_up] = 1
    s[bos_dn & trend_dn] = -1
    return s

def sig_wyckoff(df, n=50):
    """Wyckoff 简化: 低位窄幅震荡后放量突破 = 吸筹结束,做多"""
    # 价格波动率
    rng = (df["high"].rolling(n).max() - df["low"].rolling(n).min()) / df["close"]
    vol_avg = df["volume"].rolling(n).mean()

    # 低位窄幅:价格波动小 + 靠近 N 期底部
    near_bottom = df["close"] <= df["low"].rolling(n).min() * 1.05
    near_top    = df["close"] >= df["high"].rolling(n).max() * 0.95
    tight = rng < rng.rolling(n).quantile(0.3)

    # 放量突破
    vol_spike = df["volume"] > vol_avg * 1.8
    breakout_up = df["close"] > df["high"].rolling(20).max().shift(1)
    breakout_dn = df["close"] < df["low"].rolling(20).min().shift(1)

    s = pd.Series(0, index=df.index)
    s[breakout_up & vol_spike & near_bottom.shift(5).fillna(False)] = 1
    s[breakout_dn & vol_spike & near_top.shift(5).fillna(False)] = -1
    return s

# ==================== 主流程 ====================

STRATEGIES = {
    "EMA 交叉 20/50":    sig_ema_cross,
    "MACD":             sig_macd,
    "RSI 反转":          sig_rsi_reversal,
    "布林带均值回归":      sig_bb_meanrev,
    "布林带突破":         sig_bb_breakout,
    "Donchian 突破":    sig_donchian,
    "SuperTrend":       sig_supertrend,
    "SMC BOS+EMA":     sig_smc_bos,
    "Wyckoff 放量突破":   sig_wyckoff,
}

def main():
    tfs = [("1h", "ethusdt_1h.csv"), ("4h", "ethusdt_4h.csv"), ("1d", "ethusdt_1d.csv")]
    all_results: List[BTResult] = []

    for tf, fname in tfs:
        path = os.path.join(DATA_DIR, fname)
        df = pd.read_csv(path)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        atr_s = atr(df, 14)
        print(f"\n===== ETH {tf}  ({len(df)} bars, {df['timestamp'].min().date()} -> {df['timestamp'].max().date()}) =====")
        for name, fn in STRATEGIES.items():
            try:
                sigs = fn(df)
                res = run_backtest(df, sigs, name, tf, atr_s)
                all_results.append(res)
                print(f"  {name:<22} trades={res.trades:>4}  win={res.win_rate:>5.1f}%  "
                      f"PnL={res.net_pnl_pct:>7.2f}%  PF={res.profit_factor:>5.2f}  MDD={res.max_drawdown_pct:>5.1f}%")
            except Exception as e:
                print(f"  {name:<22} FAILED: {e}")

    # 保存 JSON
    out = [asdict(r) for r in all_results]
    with open(os.path.join(DATA_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    # 输出总结
    print("\n\n========== 汇总:按综合评分排序 ==========")
    # 综合评分 = net_pnl_pct * 0.4 + win_rate * 0.3 + pf * 10 * 0.2 - mdd * 0.1
    scored = []
    for r in all_results:
        score = r.net_pnl_pct * 0.4 + r.win_rate * 0.3 + r.profit_factor * 10 * 0.2 - r.max_drawdown_pct * 0.1
        scored.append((score, r))
    scored.sort(key=lambda x: -x[0])
    for score, r in scored[:15]:
        print(f"  [{r.tf:>2}] {r.strategy:<22} 评分={score:>6.2f}  trades={r.trades:>3}  win={r.win_rate:>5.1f}%  PnL={r.net_pnl_pct:>7.2f}%  PF={r.profit_factor:.2f}")

if __name__ == "__main__":
    main()
