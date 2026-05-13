"""
Wyckoff(维科夫)派发/吸筹形态分析器
为每只股票判断当前所处的 Wyckoff 阶段,给出分批建仓建议
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import pandas as pd
import numpy as np


def fetch(symbol, period="2y"):
    df = yf.download(symbol, period=period, interval="1d", progress=False, auto_adjust=True)
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=["Close", "High", "Low", "Volume"])
    return df


def analyze_wyckoff(symbol, name=""):
    df = fetch(symbol)
    if df is None or len(df) < 250:
        return None

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    vol = df["Volume"]
    last = float(close.iloc[-1])

    ma20  = close.rolling(20).mean()
    ma60  = close.rolling(60).mean()
    ma200 = close.rolling(200).mean()
    last_ma20  = float(ma20.iloc[-1])
    last_ma60  = float(ma60.iloc[-1])
    last_ma200 = float(ma200.iloc[-1])

    # 52W 位置
    recent = df.tail(252)
    hi52 = float(recent["High"].max())
    lo52 = float(recent["Low"].min())
    pos = (last - lo52) / (hi52 - lo52) * 100 if hi52 > lo52 else 50

    # 趋势斜率
    ma200_slope = (last_ma200 - float(ma200.iloc[-40])) / float(ma200.iloc[-40]) * 100
    ma60_slope  = (last_ma60  - float(ma60.iloc[-20])) / float(ma60.iloc[-20]) * 100

    # 振幅收敛
    last20 = df.tail(20)
    last60 = df.tail(60)
    range20 = (last20["High"].max() - last20["Low"].min()) / last20["Close"].mean()
    range60 = (last60["High"].max() - last60["Low"].min()) / last60["Close"].mean()
    range_ratio = range20 / range60

    # 量价
    obv = (np.sign(close.diff()).fillna(0) * vol).cumsum()
    obv_change_60 = float((obv.iloc[-1] - obv.iloc[-60]) / abs(obv.iloc[-60])) if abs(obv.iloc[-60]) > 0 else 0

    up_days = last60[last60["Close"] > last60["Open"]]
    dn_days = last60[last60["Close"] < last60["Open"]]
    up_vol = up_days["Volume"].mean() if len(up_days) > 0 else 0
    dn_vol = dn_days["Volume"].mean() if len(dn_days) > 0 else 0
    up_dn_ratio = up_vol / dn_vol if dn_vol > 0 else 1.0

    # Spring / UTAD 检测
    last30 = df.tail(30)
    has_spring = False
    has_utad = False
    spring_low = None
    utad_high = None
    prior_low = float(df.tail(120).iloc[:-30]["Low"].min())
    prior_high = float(df.tail(120).iloc[:-30]["High"].max())
    for i in range(len(last30)):
        row = last30.iloc[i]
        if float(row["Low"]) < prior_low * 0.995 and float(row["Close"]) > prior_low * 1.005:
            has_spring = True
            spring_low = float(row["Low"])
        if float(row["High"]) > prior_high * 1.005 and float(row["Close"]) < prior_high * 0.995:
            has_utad = True
            utad_high = float(row["High"])

    # 趋势分类
    if last > last_ma200 and ma200_slope > 1:
        long_trend = "上升"
    elif last < last_ma200 and ma200_slope < -1:
        long_trend = "下跌"
    else:
        long_trend = "震荡"

    if last > last_ma60 and ma60_slope > 1:
        mid_trend = "上升"
    elif last < last_ma60 and ma60_slope < -1:
        mid_trend = "下跌"
    else:
        mid_trend = "震荡"

    # ============ Wyckoff 阶段判断 ============
    phase = "未定"
    phase_detail = ""
    cycle = ""
    confidence = "中"

    if pos < 15:
        cycle = "accumulation"
        if has_spring:
            phase = "C (Spring)"
            phase_detail = f"刚出现 Spring 假跌破 ({spring_low:.2f}),最佳建仓点之一"
            confidence = "高"
        elif range_ratio < 0.6 and abs(ma60_slope) < 2:
            phase = "B (吸筹震荡)"
            phase_detail = "振幅收敛,典型吸筹阶段"
            confidence = "中"
        elif long_trend == "下跌" and mid_trend != "下跌":
            phase = "A (止跌)"
            phase_detail = "长跌后初步止跌,但还未确认企稳"
            confidence = "中"
        else:
            phase = "A/B (筑底中)"
            phase_detail = "底部区域,但形态还不明朗"
            confidence = "低"
    elif 15 <= pos < 35:
        cycle = "accumulation"
        if has_spring and obv_change_60 > -0.05:
            phase = "C->D (Spring 已确认)"
            phase_detail = "Spring 后已回升,SOS 信号待确认"
            confidence = "高"
        elif up_dn_ratio > 1.2 and obv_change_60 > 0:
            phase = "D (SOS 上涨)"
            phase_detail = "Strength of Strength 信号,主力推升"
            confidence = "高"
        elif range_ratio < 0.7:
            phase = "B (吸筹震荡)"
            phase_detail = "底部震荡,有吸筹特征"
            confidence = "中"
        else:
            phase = "A->B (筑底)"
            phase_detail = "脱离极低位但未确认突破"
            confidence = "中"
    elif 35 <= pos < 60:
        if mid_trend == "上升":
            cycle = "accumulation"
            phase = "E (上升趋势)"
            phase_detail = "已脱离吸筹区,趋势性上升中"
            confidence = "高"
        elif mid_trend == "下跌":
            cycle = "distribution"
            phase = "D (SOW 下跌)"
            phase_detail = "Sign of Weakness,从顶部回落"
            confidence = "中"
        else:
            cycle = "unclear"
            phase = "中位震荡"
            phase_detail = "无明确方向"
            confidence = "低"
    elif 60 <= pos < 85:
        if mid_trend == "上升" and long_trend == "上升":
            cycle = "accumulation"
            phase = "E (强势上升)"
            phase_detail = "趋势性上升,但已接近高位"
            confidence = "中"
        elif has_utad:
            cycle = "distribution"
            phase = "C (UTAD)"
            phase_detail = f"刚出现 UTAD 假突破 ({utad_high:.2f}),警惕顶部反转"
            confidence = "高"
        elif mid_trend == "下跌":
            cycle = "distribution"
            phase = "D (SOW 下跌)"
            phase_detail = "顶部派发后下跌中"
            confidence = "高"
        else:
            cycle = "distribution"
            phase = "B (派发震荡)"
            phase_detail = "高位震荡,可能在派发"
            confidence = "中"
    else:  # pos >= 85
        cycle = "distribution"
        if has_utad:
            phase = "C (UTAD)"
            phase_detail = f"高位假突破 ({utad_high:.2f}),典型派发顶部"
            confidence = "高"
        elif up_dn_ratio < 0.9 or obv_change_60 < 0:
            phase = "A->B (派发开始)"
            phase_detail = "高位放量但 OBV 走弱,初步派发信号"
            confidence = "中"
        else:
            phase = "趋势顶部"
            phase_detail = "持续上涨但已极度高位"
            confidence = "中"

    # 操作建议
    action = ""
    first_batch_pct = 0
    second_trigger = None
    second_trigger_desc = ""
    stop_loss = None

    if "C (Spring)" in phase:
        action = "✅ 强烈建仓"
        first_batch_pct = 60
        second_trigger = last * 1.05
        second_trigger_desc = f"突破 {second_trigger:.2f}(+5%) 加仓"
        stop_loss = spring_low * 0.97 if spring_low else last * 0.93
    elif "C->D" in phase or "D (SOS" in phase:
        action = "✅ 趋势确认建仓"
        first_batch_pct = 70
        second_trigger = last * 1.03
        second_trigger_desc = f"突破 {second_trigger:.2f}(+3%) 加仓"
        stop_loss = last_ma60 * 0.97
    elif "B (吸筹" in phase:
        action = "🟡 小仓位试探"
        first_batch_pct = 30
        last20_low = float(last20["Low"].min())
        last20_high = float(last20["High"].max())
        second_trigger = last20_high * 1.02
        second_trigger_desc = f"突破 {second_trigger:.2f} 加 / 回踩 {last20_low:.2f} 不破再加"
        stop_loss = last20_low * 0.93
    elif "A (止跌)" in phase or "A/B" in phase or "A->B (筑底)" in phase:
        action = "⚠️ 暂不建仓"
        first_batch_pct = 15
        last30_high = float(df.tail(30)["High"].max())
        second_trigger = last30_high * 1.03
        second_trigger_desc = f"等待突破 {second_trigger:.2f}(确认 SOS)再建主仓"
        stop_loss = last * 0.92
    elif "E (" in phase and "上升" in phase:
        action = "🟢 已在趋势中"
        first_batch_pct = 40
        second_trigger = last_ma20
        second_trigger_desc = f"回踩 MA20 {second_trigger:.2f} 不破加仓"
        stop_loss = last_ma60 * 0.95
    elif "C (UTAD)" in phase:
        action = "🚫 不建仓 (顶部派发)"
        first_batch_pct = 0
        second_trigger = last * 0.85
        second_trigger_desc = f"等待跌至 {second_trigger:.2f}(-15%) 再考虑"
        stop_loss = None
    elif "D (SOW" in phase:
        action = "🚫 不建仓 (派发下跌中)"
        first_batch_pct = 0
        second_trigger = last_ma200
        second_trigger_desc = f"等待跌至 MA200 {second_trigger:.2f} 附近企稳"
        stop_loss = None
    elif "B (派发" in phase or "A->B (派发" in phase or "趋势顶部" in phase:
        action = "🚫 不建仓 (高位风险)"
        first_batch_pct = 0
        second_trigger = last * 0.80
        second_trigger_desc = f"等待回调至 {second_trigger:.2f}(-20%) 再评估"
        stop_loss = None
    else:
        action = "⚪ 观望"
        first_batch_pct = 20
        second_trigger = None
        second_trigger_desc = "无明确方向"
        stop_loss = last * 0.92

    return {
        "symbol": symbol,
        "name": name or symbol,
        "price": round(last, 2),
        "pos_pct": round(pos, 1),
        "ma20": round(last_ma20, 2),
        "ma60": round(last_ma60, 2),
        "ma200": round(last_ma200, 2),
        "long_trend": long_trend,
        "mid_trend": mid_trend,
        "ma60_slope_pct": round(ma60_slope, 2),
        "range_ratio": round(range_ratio, 2),
        "obv_change_60": round(obv_change_60, 3),
        "up_dn_vol_ratio": round(up_dn_ratio, 2),
        "has_spring": has_spring,
        "spring_low": round(spring_low, 2) if spring_low else None,
        "has_utad": has_utad,
        "utad_high": round(utad_high, 2) if utad_high else None,
        "cycle": cycle,
        "phase": phase,
        "phase_detail": phase_detail,
        "confidence": confidence,
        "action": action,
        "first_batch_pct": first_batch_pct,
        "second_trigger": round(second_trigger, 2) if second_trigger else None,
        "second_trigger_desc": second_trigger_desc,
        "stop_loss": round(stop_loss, 2) if stop_loss else None,
    }


TARGETS = [
    ("NRG",       "NRG Energy"),
    ("VST",       "Vistra (核电+数据中心)"),
    ("SMR",       "NuScale Power"),
    ("STEM",      "Stem Inc (AI 储能)"),
    ("EXE",       "Expand Energy"),
    ("CEG",       "Constellation Energy"),
    ("PEG",       "Public Service"),
    ("OKLO",      "Oklo (微反应堆)"),
    ("603160.SS", "汇顶科技"),
    ("002230.SZ", "科大讯飞"),
    ("603690.SS", "至纯科技"),
    ("603893.SS", "瑞芯微"),
]


def main():
    results = []
    print(f"分析 {len(TARGETS)} 只股票的 Wyckoff 阶段...")
    for i, (sym, name) in enumerate(TARGETS, 1):
        print(f"  [{i}/{len(TARGETS)}] {sym} {name}", end=" ... ", flush=True)
        try:
            r = analyze_wyckoff(sym, name)
            if r:
                results.append(r)
                print(f"{r['phase']} | {r['action'][:20]}")
            else:
                print("✗ 数据不足")
        except Exception as e:
            print(f"✗ {e}")

    print(f"\n{'='*120}")
    print(f"{'代码':<11}{'名称':<25}{'价格':>8}{'位置%':>7}  {'阶段':<22}{'行动':<22}{'第二批':<25}{'止损':>9}")
    print(f"{'='*120}")
    for r in results:
        print(f"{r['symbol']:<11}{r['name'][:23]:<25}{r['price']:>8.2f}{r['pos_pct']:>6.1f}%  "
              f"{r['phase'][:20]:<22}{r['action'][:20]:<22}"
              f"{(r['second_trigger_desc'] or '')[:25]:<25}"
              f"{str(r['stop_loss']) if r['stop_loss'] else '—':>9}")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    out_csv = os.path.join(base_dir, "wyckoff_results.csv")
    pd.DataFrame(results).to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"\n💾 数据保存: {out_csv}")
    return results


if __name__ == "__main__":
    main()
