"""
本地回测脚本 (验证策略与实盘代码逻辑一致)
运行: python backtest_local.py
"""
from __future__ import annotations
import ccxt
import pandas as pd
from strategy import StrategyConfig, evaluate_signal


def fetch_okx(symbol: str, tf: str, days: int) -> pd.DataFrame:
    ex = ccxt.okx({"enableRateLimit": True})
    since = ex.parse8601((pd.Timestamp.utcnow() - pd.Timedelta(days=days)).isoformat())
    rows = []
    while True:
        chunk = ex.fetch_ohlcv(symbol, timeframe=tf, since=since, limit=300)
        if not chunk: break
        rows.extend(chunk)
        since = chunk[-1][0] + 1
        if len(chunk) < 10: break
    df = pd.DataFrame(rows, columns=["ts","open","high","low","close","volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df.drop_duplicates("ts").set_index("ts")


def backtest(df_4h: pd.DataFrame, df_daily: pd.DataFrame, cfg: StrategyConfig):
    """逐根K线回测,与实盘逻辑一致"""
    trades = []
    pos = None

    for i in range(250, len(df_4h) - 1):
        df_slice = df_4h.iloc[:i+1]
        ts_i = df_slice.index[-1]
        daily_slice = df_daily[df_daily.index <= ts_i]
        if len(daily_slice) < 200: continue

        sig = evaluate_signal(df_slice, daily_slice, cfg)
        bar = df_4h.iloc[i]
        nxt = df_4h.iloc[i+1]

        # 平仓逻辑
        if pos is not None:
            exit_p, reason = None, None
            if pos["side"] == "long":
                if bar["low"]  <= pos["sl"]: exit_p, reason = pos["sl"], "SL"
                elif bar["high"] >= pos["tp"]: exit_p, reason = pos["tp"], "TP"
            else:
                if bar["high"] >= pos["sl"]: exit_p, reason = pos["sl"], "SL"
                elif bar["low"]  <= pos["tp"]: exit_p, reason = pos["tp"], "TP"
            if exit_p is not None:
                pnl = (exit_p - pos["entry"]) / pos["entry"]
                pnl = pnl if pos["side"]=="long" else -pnl
                pnl -= 0.001
                trades.append({**pos, "exit": exit_p, "pnl": pnl, "reason": reason,
                               "ts_out": bar.name})
                pos = None

        # 开仓
        if pos is None and sig.side != "none":
            ep = nxt["open"]
            sl_dist = sig.atr * cfg.sl_atr_mult
            if sig.side == "long":
                pos = {"side":"long", "entry":ep,
                       "sl": ep - sl_dist, "tp": ep + sl_dist * cfg.rr_mult,
                       "ts_in": nxt.name}
            else:
                pos = {"side":"short", "entry":ep,
                       "sl": ep + sl_dist, "tp": ep - sl_dist * cfg.rr_mult,
                       "ts_in": nxt.name}

    return pd.DataFrame(trades)


if __name__ == "__main__":
    print("下载数据...")
    df_4h = fetch_okx("ETH/USDT", "4h", 730)
    df_daily = fetch_okx("ETH/USDT", "1d", 1500)
    print(f"4H: {len(df_4h)} 根, 日线: {len(df_daily)} 根")

    cfg = StrategyConfig(resonance_mode="reverse", adx_min=25, sl_atr_mult=3.0, rr_mult=1.67)
    print(f"\n回测: {cfg}")
    trades = backtest(df_4h, df_daily, cfg)

    if trades.empty:
        print("无交易"); exit()

    n = len(trades); win = (trades["pnl"] > 0).sum(); wr = win / n
    eq = (1 + trades["pnl"]).cumprod()
    ret = eq.iloc[-1] - 1
    dd = ((eq.cummax() - eq) / eq.cummax()).max()
    awin = trades.loc[trades["pnl"]>0, "pnl"].mean() or 0
    alos = trades.loc[trades["pnl"]<0, "pnl"].mean() or 0
    pf = -trades.loc[trades["pnl"]>0,"pnl"].sum()/trades.loc[trades["pnl"]<0,"pnl"].sum() \
          if (trades["pnl"]<0).any() else 99
    print(f"\n交易数: {n} | 胜率: {wr:.1%} | 盈亏比: {awin/-alos if alos else 0:.2f}")
    print(f"利润因子: {pf:.2f} | 累计收益: {ret:+.1%} | 最大回撤: {dd:.1%}")
    trades.to_csv("backtest_trades.csv", index=False)
    print("已保存 backtest_trades.csv")
