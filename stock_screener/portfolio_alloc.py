"""
低位机会资金分配分析器

输入:
  - 股票代码列表(美股 / A 股)
基本面: 市值 / PE(TTM) / 营收增速 / 利润率 / 负债率
量价: 20/60/120 日 VWAP(平均筹码代理)、量能趋势(主力进出代理)
技术面: 复用 screener.analyze 的位置/RSI/评级

输出:
  按综合评分加权的资金分配比例 + 完整分析表
"""
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import pandas as pd
import numpy as np
from screener import analyze as tech_analyze, calc_atr


def fetch_fundamentals(symbol):
    """拉取基本面: market cap, PE, revenue growth, profit margin, debt"""
    try:
        t = yf.Ticker(symbol)
        info = t.info
        return {
            "market_cap": info.get("marketCap") or info.get("enterpriseValue"),
            "pe_ttm":    info.get("trailingPE"),
            "pe_fwd":    info.get("forwardPE"),
            "ps":        info.get("priceToSalesTrailing12Months"),
            "rev_growth": info.get("revenueGrowth"),         # YoY
            "earn_growth": info.get("earningsGrowth"),
            "profit_margin": info.get("profitMargins"),
            "debt_to_eq":  info.get("debtToEquity"),
            "roe":         info.get("returnOnEquity"),
            "fcf":         info.get("freeCashflow"),
            "name":        info.get("longName") or info.get("shortName") or symbol,
            "sector":      info.get("sector"),
            "industry":    info.get("industry"),
        }
    except Exception as e:
        return {"name": symbol, "_error": str(e)}


