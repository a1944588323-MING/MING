"""
MAx10eth Auction Flow Bot
==========================
Distilled from @MAx10eth's tweets (VWAP + Volume Profile + Single Prints + Divergence).

Modes:
  --dry-run           Print signals only, no orders (DEFAULT, recommended first)
  --paper             Use exchange's paper/demo trading account
  --live              REAL ORDERS (requires --i-know-what-im-doing)

Usage examples:
  # Just watch BTC + ETH on OKX, print signals every minute, no orders
  python max10eth_bot.py --symbols BTC/USDT:USDT ETH/USDT:USDT --tf 15m --dry-run

  # Paper trade with 1% risk per signal
  python max10eth_bot.py --symbols BTC/USDT:USDT --tf 15m --paper --risk 0.01

Trading rules (mirrored from his tweets):
  LONG  : price reclaims VWAP upward AND price > last bullish single-print pivot
          AND (recent absorption OR recent bullish RSI divergence)
  SHORT : price loses VWAP downward AND price < last bearish single-print pivot
          AND (recent absorption OR recent bearish RSI divergence)
  SL    : LONG  -> below last SP-low ; SHORT -> above last SP-high
  TP    : LONG  -> next VAH (vwap + 1*sigma) ; SHORT -> next VAL (vwap - 1*sigma)
"""
from __future__ import annotations
import argparse, math, os, sys, time, json, signal
from dataclasses import dataclass, field
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import ccxt

# ---------------------------- Indicators ----------------------------

def session_vwap(df: pd.DataFrame, anchor: str = "D"):
    """Anchored VWAP that resets each new session."""
    df = df.copy()
    src = (df.h + df.l + df.c) / 3
    pv = src * df.v
    grp = df.index.floor(anchor)
    df["pv_cum"] = pv.groupby(grp).cumsum()
    df["v_cum"]  = df.v.groupby(grp).cumsum()
    vwap = df["pv_cum"] / df["v_cum"].replace(0, np.nan)
    var = ((src - vwap) ** 2 * df.v).groupby(grp).cumsum() / df["v_cum"].replace(0, np.nan)
    sigma = np.sqrt(var)
    return vwap, sigma


def rsi(c: pd.Series, n: int = 14) -> pd.Series:
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def atr(h, l, c, n=14):
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def pivots(series: pd.Series, left: int, right: int, mode: str):
    """Return series of pivot values aligned to the pivot-formation bar."""
    n = len(series)
    out = pd.Series(np.nan, index=series.index)
    s = series.values
    for i in range(left, n - right):
        win = s[i - left : i + right + 1]
        center = s[i]
        if mode == "high" and center == win.max() and (win < center).any() if False else (
            mode == "high" and center == win.max() and (win[win != center].max() < center)
        ):
            out.iloc[i] = center
        elif mode == "low" and center == win.min() and (win[win != center].min() > center):
            out.iloc[i] = center
    # simpler: argmax of window equals center, but exclude case all equal
    return out


def find_pivots(series: pd.Series, left: int, right: int, kind: str):
    """Cleaner pivot finder."""
    s = series.values
    n = len(s)
    out = pd.Series(np.nan, index=series.index)
    for i in range(left, n - right):
        win = s[i - left : i + right + 1]
        if kind == "high":
            if s[i] == win.max() and np.sum(win == s[i]) == 1:
                out.iloc[i] = s[i]
        else:
            if s[i] == win.min() and np.sum(win == s[i]) == 1:
                out.iloc[i] = s[i]
    return out


# ---------------------------- Strategy ----------------------------

@dataclass
class Signal:
    side: str            # "long" | "short"
    grade: str           # "S" | "A" | "B"
    entry: float
    sl: float
    tp: float
    timestamp: datetime
    reason: str


@dataclass
class StratParams:
    pivot_left: int = 5
    pivot_right: int = 5
    rsi_len: int = 14
    absorb_vol_mult: float = 2.0
    absorb_range_atr: float = 0.6
    band_sigma: float = 1.0


