"""
MAx10eth Auction Flow Strategy — OPTIMIZED Backtest v2
======================================================
Improvements over v1:
  1) Daily EMA trend filter (EMA50 + EMA200) — only long in uptrend, only short in downtrend
  2) S-grade signal requirement (absorption AND divergence both required)
  3) Trailing stop (ATR-based) instead of fixed TP at VAH/VAL
  4) Session time filter (only trade NY/London hours 07:00-21:00 UTC)
  5) Volume confirmation (current bar volume > 1.5x 20-period SMA)
  6) Wider pivot detection window for less noise
"""
from __future__ import annotations
import os, sys, time, math
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import ccxt

sys.path.insert(0, os.path.dirname(__file__))
from max10eth_bot import session_vwap, rsi, atr, find_pivots


# ======================== OPTIMIZED PARAMS ========================
class OptParams:
    # Trend filter
    ema_fast: int = 50
    ema_slow: int = 200
    use_trend_filter: bool = True
    trend_mode: str = "ema_cross"  # "ema_cross" | "price_above"

    # Signal quality
    require_s_grade: bool = True  # require BOTH absorption + divergence

    # Pivots / SP
    pivot_left: int = 8
    pivot_right: int = 8

    # RSI
    rsi_len: int = 14

    # Absorption
    absorb_vol_mult: float = 1.8
    absorb_range_atr: float = 0.5
    absorb_lookback: int = 8  # bars to look back for absorption

    # Volume confirmation
    use_vol_filter: bool = True
    vol_threshold: float = 1.3  # current bar vol > x * SMA(20)

    # Session filter (UTC hours)
    use_session_filter: bool = True
    session_start: int = 7   # 07:00 UTC = London open
    session_end: int = 21    # 21:00 UTC = NY close

    # Risk: Trailing stop
    initial_sl_atr: float = 1.5   # SL = entry ± x*ATR
    trail_atr: float = 2.0        # trailing stop distance
    trail_activation: float = 1.0  # start trailing after x*ATR profit

    # VWAP
    band_sigma: float = 1.0

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


# ======================== DATA ========================
def fetch_all(symbol, tf, since_ms, ex, page=300):
    rows = []
    cursor = since_ms
    end = int(time.time() * 1000)
    while cursor < end:
        try:
            r = ex.fetch_ohlcv(symbol, timeframe=tf, since=cursor, limit=page)
        except Exception as e:
            print(f"  err {e}"); time.sleep(2); continue
        if not r: break
        new = [x for x in r if not rows or x[0] > rows[-1][0]]
        if not new: break
        rows.extend(new)
        cursor = new[-1][0] + 1
        time.sleep(ex.rateLimit / 1000)
    df = pd.DataFrame(rows, columns=["t","o","h","l","c","v"]).drop_duplicates("t")
    df["dt"] = pd.to_datetime(df["t"], unit="ms", utc=True)
    df.set_index("dt", inplace=True)
    return df[["o","h","l","c","v"]].astype(float).sort_index()


