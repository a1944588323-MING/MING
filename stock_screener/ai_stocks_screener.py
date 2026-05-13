"""
A 股 AI 概念股扫描器
覆盖: 算力服务器 / AI 芯片 / 大模型应用 / 光模块 / 数据中心
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 复用 screener.py 里的 analyze 函数
from screener import analyze, ZONE_THRESHOLD_PCT
import pandas as pd

# ========== A 股 AI 概念股池(分主题) ==========
AI_STOCKS = {
    "算力/服务器": {
        "000977.SZ": "浪潮信息",
        "603019.SS": "中科曙光",
        "000938.SZ": "紫光股份",
        "601138.SS": "工业富联",
        "002230.SZ": "科大讯飞",
    },
    "AI 芯片": {
        "688256.SS": "寒武纪",
        "688041.SS": "海光信息",
        "688047.SS": "龙芯中科",
        "688008.SS": "澜起科技",
        "603501.SS": "韦尔股份",
    },
    "光模块/通信": {
        "300308.SZ": "中际旭创",
        "300502.SZ": "新易盛",
        "300394.SZ": "天孚通信",
        "000988.SZ": "华工科技",
        "603083.SS": "剑桥科技",
    },
    "AI 应用/软件": {
        "300418.SZ": "昆仑万维",
        "601360.SS": "三六零",
        "300624.SZ": "万兴科技",
        "688787.SS": "海天瑞声",
        "300229.SZ": "拓尔思",
        "002362.SZ": "汉王科技",
    },
    "数据中心/IDC": {
        "300442.SZ": "润泽科技",
        "300738.SZ": "奥飞数据",
        "300383.SZ": "光环新网",
        "000536.SZ": "华映科技",
    },
    "代工/精密制造": {
        "002475.SZ": "立讯精密",
        "002241.SZ": "歌尔股份",
    },
}

def main():
    all_codes = []
    code_to_name = {}
    code_to_theme = {}
    for theme, stocks in AI_STOCKS.items():
        for code, name in stocks.items():
            all_codes.append(code)
            code_to_name[code] = name
            code_to_theme[code] = theme

    print(f"扫描 {len(all_codes)} 只 A 股 AI 概念股...\n")

    results = []
    for i, code in enumerate(all_codes, 1):
        name = code_to_name[code]
        theme = code_to_theme[code]
        print(f"  [{i}/{len(all_codes)}] {code} {name}", end=" ... ", flush=True)
        r = analyze(code)
        if r:
            r["name"] = name
            r["theme"] = theme
            results.append(r)
            print(f"{r['rating']} 位置 {r['position_pct']:>5.1f}% RSI {r['rsi']:>4.1f}")
        else:
            print("✗ 跳过(数据不足)")

    if not results:
        print("\n没有可分析的股票")
        return

    df = pd.DataFrame(results).sort_values("score", ascending=False).reset_index(drop=True)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_stocks_results.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")

    print("\n" + "=" * 130)
    print("A 股 AI 概念股扫描结果(按评分排序)")
    print("=" * 130)
    print(f"{'排名':<4} {'代码':<11} {'名称':<10} {'主题':<14} {'当前价':>9} {'52W 区间':>20} {'位置%':>7} {'RSI':>5} {'评级':>4}")
    print("-" * 130)
    for i, r in enumerate(results, 1):
        rng = f"{r['52w_low']:.2f}-{r['52w_high']:.2f}"
        # 中文宽度调整
        name_padded = r['name'] + ' ' * (10 - len(r['name']) * 2 + len(r['name']))
        theme_padded = r['theme'] + ' ' * (14 - len(r['theme']) * 2 + len(r['theme']))
        print(f"{i:<4} {r['symbol']:<11} {name_padded[:10]:<10} {theme_padded[:14]:<14} "
              f"{r['price']:>9.2f} {rng:>20} {r['position_pct']:>6.1f}% {r['rsi']:>5.1f} {r['rating']:>4}")

    # 分组建议
    print("\n" + "=" * 130)
    print("📋 操作建议分组")
    print("=" * 130)
    for grp_name, score_range in [
        ("🔥 抄底机会 (位置 < 20%)",  (5, 99)),
        ("✅ 多单网格区 (位置 20-50%)", (4, 4)),
        ("➖ 中位震荡 (位置 ~50%)",   (3, 3)),
        ("⚠️ 偏高 (位置 50-80%)",     (2, 2)),
        ("🚫 高位禁多 (位置 > 80%)",  (0, 1)),
    ]:
        sub = [r for r in results if score_range[0] <= r["score"] <= score_range[1]]
        if sub:
            print(f"\n  {grp_name}:")
            for r in sub:
                print(f"     {r['symbol']:<11} {r['name']:<8} ({r['theme']:<12}) "
                      f"价 {r['price']:>8.2f}  位置 {r['position_pct']:>5.1f}%  RSI {r['rsi']:>4.1f}")

    print(f"\n完整数据已保存到: ai_stocks_results.csv")

if __name__ == "__main__":
    main()
