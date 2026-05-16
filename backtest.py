"""
SMC Flow Strategy — Python backtest replicating the Pine logic.

Data: Binance USDT-M perpetuals via ccxt
Logic mirrors SMC_Flow_Strategy_GridScan.pine:
  Entry  LONG  = UT-Bot Buy  & Hull up  & break of swing high
  Entry  SHORT = UT-Bot Sell & Hull dn  & break of swing low
  Exit         = ATR stop / R:R take-profit / opposite UT signal
"""
from __future__ import annotations
import math, os, sys, time, json
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import ccxt

# ---------------------------- Data ----------------------------

def fetch_ohlcv(symbol: str, tf: str, since_ms: int, exchange) -> pd.DataFrame:
    all_rows = []
    cursor = since_ms
    # exchange-specific page size
    page = 100
    if exchange.id == "okx":
        page = 300
    elif exchange.id in ("kraken", "kucoin", "bitget", "gate", "mexc"):
        page = 500
    end_ms = int(time.time() * 1000)
    while cursor < end_ms:
        try:
            rows = exchange.fetch_ohlcv(symbol, timeframe=tf, since=cursor, limit=page)
        except Exception as e:
            print(f"  fetch error at {datetime.fromtimestamp(cursor/1000, tz=timezone.utc)}: {e}", file=sys.stderr)
            time.sleep(1)
            continue
        if not rows:
            break
        # filter dupes
        new_rows = [r for r in rows if not all_rows or r[0] > all_rows[-1][0]]
        if not new_rows:
            break
        all_rows.extend(new_rows)
        last = new_rows[-1][0]
        cursor = last + 1
        time.sleep(exchange.rateLimit / 1000)
    df = pd.DataFrame(all_rows, columns=["t","o","h","l","c","v"]).drop_duplicates("t")
    df["dt"] = pd.to_datetime(df["t"], unit="ms", utc=True)
    df.set_index("dt", inplace=True)
    return df[["o","h","l","c","v"]].astype(float).sort_index()


# ------------------------ Indicators -------------------------

def atr(h, l, c, n):
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False).mean()  # Wilder smoothing


def ut_bot_signals(df: pd.DataFrame, key: float, atr_p: int):
    a = atr(df.h, df.l, df.c, atr_p).to_numpy()
    nLoss = key * a
    src = df.c.to_numpy()
    n = len(src)
    trail = np.zeros(n)
    for i in range(1, n):
        prev = trail[i - 1]
        if src[i] > prev and src[i - 1] > prev:
            trail[i] = max(prev, src[i] - nLoss[i])
        elif src[i] < prev and src[i - 1] < prev:
            trail[i] = min(prev, src[i] + nLoss[i])
        elif src[i] > prev:
            trail[i] = src[i] - nLoss[i]
        else:
            trail[i] = src[i] + nLoss[i]

    above_prev = src[:-1] <= trail[:-1]
    above_now  = src[1:]  >  trail[1:]
    below_prev = src[:-1] >= trail[:-1]
    below_now  = src[1:]  <  trail[1:]
    buy  = np.zeros(n, dtype=bool); buy[1:]  = above_prev & above_now & (src[1:] > trail[1:])
    sell = np.zeros(n, dtype=bool); sell[1:] = below_prev & below_now & (src[1:] < trail[1:])
    return buy, sell, trail, a


def wma(s: pd.Series, n: int) -> pd.Series:
    w = np.arange(1, n + 1, dtype=float)
    return s.rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)


