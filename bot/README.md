# ETH 双周期共振自动交易机器人

基于 Kiro 验证过的"日线+4H 逆向共振"策略,实盘回测数据:
- **胜率**: 62.5% | **盈亏比**: 1.79 | **利润因子**: 3.00
- **2 年累计收益**: +117.1% | **最大回撤**: 11.5% | **Calmar**: 10.2

## 文件结构

```
bot/
├── bot.py              主程序 (实盘循环)
├── strategy.py         策略核心 (双周期共振)
├── exchange.py         交易所封装 (币安/OKX)
├── notifier.py         通知 (飞书/Telegram)
├── backtest_local.py   本地回测验证
├── requirements.txt    依赖
├── .env.example        配置模板
└── README.md           本文档
```

## 使用步骤

### 1. 安装依赖

```bash
cd bot
pip install -r requirements.txt
```

### 2. 配置

```bash
cp .env.example .env
# 编辑 .env 填入 API Key 和其他参数
```

**强烈建议先用币安测试网**:
- 注册: https://testnet.binancefuture.com/
- 获取测试网 API Key
- `.env` 中设置 `USE_TESTNET=true`

### 3. 本地回测验证

先确认策略在你机器上能复现预期数据:

```bash
python backtest_local.py
```

应看到: `胜率 ~62% | 利润因子 ~3.0 | 收益 ~+100%`

### 4. 模拟运行 (不下真实单)

`.env` 中设置 `SANDBOX_MODE=true`,只打印/通知不下单:

```bash
python bot.py
```

### 5. 测试网实盘

`.env` 中:
```
USE_TESTNET=true
SANDBOX_MODE=false
```

```bash
python bot.py
```

观察至少 **1 周**,确认有信号时能正确开仓/挂单/触发SL/TP.

### 6. 生产环境实盘

`.env` 中:
```
USE_TESTNET=false
SANDBOX_MODE=false
```

建议先用 **小资金 (100 USDT)** 跑 2 周再放大.

## 运行环境建议

### 本地 VPS (推荐)

云服务器保证 24 小时在线:
- 腾讯云 / 阿里云 2 核 2GB 起步
- 系统装 Ubuntu 22.04
- 用 `screen` 或 `systemd` 保持后台运行

```bash
# 安装 screen
apt install screen -y

# 启动
screen -S bot
cd bot && python bot.py

# Ctrl+A D 分离,断开 ssh 不影响运行
# 重新连接: screen -r bot
```

### systemd 服务 (更稳)

创建 `/etc/systemd/system/eth-bot.service`:

```ini
[Unit]
Description=ETH Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/MING/bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable eth-bot
systemctl start eth-bot
systemctl status eth-bot
journalctl -u eth-bot -f   # 看日志
```

## 风控说明

机器人内置 3 层风控:

1. **日亏损上限**: 单日亏损达 5% 自动停 24h (`MAX_DAILY_LOSS_PCT`)
2. **连亏停机**: 连续亏 3 笔后停机,需人工重置状态 (`MAX_CONSECUTIVE_LOSSES`)
3. **余额下限**: 账户低于 50 USDT 禁止开单 (`MIN_BALANCE_USDT`)

手动重置连亏计数:
```bash
python -c "import json; json.dump({'consecutive_losses': 0, 'daily_pnl': 0, 'daily_date':'', 'last_signal_ts':'', 'stop_until':''}, open('bot_state.json','w'))"
```

## 通知配置

### 飞书 (推荐)

1. 创建飞书群,右上角"..." → 设置 → 群机器人
2. 添加 "自定义机器人",复制 webhook URL
3. 填入 `.env` 的 `FEISHU_WEBHOOK`

### Telegram

1. 与 [@BotFather](https://t.me/BotFather) 对话创建机器人,获得 Token
2. 与你的新机器人对话发任意消息
3. 访问 `https://api.telegram.org/bot<TOKEN>/getUpdates` 获取 `chat_id`
4. 填入 `.env` 的 `TG_BOT_TOKEN` 和 `TG_CHAT_ID`

## 安全提醒

- ❗ **API 权限**: 只勾选"合约交易",**一定不要勾"提现"**
- ❗ **IP 白名单**: 绑定你 VPS 的固定 IP
- ❗ **资金管理**: 单策略不超过总资金 20%
- ❗ **杠杆**: 建议 ≤3x,高杠杆会放大爆仓风险
- ❗ **数据备份**: 定期备份 `bot_state.json` 和 `bot.log`

## 策略参数对照

| 参数 | 默认值 | 含义 |
|---|---|---|
| `ADX_MIN` | 25 | 最低趋势强度阈值 |
| `SL_ATR_MULT` | 3.0 | 止损 ATR 倍数 |
| `RR_MULT` | 1.67 | 盈亏比 |
| `TOUCH_TOL_PCT` | 0.5 | 回调容忍度 % |
| `RESONANCE_MODE` | reverse | 共振模式 (reverse/pure/forward) |
| `DAILY_STRONG_PCT` | 5.0 | 日线强趋势阈值 |

## 免责声明

- 本代码仅供学习研究,不构成投资建议
- 实盘交易风险自担,加密货币波动剧烈,可能全部亏损
- 回测表现不代表未来收益
- 建议先测试网跑满 1 个月,确认无 BUG 再上实盘
