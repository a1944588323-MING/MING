"""
通用主题扫描器
用法:
  python theme_screener.py ai          # A 股 AI 概念股 (50+ 只)
  python theme_screener.py hk_ai       # 港股 AI 概念股
  python theme_screener.py energy      # 新能源
  python theme_screener.py liquor      # 白酒
  python theme_screener.py pharma      # 医药
  python theme_screener.py military    # 军工
  python theme_screener.py solar       # 光伏
  python theme_screener.py all         # 全部主题串行扫描

每个主题输出独立的 CSV: theme_<key>_results.csv
"""
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from screener import analyze
from pools import POOLS, get_pool_flat
import pandas as pd


def scan_pool(pool_key: str):
    if pool_key not in POOLS:
        print(f"未知主题: {pool_key}\n可选: {', '.join(POOLS.keys())}")
        return None

    title, pool_dict = POOLS[pool_key]
    flat = get_pool_flat(pool_dict)
    print(f"\n{'='*100}")
    print(f"扫描主题: {title}  ({len(flat)} 只)")
    print(f"{'='*100}")

    results = []
    for i, (code, name, theme) in enumerate(flat, 1):
        print(f"  [{i}/{len(flat)}] {code:<12} {name:<10}", end=" ... ", flush=True)
        try:
            r = analyze(code)
        except Exception as e:
            print(f"✗ 失败: {e}")
            continue
        if r:
            r["name"] = name
            r["theme"] = theme
            results.append(r)
            tag = "🔥" if r["score"] >= 5 else "✅" if r["score"] >= 4 else "➖" if r["score"] >= 3 else "⚠️" if r["score"] >= 2 else "🚫"
            print(f"{tag} {r['rating']:>3}  位置 {r['position_pct']:>5.1f}%  RSI {r['rsi']:>4.1f}")
        else:
            print("✗ 跳过(数据不足)")
        time.sleep(0.05)

    if not results:
        print("\n没有可分析的股票")
        return None

    df = pd.DataFrame(results).sort_values("score", ascending=False).reset_index(drop=True)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"theme_{pool_key}_results.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")

    # 报告
    print(f"\n{'─'*100}")
    print(f"📊 {title} 操作建议分组")
    print(f"{'─'*100}")
    groups = [
        ("🔥 抄底机会 (位置 < 20%)", lambda r: r["score"] >= 5),
        ("✅ 多单网格区 (位置 20-50%)", lambda r: r["score"] == 4),
        ("➖ 中位震荡",                lambda r: r["score"] == 3),
        ("⚠️ 偏高 谨慎",              lambda r: r["score"] == 2),
        ("🚫 高位禁多 (位置 > 80%)",  lambda r: r["score"] <= 1),
    ]
    for grp_name, cond in groups:
        sub = [r for r in results if cond(r)]
        if not sub:
            continue
        print(f"\n  {grp_name}:")
        for r in sub:
            print(f"     {r['symbol']:<11} {r['name']:<8} ({r['theme']:<14})  "
                  f"价 {r['price']:>9.2f}  位置 {r['position_pct']:>5.1f}%  RSI {r['rsi']:>4.1f}  评级 {r['rating']}")

    print(f"\n💾 完整数据: {out}")
    return df


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n可选主题:")
        for k, (title, _) in POOLS.items():
            n = len(get_pool_flat(_))
            print(f"  {k:<10} - {title} ({n} 只)")
        return

    target = sys.argv[1].lower()
    if target == "all":
        for k in POOLS.keys():
            scan_pool(k)
    else:
        scan_pool(target)


if __name__ == "__main__":
    main()