def hma(s: pd.Series, n: int) -> pd.Series:
    half = max(1, n // 2)
    sqrt_n = max(1, int(round(math.sqrt(n))))
    return wma(2 * wma(s, half) - wma(s, n), sqrt_n)


# ------------------------- Backtest --------------------------

def backtest(df: pd.DataFrame, p: dict, fee: float = 0.0005, slip_bp: float = 2.0) -> dict:
    buy, sell, trail, a = ut_bot_signals(df, p["utKey"], p["utATR"])
    h = hma(df.c, p["hullLen"])
    hull_up = (h > h.shift(2)).to_numpy()
    hull_dn = (h < h.shift(2)).to_numpy()

    swing_hi = df.h.rolling(p["swLb"]).max().shift(1).to_numpy()
    swing_lo = df.l.rolling(p["swLb"]).min().shift(1).to_numpy()
    close = df.c.to_numpy()
    high  = df.h.to_numpy()
    low   = df.l.to_numpy()
    n = len(close)

    long_cond = buy  & (hull_up | (not p["useHull"])) & ((close > swing_hi) | (not p["useBoS"]))
    short_cond = sell & (hull_dn | (not p["useHull"])) & ((close < swing_lo) | (not p["useBoS"]))

    equity = 1.0
    pos = 0           # 1 long, -1 short, 0 flat
    entry = 0.0
    sl = tp = 0.0
    qty = 0.0
    eq_curve = np.zeros(n)
    trades = []
    slip = slip_bp / 1e4

    def open_trade(i, direction):
        nonlocal pos, entry, sl, tp, qty, equity
        px = close[i] * (1 + slip if direction == 1 else 1 - slip)
        equity *= (1 - fee)         # entry fee
        qty = equity / px
        entry = px
        pos = direction
        atr_v = a[i]
        if direction == 1:
            sl = entry - p["slMult"] * atr_v
            tp = entry + p["slMult"] * atr_v * p["rrR"]
        else:
            sl = entry + p["slMult"] * atr_v
            tp = entry - p["slMult"] * atr_v * p["rrR"]

    def close_trade(i, exit_px, reason):
        nonlocal pos, equity, qty
        exit_px_eff = exit_px * (1 - slip if pos == 1 else 1 + slip)
        pnl_factor = (exit_px_eff / entry) if pos == 1 else (entry / exit_px_eff)
        equity = qty * exit_px_eff
        equity *= (1 - fee)         # exit fee
        trades.append({
            "side": "L" if pos == 1 else "S",
            "entry": entry, "exit": exit_px_eff,
            "pnl_pct": (pnl_factor - 1) * 100,
            "reason": reason,
            "i": i,
        })
        pos = 0
        qty = 0.0

    for i in range(max(p["utATR"], p["hullLen"], p["swLb"]) + 5, n):
        # 1) check exits first (intra-bar SL/TP using high/low)
        if pos == 1:
            if low[i] <= sl:
                close_trade(i, sl, "SL")
            elif high[i] >= tp:
                close_trade(i, tp, "TP")
            elif sell[i]:
                close_trade(i, close[i], "FLIP")
        elif pos == -1:
            if high[i] >= sl:
                close_trade(i, sl, "SL")
            elif low[i] <= tp:
                close_trade(i, tp, "TP")
            elif buy[i]:
                close_trade(i, close[i], "FLIP")

        # 2) entries (after potential close)
        if pos == 0:
            if long_cond[i]:
                open_trade(i, 1)
            elif short_cond[i]:
                open_trade(i, -1)

        # 3) mark-to-market equity curve
        if pos == 1:
            eq_curve[i] = qty * close[i]
        elif pos == -1:
            # short equity = entry value + (entry - close)*qty_at_entry
            eq_curve[i] = qty * (2 * entry - close[i])
        else:
            eq_curve[i] = equity

    # final close at last bar
    if pos != 0:
        close_trade(n - 1, close[-1], "EOD")
        eq_curve[-1] = equity

    # ---- metrics ----
    eq_curve = pd.Series(np.where(eq_curve == 0, np.nan, eq_curve), index=df.index).ffill().fillna(1.0)
    net_ret = eq_curve.iloc[-1] - 1
    days = (df.index[-1] - df.index[0]).days
    years = days / 365.25 if days > 0 else 1
    cagr = (eq_curve.iloc[-1]) ** (1 / years) - 1 if years > 0 else 0
    peak = eq_curve.cummax()
    dd = (eq_curve / peak - 1).min()

    if trades:
        tdf = pd.DataFrame(trades)
        wins = tdf[tdf.pnl_pct > 0].pnl_pct.sum()
        losses = abs(tdf[tdf.pnl_pct < 0].pnl_pct.sum())
        pf = wins / losses if losses > 0 else float("inf")
        wr = (tdf.pnl_pct > 0).mean() * 100
    else:
        pf = 0
        wr = 0

    return {
        "Net%": round(net_ret * 100, 2),
        "CAGR%": round(cagr * 100, 2),
        "MaxDD%": round(dd * 100, 2),
        "PF": round(pf, 2) if math.isfinite(pf) else 999,
        "WinRate%": round(wr, 1),
        "Trades": len(trades),
    }


# ------------------------ Presets ----------------------------

PRESETS = {
    # name           utKey utATR hullLen swLb slMult rrR  useHull useBoS
    "Conservative": dict(utKey=2.0, utATR=14, hullLen=89, swLb=14, slMult=2.5, rrR=3.0, useHull=True,  useBoS=True),
    "Balanced":     dict(utKey=1.5, utATR=10, hullLen=55, swLb=10, slMult=2.0, rrR=2.0, useHull=True,  useBoS=True),
    "Aggressive":   dict(utKey=1.0, utATR=7,  hullLen=34, swLb=7,  slMult=1.5, rrR=1.5, useHull=True,  useBoS=False),
    "Trend-Rider":  dict(utKey=2.5, utATR=21, hullLen=89, swLb=20, slMult=3.0, rrR=4.0, useHull=True,  useBoS=True),
    "Scalp":        dict(utKey=1.0, utATR=5,  hullLen=21, swLb=5,  slMult=1.2, rrR=1.2, useHull=False, useBoS=False),
}

# --------------------------- Run -----------------------------

def main():
    symbol = os.environ.get("SYMBOL", "BTC/USDT:USDT")
    since_iso = os.environ.get("SINCE", "2023-01-01")
    exchange_id = os.environ.get("EXCHANGE", "bybit")
    tfs = ["1h", "4h", "1d"]

    ex_cls = getattr(ccxt, exchange_id)
    ex = ex_cls({"enableRateLimit": True, "options": {"defaultType": "swap"}})
    ex.load_markets()
    since_ms = int(datetime.fromisoformat(since_iso).replace(tzinfo=timezone.utc).timestamp() * 1000)

    print(f"Symbol: {symbol}  Exchange: {exchange_id}  Since: {since_iso}")
    cache_dir = "/tmp/ohlcv_cache"
    os.makedirs(cache_dir, exist_ok=True)

    data = {}
    for tf in tfs:
        cache = f"{cache_dir}/{exchange_id}_{symbol.replace('/','_').replace(':','_')}_{tf}_{since_iso}.parquet"
        if os.path.exists(cache):
            df = pd.read_parquet(cache)
            print(f"\n[{tf}] cached  bars={len(df)}  range={df.index[0]} -> {df.index[-1]}")
        else:
            print(f"\n[{tf}] fetching ...")
            df = fetch_ohlcv(symbol, tf, since_ms, ex)
            print(f"[{tf}] fetched bars={len(df)}  range={df.index[0]} -> {df.index[-1]}")
            df.to_parquet(cache)
        data[tf] = df

    out = {}
    for tf in tfs:
        df = data[tf]
        rows = []
        for name, p in PRESETS.items():
            r = backtest(df, p)
            r["Preset"] = name
            rows.append(r)
        rdf = pd.DataFrame(rows).set_index("Preset")[["Net%", "CAGR%", "MaxDD%", "PF", "WinRate%", "Trades"]]
        print(f"\n=== {tf.upper()} === (bars={len(df)})")
        print(rdf.to_string())
        out[tf] = rdf

    print("\n=== Buy & Hold reference ===")
    bh_rows = []
    for tf in tfs:
        df = data[tf]
        ret = df.c.iloc[-1] / df.c.iloc[0] - 1
        years = (df.index[-1] - df.index[0]).days / 365.25
        cagr = (1 + ret) ** (1 / years) - 1 if years > 0 else 0
        bh_rows.append({"tf": tf, "Net%": round(ret*100,2), "CAGR%": round(cagr*100,2), "Years": round(years,2)})
    print(pd.DataFrame(bh_rows).to_string(index=False))

    print("\n=== Cross-timeframe CAGR% summary ===")
    summary = pd.DataFrame({tf: out[tf]["CAGR%"] for tf in tfs})
    print(summary.to_string())

if __name__ == "__main__":
    main()
