"""
交易所封装 (基于 ccxt)
支持币安 / OKX 合约 + 测试网
"""
from __future__ import annotations
import ccxt
import pandas as pd
import time
from dataclasses import dataclass


@dataclass
class ExchangeConfig:
    name: str          # "binance" / "okx"
    api_key: str
    api_secret: str
    passphrase: str = ""
    use_testnet: bool = True
    symbol: str = "ETH/USDT:USDT"
    leverage: int = 3


class ExchangeClient:
    def __init__(self, cfg: ExchangeConfig):
        self.cfg = cfg
        self.client = self._init_client()
        self._setup()

    def _init_client(self) -> ccxt.Exchange:
        c = self.cfg
        if c.name == "binance":
            ex = ccxt.binance({
                "apiKey": c.api_key,
                "secret": c.api_secret,
                "options": {"defaultType": "swap"},  # U本位永续
                "enableRateLimit": True,
            })
            if c.use_testnet:
                ex.set_sandbox_mode(True)
        elif c.name == "okx":
            ex = ccxt.okx({
                "apiKey": c.api_key,
                "secret": c.api_secret,
                "password": c.passphrase,
                "options": {"defaultType": "swap"},
                "enableRateLimit": True,
            })
            if c.use_testnet:
                ex.set_sandbox_mode(True)
        else:
            raise ValueError(f"不支持的交易所: {c.name}")
        return ex

    def _setup(self):
        """加载市场 + 设置杠杆"""
        self.client.load_markets()
        try:
            # 币安合约需要单独设置杠杆
            if self.cfg.name == "binance":
                self.client.set_leverage(self.cfg.leverage, self.cfg.symbol)
            elif self.cfg.name == "okx":
                self.client.set_leverage(self.cfg.leverage, self.cfg.symbol,
                                          params={"mgnMode": "cross"})
        except Exception as e:
            print(f"[警告] 设置杠杆失败(可能已设过): {e}")

    # ==================== 数据 ====================
    def fetch_ohlcv(self, timeframe: str, limit: int = 300) -> pd.DataFrame:
        rows = self.client.fetch_ohlcv(self.cfg.symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(rows, columns=["ts","open","high","low","close","volume"])
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        return df.set_index("ts")

    def fetch_price(self) -> float:
        t = self.client.fetch_ticker(self.cfg.symbol)
        return float(t["last"])

    # ==================== 账户 ====================
    def balance_usdt(self) -> float:
        b = self.client.fetch_balance()
        if self.cfg.name == "binance":
            return float(b.get("USDT", {}).get("free", 0))
        elif self.cfg.name == "okx":
            return float(b.get("USDT", {}).get("free", 0))
        return 0.0

    def get_position(self) -> dict | None:
        """返回持仓字典,没有持仓返回 None"""
        try:
            positions = self.client.fetch_positions([self.cfg.symbol])
            for p in positions:
                contracts = float(p.get("contracts") or 0)
                if contracts != 0:
                    return {
                        "side": p.get("side"),
                        "size": contracts,
                        "entry": float(p.get("entryPrice") or 0),
                        "unrealized_pnl": float(p.get("unrealizedPnl") or 0),
                        "leverage": p.get("leverage"),
                    }
        except Exception as e:
            print(f"[警告] 获取持仓失败: {e}")
        return None

    # ==================== 下单 ====================
    def calc_qty(self, price: float, usdt_amount: float) -> float:
        """
        根据 USDT 数额和价格计算合约张数.
        币安 ETH 永续: 1 张 = 1 ETH (contractSize)
        """
        market = self.client.market(self.cfg.symbol)
        contract_size = float(market.get("contractSize") or 1)
        qty = usdt_amount * self.cfg.leverage / (price * contract_size)
        # 按最小精度取整
        qty = float(self.client.amount_to_precision(self.cfg.symbol, qty))
        return qty

    def open_position(self, side: str, price: float, sl: float, tp: float,
                      usdt_amount: float) -> dict:
        """
        开仓 (市价) + 同时挂止损/止盈
        side: "long" / "short"
        """
        qty = self.calc_qty(price, usdt_amount)
        ccxt_side = "buy" if side == "long" else "sell"

        # 1. 开仓市价单
        order = self.client.create_order(
            symbol=self.cfg.symbol,
            type="market",
            side=ccxt_side,
            amount=qty,
        )

        time.sleep(1)  # 等待成交

        # 2. 挂止损止盈 (reduceOnly)
        opp_side = "sell" if side == "long" else "buy"
        sl_order = None
        tp_order = None

        try:
            if self.cfg.name == "binance":
                # 币安: stop loss market (触发价) + take profit limit
                sl_order = self.client.create_order(
                    symbol=self.cfg.symbol, type="STOP_MARKET",
                    side=opp_side, amount=qty,
                    params={"stopPrice": self.client.price_to_precision(self.cfg.symbol, sl),
                            "reduceOnly": True, "workingType": "MARK_PRICE"})
                tp_order = self.client.create_order(
                    symbol=self.cfg.symbol, type="TAKE_PROFIT_MARKET",
                    side=opp_side, amount=qty,
                    params={"stopPrice": self.client.price_to_precision(self.cfg.symbol, tp),
                            "reduceOnly": True, "workingType": "MARK_PRICE"})
            elif self.cfg.name == "okx":
                # OKX 条件单: algo-order
                sl_order = self.client.create_order(
                    symbol=self.cfg.symbol, type="market",
                    side=opp_side, amount=qty,
                    params={"stopLossPrice": sl, "reduceOnly": True})
                tp_order = self.client.create_order(
                    symbol=self.cfg.symbol, type="market",
                    side=opp_side, amount=qty,
                    params={"takeProfitPrice": tp, "reduceOnly": True})
        except Exception as e:
            print(f"[警告] 挂SL/TP失败: {e}")

        return {
            "order": order,
            "sl_order": sl_order,
            "tp_order": tp_order,
            "qty": qty,
            "side": side,
        }

    def close_all(self):
        """平掉所有持仓 + 取消所有挂单"""
        try:
            self.client.cancel_all_orders(self.cfg.symbol)
        except Exception as e:
            print(f"[警告] 取消订单失败: {e}")
        pos = self.get_position()
        if pos:
            side = "sell" if pos["side"] == "long" else "buy"
            self.client.create_order(
                symbol=self.cfg.symbol, type="market",
                side=side, amount=pos["size"],
                params={"reduceOnly": True})