def evaluate(df: pd.DataFrame, p: StratParams = StratParams()) -> Signal | None:
    """Evaluate latest closed bar. Return Signal or None."""
    if len(df) < 200:
        return None

    vwap, sigma = session_vwap(df, "D")
    df = df.assign(vwap=vwap, sigma=sigma)
    df["vah"] = df.vwap + p.band_sigma * df.sigma
    df["val"] = df.vwap - p.band_sigma * df.sigma
    df["rsi"] = rsi(df.c, p.rsi_len)
    df["atr"] = atr(df.h, df.l, df.c, 14)
    df["volSMA"] = df.v.rolling(20).mean()

    df["ph"] = find_pivots(df.h, p.pivot_left, p.pivot_right, "high")
    df["pl"] = find_pivots(df.l, p.pivot_left, p.pivot_right, "low")

    last_ph = df.ph.dropna().iloc[-1] if df.ph.notna().any() else np.nan
    last_pl = df.pl.dropna().iloc[-1] if df.pl.notna().any() else np.nan

    # absorption: high vol + small range bar in last 5 bars
    recent = df.tail(6).iloc[:-1]  # last 5 closed bars (skip the very latest still-forming if any)
    absorb = ((recent.v > recent.volSMA * p.absorb_vol_mult)
              & ((recent.h - recent.l) < recent.atr * p.absorb_range_atr)).any()

    # divergence (last 50 bars: 2 most recent pivot highs/lows)
    ph_ser = df.ph.dropna().tail(2)
    pl_ser = df.pl.dropna().tail(2)
    bear_div = False
    bull_div = False
    if len(ph_ser) == 2:
        idx = ph_ser.index
        if ph_ser.iloc[1] > ph_ser.iloc[0] and df.rsi.loc[idx[1]] < df.rsi.loc[idx[0]]:
            bear_div = True
    if len(pl_ser) == 2:
        idx = pl_ser.index
        if pl_ser.iloc[1] < pl_ser.iloc[0] and df.rsi.loc[idx[1]] > df.rsi.loc[idx[0]]:
            bull_div = True

    # VWAP cross on last bar
    cur, prev = df.iloc[-1], df.iloc[-2]
    long_cross  = prev.c <= prev.vwap and cur.c > cur.vwap
    short_cross = prev.c >= prev.vwap and cur.c < cur.vwap

    above_sp = not np.isnan(last_pl) and cur.c > last_pl
    below_sp = not np.isnan(last_ph) and cur.c < last_ph

    long_sig  = long_cross  and above_sp and (absorb or bull_div)
    short_sig = short_cross and below_sp and (absorb or bear_div)

    if not (long_sig or short_sig):
        return None

    if long_sig:
        grade = "S" if (absorb and bull_div) else "A" if (absorb or bull_div) else "B"
        return Signal(
            side="long",
            grade=grade,
            entry=float(cur.c),
            sl=float(last_pl - 0.05 * cur.atr) if not np.isnan(last_pl) else float(cur.c - 1.5 * cur.atr),
            tp=float(cur.vah),
            timestamp=df.index[-1].to_pydatetime(),
            reason=f"VWAP reclaim + above SP↓({last_pl:.2f}) + " + ("absorb+bullDiv" if (absorb and bull_div) else ("absorb" if absorb else "bullDiv")),
        )
    else:
        grade = "S" if (absorb and bear_div) else "A" if (absorb or bear_div) else "B"
        return Signal(
            side="short",
            grade=grade,
            entry=float(cur.c),
            sl=float(last_ph + 0.05 * cur.atr) if not np.isnan(last_ph) else float(cur.c + 1.5 * cur.atr),
            tp=float(cur.val),
            timestamp=df.index[-1].to_pydatetime(),
            reason=f"VWAP loss + below SP↑({last_ph:.2f}) + " + ("absorb+bearDiv" if (absorb and bear_div) else ("absorb" if absorb else "bearDiv")),
        )


# ---------------------------- Exchange wrapper ----------------------------

def fetch_recent(exchange, symbol: str, tf: str, n: int = 500) -> pd.DataFrame:
    rows = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=n)
    df = pd.DataFrame(rows, columns=["t", "o", "h", "l", "c", "v"])
    df["dt"] = pd.to_datetime(df["t"], unit="ms", utc=True)
    df.set_index("dt", inplace=True)
    return df[["o", "h", "l", "c", "v"]].astype(float)


def place_order(exchange, symbol: str, sig: Signal, risk_usd: float, dry: bool):
    """Place market entry + reduce-only stop + reduce-only TP."""
    side = "buy" if sig.side == "long" else "sell"
    opp  = "sell" if side == "buy" else "buy"
    risk_per_unit = abs(sig.entry - sig.sl)
    qty = max(risk_usd / risk_per_unit, 1e-6)
    qty = float(exchange.amount_to_precision(symbol, qty))

    if dry:
        print(f"  [DRY] would place {side.upper()} {qty} {symbol} @ ~{sig.entry}  SL={sig.sl}  TP={sig.tp}")
        return None

    print(f"  [LIVE] placing {side.upper()} {qty} {symbol} @ market")
    o = exchange.create_order(symbol, "market", side, qty)
    # reduce-only SL
    exchange.create_order(symbol, "stop", opp, qty, sig.sl, params={"reduceOnly": True, "stopPrice": sig.sl})
    # reduce-only TP
    exchange.create_order(symbol, "limit", opp, qty, sig.tp, params={"reduceOnly": True})
    return o


