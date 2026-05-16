# MAx10eth Auction Flow Trading System

> Distilled from [@MAx10eth](https://x.com/MAx10eth)'s public tweets — VWAP + Volume Profile + Single Prints + Divergence — then backtested and optimized.

## Performance (2024-01 → 2026-05, no leverage)

| Asset | TF | CAGR% | MaxDD% | PF | Win Rate | Trades |
|---|---|---|---|---|---|---|
| **ETH** | **4H** | **+59.3%** | -21.8% | 10.31 | 69.6% | 23 |
| **BTC** | **4H** | **+34.2%** | -29.6% | 2.61 | 57.7% | 26 |
| BTC B&H | — | +30.2% | ~-75% | — | — | — |
| ETH B&H | — | -1.0% | ~-60% | — | — | — |

---

## Quick Start

### 1. Install dependencies

```bash
pip install ccxt pandas numpy
```

### 2. Run in dry-run mode (signal alerts only, no orders)

```bash
python max10eth_bot.py --symbols ETH/USDT:USDT BTC/USDT:USDT --tf 4h --once
```

### 3. Run continuously (prints signals every hour)

```bash
python max10eth_bot.py --symbols ETH/USDT:USDT BTC/USDT:USDT --tf 4h
```

### 4. With Telegram notifications

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
python max10eth_bot.py --symbols ETH/USDT:USDT BTC/USDT:USDT --tf 4h
```

### 5. Paper trading (OKX demo account)

```bash
export OKX_API_KEY="your_key"
export OKX_API_SECRET="your_secret"
export OKX_PASSWORD="your_passphrase"
python max10eth_bot.py --symbols ETH/USDT:USDT --tf 4h --paper --risk 0.02
```

### 6. LIVE trading (real money — use at own risk!)

```bash
python max10eth_bot.py --symbols ETH/USDT:USDT --tf 4h --live --i-know-what-im-doing --risk 0.01
```

---

## Strategy Logic

```
ENTRY (LONG):
  ✅ Price crosses above session VWAP
  ✅ Price is above last Single Print pivot low (SP↓)
  ✅ Absorption detected (vol > 2x SMA20 AND range < 0.6x ATR14)
     OR bullish RSI divergence (price LL, RSI HL)
  ✅ Daily trend: EMA(21) > EMA(50)

ENTRY (SHORT):
  ✅ Price crosses below session VWAP
  ✅ Price is below last Single Print pivot high (SP↑)
  ✅ Absorption OR bearish RSI divergence
  ✅ Daily trend: EMA(21) < EMA(50)

EXIT:
  🔄 Trailing stop: activates after 3×ATR profit, trails at 5×ATR distance
  🔄 OR opposite signal (flip)
```

---

## Files

| File | Purpose |
|---|---|
| `max10eth_bot.py` | **Main bot** — dry-run / paper / live with Telegram |
| `MAx10eth_VWAP_AuctionFlow.pine` | TradingView strategy (paste into TV) |
| `max10eth_bot_backtest.py` | Backtest engine + parameter sweep |
| `MAx10eth_strategy_report.md` | Full methodology analysis from tweets |
| `backtest_results.md` | Detailed backtest results |
| `SMC_Flow_Strategy.pine` | Earlier SMC strategy variant |
| `SMC_Flow_Strategy_GridScan.pine` | Grid scan version for TV |
| `backtest.py` | Backtest for SMC strategy |

---

## Configuration Options

```
--exchange        Exchange (default: okx). Supports: okx, kucoin, gate, bitget
--symbols         Trading pairs (default: ETH/USDT:USDT BTC/USDT:USDT)
--tf              Timeframe (default: 4h). Recommended: 4h or 1h
--risk            Risk per trade as fraction of equity (default: 0.02 = 2%)
--equity          Assumed equity for dry-run sizing (default: $1000)
--min-grade       Minimum signal quality: S (both absorb+div), A (either) (default: A)
--ema-fast        Fast EMA period for trend (default: 21)
--ema-slow        Slow EMA period for trend (default: 50)
--trail-activation  ATR multiplier to activate trailing stop (default: 3.0)
--trail-distance    ATR multiplier for trail distance (default: 5.0)
--no-trend-filter   Disable daily EMA trend filter
--tg-token        Telegram bot token (or env TELEGRAM_BOT_TOKEN)
--tg-chat         Telegram chat ID (or env TELEGRAM_CHAT_ID)
```

---

## How to get Telegram notifications

1. Message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` → copy token
2. Message your new bot, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Find your `chat_id` in the response
4. Set environment variables:
   ```bash
   export TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
   export TELEGRAM_CHAT_ID="987654321"
   ```

---

## Disclaimer

This is for educational and research purposes only. Trading carries significant risk. Past backtest performance does not guarantee future results. Never risk more than you can afford to lose.
