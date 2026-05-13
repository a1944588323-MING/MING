"""
把 portfolio_alloc 的结果做成可视化 Excel
- 美股 / A 股 分两个 sheet
- 资金分配饼图、综合评分柱状图
- 条件格式: 数据条 + 颜色梯度 + 图标
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import (Font, PatternFill, Alignment, Border, Side, NamedStyle)
from openpyxl.formatting.rule import (DataBarRule, ColorScaleRule, CellIsRule, FormulaRule)
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, PieChart, Reference, BarChart3D
from openpyxl.chart.label import DataLabelList

from portfolio_alloc import analyze_one, composite_score, fmt_market_cap

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ============ 样式 ============
THIN_BORDER = Border(
    left=Side(style='thin', color='D0D0D0'),
    right=Side(style='thin', color='D0D0D0'),
    top=Side(style='thin', color='D0D0D0'),
    bottom=Side(style='thin', color='D0D0D0'),
)

HEADER_FILL = PatternFill(start_color='1F4E78', end_color='1F4E78', fill_type='solid')
HEADER_FONT = Font(name='微软雅黑', size=11, color='FFFFFF', bold=True)
TITLE_FONT  = Font(name='微软雅黑', size=14, color='1F4E78', bold=True)
SUBTITLE_FONT = Font(name='微软雅黑', size=10, color='808080', italic=True)
CENTER = Alignment(horizontal='center', vertical='center', wrap_text=True)
LEFT   = Alignment(horizontal='left',   vertical='center')
RIGHT  = Alignment(horizontal='right',  vertical='center')


def fetch_data():
    us = ["NRG", "VST", "SMR", "STEM", "EXE", "CEG", "PEG", "OKLO"]
    cn = ["603160.SS", "002230.SZ", "603690.SS", "603893.SS"]
    print("拉取美股数据...")
    us_data = []
    for i, s in enumerate(us, 1):
        print(f"  [{i}/{len(us)}] {s}")
        r = analyze_one(s)
        if r:
            r["composite_score"] = composite_score(r)
            us_data.append(r)
    print("拉取 A 股数据...")
    cn_data = []
    for i, s in enumerate(cn, 1):
        print(f"  [{i}/{len(cn)}] {s}")
        r = analyze_one(s)
        if r:
            r["composite_score"] = composite_score(r)
            cn_data.append(r)
    return us_data, cn_data


def calc_allocations(rows):
    scored = sorted(rows, key=lambda r: -r["composite_score"])
    total = sum(r["composite_score"] for r in scored) or 1
    n = len(scored)
    max_pct = 0.25 if n >= 5 else 0.40
    raw = [r["composite_score"]/total for r in scored]
    capped, overflow = [], 0
    for p in raw:
        if p > max_pct:
            overflow += (p - max_pct); capped.append(max_pct)
        else:
            capped.append(p)
    if overflow > 0:
        room = sum(max_pct - c for c in capped)
        if room > 0:
            capped = [c + (max_pct - c)/room*overflow if c < max_pct else c for c in capped]
    capped = [max(p, 0.05) for p in capped]
    s = sum(capped)
    final = [p/s for p in capped]
    for r, pct in zip(scored, final):
        r["alloc_pct"] = pct
    return scored


def write_overview_sheet(wb, us, cn):
    ws = wb.create_sheet("📊 总览", 0)
    ws.column_dimensions['A'].width = 22
    ws.column_dimensions['B'].width = 30

    ws['A1'] = "📊 资金分配 - 总览"
    ws['A1'].font = Font(name='微软雅黑', size=18, color='1F4E78', bold=True)
    ws.merge_cells('A1:E1')

    ws['A2'] = "数据来源: yfinance | 平均筹码代理: 60d VWAP | 主力推断: OBV+CMF+涨跌量比"
    ws['A2'].font = SUBTITLE_FONT
    ws.merge_cells('A2:E2')

    ws['A4'] = "组合"; ws['B4'] = "股票数"; ws['C4'] = "总分"; ws['D4'] = "首选(评分最高)"; ws['E4'] = "投机仓(评分最低)"
    for cell in ws[4]:
        cell.font = HEADER_FONT; cell.fill = HEADER_FILL; cell.alignment = CENTER

    us_top = max(us, key=lambda r: r["composite_score"])
    us_low = min(us, key=lambda r: r["composite_score"])
    cn_top = max(cn, key=lambda r: r["composite_score"])
    cn_low = min(cn, key=lambda r: r["composite_score"])

    ws['A5'] = "🇺🇸 美股 AI 能源"
    ws['B5'] = len(us)
    ws['C5'] = sum(r["composite_score"] for r in us)
    ws['D5'] = f"{us_top['symbol']} ({us_top['composite_score']:.0f}分)"
    ws['E5'] = f"{us_low['symbol']} ({us_low['composite_score']:.0f}分)"

    ws['A6'] = "🇨🇳 A 股 存储/AI"
    ws['B6'] = len(cn)
    ws['C6'] = sum(r["composite_score"] for r in cn)
    ws['D6'] = f"{cn_top['symbol']} ({cn_top['composite_score']:.0f}分)"
    ws['E6'] = f"{cn_low['symbol']} ({cn_low['composite_score']:.0f}分)"

    for row in ws.iter_rows(min_row=5, max_row=6, max_col=5):
        for cell in row:
            cell.alignment = LEFT
            cell.font = Font(name='微软雅黑', size=11)
            cell.border = THIN_BORDER

    # 颜色区分
    ws['A5'].fill = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')
    ws['A6'].fill = PatternFill(start_color='FFEB9C', end_color='FFEB9C', fill_type='solid')

    # 评分逻辑说明
    ws['A8'] = "📋 评分维度说明"
    ws['A8'].font = TITLE_FONT
    ws.merge_cells('A8:E8')

    explanation = [
        ("位置 % (52周区间)", "<10% +30 分,<20% +25 分,<30% +18 分,>80% 0 分"),
        ("RSI 摆动", "<25 +15 分,<35 +10 分,>70 -10 分"),
        ("PE (TTM)", "<15 +15 分,<25 +10 分,>50 -5 分,>80 -10 分"),
        ("营收增长 YoY", ">30% +15 分,>15% +10 分,<-10% -10 分"),
        ("利润率", ">20% +10 分,<-5% -10 分"),
        ("ROE", ">20% +10 分,>10% +5 分,<0 -5 分"),
        ("主力资金信号", "建仓 +10 分,净流入 +5 分,派发 -10 分"),
        ("市值规避微盘", "<10亿 -5 分,>500亿 +3 分"),
    ]
    for i, (k, v) in enumerate(explanation, 9):
        ws.cell(row=i, column=1, value=k).font = Font(name='微软雅黑', size=10, bold=True)
        ws.cell(row=i, column=2, value=v).font = Font(name='微软雅黑', size=10)
        ws.merge_cells(start_row=i, start_column=2, end_row=i, end_column=5)

    # 重要说明
    note_row = 9 + len(explanation) + 1
    ws.cell(row=note_row, column=1, value="⚠️ 重要说明").font = TITLE_FONT
    ws.merge_cells(start_row=note_row, start_column=1, end_row=note_row, end_column=5)

    notes = [
        "1. 平均筹码价格 用 60 日 VWAP(成交量加权均价)代理 — 严格的'持仓成本'需要 Tick 数据,本表近似",
        "2. 主力资金/庄家建仓 用 OBV+CMF+涨跌量比 推断 — 准确判断需要 L2 主力净流入数据",
        "3. 本报告为按规则的资金分配,不构成任何投资建议。投资决策请结合基本面、行业景气度自行判断",
        "4. 风险提示: 单笔仓位 ≥ 5%, ≤ 25%(4只组合 ≤ 40%);跌破 52W 低 5% 强制止损",
    ]
    for i, n in enumerate(notes, note_row+1):
        c = ws.cell(row=i, column=1, value=n)
        c.font = Font(name='微软雅黑', size=10, color='C00000')
        ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=5)


def write_market_sheet(wb, rows, sheet_name, market_label, total_capital, currency):
    ws = wb.create_sheet(sheet_name)

    # 列宽
    widths = [9, 28, 11, 11, 9, 11, 9, 9, 11, 9, 11, 9, 9, 12, 13, 24]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # 标题
    ws['A1'] = f"💰 {market_label} 资金分配方案"
    ws['A1'].font = TITLE_FONT
    ws.merge_cells('A1:P1')
    ws['A2'] = f"总资金 {currency}{total_capital:,} | 数据时间: 实时(yfinance)"
    ws['A2'].font = SUBTITLE_FONT
    ws.merge_cells('A2:P2')

    # 表头
    headers = ["代码", "名称", "综合分", "分配 %", "分配金额", "估算手数",
               "市值", "PE", "营收增长", "利润率", "ROE", "位置 %", "RSI",
               "60d VWAP", "当前/VWAP", "主力推断"]
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=4, column=i, value=h)
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.alignment = CENTER
        c.border = THIN_BORDER

    # 数据
    for ri, r in enumerate(rows, 5):
        amt = total_capital * r["alloc_pct"]
        shares = int(amt / r["price"]) if r["price"] > 0 else 0
        cells = [
            r["symbol"],
            (r.get("name") or r["symbol"])[:25],
            r["composite_score"],
            r["alloc_pct"],
            amt,
            shares,
            r.get("market_cap"),
            r.get("pe_ttm"),
            r.get("rev_growth"),
            r.get("profit_margin"),
            r.get("roe"),
            r.get("position_pct"),
            r.get("rsi"),
            r.get("vwap_60"),
            (r.get("premium_60vwap") or 0) / 100 if r.get("premium_60vwap") is not None else None,
            r.get("institutional"),
        ]
        for ci, v in enumerate(cells, 1):
            c = ws.cell(row=ri, column=ci, value=v)
            c.border = THIN_BORDER
            c.font = Font(name='微软雅黑', size=10)
            c.alignment = CENTER if ci <= 13 else LEFT

    # 数字格式
    for r in range(5, 5 + len(rows)):
        ws.cell(row=r, column=4).number_format = '0.0%'           # 分配%
        ws.cell(row=r, column=5).number_format = f'"{currency}"#,##0'  # 金额
        ws.cell(row=r, column=7).number_format = '#,##0'          # 市值
        ws.cell(row=r, column=8).number_format = '0.0'            # PE
        ws.cell(row=r, column=9).number_format = '0.0%'           # 营收增长
        ws.cell(row=r, column=10).number_format = '0.0%'          # 利润率
        ws.cell(row=r, column=11).number_format = '0.0%'          # ROE
        ws.cell(row=r, column=12).number_format = '0.0"%"'         # 位置
        ws.cell(row=r, column=13).number_format = '0.0'           # RSI
        ws.cell(row=r, column=14).number_format = '0.00'          # VWAP
        ws.cell(row=r, column=15).number_format = '+0.0%;-0.0%'   # 当前/VWAP

    last_row = 4 + len(rows)

    # ============ 条件格式 ============
    # 综合分 - 颜色梯度(红黄绿)
    ws.conditional_formatting.add(
        f"C5:C{last_row}",
        ColorScaleRule(start_type='num', start_value=0, start_color='F8696B',
                       mid_type='num', mid_value=40, mid_color='FFEB84',
                       end_type='num', end_value=80, end_color='63BE7B')
    )
    # 分配 % - 数据条
    ws.conditional_formatting.add(
        f"D5:D{last_row}",
        DataBarRule(start_type='min', end_type='max', color='5B9BD5')
    )
    # 分配金额 - 数据条
    ws.conditional_formatting.add(
        f"E5:E{last_row}",
        DataBarRule(start_type='min', end_type='max', color='70AD47')
    )
    # 营收增长 - 颜色梯度(<0 红, >0 绿)
    ws.conditional_formatting.add(
        f"I5:I{last_row}",
        ColorScaleRule(start_type='num', start_value=-0.3, start_color='F8696B',
                       mid_type='num', mid_value=0, mid_color='FFFFFF',
                       end_type='num', end_value=0.5, end_color='63BE7B')
    )
    # 利润率
    ws.conditional_formatting.add(
        f"J5:J{last_row}",
        ColorScaleRule(start_type='num', start_value=-0.1, start_color='F8696B',
                       mid_type='num', mid_value=0, mid_color='FFFFFF',
                       end_type='num', end_value=0.3, end_color='63BE7B')
    )
    # ROE
    ws.conditional_formatting.add(
        f"K5:K{last_row}",
        ColorScaleRule(start_type='num', start_value=-0.1, start_color='F8696B',
                       mid_type='num', mid_value=0, mid_color='FFFFFF',
                       end_type='num', end_value=0.3, end_color='63BE7B')
    )
    # 位置 % - 颜色梯度(低位绿,高位红)
    ws.conditional_formatting.add(
        f"L5:L{last_row}",
        ColorScaleRule(start_type='num', start_value=0, start_color='63BE7B',
                       mid_type='num', mid_value=50, mid_color='FFEB84',
                       end_type='num', end_value=100, end_color='F8696B')
    )
    # RSI - 双向颜色
    ws.conditional_formatting.add(
        f"M5:M{last_row}",
        ColorScaleRule(start_type='num', start_value=20, start_color='63BE7B',
                       mid_type='num', mid_value=50, mid_color='FFFFFF',
                       end_type='num', end_value=80, end_color='F8696B')
    )
    # 当前/VWAP - 双向颜色
    ws.conditional_formatting.add(
        f"O5:O{last_row}",
        ColorScaleRule(start_type='num', start_value=-0.2, start_color='63BE7B',
                       mid_type='num', mid_value=0, mid_color='FFFFFF',
                       end_type='num', end_value=0.2, end_color='F8696B')
    )
    # 主力派发 - 整行红色
    ws.conditional_formatting.add(
        f"P5:P{last_row}",
        FormulaRule(formula=[f'ISNUMBER(SEARCH("派发",P5))'],
                    fill=PatternFill(start_color='FFE6E6', end_color='FFE6E6', fill_type='solid'))
    )
    ws.conditional_formatting.add(
        f"P5:P{last_row}",
        FormulaRule(formula=[f'ISNUMBER(SEARCH("建仓",P5))'],
                    fill=PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid'))
    )
    ws.conditional_formatting.add(
        f"P5:P{last_row}",
        FormulaRule(formula=[f'ISNUMBER(SEARCH("流入",P5))'],
                    fill=PatternFill(start_color='E2EFDA', end_color='E2EFDA', fill_type='solid'))
    )

    # ============ 总计行 ============
    total_row = last_row + 2
    ws.cell(row=total_row, column=1, value="💰 总计").font = Font(name='微软雅黑', size=11, bold=True, color='FFFFFF')
    ws.cell(row=total_row, column=1).fill = HEADER_FILL
    ws.cell(row=total_row, column=4, value=f"=SUM(D5:D{last_row})").number_format = '0.0%'
    ws.cell(row=total_row, column=5, value=f"=SUM(E5:E{last_row})").number_format = f'"{currency}"#,##0'
    for c in range(1, 17):
        cell = ws.cell(row=total_row, column=c)
        cell.font = Font(name='微软雅黑', size=11, bold=True)
        cell.fill = PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')
        cell.border = THIN_BORDER
        cell.alignment = CENTER

    # ============ 资金分配饼图 ============
    pie = PieChart()
    pie.title = f"{market_label} - 资金分配比例"
    labels = Reference(ws, min_col=1, min_row=5, max_row=last_row)
    data   = Reference(ws, min_col=4, min_row=4, max_row=last_row)
    pie.add_data(data, titles_from_data=True)
    pie.set_categories(labels)
    pie.height = 11
    pie.width = 16
    pie.dataLabels = DataLabelList(showPercent=True, showCatName=True)
    ws.add_chart(pie, f"R4")

    # ============ 综合分柱状图 ============
    bar = BarChart()
    bar.type = "bar"
    bar.style = 11
    bar.title = "综合评分排序"
    bar.y_axis.title = '股票'
    bar.x_axis.title = '综合分'
    cat = Reference(ws, min_col=1, min_row=5, max_row=last_row)
    val = Reference(ws, min_col=3, min_row=4, max_row=last_row)
    bar.add_data(val, titles_from_data=True)
    bar.set_categories(cat)
    bar.height = 11
    bar.width = 16
    bar.dataLabels = DataLabelList(showVal=True)
    ws.add_chart(bar, f"R26")

    # 冻结表头
    ws.freeze_panes = "A5"


def write_signals_sheet(wb, all_data):
    ws = wb.create_sheet("⚡ 信号汇总")
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 28
    ws.column_dimensions['C'].width = 12
    ws.column_dimensions['D'].width = 30
    ws.column_dimensions['E'].width = 22
    ws.column_dimensions['F'].width = 30

    ws['A1'] = "⚡ 主力资金信号 + 筹码状态"
    ws['A1'].font = TITLE_FONT
    ws.merge_cells('A1:F1')

    headers = ["代码", "名称", "市场", "筹码状态", "主力推断", "操作建议"]
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=3, column=i, value=h)
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.alignment = CENTER
        c.border = THIN_BORDER

    advice_map = {
        "建仓": "🟢 优先关注 - 主力疑似进场,可适度增加首笔仓位",
        "流入": "🟢 资金温和买入 - 可正常配置",
        "派发": "🔴 警惕! 首笔不超过分配额 30%,等回调",
        "异常放量": "🟡 突破存疑,等下根 K 确认",
        "中性": "⚪ 量价无明显方向,按计划执行",
    }
    def get_advice(text):
        for k, v in advice_map.items():
            if k in (text or ""):
                return v
        return "⚪ 按计划执行"

    ri = 4
    for market, rows in all_data:
        for r in rows:
            cells = [r["symbol"], (r.get("name") or "")[:25], market,
                     r.get("chip_status", ""), r.get("institutional", ""),
                     get_advice(r.get("institutional", ""))]
            for ci, v in enumerate(cells, 1):
                c = ws.cell(row=ri, column=ci, value=v)
                c.border = THIN_BORDER
                c.font = Font(name='微软雅黑', size=10)
                c.alignment = LEFT
            ri += 1

    last = ri - 1

    # 主力派发整行高亮
    ws.conditional_formatting.add(
        f"A4:F{last}",
        FormulaRule(formula=[f'ISNUMBER(SEARCH("派发",$E4))'],
                    fill=PatternFill(start_color='FFE6E6', end_color='FFE6E6', fill_type='solid'))
    )
    ws.conditional_formatting.add(
        f"A4:F{last}",
        FormulaRule(formula=[f'ISNUMBER(SEARCH("建仓",$E4))'],
                    fill=PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid'))
    )
    ws.conditional_formatting.add(
        f"A4:F{last}",
        FormulaRule(formula=[f'ISNUMBER(SEARCH("流入",$E4))'],
                    fill=PatternFill(start_color='E2EFDA', end_color='E2EFDA', fill_type='solid'))
    )
    ws.freeze_panes = "A4"


def main():
    us, cn = fetch_data()

    # 计算分配
    us = calc_allocations(us)
    cn = calc_allocations(cn)

    wb = Workbook()
    # 默认 sheet 删掉
    if 'Sheet' in wb.sheetnames:
        del wb['Sheet']

    write_overview_sheet(wb, us, cn)
    write_market_sheet(wb, us, "🇺🇸 美股 AI 能源", "美股 AI 能源 (8 只)", 100000, "$")
    write_market_sheet(wb, cn, "🇨🇳 A股 存储与AI", "A 股 存储/AI (4 只)", 100000, "¥")
    write_signals_sheet(wb, [("🇺🇸 美股", us), ("🇨🇳 A 股", cn)])

    out = os.path.join(BASE_DIR, "资金分配可视化.xlsx")
    wb.save(out)
    print(f"\n✅ 已生成: {out}")
    print(f"   文件大小: {os.path.getsize(out)/1024:.1f} KB")


if __name__ == "__main__":
    main()
