"""
每日自动扫描报告
扫描全部主题,生成 Markdown 格式日报,只保留每个主题 TOP 抄底 + 高位预警

用法:
  python daily_report.py                    # 扫描全部主题,输出到 reports/YYYY-MM-DD.md
  python daily_report.py ai energy          # 只扫描指定主题
  python daily_report.py --quiet            # 静默模式(不打印进度)
"""
import sys
import os
import time
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from screener import analyze
from pools import POOLS, get_pool_flat


def scan_for_report(pool_key, quiet=False):
    title, pool_dict = POOLS[pool_key]
    flat = get_pool_flat(pool_dict)
    if not quiet:
        print(f"  [{pool_key}] 扫描 {title} ({len(flat)} 只)...", flush=True)
    results = []
    for code, name, theme in flat:
        try:
            r = analyze(code)
            if r:
                r["name"] = name
                r["theme"] = theme
                results.append(r)
        except Exception:
            continue
        time.sleep(0.05)
    return title, results


def render_section(title, results, top_n=8):
    """渲染单个主题的 Markdown 章节"""
    lines = []
    lines.append(f"## 📊 {title}\n")
    lines.append(f"_共扫描 {len(results)} 只_\n")

    buy_zone = sorted([r for r in results if r["score"] >= 4], key=lambda r: r["position_pct"])[:top_n]
    danger_zone = sorted([r for r in results if r["score"] <= 1], key=lambda r: -r["position_pct"])[:top_n]

    if buy_zone:
        lines.append(f"### 🔥 低位机会 (Top {len(buy_zone)})\n")
        lines.append("| 代码 | 名称 | 主题 | 当前价 | 52W 位置 | RSI | 评级 |")
        lines.append("|---|---|---|---:|---:|---:|:-:|")
        for r in buy_zone:
            lines.append(f"| {r['symbol']} | {r['name']} | {r['theme']} | {r['price']:.2f} | "
                        f"{r['position_pct']:.1f}% | {r['rsi']:.1f} | **{r['rating']}** |")
        lines.append("")

    if danger_zone:
        lines.append(f"### 🚫 高位预警 (Top {len(danger_zone)})\n")
        lines.append("| 代码 | 名称 | 主题 | 当前价 | 52W 位置 | RSI | 评级 |")
        lines.append("|---|---|---|---:|---:|---:|:-:|")
        for r in danger_zone:
            lines.append(f"| {r['symbol']} | {r['name']} | {r['theme']} | {r['price']:.2f} | "
                        f"{r['position_pct']:.1f}% | {r['rsi']:.1f} | {r['rating']} |")
        lines.append("")

    return "\n".join(lines)


def render_summary(all_data):
    """全市场摘要"""
    total = sum(len(r) for _, r in all_data.values())
    total_low = sum(len([x for x in r if x["score"] >= 4]) for _, r in all_data.values())
    total_high = sum(len([x for x in r if x["score"] <= 1]) for _, r in all_data.values())

    lines = [
        "## 📈 全市场摘要\n",
        f"- **共扫描股票**: {total} 只",
        f"- **低位机会**: {total_low} 只 ({total_low/total*100:.1f}%)" if total else "",
        f"- **高位预警**: {total_high} 只 ({total_high/total*100:.1f}%)" if total else "",
        "",
        "### 各主题概览\n",
        "| 主题 | 总数 | 低位 🔥 | 高位 🚫 | 偏度 |",
        "|---|---:|---:|---:|:-:|",
    ]
    for key, (title, results) in all_data.items():
        if not results:
            continue
        n = len(results)
        low = len([r for r in results if r["score"] >= 4])
        high = len([r for r in results if r["score"] <= 1])
        if high > low * 2:
            bias = "🔥 过热"
        elif low > high * 2:
            bias = "💎 冷门"
        else:
            bias = "⚖️ 均衡"
        lines.append(f"| {title} | {n} | {low} | {high} | {bias} |")
    lines.append("")
    return "\n".join(lines)


def render_top_picks(all_data, n=10):
    """跨市场综合 Top N 候选"""
    pool = []
    for _, results in all_data.values():
        pool.extend(results)
    pool.sort(key=lambda r: (-r["score"], r["position_pct"]))
    top = pool[:n]
    lines = [
        f"## 🌟 全市场综合 Top {n} 候选\n",
        "_按综合评分排序,优先低位、超卖、放量_\n",
        "| # | 代码 | 名称 | 主题 | 当前价 | 52W 位置 | RSI | 评级 | 建议 |",
        "|---:|---|---|---|---:|---:|---:|:-:|---|",
    ]
    for i, r in enumerate(top, 1):
        lines.append(f"| {i} | {r['symbol']} | {r['name']} | {r['theme']} | {r['price']:.2f} | "
                    f"{r['position_pct']:.1f}% | {r['rsi']:.1f} | **{r['rating']}** | {r['advice']} |")
    lines.append("")
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    quiet = "--quiet" in args
    args = [a for a in args if not a.startswith("--")]

    targets = args if args else list(POOLS.keys())
    targets = [t for t in targets if t in POOLS]
    if not targets:
        print("没有有效的主题")
        return

    if not quiet:
        print(f"开始扫描 {len(targets)} 个主题: {', '.join(targets)}")
        print(f"时间: {datetime.now():%Y-%m-%d %H:%M:%S}\n")

    all_data = {}
    for key in targets:
        title, results = scan_for_report(key, quiet=quiet)
        all_data[key] = (title, results)

    # 生成报告
    today = datetime.now().strftime("%Y-%m-%d")
    timestr = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md = []
    md.append(f"# 📊 每日股票扫描报告 - {today}\n")
    md.append(f"_生成时间: {timestr}_\n")
    md.append(f"_数据来源: yfinance_\n")
    md.append("---\n")
    md.append(render_summary(all_data))
    md.append("---\n")
    md.append(render_top_picks(all_data, n=15))
    md.append("---\n")
    for key, (title, results) in all_data.items():
        md.append(render_section(title, results))
        md.append("---\n")

    md.append("## ⚠️ 免责声明\n")
    md.append("本报告基于公开历史价格数据自动生成,仅供研究参考,**不构成任何投资建议**。")
    md.append("加密货币与股票均存在重大风险,投资决策请结合基本面、行业面及个人风险承受能力。\n")

    out_text = "\n".join(md)

    # 保存
    reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    out_file = os.path.join(reports_dir, f"{today}.md")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(out_text)

    if not quiet:
        print(f"\n✅ 日报已生成: {out_file}")
        print(f"   总共扫描: {sum(len(r) for _, r in all_data.values())} 只股票")
        print(f"   字符数: {len(out_text):,}")


if __name__ == "__main__":
    main()