# ======================== BACKTEST ENGINE ========================
def backtest_v2(df: pd.DataFrame, p: OptParams = OptParams(), fee=0.0005, slip=0.0002):
    df = df.copy()

    # ---- Indicators ----
    vwap_v, sigma_v = session_vwap(df, "D")
    df["vwap"] = vwap_v
    df["sigma"] = sigma_v
    df["vah"] = df.vwap + p.band_sigma * df.sigma
    df["val"] = df.vwap - p.band_sigma * df.sigma
    df["rsi"] = rsi(df.c, p.rsi_len)
    df["atr"] = atr(df.h, df.l, df.c, 14)
    df["volSMA"] = df.v.rolling(20).mean()

    # ---- Daily EMA trend filter ----
    # Resample to daily, compute EMAs, then map back
    daily = df.c.resample("D").last().dropna()
    ema_fast = daily.ewm(span=p.ema_fast, adjust=False).mean()
    ema_slow = daily.ewm(span=p.ema_slow, adjust=False).mean()
    # daily trend: 1=bull, -1=bear, 0=neutral
    daily_trend = pd.Series(0, index=daily.index)
    daily_trend[ema_fast > ema_slow] = 1
    daily_trend[ema_fast < ema_slow] = -1
    # Also require price above fast EMA for bull
    daily_trend[(ema_fast > ema_slow) & (daily > ema_fast)] = 1
    daily_trend[(ema_fast < ema_slow) & (daily < ema_fast)] = -1
    # Map to original timeframe
    df["daily_trend"] = daily_trend.reindex(df.index, method="ffill").fillna(0).astype(int)
    df["ema_fast_d"] = ema_fast.reindex(df.index, method="ffill")
    df["ema_slow_d"] = ema_slow.reindex(df.index, method="ffill")

    # ---- Pivots ----
    df["ph"] = find_pivots(df.h, p.pivot_left, p.pivot_right, "high")
    df["pl"] = find_pivots(df.l, p.pivot_left, p.pivot_right, "low")

    # ---- Numpy arrays for speed ----
    n = len(df)
    h, l, c = df.h.values, df.l.values, df.c.values
    vw = df.vwap.values
    a = df.atr.values
    vol = df.v.values
    volSMA = df.volSMA.values
    rsi_v = df.rsi.values
    trend = df.daily_trend.values
    ph_idx = np.where(~df.ph.isna())[0]
    pl_idx = np.where(~df.pl.isna())[0]
    ph_vals = df.ph.values
    pl_vals = df.pl.values
    hours = df.index.hour

    # ---- State ----
    equity = 1.0
    pos = 0  # 1=long, -1=short, 0=flat
    entry = 0.0
    sl = 0.0
    highest_since_entry = 0.0
    lowest_since_entry = 999999.0
    trail_active = False
    trades = []
    eq = np.full(n, np.nan)

    def get_last_pivot(idx_arr, vals, i):
        valid = idx_arr[idx_arr <= i]
        if len(valid) == 0: return np.nan
        return vals[valid[-1]]

    def get_prev2(idx_arr, vals, rsi_arr, i):
        valid = idx_arr[idx_arr <= i]
        if len(valid) < 2: return None
        i1, i2 = valid[-2], valid[-1]
        return (vals[i1], vals[i2], rsi_arr[i1], rsi_arr[i2])

    for i in range(max(p.pivot_left + p.pivot_right + 5, 60), n):
        # ---- Check absorption (last N bars) ----
        absorb = False
        for j in range(max(0, i - p.absorb_lookback), i + 1):
            if not np.isnan(volSMA[j]) and not np.isnan(a[j]) and a[j] > 0:
                if vol[j] > volSMA[j] * p.absorb_vol_mult and (h[j] - l[j]) < a[j] * p.absorb_range_atr:
                    absorb = True
                    break

        # ---- Check divergence ----
        bull_div = False
        bear_div = False
        ph2 = get_prev2(ph_idx, ph_vals, rsi_v, i)
        pl2 = get_prev2(pl_idx, pl_vals, rsi_v, i)
        if ph2 and not np.isnan(ph2[0]) and not np.isnan(ph2[1]):
            if ph2[1] > ph2[0] and ph2[3] < ph2[2]:
                bear_div = True
        if pl2 and not np.isnan(pl2[0]) and not np.isnan(pl2[1]):
            if pl2[1] < pl2[0] and pl2[3] > pl2[2]:
                bull_div = True

        # ---- S-grade check ----
        if p.require_s_grade:
            long_quality = absorb and bull_div
            short_quality = absorb and bear_div
        else:
            long_quality = absorb or bull_div
            short_quality = absorb or bear_div

        # ---- Pivot levels ----
        last_ph = get_last_pivot(ph_idx, ph_vals, i)
        last_pl = get_last_pivot(pl_idx, pl_vals, i)

        # ---- VWAP cross ----
        long_cross = (not np.isnan(vw[i]) and not np.isnan(vw[i-1])
                     and c[i-1] <= vw[i-1] and c[i] > vw[i])
        short_cross = (not np.isnan(vw[i]) and not np.isnan(vw[i-1])
                      and c[i-1] >= vw[i-1] and c[i] < vw[i])

        above_sp = not np.isnan(last_pl) and c[i] > last_pl
        below_sp = not np.isnan(last_ph) and c[i] < last_ph

        # ---- Filters ----
        # Trend filter
        trend_ok_long = (not p.use_trend_filter) or (trend[i] >= 1)
        trend_ok_short = (not p.use_trend_filter) or (trend[i] <= -1)

        # Volume filter
        vol_ok = (not p.use_vol_filter) or (not np.isnan(volSMA[i]) and vol[i] > volSMA[i] * p.vol_threshold)

        # Session filter
        hr = hours[i]
        session_ok = (not p.use_session_filter) or (p.session_start <= hr < p.session_end)

        # ---- Final signal ----
        long_sig = (long_cross and above_sp and long_quality
                   and trend_ok_long and vol_ok and session_ok)
        short_sig = (short_cross and below_sp and short_quality
                    and trend_ok_short and vol_ok and session_ok)

        # ===== EXIT LOGIC (trailing stop) =====
        if pos == 1:
            highest_since_entry = max(highest_since_entry, h[i])
            # Activate trailing after profit threshold
            if not trail_active and (highest_since_entry - entry) >= p.trail_activation * a[i]:
                trail_active = True
            # Update trailing stop
            if trail_active:
                new_sl = highest_since_entry - p.trail_atr * a[i]
                sl = max(sl, new_sl)

            if l[i] <= sl:
                px = max(sl, l[i]) * (1 - slip)
                pnl = px / entry - 1
                equity *= (1 + pnl) * (1 - fee)
                trades.append(("L", entry, px, pnl * 100, "TRAIL" if trail_active else "SL", i))
                pos = 0; trail_active = False
            elif short_sig:
                px = c[i] * (1 - slip)
                pnl = px / entry - 1
                equity *= (1 + pnl) * (1 - fee)
                trades.append(("L", entry, px, pnl * 100, "FLIP", i))
                pos = 0; trail_active = False

        elif pos == -1:
            lowest_since_entry = min(lowest_since_entry, l[i])
            if not trail_active and (entry - lowest_since_entry) >= p.trail_activation * a[i]:
                trail_active = True
            if trail_active:
                new_sl = lowest_since_entry + p.trail_atr * a[i]
                sl = min(sl, new_sl)

            if h[i] >= sl:
                px = min(sl, h[i]) * (1 + slip)
                pnl = entry / px - 1
                equity *= (1 + pnl) * (1 - fee)
                trades.append(("S", entry, px, pnl * 100, "TRAIL" if trail_active else "SL", i))
                pos = 0; trail_active = False
            elif long_sig:
                px = c[i] * (1 + slip)
                pnl = entry / px - 1
                equity *= (1 + pnl) * (1 - fee)
                trades.append(("S", entry, px, pnl * 100, "FLIP", i))
                pos = 0; trail_active = False

        # ===== ENTRY LOGIC =====
        if pos == 0:
            if long_sig and not np.isnan(a[i]) and a[i] > 0:
                pos = 1
                entry = c[i] * (1 + slip)
                equity *= (1 - fee)
                sl = entry - p.initial_sl_atr * a[i]
                highest_since_entry = h[i]
                trail_active = False
            elif short_sig and not np.isnan(a[i]) and a[i] > 0:
                pos = -1
                entry = c[i] * (1 - slip)
                equity *= (1 - fee)
                sl = entry + p.initial_sl_atr * a[i]
                lowest_since_entry = l[i]
                trail_active = False

        # ---- Equity curve ----
        if pos == 1:
            eq[i] = equity * (c[i] / entry)
        elif pos == -1:
            eq[i] = equity * (entry / c[i])
        else:
            eq[i] = equity

    # Final close
    if pos != 0:
        px = c[-1]
        pnl = (px / entry - 1) if pos == 1 else (entry / px - 1)
        equity *= (1 + pnl) * (1 - fee)
        trades.append(("L" if pos == 1 else "S", entry, px, pnl * 100, "EOD", n - 1))
        eq[-1] = equity

    # ---- Metrics ----
    eq_s = pd.Series(eq, index=df.index).ffill().fillna(1.0)
    days = (df.index[-1] - df.index[0]).days
    years = days / 365.25 if days > 0 else 1
    final_eq = eq_s.iloc[-1]
    cagr = final_eq ** (1 / years) - 1 if years > 0 and final_eq > 0 else -1
    dd = (eq_s / eq_s.cummax() - 1).min()
    if trades:
        td = pd.DataFrame(trades, columns=["side", "entry", "exit", "pnl", "reason", "i"])
        wr = (td.pnl > 0).mean() * 100
        wins = td[td.pnl > 0].pnl.sum()
        loss = -td[td.pnl < 0].pnl.sum()
        pf = wins / loss if loss > 0 else 999
        avg_win = td[td.pnl > 0].pnl.mean() if (td.pnl > 0).any() else 0
        avg_loss = td[td.pnl < 0].pnl.mean() if (td.pnl < 0).any() else 0
    else:
        td = pd.DataFrame()
        wr = pf = avg_win = avg_loss = 0
    return {
        "Net%": round((final_eq - 1) * 100, 2),
        "CAGR%": round(cagr * 100, 2),
        "MaxDD%": round(dd * 100, 2),
        "PF": round(pf, 2) if math.isfinite(pf) else 999,
        "WR%": round(wr, 1),
        "Trades": len(trades),
        "AvgWin%": round(avg_win, 2),
        "AvgLoss%": round(avg_loss, 2),
        "Years": round(years, 2),
    }, td


