# @MAx10eth 交易方法蒸馏报告

> 数据来源:推特 [@MAx10eth](https://x.com/MAx10eth) 公开推文(2026-03 ~ 2026-05,共 12 条核心交易推文)
> 蒸馏方式:对推文文本逐条提取交易概念,统计出现频次,逆向重建决策树

---

## 1. 交易者画像

- **Bio 自述**:"A terrible trader, still learning... Heavy poor-high/poor-low trader" — 自嘲为"重度Poor High/Poor Low玩家"
- **Leader**:`KBeast.eth`(其策略导师)
- **核心标的**:几乎全是 `$btc`,偶尔 ETH
- **交易频率**:中频,平均每周 1-3 条交易思路推文
- **风格定性**:**纯订单流 / 拍卖理论(Auction Theory)** 派,不是传统 K 线/趋势派

---

## 2. 推文内容核心概念出现频次

| 概念 | 出现次数 | 含义 |
|---|---|---|
| **VWAP** | 8 | 成交量加权均价(他的核心工具,反复提到 "reclaim VWAP", "edge of VWAP", "tap into VWAP") |
| **Divergence** | 3 | 指标背离(常和高点结合) |
| **Single Prints (SP)** | 3 | TPO 单次打印区域(Market Profile 概念) |
| **VAH / VAL / VA** | 3 | Value Area High/Low(价值区上下沿) |
| **Reclaim** | 3 | 价格重夺某关键位 |
| **POI** | 2 | Point of Interest(关注价位) |
| **TPO** | 2 | Time Price Opportunity(市场轮廓) |
| **Imbalance** | 2 | 卖侧/买侧失衡区 |
| **Absorption** | 2 | 吸筹/吃单 |
| **Trapped sellers/buyers** | 1 | 被套交易者 |
| **Poor high/low** | bio | 不规整高/低点(ICT 概念) |

**结论**:他的工具箱是 **VWAP + Volume Profile + Market Profile(TPO)+ ICT 流动性**,没有用 MA/RSI/MACD 之类传统指标。

---

## 3. 入场决策树(从推文逆向工程)

```
                   ┌──────────────────────────────┐
                   │  价格逼近关键位(VWAP/SP/VA) │
                   └─────────────┬────────────────┘
                                 │
              ┌──────────────────┼─────────────────┐
              ▼                  ▼                 ▼
        多头入场条件         空头入场条件        观望条件
        ─────────────        ─────────────       ─────────────
   ✅ 价格 reclaim VWAP   ✅ 高点出现背离      ❌ "missing something"
      并被市场接受          ✅ 第二次回测高点      → 等更确定信号
   ✅ 出现 absorption       出现 single prints
   ✅ Trapped sellers     ✅ 高点TPO顶部 + 小单
      在 VWAP 下方
   ✅ 价格在 SP 上方
      "bulls in control"
```

**他原话样本**:
- 多头:*"If VWAP is reclaimed and accepted, the auction continues upward"*
- 空头:*"Bearish divergence at the high. On the second revisit, single prints appear"*
- 多头确认:*"Above the lower SP level, bulls remain in control"*
- 多头形态:*"Moving along the edge of VWAP — very strong"*

---

## 4. 信号强度分级(用于机器人优先级)

| 等级 | 触发条件组合 | 置信度 |
|---|---|---|
| **S 级(强)** | VWAP reclaim + absorption + 价格在 SP 上方 | ★★★★★ |
| **A 级** | 价格沿 VWAP 边缘运行 + 上次低点未破 | ★★★★ |
| **B 级** | 单一指标背离 + VWAP 触碰 | ★★★ |
| **C 级(慎)** | 单纯背离 / 单纯 single prints | ★★ |

---

## 5. 出场逻辑(从他历史推文反推)

- 没有固定 R:R,他会 **跟随结构变化** 调整(典型 Auction Theory)
- 「If price tests the lower VA again **and reclaims it**」→ 失守 VA 即止损
- 「**SP must hold**」→ SP 是硬止损线
- 高点 single prints 出现 → 减仓/平多

---

## 6. 蒸馏出的核心交易规则(可量化版)

```
LONG ENTRY:
  Price crosses above session VWAP
  AND price is above the most recent Single Print (SP) level
  AND volume confirms (absorption: large green bar at VWAP)

SHORT ENTRY:
  Price rejects at VAH (Value Area High)
  AND bearish RSI/CVD divergence vs prior swing high
  AND price re-tests high with shrinking volume

EXIT:
  LONG  : SL = below SP / VAL ; TP = next VAH / opposite single print
  SHORT : SL = above recent high single print ; TP = VWAP / VAL

POSITION SIZING:
  Risk per trade ≤ 1-2% (他自嘲 "punished daily" 暗示他自己就是没控好仓)
```
