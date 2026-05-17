"""
A 股做 T 实战日志生成器
运行: python AStock_T_Trading_Log_Template.py
输出: A股做T日志.xlsx
"""
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime, timedelta

wb = openpyxl.Workbook()
wb.remove(wb.active)

# 样式
header_fill = PatternFill("solid", fgColor="1F4E78")
header_font = Font(bold=True, color="FFFFFF", size=11)
center = Alignment(horizontal="center", vertical="center")
border = Border(*[Side(style="thin", color="888888")]*4)
green_fill = PatternFill("solid", fgColor="C6EFCE")
red_fill = PatternFill("solid", fgColor="FFC7CE")
yellow_fill = PatternFill("solid", fgColor="FFEB9C")

# ===== Sheet 1: 操作纪律 =====
ws1 = wb.create_sheet("① 操作纪律")
ws1.column_dimensions['A'].width = 30
ws1.column_dimensions['B'].width = 50

ws1['A1'] = "A股做T 铁律 (每天必看)"
ws1['A1'].font = Font(bold=True, size=14, color="1F4E78")
ws1.merge_cells('A1:B1')

rules = [
    ("✅ 选股标准", "1只标的(东方财富/同花顺/比亚迪) | 振幅>3% | 成交>5亿"),
    ("✅ 资金分配", "底仓 70% ($7000) | 机动 30% ($3000)"),
    ("✅ 单笔止损", "-1% ($100) - 触发立即砍仓,不能拖"),
    ("✅ 单日止损", "-3% ($300) - 当天关电脑去散步"),
    ("✅ 单周止损", "-8% ($800) - 暂停 1 周复盘"),
    ("✅ 月度目标", "+6-10% (日均 +0.4% 复利)"),
    ("⚠️ 黄金时段", "10:00-10:30 (首攻) | 14:00-14:30 (二攻) | 14:50 必须建回底仓"),
    ("⚠️ 禁忌1", "❌ 不追涨 (前 15 分钟假动作多)"),
    ("⚠️ 禁忌2", "❌ 不杠杆 (融资融券先放下)"),
    ("⚠️ 禁忌3", "❌ 不听消息 (听消息=接盘)"),
    ("⚠️ 禁忌4", "❌ 不切换股票 (1只做透,频繁切=亏手续费)"),
    ("⚠️ 禁忌5", "❌ 跌破止损不砍仓 (死扛=爆仓预备)"),
]

for i, (k, v) in enumerate(rules, start=3):
    ws1[f'A{i}'] = k
    ws1[f'A{i}'].font = Font(bold=True)
    ws1[f'A{i}'].fill = yellow_fill
    ws1[f'B{i}'] = v
    ws1[f'A{i}'].alignment = center
    ws1[f'A{i}'].border = border
    ws1[f'B{i}'].border = border

# ===== Sheet 2: 选股清单 =====
ws2 = wb.create_sheet("② 选股清单")
headers2 = ["股票代码", "股票名称", "行业", "现价", "振幅%", "成交额(亿)", "推荐度", "备注"]
for c, h in enumerate(headers2, 1):
    cell = ws2.cell(1, c, h)
    cell.fill = header_fill
    cell.font = header_font
    cell.alignment = center

stocks = [
    ("300059", "东方财富", "券商", 14.50, 4.2, 35.0, "⭐⭐⭐⭐⭐", "做T最佳标的,流动性强"),
    ("300033", "同花顺", "券商", 78.00, 5.5, 20.0, "⭐⭐⭐⭐", "高价股,1万买不多"),
    ("002594", "比亚迪", "新能源", 250.00, 3.5, 50.0, "⭐⭐⭐⭐", "适合波段+T"),
    ("300750", "宁德时代", "新能源", 220.00, 3.8, 45.0, "⭐⭐⭐⭐", "白马股稳定"),
    ("002230", "科大讯飞", "AI", 45.00, 5.0, 28.0, "⭐⭐⭐⭐", "AI热点波动大"),
    ("002475", "立讯精密", "电子", 35.00, 4.0, 30.0, "⭐⭐⭐", "苹果产业链"),
    ("000725", "京东方A", "面板", 4.20, 3.0, 25.0, "⭐⭐", "低价股慎用"),
    ("600519", "贵州茅台", "白酒", 1500, 1.5, 80.0, "❌", "振幅小不适合做T"),
]

for r, s in enumerate(stocks, start=2):
    for c, v in enumerate(s, 1):
        cell = ws2.cell(r, c, v)
        cell.alignment = center
        cell.border = border
        if "⭐⭐⭐⭐⭐" in str(v):
            cell.fill = green_fill
        elif "❌" in str(v):
            cell.fill = red_fill

for col, w in enumerate([10, 12, 8, 10, 10, 12, 12, 30], 1):
    ws2.column_dimensions[get_column_letter(col)].width = w

# ===== Sheet 3: 日交易日志 =====
ws3 = wb.create_sheet("③ 日交易日志")
headers3 = ["日期", "股票", "时间", "方向", "买/卖", "价格", "数量", "金额", "盈亏", "盈亏%", "理由", "复盘"]
for c, h in enumerate(headers3, 1):
    cell = ws3.cell(1, c, h)
    cell.fill = header_fill
    cell.font = header_font
    cell.alignment = center