def fetch_volume_price_signals(symbol):
    """量价行为信号 - 用于推断主力资金动向"""
    try:
        df = yf.download(symbol, period="2y", interval="1d",
                         progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna(subset=["Close", "High", "Low", "Volume"])
        if len(df) < 130:
            return None

        close = df["Close"]
        vol = df["Volume"]
        last = float(close.iloc[-1])

        # ============ VWAP (体积加权均价) - 平均筹码代理 ============
        # 公式: sum(close * volume) / sum(volume)
        def vwap(n):
            if len(df) < n:
                return None
            seg = df.tail(n)
            v = seg["Volume"].values
            tp = ((seg["High"] + seg["Low"] + seg["Close"]) / 3).values
            return float((tp * v).sum() / v.sum()) if v.sum() > 0 else None

        vwap20  = vwap(20)
        vwap60  = vwap(60)
        vwap120 = vwap(120)

        # 当前价与 VWAP 的相对位置
        chip_status = ""
        if vwap60 is not None:
            premium_60 = (last / vwap60 - 1) * 100
            if premium_60 > 5:
                chip_status = "套利盘多(price > 60d VWAP +5%)"
            elif premium_60 < -5:
                chip_status = "深套(price < 60d VWAP -5%)"
            else:
                chip_status = "成本附近震荡"

        # ============ 主力资金行为代理 ============
        # 思路 1: 上涨日成交量 vs 下跌日成交量 (60日)
        last60 = df.tail(60).copy()
        up_days   = last60[last60["Close"] > last60["Open"]]
        down_days = last60[last60["Close"] < last60["Open"]]
        up_vol_avg   = up_days["Volume"].mean()   if len(up_days) > 0 else 0
        down_vol_avg = down_days["Volume"].mean() if len(down_days) > 0 else 0
        # OBV 累积量平衡指标
        obv = (np.sign(close.diff()).fillna(0) * vol).cumsum()
        obv_change_60 = float((obv.iloc[-1] - obv.iloc[-60]) / abs(obv.iloc[-60])) if abs(obv.iloc[-60]) > 0 else 0

        # 资金累积 / 派发线 (CMF 简化版)
        # CMF = sum((close-low) - (high-close)) / (high-low) * volume / sum(volume)
        money_flow_mult = ((close - df["Low"]) - (df["High"] - close)) / (df["High"] - df["Low"]).replace(0, np.nan)
        money_flow_vol = money_flow_mult * vol
        cmf_20 = float(money_flow_vol.tail(20).sum() / vol.tail(20).sum()) if vol.tail(20).sum() > 0 else 0

        # 量能趋势(过去 60 日均量 vs 240 日均量)
        recent_vol = vol.tail(60).mean()
        baseline_vol = vol.tail(240).mean() if len(vol) >= 240 else vol.mean()
        vol_trend_pct = (recent_vol / baseline_vol - 1) * 100 if baseline_vol > 0 else 0

        # 主力推断
        institutional_signal = ""
        score = 0
        if up_vol_avg > down_vol_avg * 1.3 and obv_change_60 > 0:
            institutional_signal = "✅ 放量上涨缩量回调 → 主力疑似建仓"
            score = 2
        elif up_vol_avg > down_vol_avg * 1.1 and cmf_20 > 0.05:
            institutional_signal = "✅ 资金温和净流入"
            score = 1
        elif down_vol_avg > up_vol_avg * 1.3 or cmf_20 < -0.1:
            institutional_signal = "🔻 放量下跌 → 主力疑似派发"
            score = -2
        elif vol_trend_pct > 30 and cmf_20 > 0:
            institutional_signal = "⚠️ 异常放量 注意是否突破"
            score = 1
        else:
            institutional_signal = "➖ 量价中性"
            score = 0

        return {
            "vwap_20":  round(vwap20, 2) if vwap20 else None,
            "vwap_60":  round(vwap60, 2) if vwap60 else None,
            "vwap_120": round(vwap120, 2) if vwap120 else None,
            "chip_status": chip_status,
            "premium_to_60vwap_pct": round((last/vwap60 - 1) * 100, 2) if vwap60 else None,
            "up_vol_vs_down": round(up_vol_avg / down_vol_avg, 2) if down_vol_avg > 0 else None,
            "obv_change_60d": round(obv_change_60, 3),
            "cmf_20": round(cmf_20, 3),
            "vol_trend_pct": round(vol_trend_pct, 1),
            "institutional_signal": institutional_signal,
            "institutional_score": score,
        }
    except Exception as e:
        return None


def analyze_one(symbol):
    """整合: 技术面 + 基本面 + 量价"""
    tech = tech_analyze(symbol)
    if not tech:
        return None
    fund = fetch_fundamentals(symbol) or {}
    flow = fetch_volume_price_signals(symbol) or {}

    return {
        "symbol": symbol,
        "name": fund.get("name", symbol),
        "sector": fund.get("sector"),
        "price": tech["price"],
        "position_pct": tech["position_pct"],
        "rsi": tech["rsi"],
        "rating": tech["rating"],
        "tech_score": tech["score"],
        # 基本面
        "market_cap": fund.get("market_cap"),
        "pe_ttm": fund.get("pe_ttm"),
        "pe_fwd": fund.get("pe_fwd"),
        "rev_growth": fund.get("rev_growth"),
        "profit_margin": fund.get("profit_margin"),
        "roe": fund.get("roe"),
        "debt_to_eq": fund.get("debt_to_eq"),
        # 量价
        "vwap_60": flow.get("vwap_60"),
        "vwap_120": flow.get("vwap_120"),
        "premium_60vwap": flow.get("premium_to_60vwap_pct"),
        "up_vol_vs_down": flow.get("up_vol_vs_down"),
        "cmf_20": flow.get("cmf_20"),
        "obv_60d": flow.get("obv_change_60d"),
        "vol_trend_pct": flow.get("vol_trend_pct"),
        "chip_status": flow.get("chip_status"),
        "institutional": flow.get("institutional_signal"),
        "inst_score": flow.get("institutional_score", 0),
    }


def composite_score(r):
    """综合评分 - 用于资金分配"""
    s = 0
    # 技术面位置 (越低分越高)
    pos = r.get("position_pct") or 50
    if pos < 10:    s += 30
    elif pos < 20:  s += 25
    elif pos < 30:  s += 18
    elif pos < 50:  s += 10
    elif pos < 70:  s += 5
    else:           s += 0

    # RSI (超卖加分)
    rsi = r.get("rsi") or 50
    if rsi < 25:    s += 15
    elif rsi < 35:  s += 10
    elif rsi < 45:  s += 5
    elif rsi > 70:  s -= 10

    # 估值 PE
    pe = r.get("pe_ttm")
    if pe is not None and pe > 0:
        if pe < 15:   s += 15
        elif pe < 25: s += 10
        elif pe < 40: s += 5
        elif pe > 80: s -= 10
        elif pe > 50: s -= 5

    # 营收增速
    rg = r.get("rev_growth")
    if rg is not None:
        if rg > 0.30: s += 15
        elif rg > 0.15: s += 10
        elif rg > 0.05: s += 5
        elif rg < -0.10: s -= 10

    # 利润率
    pm = r.get("profit_margin")
    if pm is not None:
        if pm > 0.20: s += 10
        elif pm > 0.10: s += 5
        elif pm > 0:    s += 2
        elif pm < -0.05: s -= 10

    # 负债率
    de = r.get("debt_to_eq")
    if de is not None:
        if de < 50:  s += 5
        elif de > 200: s -= 5

    # ROE
    roe = r.get("roe")
    if roe is not None:
        if roe > 0.20: s += 10
        elif roe > 0.10: s += 5
        elif roe < 0:    s -= 5

    # 主力资金
    s += (r.get("inst_score") or 0) * 5

    # 市值(规避微盘风险)
    mc = r.get("market_cap") or 0
    if mc > 0:
        if mc < 1e9:    s -= 5   # < 10 亿美元/RMB(微盘)
        elif mc > 5e10: s += 3   # 大盘股加点

    return max(0, s)  # 不允许负分


def fmt_market_cap(mc):
    if not mc: return "N/A"
    if mc > 1e12: return f"{mc/1e12:.2f}T"
    if mc > 1e9:  return f"{mc/1e9:.1f}B"
    if mc > 1e6:  return f"{mc/1e6:.0f}M"
    return f"{mc:,.0f}"


def allocate_capital(results, total_capital=100000, label="组合"):
    """按综合评分加权分配资金,加上单笔上下限"""
    print(f"\n{'='*120}")
    print(f"💰 资金分配方案 - {label} (总资金 {total_capital:,})")
    print(f"{'='*120}\n")

    scored = [(composite_score(r), r) for r in results]
    scored.sort(key=lambda x: -x[0])
    total_score = sum(s for s, _ in scored)
    if total_score == 0:
        print("没有有效股票")
        return

    # 单笔限制: 最少 5% 最多 25%
    n = len(scored)
    min_pct = 0.05
    max_pct = 0.25 if n >= 5 else 0.40

    raw_pcts = [(s/total_score) for s, _ in scored]
    # 套上上限,溢出部分按比例分给其他
    capped = []
    overflow = 0
    for p in raw_pcts:
        if p > max_pct:
            overflow += (p - max_pct)
            capped.append(max_pct)
        else:
            capped.append(p)
    if overflow > 0:
        # 把溢出按剩余空间比例分回去
        free_room = sum(max_pct - c for c in capped)
        if free_room > 0:
            capped = [c + (max_pct - c) / free_room * overflow if c < max_pct else c
                     for c in capped]
    # 套下限
    capped = [max(p, min_pct) for p in capped]
    # 重新归一化
    s_sum = sum(capped)
    final_pcts = [p / s_sum for p in capped]

    print(f"{'排名':<4}{'代码':<10}{'名称':<26}{'综合分':>7}{'分配 %':>9}{'分配金额':>12}{'股价':>9}{'估算手数':>10}")
    print("-" * 120)
    for i, ((sc, r), pct) in enumerate(zip(scored, final_pcts), 1):
        amount = total_capital * pct
        shares = int(amount / r["price"]) if r["price"] > 0 else 0
        name_short = (r["name"] or r["symbol"])[:24]
        print(f"{i:<4}{r['symbol']:<10}{name_short:<26}{sc:>7.0f}{pct*100:>8.1f}%{amount:>12,.0f}{r['price']:>9.2f}{shares:>10}")
    print()

    # 详情表
    print(f"{'─'*120}")
    print(f"📊 基本面 + 量价详情")
    print(f"{'─'*120}\n")
    print(f"{'代码':<10}{'市值':>10}{'PE_TTM':>9}{'营收增长':>9}{'利润率':>8}{'ROE':>7}{'位置%':>7}{'RSI':>6}{'60d VWAP':>10}{'当前/VWAP':>11}")
    print("-" * 120)
    for sc, r in scored:
        mc = fmt_market_cap(r.get("market_cap"))
        pe = f"{r['pe_ttm']:.1f}" if r.get("pe_ttm") and r["pe_ttm"] > 0 else "—"
        rg = f"{r['rev_growth']*100:+.1f}%" if r.get("rev_growth") else "—"
        pm = f"{r['profit_margin']*100:.1f}%" if r.get("profit_margin") else "—"
        roe = f"{r['roe']*100:.1f}%" if r.get("roe") else "—"
        vwap60 = f"{r['vwap_60']:.2f}" if r.get("vwap_60") else "—"
        prem = f"{r['premium_60vwap']:+.1f}%" if r.get("premium_60vwap") is not None else "—"
        print(f"{r['symbol']:<10}{mc:>10}{pe:>9}{rg:>9}{pm:>8}{roe:>7}{r['position_pct']:>6.1f}%{r['rsi']:>6.1f}{vwap60:>10}{prem:>11}")
    print()

    print(f"{'─'*120}")
    print(f"🎯 主力资金 / 筹码状态推断 (基于量价行为,不是 L2 数据)")
    print(f"{'─'*120}\n")
    for sc, r in scored:
        print(f"  {r['symbol']:<10} {r['name'][:20]:<20}  {r.get('chip_status',''):<22}  {r.get('institutional','')}")
    print()
    return [(r, pct, amount) for ((sc, r), pct, amount) in zip(scored, final_pcts, [total_capital*p for p in final_pcts])]


def main():
    # ========== 美股部分 ==========
    us_stocks = ["NRG", "VST", "SMR", "STEM", "EXE", "CEG", "PEG", "OKLO"]
    us_results = []
    print(f"分析美股 {len(us_stocks)} 只...")
    for i, s in enumerate(us_stocks, 1):
        print(f"  [{i}/{len(us_stocks)}] {s}", end=" ... ", flush=True)
        r = analyze_one(s)
        if r:
            us_results.append(r)
            print(f"OK 评分 {composite_score(r):.0f}")
        else:
            print("跳过")
        time.sleep(0.2)

    # ========== A 股部分(截图里的 4 只低位机会) ==========
    base_dir = os.path.dirname(os.path.abspath(__file__))
    a_share_list = ["603160.SS", "002230.SZ", "603690.SS", "603893.SS"]
    print(f"\n分析 A 股截图 4 只...")
    a_results = []
    for i, s in enumerate(a_share_list, 1):
        print(f"  [{i}/{len(a_share_list)}] {s}", end=" ... ", flush=True)
        r = analyze_one(s)
        if r:
            a_results.append(r)
            print(f"OK 评分 {composite_score(r):.0f}")
        else:
            print("跳过")
        time.sleep(0.2)

    us_alloc = allocate_capital(us_results, 100000, label="美股 AI 能源 (8 只)")
    a_alloc = allocate_capital(a_results, 100000, label="A 股 4 只低位机会(截图)")

    # 保存到 CSV
    out_us = os.path.join(base_dir, "alloc_us.csv")
    out_cn = os.path.join(base_dir, "alloc_cn.csv")
    pd.DataFrame(us_results).to_csv(out_us, index=False, encoding="utf-8-sig")
    pd.DataFrame(a_results).to_csv(out_cn, index=False, encoding="utf-8-sig")
    print(f"💾 详情 CSV: {out_us}, {out_cn}")


if __name__ == "__main__":
    main()
