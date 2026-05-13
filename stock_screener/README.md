# 📊 股票扫描器 (Stock Screener)

基于 **52 周高低点 + RSI + 布林带** 的多市场股票筛选工具。
支持 A 股 / 港股 / 美股,涵盖 7 大主题股票池。

## 📁 文件清单

| 文件 | 用途 |
|---|---|
| `screener.py` | 核心筛选引擎(单股票分析逻辑 + 默认股票池) |
| `pools.py` | 股票池数据库(7 大主题 ≈ 130+ 只) |
| `theme_screener.py` | 通用主题扫描器(命令行选主题) |
| `deep_analyze.py` | 单股深度分析(技术面 + 综合评分) |
| `daily_report.py` | 每日自动扫描报告(Markdown 格式) |
| `ai_stocks_screener.py` | A 股 AI 概念股专用扫描脚本 |
| `reports/` | 历史日报存档目录 |

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install yfinance pandas numpy
```

### 2. 三种使用方式

#### 方式 A:扫描单个主题
```bash
python theme_screener.py ai          # A 股 AI 概念
python theme_screener.py hk_ai       # 港股 AI
python theme_screener.py liquor      # 白酒
python theme_screener.py energy      # 新能源
python theme_screener.py pharma      # 医药
python theme_screener.py military    # 军工
python theme_screener.py solar       # 光伏
python theme_screener.py storage     # A 股 内存/存储
python theme_screener.py us_energy   # 美股 AI 能源(核电/电力)
python theme_screener.py all         # 全部主题串行
```

输出文件:`theme_<主题>_results.csv`

#### 方式 B:深度分析单只股票
```bash
python deep_analyze.py 600519.SS                     # 茅台
python deep_analyze.py AAPL                          # 苹果
python deep_analyze.py 0700.HK                       # 腾讯
python deep_analyze.py 600519.SS 000858.SZ 002230.SZ # 多只一起
```

输出 7 大模块:价格信息、52W 区间、均线系统、RSI、MACD、布林带、成交量、ATR + 综合评分。

#### 方式 C:生成每日全市场报告
```bash
python daily_report.py                # 扫描全部 7 个主题
python daily_report.py ai energy      # 只扫指定主题
python daily_report.py --quiet        # 静默模式
```

输出:`reports/YYYY-MM-DD.md`(Markdown 格式,含全市场摘要 + Top 15 候选 + 各主题低位/高位预警)

### 3. Cron 定时任务示例(每天早上 9:30 自动跑)
```bash
30 9 * * 1-5 cd /path/to/stock_screener && python daily_report.py --quiet
```

## 📊 评分逻辑

| 评级 | 评分 | 含义 |
|---|---|---|
| **A+** | 5+ | 🔥 抄底机会(52W 位置 < 20%) |
| **A** | 4 | ✅ 多单网格区(20-50%) |
| **B** | 3 | ➖ 中位震荡 |
| **C** | 2 | ⚠️ 偏高谨慎(50-80%) |
| **D** | 0-1 | 🚫 高位禁多(>80%) |

加分项:RSI < 30 (超卖) 加 1 分
减分项:RSI > 70 (超买) 减 1 分

## 🎯 股票代码格式

| 市场 | 格式 | 示例 |
|---|---|---|
| 美股 | 直接代码 | `AAPL`, `TSLA`, `NVDA` |
| 港股 | `代码.HK` | `0700.HK`(腾讯) |
| 上海 A 股 | `代码.SS` | `600519.SS`(茅台) |
| 深圳 A 股 | `代码.SZ` | `000858.SZ`(五粮液) |
| ETF | 同上 | `QQQ`, `510300.SS` |

## 📋 当前股票池主题(可在 `pools.py` 自由扩展)

- **ai** - A 股 AI 概念(45 只): 算力服务器、芯片、光模块、AI 应用、IDC、机器人
- **hk_ai** - 港股 AI(15 只): 腾讯/阿里/美团/百度/小米等
- **energy** - 新能源(19 只): 锂电、光伏、风电、新能源车
- **liquor** - 白酒(11 只): 茅五泸 + 二线
- **pharma** - 医药(15 只): 创新药、中药、医疗器械、疫苗
- **military** - 军工(12 只): 航空、电子信息、船舶
- **solar** - 光伏(12 只): 硅料、电池、逆变器、辅材
- **storage** - A 股 内存/存储(25 只): 存储芯片、模组、HBM、存储服务器
- **us_energy** - 美股 AI 能源(35 只): 核电运营、SMR、电力公用、数据中心电力、电网储能、燃气

## ⚠️ 免责声明

本工具基于公开历史价格数据自动生成分析,**仅供研究参考,不构成任何投资建议**。
股市有风险,投资需谨慎,请结合基本面、行业景气度、个人风险承受能力自行决策。
