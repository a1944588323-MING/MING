"""
MAx10eth Auction Flow Bot v2 (Optimized)
==========================================
Distilled from @MAx10eth's tweets + backtested & optimized.

Winner config: v1+fastTrend+looseTrail
  - ETH 4H: +59.3% CAGR, -21.8% MaxDD, PF 10.31, 70% WR
  - BTC 4H: +34.2% CAGR, -29.6% MaxDD, PF 2.61, 58% WR

Core Logic:
  Entry LONG  : VWAP reclaim + above last SP pivot + absorption/divergence + EMA21>EMA50 (daily)
  Entry SHORT : VWAP loss + below last SP pivot + absorption/divergence + EMA21<EMA50 (daily)
  Exit        : Trailing stop (activates after 3xATR profit, trails at 5xATR)
                OR opposite signal

Modes:
  --dry-run           Print signals only (DEFAULT)
  --paper             Use exchange demo account
  --live              REAL ORDERS (requires --i-know-what-im-doing)

Telegram:
  Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars for notifications.

Usage:
  python max10eth_bot.py --symbols ETH/USDT:USDT BTC/USDT:USDT --tf 4h --dry-run
  python max10eth_bot.py --symbols ETH/USDT:USDT --tf 4h --paper --risk 0.02
"""
from __future__ import annotations
import argparse, math, os, sys, time, json, signal as sig_mod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import numpy as np
import pandas as pd
import ccxt

# ========================== TELEGRAM ==========================