# ======================== PARAMETER SWEEP ========================
CONFIGS = {
    # === Round 2: Based on findings that v1_original's no-trail approach wins ===
    # v1 was best because it lets winners run. Key insight: the trail was killing profits.
    # Strategy: keep v1 exit style (no trail) but add trend filter to reduce losers.

    # A: v1 + trend filter (EMA50>200 = long only, EMA50<200 = short only)
    "v1+trend": OptParams(
        use_trend_filter=True, require_s_grade=False,
        use_vol_filter=False, use_session_filter=False,
        pivot_left=5, pivot_right=5,
        absorb_vol_mult=2.0, absorb_range_atr=0.6, absorb_lookback=5,
        initial_sl_atr=99.0, trail_atr=99.0, trail_activation=999.0,
    ),
    # B: v1 + faster trend (EMA21>50)
    "v1+fastTrend": OptParams(
        use_trend_filter=True, require_s_grade=False,
        use_vol_filter=False, use_session_filter=False,
        pivot_left=5, pivot_right=5,
        absorb_vol_mult=2.0, absorb_range_atr=0.6, absorb_lookback=5,
        initial_sl_atr=99.0, trail_atr=99.0, trail_activation=999.0,
        ema_fast=21, ema_slow=50,
    ),
    # C: v1 + very loose trail (activate after 3x ATR profit, trail at 5x ATR)
    "v1+looseTrail": OptParams(
        use_trend_filter=False, require_s_grade=False,
        use_vol_filter=False, use_session_filter=False,
        pivot_left=5, pivot_right=5,
        absorb_vol_mult=2.0, absorb_range_atr=0.6, absorb_lookback=5,
        initial_sl_atr=99.0, trail_atr=5.0, trail_activation=3.0,
    ),
    # D: v1 + trend + loose trail
    "v1+trend+looseTrail": OptParams(
        use_trend_filter=True, require_s_grade=False,
        use_vol_filter=False, use_session_filter=False,
        pivot_left=5, pivot_right=5,
        absorb_vol_mult=2.0, absorb_range_atr=0.6, absorb_lookback=5,
        initial_sl_atr=99.0, trail_atr=5.0, trail_activation=3.0,
    ),
    # E: v1 + fastTrend + loose trail 
    "v1+fastTrend+looseTrail": OptParams(
        use_trend_filter=True, require_s_grade=False,
        use_vol_filter=False, use_session_filter=False,
        pivot_left=5, pivot_right=5,
        absorb_vol_mult=2.0, absorb_range_atr=0.6, absorb_lookback=5,
        initial_sl_atr=99.0, trail_atr=5.0, trail_activation=3.0,
        ema_fast=21, ema_slow=50,
    ),
    # F: v1 + session filter (only trade London/NY)
    "v1+session": OptParams(
        use_trend_filter=False, require_s_grade=False,
        use_vol_filter=False, use_session_filter=True,
        pivot_left=5, pivot_right=5,
        absorb_vol_mult=2.0, absorb_range_atr=0.6, absorb_lookback=5,
        initial_sl_atr=99.0, trail_atr=99.0, trail_activation=999.0,
    ),
    # G: v1 + trend + session
    "v1+trend+session": OptParams(
        use_trend_filter=True, require_s_grade=False,
        use_vol_filter=False, use_session_filter=True,
        pivot_left=5, pivot_right=5,
        absorb_vol_mult=2.0, absorb_range_atr=0.6, absorb_lookback=5,
        initial_sl_atr=99.0, trail_atr=99.0, trail_activation=999.0,
    ),
    # H: Original v1 (baseline)
    "v1_original": OptParams(
        use_trend_filter=False, require_s_grade=False,
        use_vol_filter=False, use_session_filter=False,
        pivot_left=5, pivot_right=5,
        absorb_vol_mult=2.0, absorb_range_atr=0.6, absorb_lookback=5,
        initial_sl_atr=99.0, trail_atr=99.0, trail_activation=999.0,
    ),
}