# ---------------------------- Main loop ----------------------------

def make_exchange(exchange_id: str, paper: bool):
    cls = getattr(ccxt, exchange_id)
    cfg = {"enableRateLimit": True, "options": {"defaultType": "swap"}}
    api = os.environ.get(f"{exchange_id.upper()}_API_KEY", "")
    sec = os.environ.get(f"{exchange_id.upper()}_API_SECRET", "")
    pw  = os.environ.get(f"{exchange_id.upper()}_PASSWORD", "")
    if api and sec:
        cfg["apiKey"] = api
        cfg["secret"] = sec
        if pw:
            cfg["password"] = pw
    ex = cls(cfg)
    if paper and exchange_id == "okx":
        ex.headers = {"x-simulated-trading": "1"}
    ex.load_markets()
    return ex


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exchange", default="okx")
    ap.add_argument("--symbols", nargs="+", default=["BTC/USDT:USDT", "ETH/USDT:USDT"])
    ap.add_argument("--tf", default="15m")
    ap.add_argument("--risk", type=float, default=0.01, help="Risk per trade as fraction of equity")
    ap.add_argument("--equity", type=float, default=1000.0, help="Assumed equity (USD) for sizing in dry-run")
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--paper",   action="store_true")
    ap.add_argument("--live",    action="store_true")
    ap.add_argument("--i-know-what-im-doing", action="store_true")
    ap.add_argument("--min-grade", choices=["S", "A", "B"], default="A")
    ap.add_argument("--once", action="store_true", help="Run one evaluation and exit (testing)")
    args = ap.parse_args()

    if args.live and not args.i_know_what_im_doing:
        print("ERROR: --live requires --i-know-what-im-doing"); sys.exit(2)

    mode = "LIVE" if args.live else ("PAPER" if args.paper else "DRY-RUN")
    dry = not args.live

    ex = make_exchange(args.exchange, args.paper)
    print(f"[{mode}] exchange={args.exchange} tf={args.tf} symbols={args.symbols} min_grade={args.min_grade}")

    last_signal_ts = {s: None for s in args.symbols}

    def run_once():
        for sym in args.symbols:
            try:
                df = fetch_recent(ex, sym, args.tf, 500)
                sig = evaluate(df)
                price = df.c.iloc[-1]
                vwap, sigma = session_vwap(df, "D")
                vw = vwap.iloc[-1]
                print(f"[{datetime.now():%H:%M:%S}] {sym}  px={price:.2f}  vwap={vw:.2f}  ", end="")
                if sig is None:
                    print("no signal")
                    continue
                if sig.timestamp == last_signal_ts.get(sym):
                    print(f"signal {sig.side} {sig.grade} (already handled)")
                    continue
                grades_order = {"S": 3, "A": 2, "B": 1}
                if grades_order[sig.grade] < grades_order[args.min_grade]:
                    print(f"signal {sig.side} {sig.grade} below threshold")
                    continue
                last_signal_ts[sym] = sig.timestamp
                print(f"\n  SIGNAL  {sig.side.upper()} [{sig.grade}]  entry={sig.entry:.2f} SL={sig.sl:.2f} TP={sig.tp:.2f}")
                print(f"  reason: {sig.reason}")
                risk_usd = args.equity * args.risk
                place_order(ex, sym, sig, risk_usd, dry)
            except Exception as e:
                print(f"  ERROR {sym}: {e}")

    if args.once:
        run_once()
        return

    # main loop: every (tf seconds / 4)
    tf_sec = ex.parse_timeframe(args.tf)
    sleep_s = max(30, tf_sec // 4)
    print(f"loop interval: {sleep_s}s")

    stop = False
    def handler(sig, frame):
        nonlocal stop; stop = True; print("\nstopping…")
    signal.signal(signal.SIGINT, handler)

    while not stop:
        run_once()
        for _ in range(sleep_s):
            if stop: break
            time.sleep(1)


if __name__ == "__main__":
    main()
