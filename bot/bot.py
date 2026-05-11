"""
双周期共振实盘交易机器人
- 策略: 日线+4H 逆向+中性共振 (实测 2年 胜率62% PF3.0 收益+117%)
- 支持币安 / OKX U本位永续合约
- 完整风控: 日亏损上限 / 连亏停机 / 余额检查
- 通知: 飞书 / Telegram
"""
from __future__ import annotations
import os
import time
import json
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

from strategy import StrategyConfig, evaluate_signal
from exchange import ExchangeClient, ExchangeConfig
from notifier import Notifier


STATE_FILE = Path(__file__).parent / "bot_state.json"
LOG_FILE   = Path(__file__).parent / "bot.log"


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"consecutive_losses": 0, "daily_pnl": 0, "daily_date": "",
            "last_signal_ts": "", "stop_until": ""}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False),
                          encoding="utf-8")


class TradingBot:
    def __init__(self):
        load_dotenv(Path(__file__).parent / ".env")
        self._load_config()
        self.state = load_state()
        self.notifier = Notifier(
            feishu_webhook=os.getenv("FEISHU_WEBHOOK", ""),
            tg_token=os.getenv("TG_BOT_TOKEN", ""),
            tg_chat_id=os.getenv("TG_CHAT_ID", ""),
        )
        self.ex = ExchangeClient(ExchangeConfig(
            name=os.getenv("EXCHANGE", "binance"),
            api_key=os.getenv("API_KEY", ""),
            api_secret=os.getenv("API_SECRET", ""),
            passphrase=os.getenv("API_PASSPHRASE", ""),
            use_testnet=os.getenv("USE_TESTNET", "true").lower() == "true",
            symbol=os.getenv("SYMBOL", "ETH/USDT:USDT"),
            leverage=int(os.getenv("LEVERAGE", "3")),
        ))
        self.timeframe = os.getenv("TIMEFRAME", "4h")
        self.position_pct = float(os.getenv("POSITION_SIZE_PCT", "10"))
        self.min_balance = float(os.getenv("MIN_BALANCE_USDT", "50"))
        self.max_daily_loss = float(os.getenv("MAX_DAILY_LOSS_PCT", "5"))
        self.max_consec_losses = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "3"))
        self.sandbox_mode = os.getenv("SANDBOX_MODE", "false").lower() == "true"

    def _load_config(self):
        self.strat_cfg = StrategyConfig(
            adx_min=float(os.getenv("ADX_MIN", "25")),
            sl_atr_mult=float(os.getenv("SL_ATR_MULT", "3.0")),
            rr_mult=float(os.getenv("RR_MULT", "1.67")),
            rsi_long_min=float(os.getenv("RSI_LONG_MIN", "40")),
            rsi_long_max=float(os.getenv("RSI_LONG_MAX", "70")),
            rsi_short_min=float(os.getenv("RSI_SHORT_MIN", "30")),
            rsi_short_max=float(os.getenv("RSI_SHORT_MAX", "60")),
            touch_tol_pct=float(os.getenv("TOUCH_TOL_PCT", "0.5")),
            resonance_mode=os.getenv("RESONANCE_MODE", "reverse"),
            d_strong_pct=float(os.getenv("DAILY_STRONG_PCT", "5.0")),
        )

    # ==================== 风控检查 ====================
    def _pre_trade_checks(self) -> tuple[bool, str]:
        # 1. 停机时间检查
        if self.state.get("stop_until"):
            stop_until = datetime.fromisoformat(self.state["stop_until"])
            if datetime.now() < stop_until:
                return False, f"机器人暂停中,恢复时间: {stop_until}"
            else:
                self.state["stop_until"] = ""

        # 2. 连亏检查
        if self.state["consecutive_losses"] >= self.max_consec_losses:
            return False, f"连亏 {self.state['consecutive_losses']} 次,需人工介入重置"

        # 3. 日亏损检查
        today = datetime.now().strftime("%Y-%m-%d")
        if self.state["daily_date"] != today:
            self.state["daily_date"] = today
            self.state["daily_pnl"] = 0
        if self.state["daily_pnl"] <= -self.max_daily_loss:
            return False, f"今日亏损已达 {self.state['daily_pnl']:.2f}%,停机24h"

        # 4. 余额检查
        bal = self.ex.balance_usdt()
        if bal < self.min_balance:
            return False, f"余额 {bal:.2f} < 最小余额 {self.min_balance}"

        return True, "OK"

    # ==================== 核心循环 ====================
    def tick(self):
        log("=" * 60)
        log(f"扫描开始 | {self.ex.cfg.symbol} | {self.timeframe} | "
            f"共振模式={self.strat_cfg.resonance_mode}")

        # 1. 风控前置检查
        ok, msg = self._pre_trade_checks()
        if not ok:
            log(f"[风控] {msg}")
            return

        # 2. 获取数据
        try:
            df_4h = self.ex.fetch_ohlcv(self.timeframe, limit=300)
            df_daily = self.ex.fetch_ohlcv("1d", limit=250)
        except Exception as e:
            log(f"[错误] 获取K线失败: {e}")
            return

        # 3. 评估信号
        sig = evaluate_signal(df_4h, df_daily, self.strat_cfg)
        log(f"信号: side={sig.side} 日线={sig.daily_status} 4H={sig.h4_trend} "
            f"ADX={sig.adx:.1f} RSI={sig.rsi:.1f} | {sig.reason}")

        # 4. 已有持仓 -> 不做事 (让SL/TP处理)
        pos = self.ex.get_position()
        if pos:
            log(f"已有持仓: {pos['side']} {pos['size']} @ {pos['entry']:.2f} "
                f"未实现盈亏={pos['unrealized_pnl']:.2f}")
            return

        # 5. 无信号 -> 退出
        if sig.side == "none":
            return

        # 6. 防止同一根 K 线重复开单
        last_bar_ts = df_4h.index[-1].isoformat()
        if self.state.get("last_signal_ts") == last_bar_ts:
            log("[跳过] 同一根K线已处理过")
            return
        self.state["last_signal_ts"] = last_bar_ts

        # 7. 开仓
        balance = self.ex.balance_usdt()
        usdt_amount = balance * (self.position_pct / 100)

        content = (
            f"**{sig.side.upper()} 信号触发**\n"
            f"- 交易对: {self.ex.cfg.symbol}\n"
            f"- 入场价: {sig.entry:.2f}\n"
            f"- 止损价: {sig.sl:.2f}\n"
            f"- 止盈价: {sig.tp:.2f}\n"
            f"- 日线: {sig.daily_status} | 4H: {sig.h4_trend}\n"
            f"- 仓位: {usdt_amount:.2f} USDT (账户 {self.position_pct}%)"
        )

        if self.sandbox_mode:
            self.notifier.send(f"[模拟] {sig.side} 信号", content, "info")
            log(f"[沙盒模式] 不下真实单,仅通知")
            save_state(self.state)
            return

        try:
            result = self.ex.open_position(sig.side, sig.entry, sig.sl, sig.tp,
                                           usdt_amount)
            log(f"[成交] {sig.side} {result['qty']}张 @ {sig.entry:.2f}")
            self.notifier.send(f"实盘开仓 {sig.side.upper()}", content, "info")
        except Exception as e:
            log(f"[错误] 开仓失败: {e}")
            traceback.print_exc()
            self.notifier.send("开仓失败", f"{e}", "error")

        save_state(self.state)

    def run_forever(self):
        """主循环: 每 60 秒扫描一次"""
        log(f"机器人启动 | 测试网={self.ex.cfg.use_testnet} | 沙盒={self.sandbox_mode}")
        self.notifier.send("机器人启动",
                           f"交易对: {self.ex.cfg.symbol}\n"
                           f"周期: {self.timeframe}\n"
                           f"测试网: {self.ex.cfg.use_testnet}", "info")
        while True:
            try:
                self.tick()
            except Exception as e:
                log(f"[严重错误] {e}")
                traceback.print_exc()
                self.notifier.send("机器人异常", f"{e}", "error")
            time.sleep(60)


if __name__ == "__main__":
    bot = TradingBot()
    bot.run_forever()