def send_telegram(msg: str, token: str = "", chat_id: str = ""):
    """Send message via Telegram bot. Silent fail if not configured."""
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        import urllib.request
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = json.dumps({"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"  [TG] send failed: {e}")


# ========================== INDICATORS ==========================

def session_vwap(df: pd.DataFrame, anchor: str = "D"):
    """Anchored VWAP that resets each new session."""
    df = df.copy()
    src = (df.h + df.l + df.c) / 3
    pv = src * df.v
    grp = df.index.floor(anchor)
    df["pv_cum"] = pv.groupby(grp).cumsum()
    df["v_cum"] = df.v.groupby(grp).cumsum()
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


def find_pivots(series: pd.Series, left: int, right: int, kind: str):
    """Pivot finder."""
    s = series.values
    n = len(s)
    out = pd.Series(np.nan, index=series.index)
    for i in range(left, n - right):
        win = s[i - left: i + right + 1]
        if kind == "high":
            if s[i] == win.max() and np.sum(win == s[i]) == 1:
                out.iloc[i] = s[i]
        else:
            if s[i] == win.min() and np.sum(win == s[i]) == 1:
                out.iloc[i] = s[i]
    return out


# ========================== STRATEGY PARAMS ==========================

@dataclass
class StratParams:
    # Pivots
    pivot_left: int = 5
    pivot_right: int = 5
    # RSI
    rsi_len: int = 14
    # Absorption detection
    absorb_vol_mult: float = 2.0
    absorb_range_atr: float = 0.6
    absorb_lookback: int = 5
    # VWAP band
    band_sigma: float = 1.0
    # Trend filter (daily EMA)
    use_trend_filter: bool = True
    ema_fast: int = 21
    ema_slow: int = 50
    # Trailing stop
    trail_activation_atr: float = 3.0  # activate after this much profit
    trail_distance_atr: float = 5.0    # trail at this distance


# ========================== SIGNAL ==========================

@dataclass
class Signal:
    side: str            # "long" | "short"
    grade: str           # "S" | "A" | "B"
    entry: float
    sl: float
    tp: float            # indicative TP (VAH/VAL), actual exit via trail
    timestamp: datetime
    reason: str
    trend: str = ""      # "BULL" | "BEAR" | "NEUTRAL"
    atr_val: float = 0.0


# ========================== CORE EVALUATE ==========================

def evaluate(df: pd.DataFrame, p: StratParams = StratParams()) -> Optional[Signal]:
    """Evaluate latest closed bar. Return Signal or None."""
    if len(df) < 250:
        return None

    # --- Indicators ---
    vwap, sigma = session_vwap(df, "D")
    df = df.assign(vwap=vwap, sigma=sigma)
    df["vah"] = df.vwap + p.band_sigma * df.sigma
    df["val"] = df.vwap - p.band_sigma * df.sigma
    df["rsi"] = rsi(df.c, p.rsi_len)
    df["atr"] = atr(df.h, df.l, df.c, 14)
    df["volSMA"] = df.v.rolling(20).mean()
    df["ph"] = find_pivots(df.h, p.pivot_left, p.pivot_right, "high")
    df["pl"] = find_pivots(df.l, p.pivot_left, p.pivot_right, "low")

    # --- Daily trend filter ---
    daily = df.c.resample("D").last().dropna()
    if len(daily) < p.ema_slow + 5:
        return None
    ema_f = daily.ewm(span=p.ema_fast, adjust=False).mean()
    ema_s = daily.ewm(span=p.ema_slow, adjust=False).mean()
    trend_bull = ema_f.iloc[-1] > ema_s.iloc[-1]
    trend_bear = ema_f.iloc[-1] < ema_s.iloc[-1]
    trend_str = "BULL" if trend_bull else ("BEAR" if trend_bear else "NEUTRAL")

    # --- Pivot levels ---
    last_ph = df.ph.dropna().iloc[-1] if df.ph.notna().any() else np.nan
    last_pl = df.pl.dropna().iloc[-1] if df.pl.notna().any() else np.nan

    # --- Absorption (last N bars) ---
    recent = df.tail(p.absorb_lookback + 1).iloc[:-1]
    absorb = ((recent.v > recent.volSMA * p.absorb_vol_mult)
              & ((recent.h - recent.l) < recent.atr * p.absorb_range_atr)).any()

    # --- Divergence ---
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

    # --- VWAP cross ---
    cur, prev = df.iloc[-1], df.iloc[-2]
    long_cross = prev.c <= prev.vwap and cur.c > cur.vwap
    short_cross = prev.c >= prev.vwap and cur.c < cur.vwap

    above_sp = not np.isnan(last_pl) and cur.c > last_pl
    below_sp = not np.isnan(last_ph) and cur.c < last_ph

    # --- Quality ---
    long_quality = absorb or bull_div
    short_quality = absorb or bear_div

    # --- Trend filter ---
    if p.use_trend_filter:
        trend_ok_long = trend_bull
        trend_ok_short = trend_bear
    else:
        trend_ok_long = trend_ok_short = True

    # --- Final signal ---
    long_sig = long_cross and above_sp and long_quality and trend_ok_long
    short_sig = short_cross and below_sp and short_quality and trend_ok_short

    if not (long_sig or short_sig):
        return None

    atr_val = float(cur.atr) if not np.isnan(cur.atr) else 0.0

    if long_sig:
        grade = "S" if (absorb and bull_div) else "A"
        return Signal(
            side="long", grade=grade,
            entry=float(cur.c),
            sl=float(last_pl - 0.05 * atr_val) if not np.isnan(last_pl) else float(cur.c - 1.5 * atr_val),
            tp=float(cur.vah),
            timestamp=df.index[-1].to_pydatetime(),
            reason=f"VWAP↑ + SP↓({last_pl:.1f}) + {'absorb+div' if (absorb and bull_div) else 'absorb' if absorb else 'bullDiv'} + trend={trend_str}",
            trend=trend_str,
            atr_val=atr_val,
        )
    else:
        grade = "S" if (absorb and bear_div) else "A"
        return Signal(
            side="short", grade=grade,
            entry=float(cur.c),
            sl=float(last_ph + 0.05 * atr_val) if not np.isnan(last_ph) else float(cur.c + 1.5 * atr_val),
            tp=float(cur.val),
            timestamp=df.index[-1].to_pydatetime(),
            reason=f"VWAP↓ + SP↑({last_ph:.1f}) + {'absorb+div' if (absorb and bear_div) else 'absorb' if absorb else 'bearDiv'} + trend={trend_str}",
            trend=trend_str,
            atr_val=atr_val,
        )


# ========================== POSITION TRACKER ==========================

@dataclass
class Position:
    side: str  # "long" | "short"
    entry: float
    sl: float
    highest: float = 0.0
    lowest: float = 999999.0
    trail_active: bool = False
    trail_atr: float = 5.0
    trail_activation: float = 3.0
    atr_at_entry: float = 0.0

    def update(self, high: float, low: float, close: float, cur_atr: float) -> Optional[str]:
        """Returns 'exit' reason or None."""
        if self.side == "long":
            self.highest = max(self.highest, high)
            if not self.trail_active:
                if (self.highest - self.entry) >= self.trail_activation * self.atr_at_entry:
                    self.trail_active = True
            if self.trail_active:
                new_sl = self.highest - self.trail_atr * cur_atr
                self.sl = max(self.sl, new_sl)
            if low <= self.sl:
                return "TRAIL_STOP" if self.trail_active else "STOP_LOSS"
        else:
            self.lowest = min(self.lowest, low)
            if not self.trail_active:
                if (self.entry - self.lowest) >= self.trail_activation * self.atr_at_entry:
                    self.trail_active = True
            if self.trail_active:
                new_sl = self.lowest + self.trail_atr * cur_atr
                self.sl = min(self.sl, new_sl)
            if high >= self.sl:
                return "TRAIL_STOP" if self.trail_active else "STOP_LOSS"
        return None


# ========================== EXCHANGE WRAPPER ==========================

def fetch_recent(exchange, symbol: str, tf: str, n: int = 500) -> pd.DataFrame:
    rows = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=n)
    df = pd.DataFrame(rows, columns=["t", "o", "h", "l", "c", "v"])
    df["dt"] = pd.to_datetime(df["t"], unit="ms", utc=True)
    df.set_index("dt", inplace=True)
    return df[["o", "h", "l", "c", "v"]].astype(float)


def place_order(exchange, symbol: str, sig: Signal, risk_usd: float, dry: bool, tg_token="", tg_chat=""):
    """Place market entry + stop loss."""
    side = "buy" if sig.side == "long" else "sell"
    opp = "sell" if side == "buy" else "buy"
    risk_per_unit = abs(sig.entry - sig.sl)
    if risk_per_unit <= 0:
        risk_per_unit = sig.atr_val * 1.5
    qty = max(risk_usd / risk_per_unit, 1e-6)

    msg = (f"{'🟢' if sig.side=='long' else '🔴'} *{sig.side.upper()} {symbol}*\n"
           f"Grade: {sig.grade} | Entry: {sig.entry:.2f}\n"
           f"SL: {sig.sl:.2f} | Target: {sig.tp:.2f}\n"
           f"ATR: {sig.atr_val:.2f} | Trend: {sig.trend}\n"
           f"Reason: {sig.reason}\n"
           f"Risk: ${risk_usd:.2f} | Qty: {qty:.6f}")

    if dry:
        print(f"  [DRY] {msg.replace(chr(10), ' | ')}")
        send_telegram(f"[DRY] {msg}", tg_token, tg_chat)
        return None

    try:
        qty = float(exchange.amount_to_precision(symbol, qty))
        print(f"  [LIVE] {side.upper()} {qty} {symbol} @ market")
        o = exchange.create_order(symbol, "market", side, qty)
        # SL order
        exchange.create_order(symbol, "stop", opp, qty, sig.sl,
                              params={"reduceOnly": True, "stopPrice": sig.sl})
        send_telegram(f"[EXECUTED] {msg}", tg_token, tg_chat)
        return o
    except Exception as e:
        err_msg = f"[ORDER ERROR] {symbol}: {e}"
        print(f"  {err_msg}")
        send_telegram(err_msg, tg_token, tg_chat)
        return None


def make_exchange(exchange_id: str, paper: bool):
    cls = getattr(ccxt, exchange_id)
    cfg = {"enableRateLimit": True, "options": {"defaultType": "swap"}}
    api = os.environ.get(f"{exchange_id.upper()}_API_KEY", "")
    sec = os.environ.get(f"{exchange_id.upper()}_API_SECRET", "")
    pw = os.environ.get(f"{exchange_id.upper()}_PASSWORD", "")
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


# ========================== MAIN ==========================

def main():
    ap = argparse.ArgumentParser(description="MAx10eth Auction Flow Bot v2")
    ap.add_argument("--exchange", default="okx")
    ap.add_argument("--symbols", nargs="+", default=["ETH/USDT:USDT", "BTC/USDT:USDT"])
    ap.add_argument("--tf", default="4h", help="Timeframe (recommended: 4h)")
    ap.add_argument("--risk", type=float, default=0.02, help="Risk per trade (fraction of equity)")
    ap.add_argument("--equity", type=float, default=1000.0, help="Equity USD (for dry-run sizing)")
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--paper", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--i-know-what-im-doing", action="store_true")
    ap.add_argument("--min-grade", choices=["S", "A", "B"], default="A")
    ap.add_argument("--once", action="store_true", help="Run one eval and exit")
    # Telegram
    ap.add_argument("--tg-token", default="", help="Telegram bot token (or env TELEGRAM_BOT_TOKEN)")
    ap.add_argument("--tg-chat", default="", help="Telegram chat ID (or env TELEGRAM_CHAT_ID)")
    # Strategy overrides
    ap.add_argument("--no-trend-filter", action="store_true", help="Disable daily EMA trend filter")
    ap.add_argument("--ema-fast", type=int, default=21)
    ap.add_argument("--ema-slow", type=int, default=50)
    ap.add_argument("--trail-activation", type=float, default=3.0, help="ATR mult to activate trail")
    ap.add_argument("--trail-distance", type=float, default=5.0, help="ATR mult for trail distance")
    args = ap.parse_args()

    if args.live and not args.i_know_what_im_doing:
        print("ERROR: --live requires --i-know-what-im-doing")
        sys.exit(2)

    mode = "LIVE" if args.live else ("PAPER" if args.paper else "DRY-RUN")
    dry = not args.live
    tg_token = args.tg_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    tg_chat = args.tg_chat or os.environ.get("TELEGRAM_CHAT_ID", "")

    params = StratParams(
        use_trend_filter=not args.no_trend_filter,
        ema_fast=args.ema_fast,
        ema_slow=args.ema_slow,
        trail_activation_atr=args.trail_activation,
        trail_distance_atr=args.trail_distance,
    )

    ex = make_exchange(args.exchange, args.paper)
    startup_msg = (f"[{mode}] MAx10eth Bot v2 started\n"
                   f"Exchange: {args.exchange} | TF: {args.tf}\n"
                   f"Symbols: {', '.join(args.symbols)}\n"
                   f"Trend: EMA{params.ema_fast}/{params.ema_slow} | Trail: {params.trail_activation_atr}/{params.trail_distance_atr}x ATR\n"
                   f"Min grade: {args.min_grade} | Risk: {args.risk*100:.1f}%")
    print(startup_msg)
    send_telegram(startup_msg, tg_token, tg_chat)

    # Position tracking per symbol
    positions: dict[str, Optional[Position]] = {s: None for s in args.symbols}
    last_signal_ts = {s: None for s in args.symbols}

    def run_once():
        for sym in args.symbols:
            try:
                df = fetch_recent(ex, sym, args.tf, 500)
                cur = df.iloc[-1]
                price = float(cur.c)
                cur_atr_val = float(atr(df.h, df.l, df.c, 14).iloc[-1])

                # --- Check existing position for trailing stop exit ---
                pos = positions[sym]
                if pos is not None:
                    exit_reason = pos.update(float(cur.h) if hasattr(cur, 'h') else price,
                                             float(cur.l) if hasattr(cur, 'l') else price,
                                             price, cur_atr_val)
                    if exit_reason:
                        pnl = ((price / pos.entry - 1) if pos.side == "long" else (pos.entry / price - 1)) * 100
                        exit_msg = (f"{'🏁'} *EXIT {sym}* ({exit_reason})\n"
                                    f"Side: {pos.side} | Entry: {pos.entry:.2f} | Exit: {price:.2f}\n"
                                    f"PnL: {pnl:+.2f}% | Trail active: {pos.trail_active}")
                        print(f"  {exit_msg.replace(chr(10), ' | ')}")
                        send_telegram(exit_msg, tg_token, tg_chat)
                        positions[sym] = None

                # --- Evaluate new signal ---
                sig = evaluate(df, params)

                vwap_v, _ = session_vwap(df, "D")
                vw = vwap_v.iloc[-1]
                trend_str = sig.trend if sig else "?"
                pos_str = f"pos={positions[sym].side}" if positions[sym] else "flat"

                print(f"[{datetime.now():%H:%M:%S}] {sym}  px={price:.2f}  vwap={vw:.2f}  trend={trend_str}  {pos_str}  ", end="")

                if sig is None:
                    print("no signal")
                    continue

                if sig.timestamp == last_signal_ts.get(sym):
                    print(f"signal {sig.side} {sig.grade} (already handled)")
                    continue

                grades_order = {"S": 3, "A": 2, "B": 1}
                if grades_order[sig.grade] < grades_order[args.min_grade]:
                    print(f"signal {sig.side} {sig.grade} below min-grade {args.min_grade}")
                    continue

                # Don't open if already in position same direction
                if positions[sym] and positions[sym].side == sig.side:
                    print(f"already {sig.side}, skip")
                    continue

                # If in opposite position, close first (flip)
                if positions[sym] and positions[sym].side != sig.side:
                    flip_msg = f"FLIP {sym}: closing {positions[sym].side} -> opening {sig.side}"
                    print(f"\n  {flip_msg}")
                    send_telegram(flip_msg, tg_token, tg_chat)
                    positions[sym] = None

                last_signal_ts[sym] = sig.timestamp
                print(f"\n  SIGNAL {sig.side.upper()} [{sig.grade}]  entry={sig.entry:.2f} SL={sig.sl:.2f} TP={sig.tp:.2f}")
                print(f"  reason: {sig.reason}")

                risk_usd = args.equity * args.risk
                place_order(ex, sym, sig, risk_usd, dry, tg_token, tg_chat)

                # Track position locally
                positions[sym] = Position(
                    side=sig.side, entry=sig.entry, sl=sig.sl,
                    highest=price if sig.side == "long" else 0,
                    lowest=price if sig.side == "short" else 999999,
                    trail_atr=params.trail_distance_atr,
                    trail_activation=params.trail_activation_atr,
                    atr_at_entry=sig.atr_val,
                )

            except Exception as e:
                print(f"  ERROR {sym}: {e}")

    if args.once:
        run_once()
        return

    # Main loop
    tf_sec = ex.parse_timeframe(args.tf)
    sleep_s = max(60, tf_sec // 4)
    print(f"Loop interval: {sleep_s}s ({sleep_s//60}min)")

    stop = False
    def handler(s, frame):
        nonlocal stop
        stop = True
        print("\nStopping...")
        send_telegram("Bot stopped.", tg_token, tg_chat)
    sig_mod.signal(sig_mod.SIGINT, handler)

    while not stop:
        run_once()
        for _ in range(sleep_s):
            if stop:
                break
            time.sleep(1)


if __name__ == "__main__":
    main()