# ======================== MAIN ========================
def main():
    ex = ccxt.okx({"enableRateLimit": True, "options": {"defaultType": "swap"}})
    ex.load_markets()
    since = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    cache = "/tmp/max10_cache"
    os.makedirs(cache, exist_ok=True)

    # Fetch data
    data = {}
    for sym in ["BTC/USDT:USDT", "ETH/USDT:USDT"]:
        for tf in ["15m", "1h", "4h"]:
            key = f"{sym}_{tf}"
            cf = f"{cache}/{sym.replace('/','_').replace(':','_')}_{tf}.csv"
            if os.path.exists(cf):
                df = pd.read_csv(cf, index_col=0, parse_dates=True)
            else:
                print(f"fetching {sym} {tf} ...")
                df = fetch_all(sym, tf, since, ex)
                df.to_csv(cf)
            data[key] = df
            print(f"  {sym} {tf}  bars={len(df)}  {df.index[0]} -> {df.index[-1]}")

    # Run all configs
    all_results = []
    for config_name, p in CONFIGS.items():
        for sym in ["BTC/USDT:USDT", "ETH/USDT:USDT"]:
            for tf in ["15m", "1h", "4h"]:
                key = f"{sym}_{tf}"
                df = data[key]
                r, td = backtest_v2(df, p)
                r["Config"] = config_name
                r["Symbol"] = sym.split("/")[0]
                r["TF"] = tf
                all_results.append(r)

    rdf = pd.DataFrame(all_results)
    rdf = rdf.set_index(["Config", "Symbol", "TF"])[
        ["Net%", "CAGR%", "MaxDD%", "PF", "WR%", "Trades", "AvgWin%", "AvgLoss%"]
    ]
    print("\n" + "=" * 80)
    print("FULL RESULTS")
    print("=" * 80)
    print(rdf.to_string())

    # Best configs summary
    print("\n" + "=" * 80)
    print("SUMMARY: Average CAGR% by Config")
    print("=" * 80)
    summary = rdf.reset_index().groupby("Config")[["CAGR%", "MaxDD%", "PF", "WR%", "Trades"]].mean()
    summary["Calmar"] = summary["CAGR%"] / summary["MaxDD%"].abs().replace(0, 1)
    print(summary.sort_values("CAGR%", ascending=False).to_string())

    # Buy & hold
    print("\n=== Buy & Hold reference ===")
    for sym in ["BTC/USDT:USDT", "ETH/USDT:USDT"]:
        key = f"{sym}_4h"
        df = data[key]
        ret = df.c.iloc[-1] / df.c.iloc[0] - 1
        years = (df.index[-1] - df.index[0]).days / 365.25
        cagr = (1 + ret) ** (1 / years) - 1 if years > 0 else 0
        print(f"  {sym}: Net={ret*100:.2f}%  CAGR={cagr*100:.2f}%  ({years:.2f}y)")


if __name__ == "__main__":
    main()
