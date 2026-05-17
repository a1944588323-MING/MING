"""配置文件 - 修改这里就行,不用动主程序"""

# ===== 标的 =====
STOCK_CODE = "300059"          # 东方财富 (推荐)
STOCK_NAME = "东方财富"
INITIAL_PRICE = 14.50          # 第一次启动时的价格 (用于计算初始底仓)

# ===== 资金 =====
CAPITAL = 10000                # 总资金
BTC_POSITION_PCT = 0.7         # 底仓比例 (70%)
MIN_T_SHARES = 500             # 每次做 T 的股数 (A股必须 100 整数倍)

# ===== 信号阈值 =====
SELL_THRESHOLD = 1.5           # 拉升 +1.5% 触发卖出
BUY_THRESHOLD = -1.0           # 回调 -1% 触发买入

# ===== 风控 =====
MAX_DAILY_LOSS = 0.03          # 单日最大亏损 3%
COMMISSION = 0.0003            # 手续费 (双边万 3)

# ===== 监控 =====
CHECK_INTERVAL = 60            # 检查频率 (秒)

# ===== 通知 =====
# Server酱微信推送 (免费)
# 申请: https://sct.ftqq.com/
SERVERCHAN_KEY = ""            # 填你的 Key, 如 "SCT123abc..."

# ===== 文件路径 =====
LOG_DIR = "logs"
POSITION_FILE = "logs/position.json"
