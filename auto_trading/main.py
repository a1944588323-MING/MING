"""
A 股做 T 半自动化交易系统 (主程序)
功能:
  1. 实时拉取股票分钟级数据
  2. 自动检测做 T 信号 (拉升卖出/回调买入)
  3. 微信/桌面通知 (1秒响应)
  4. 自动生成挂单清单
  5. 自动记录交易日志

运行: python main.py
依赖: pip install akshare pandas requests plyer
"""
import akshare as ak
import pandas as pd
import time
import json
import os
from datetime import datetime, time as dtime
import requests
try:
    from plyer import notification
except ImportError:
    notification = None
from config import *


class TradingBot:
    def __init__(self):
        self.last_signal = None
        self.last_signal_time = None
        os.makedirs(LOG_DIR, exist_ok=True)
        self.position = self.load_position()
        self.daily_trades = 0
        self.daily_pnl = 0
        self.session_start_value = self.position.get('cash', CAPITAL) + \
                                    self.position.get('shares', 0) * self.position.get('avg_price', 0)

    def load_position(self):
        """加载持仓状态 (重启后保持一致)"""
        if os.path.exists(POSITION_FILE):
            return json.loads(open(POSITION_FILE).read())
        return {
            "shares": int(CAPITAL * BTC_POSITION_PCT / INITIAL_PRICE / 100) * 100,
            "avg_price": INITIAL_PRICE,
            "cash": CAPITAL * (1 - BTC_POSITION_PCT)
        }

    def save_position(self):
        json.dump(self.position, open(POSITION_FILE, 'w'), indent=2, ensure_ascii=False)

    def is_trading_hour(self):
        now = datetime.now().time()
        return (dtime(9, 30) <= now <= dtime(11, 30)) or \
               (dtime(13, 0) <= now <= dtime(15, 0))

    def get_realtime_data(self):
        try:
            df = ak.stock_zh_a_hist_min_em(
                symbol=STOCK_CODE,
                period="1",
                start_date=datetime.now().strftime("%Y-%m-%d") + " 09:30:00",
                end_date=datetime.now().strftime("%Y-%m-%d") + " 15:00:00",
                adjust=""
            )
            if df is None or len(df) < 2:
                return None
            return df
        except Exception as e:
            print(f"[ERR] 数据获取失败: {e}")
            return None

    def calc_indicators(self, df):
        close = df["收盘"] if "收盘" in df.columns else df["close"]
        delta = close.diff()
        up = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        dn = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        df["rsi"] = 100 - 100/(1+up/dn.replace(0, float('nan')))
        df["ma5"] = close.rolling(5).mean()
        df["ma20"] = close.rolling(20).mean()
        df["close"] = close
        return df

    def detect_signal(self, df):
        if df is None or len(df) < 20:
            return None, "数据不足"
        df = self.calc_indicators(df)
        open_p = (df["开盘"] if "开盘" in df.columns else df["open"]).iloc[0]
        cur = df["close"].iloc[-1]
        high = (df["最高"] if "最高" in df.columns else df["high"]).max()
        low = (df["最低"] if "最低" in df.columns else df["low"]).min()
        pct = (cur - open_p) / open_p * 100
        amp = (high - low) / open_p * 100
        rsi = df["rsi"].iloc[-1]
        info = {"price":cur,"open":open_p,"pct":pct,"amp":amp,"rsi":rsi,
                "ma5":df["ma5"].iloc[-1],"ma20":df["ma20"].iloc[-1]}

        if pct >= SELL_THRESHOLD and rsi > 65 and self.position["shares"] >= MIN_T_SHARES * 2:
            return "SELL", info
        if pct <= BUY_THRESHOLD and rsi < 35 and self.position["cash"] >= cur * MIN_T_SHARES:
            return "BUY", info
        return None, info

    def send_wechat(self, title, content):
        if not SERVERCHAN_KEY:
            return
        url = f"https://sctapi.ftqq.com/{SERVERCHAN_KEY}.send"
        try:
            requests.post(url, data={"title": title, "desp": content}, timeout=5)
        except Exception as e:
            print(f"[微信推送失败] {e}")

    def desktop_notify(self, title, msg):
        if notification:
            try:
                notification.notify(title=title, message=msg, app_name="A股做T", timeout=10)
            except:
                pass

    def write_order(self, signal, qty, price, info):
        log_file = os.path.join(LOG_DIR, f"orders_{datetime.now().strftime('%Y%m')}.csv")
        new_file = not os.path.exists(log_file)
        with open(log_file, "a", encoding="utf-8-sig") as f:
            if new_file:
                f.write("时间,代码,名称,方向,数量,价格,金额,RSI,涨跌%,理由\n")
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')},"
                    f"{STOCK_CODE},{STOCK_NAME},{signal},{qty},{price:.2f},"
                    f"{qty*price:.2f},{info['rsi']:.1f},{info['pct']:+.2f}%,"
                    f"{'拉升超买' if signal=='SELL' else '回调超卖'}\n")

    def execute_signal(self, signal, info):
        now = datetime.now().strftime("%H:%M:%S")
        price = info["price"]

        if self.last_signal == signal:
            if self.last_signal_time and (datetime.now() - self.last_signal_time).seconds < 300:
                return

        self.last_signal = signal
        self.last_signal_time = datetime.now()

        if signal == "SELL":
            qty = MIN_T_SHARES
            title = f"🔴 卖出信号 {STOCK_NAME}({STOCK_CODE})"
            content = (f"时间: {now}\n操作: 卖出 {qty} 股 @ ¥{price:.2f}\n"
                       f"原因: 拉升 {info['pct']:+.2f}%, RSI {info['rsi']:.1f}\n"
                       f"预计收入: ¥{qty*price:.2f}\n⚠️ 请在 1 分钟内手动卖出")
        else:
            qty = MIN_T_SHARES
            title = f"🟢 买入信号 {STOCK_NAME}({STOCK_CODE})"
            content = (f"时间: {now}\n操作: 买入 {qty} 股 @ ¥{price:.2f}\n"
                       f"原因: 回调 {info['pct']:+.2f}%, RSI {info['rsi']:.1f}\n"
                       f"预计花费: ¥{qty*price:.2f}\n⚠️ 请在 1 分钟内手动买入")

        self.send_wechat(title, content)
        self.desktop_notify(title, content[:60])
        print(f"\n{'='*60}\n{title}\n{content}\n{'='*60}")
        print("\a" * 5)
        self.write_order(signal, qty, price, info)

        try:
            input("\n👉 已手动操作完毕? 按 Enter 确认 (Ctrl+C 跳过): ")
            if signal == "SELL":
                self.position["cash"] += qty * price * (1 - COMMISSION)
                self.position["shares"] -= qty
            else:
                self.position["cash"] -= qty * price * (1 + COMMISSION)
                new_total = self.position["shares"] + qty
                new_avg = (self.position["shares"]*self.position["avg_price"] + qty*price) / new_total
                self.position["shares"] = new_total
                self.position["avg_price"] = new_avg
            self.save_position()
            self.daily_trades += 1
            print(f"✅ 持仓更新: {self.position['shares']} 股 + ¥{self.position['cash']:.0f} 现金\n")
        except KeyboardInterrupt:
            print("\n⏭ 跳过本次信号")

    def print_status(self, info):
        now = datetime.now().strftime("%H:%M:%S")
        total = self.position["cash"] + self.position["shares"] * info["price"]
        daily_ret = (total - self.session_start_value) / self.session_start_value * 100 if self.session_start_value else 0
        print(f"[{now}] {STOCK_NAME} ¥{info['price']:.2f} 涨跌{info['pct']:+.2f}% | "
              f"RSI {info['rsi']:.1f} | 持仓 {self.position['shares']} 股 + ¥{self.position['cash']:.0f} | "
              f"今日 {daily_ret:+.2f}% / {self.daily_trades}笔")

    def run(self):
        print(f"\n{'='*60}\nA股做T 半自动化系统启动\n{'='*60}")
        print(f"标的: {STOCK_NAME} ({STOCK_CODE})")
        print(f"卖出阈值: +{SELL_THRESHOLD}% | 买入阈值: {BUY_THRESHOLD}%")
        print(f"持仓: {self.position['shares']} 股 + ¥{self.position['cash']:.0f}")
        print(f"通知: {'微信✓' if SERVERCHAN_KEY else '微信✗ (建议配置)'}\n")

        while True:
            try:
                if not self.is_trading_hour():
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 非交易时段")
                    time.sleep(60)
                    continue
                if self.daily_pnl < -CAPITAL * MAX_DAILY_LOSS:
                    print(f"⛔ 单日亏损达 {MAX_DAILY_LOSS*100}%, 停止交易")
                    time.sleep(300)
                    continue
                df = self.get_realtime_data()
                signal, info = self.detect_signal(df)
                if isinstance(info, dict):
                    self.print_status(info)
                    if signal:
                        self.execute_signal(signal, info)
                time.sleep(CHECK_INTERVAL)
            except KeyboardInterrupt:
                print("\n手动停止")
                break
            except Exception as e:
                print(f"[ERR] {e}")
                time.sleep(30)


if __name__ == "__main__":
    TradingBot().run()