example = [
    ("2026/05/17", "300059", "10:05", "做T", "卖出", 15.30, 500, 7650.00, 0, 0, "盘中拉升+2%, 触及短线压力", ""),
    ("2026/05/17", "300059", "10:25", "做T", "买入", 15.05, 508, 7645.40, 0, 0, "回踩到 5 日线,放量企稳", ""),
    ("2026/05/17", "300059", "14:32", "做T", "卖出", 15.25, 508, 7747.00, 0, 0, "尾盘第二次拉升", ""),
    ("2026/05/17", "300059", "14:52", "做T", "买入", 15.10, 513, 7746.30, 273.40, "+2.7%", "尾盘建回底仓", "✅ 完美 T"),
]

for r, e in enumerate(example, start=2):
    for c, v in enumerate(e, 1):
        cell = ws3.cell(r, c, v)
        cell.alignment = center
        cell.border = border

# 留 100 行模板
for r in range(6, 106):
    for c in range(1, 13):
        cell = ws3.cell(r, c, "")
        cell.border = border

for col, w in enumerate([12, 10, 8, 8, 8, 10, 8, 12, 10, 10, 30, 25], 1):
    ws3.column_dimensions[get_column_letter(col)].width = w

# ===== Sheet 4: 月度统计 =====
ws4 = wb.create_sheet("④ 月度统计")
headers4 = ["月份", "交易次数", "盈利次数", "亏损次数", "胜率", "总盈亏", "月收益率", "月初资金", "月末资金", "最大回撤", "评价"]
for c, h in enumerate(headers4, 1):
    cell = ws4.cell(1, c, h)
    cell.fill = header_fill
    cell.font = header_font
    cell.alignment = center

months = [
    ("2026-05", 22, 14, 8, "63.6%", 670, "+6.7%", 10000, 10670, "1.2%", "✅ 达标"),
    ("2026-06", "", "", "", "", "", "", "", "", "", ""),
    ("2026-07", "", "", "", "", "", "", "", "", "", ""),
    ("2026-08", "", "", "", "", "", "", "", "", "", ""),
    ("2026-09", "", "", "", "", "", "", "", "", "", ""),
    ("2026-10", "", "", "", "", "", "", "", "", "", ""),
    ("2026-11", "", "", "", "", "", "", "", "", "", ""),
    ("2026-12", "", "", "", "", "", "", "", "", "", ""),
    ("2027-01", "", "", "", "", "", "", "", "", "", ""),
    ("2027-02", "", "", "", "", "", "", "", "", "", ""),
    ("2027-03", "", "", "", "", "", "", "", "", "", ""),
    ("2027-04", "", "", "", "", "", "", "", "", "", ""),
]
for r, m in enumerate(months, start=2):
    for c, v in enumerate(m, 1):
        cell = ws4.cell(r, c, v)
        cell.alignment = center
        cell.border = border

for col, w in enumerate([12, 10, 10, 10, 10, 12, 12, 12, 12, 12, 15], 1):
    ws4.column_dimensions[get_column_letter(col)].width = w

# ===== Sheet 5: 复利计算器 =====
ws5 = wb.create_sheet("⑤ 复利计算器")
ws5.column_dimensions['A'].width = 18
ws5.column_dimensions['B'].width = 15

ws5['A1'] = "1万本金复利展示"
ws5['A1'].font = Font(bold=True, size=14, color="1F4E78")
ws5.merge_cells('A1:E1')

ws5['A3'] = "本金"
ws5['B3'] = 10000
ws5['B3'].fill = yellow_fill
ws5['A4'] = "日收益目标%"
ws5['B4'] = 0.4
ws5['B4'].fill = yellow_fill

scenarios = [
    ("天数", "保守 (0.2%/日)", "标准 (0.4%/日)", "激进 (0.6%/日)", "顶级 (0.8%/日)"),
    (1, 10020, 10040, 10060, 10080),
    (5, 10100, 10202, 10304, 10408),
    (10, 10202, 10408, 10619, 10833),
    (20, 10408, 10832, 11272, 11729),
    (30, 10618, 11272, 11966, 12704),
    (60, 11271, 12707, 14318, 16139),
    (90, 11969, 14323, 17128, 20492),
    (120, 12708, 16140, 20488, 26023),
    (180, 14318, 20549, 29378, 41972),
    (250, 16484, 26985, 44378, 72954),
]

for r, row in enumerate(scenarios, start=6):
    for c, v in enumerate(row, 1):
        cell = ws5.cell(r, c, v)
        cell.alignment = center
        cell.border = border
        if r == 6:
            cell.fill = header_fill
            cell.font = header_font
        elif r == 16:
            cell.fill = green_fill
            cell.font = Font(bold=True)

for col in range(1, 6):
    ws5.column_dimensions[get_column_letter(col)].width = 18

ws5['A18'] = "📊 结论:"
ws5['A18'].font = Font(bold=True, size=12)
ws5['A19'] = "日均 +0.4% (40元), 一年 (250 交易日) 复利后 = $26,985 (+170%)"
ws5['A20'] = "日均 +0.6% (60元), 一年复利后 = $44,378 (+343%)"
ws5['A21'] = "⚠️ 现实: 95% 散户做不到日均 +0.4%, 因为情绪化交易"

wb.save("/projects/sandbox/MING/A股做T日志.xlsx")
print("✅ A股做T日志.xlsx 已生成")
print("包含 5 个 Sheet:")
print("  ①操作纪律  ②选股清单  ③日交易日志  ④月度统计  ⑤复利计算器")
