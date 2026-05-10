"""
DCA 持仓计算器 - Excel 生成脚本
生成一个 WPS/Excel 兼容的 xlsx 文件，包含完整公式自动计算
"""
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.worksheet.table import Table, TableStyleInfo

wb = Workbook()
ws = wb.active
ws.title = "DCA持仓计算器"

# ===== 样式定义 =====
thin = Side(border_style="thin", color="888888")
border = Border(left=thin, right=thin, top=thin, bottom=thin)

title_font = Font(name="微软雅黑", size=14, bold=True, color="FFFFFF")
title_fill = PatternFill("solid", fgColor="1F4E78")

header_font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
header_fill = PatternFill("solid", fgColor="2E75B6")

input_font = Font(name="微软雅黑", size=11, bold=True, color="000000")
input_fill = PatternFill("solid", fgColor="FFF2CC")

formula_font = Font(name="微软雅黑", size=11, color="1F4E78")
formula_fill = PatternFill("solid", fgColor="E7F0F9")

summary_font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
summary_fill = PatternFill("solid", fgColor="70AD47")

warn_fill = PatternFill("solid", fgColor="FFE699")

center = Alignment(horizontal="center", vertical="center")

# ===== 第1行 标题 =====
ws.merge_cells("A1:L1")
ws["A1"] = "DCA 动态加仓持仓计算器 （黄色格子填入实际交易）"
ws["A1"].font = title_font
ws["A1"].fill = title_fill
ws["A1"].alignment = center
ws.row_dimensions[1].height = 28

# ===== 第3行 参数设置区 =====
ws["A3"] = "初始本金"
ws["A3"].font = header_font
ws["A3"].fill = header_fill
ws["A3"].alignment = center
ws["A3"].border = border

ws["B3"] = 10000
ws["B3"].font = input_font
ws["B3"].fill = input_fill
ws["B3"].alignment = center
ws["B3"].border = border
ws["B3"].number_format = "$#,##0"

ws["C3"] = "首次买入%"
ws["C3"].font = header_font
ws["C3"].fill = header_fill
ws["C3"].alignment = center
ws["C3"].border = border

ws["D3"] = 0.10
ws["D3"].font = input_font
ws["D3"].fill = input_fill
ws["D3"].alignment = center
ws["D3"].border = border
ws["D3"].number_format = "0.0%"

ws["E3"] = "买入倍率"
ws["E3"].font = header_font
ws["E3"].fill = header_fill
ws["E3"].alignment = center
ws["E3"].border = border

ws["F3"] = 1.0
ws["F3"].font = input_font
ws["F3"].fill = input_fill
ws["F3"].alignment = center
ws["F3"].border = border
ws["F3"].number_format = "0.00"

ws["G3"] = "卖出倍率"
ws["G3"].font = header_font
ws["G3"].fill = header_fill
ws["G3"].alignment = center
ws["G3"].border = border

ws["H3"] = 1.0
ws["H3"].font = input_font
ws["H3"].fill = input_fill
ws["H3"].alignment = center
ws["H3"].border = border
ws["H3"].number_format = "0.00"

ws["I3"] = "当前市价"
ws["I3"].font = header_font
ws["I3"].fill = header_fill
ws["I3"].alignment = center
ws["I3"].border = border

ws["J3"] = 2350
ws["J3"].font = input_font
ws["J3"].fill = input_fill
ws["J3"].alignment = center
ws["J3"].border = border
ws["J3"].number_format = "#,##0.00"

ws["K3"] = "币种"
ws["K3"].font = header_font
ws["K3"].fill = header_fill
ws["K3"].alignment = center
ws["K3"].border = border

ws["L3"] = "ETH"
ws["L3"].font = input_font
ws["L3"].fill = input_fill
ws["L3"].alignment = center
ws["L3"].border = border

# 规则说明
ws.merge_cells("A4:L4")
ws["A4"] = "规则：首次按固定%建仓 → 后续每次BUY：跌幅% × 买入倍率 = 本次买入占本金% ｜ SELL：涨幅% × 卖出倍率 = 本次卖出占持仓%"
ws["A4"].font = Font(name="微软雅黑", size=10, italic=True, color="666666")
ws["A4"].alignment = Alignment(horizontal="center", vertical="center")
ws["A4"].fill = PatternFill("solid", fgColor="F2F2F2")

# ===== 第6行 表头 =====
headers = ["#", "操作", "日期", "成交价", "涨跌%", "建议%", "实际投入%", "金额$", "数量", "平均成本", "累计持仓", "累计投入$"]
for col, h in enumerate(headers, 1):
    c = ws.cell(row=6, column=col, value=h)
    c.font = header_font
    c.fill = header_fill
    c.alignment = center
    c.border = border

# ===== 数据行 第7行开始 最多20笔 =====
MAX_ROWS = 20
START_ROW = 7

for i in range(MAX_ROWS):
    r = START_ROW + i
    idx = i + 1
    prev_row = r - 1
    
    # A: 序号
    ws.cell(row=r, column=1, value=idx).alignment = center
    ws.cell(row=r, column=1).font = Font(name="微软雅黑", size=10, bold=True, color="666666")
    
    # B: 操作 (用户输入 BUY 或 SELL)
    c_action = ws.cell(row=r, column=2)
    c_action.alignment = center
    c_action.fill = input_fill
    c_action.font = input_font
    
    # C: 日期 (用户输入)
    c_date = ws.cell(row=r, column=3)
    c_date.alignment = center
    c_date.fill = input_fill
    c_date.font = input_font
    c_date.number_format = "yyyy-mm-dd"
    
    # D: 成交价 (用户输入)
    c_price = ws.cell(row=r, column=4)
    c_price.alignment = center
    c_price.fill = input_fill
    c_price.font = input_font
    c_price.number_format = "#,##0.00"
    
    if i == 0:
        # 第一行
        # E: 涨跌% = 0 (首次无对比)
        ws.cell(row=r, column=5, value=0).number_format = "0.00%"
        # F: 建议% = 首次买入%
        ws.cell(row=r, column=6, value="=$D$3")
        # G: 实际投入% (用户可覆盖，默认等于建议%)
        c_pct = ws.cell(row=r, column=7, value="=F7")
        c_pct.fill = input_fill
        c_pct.font = input_font
        # H: 金额 = 本金 * 实际投入%
        ws.cell(row=r, column=8, value=f"=IF(B{r}=\"BUY\",$B$3*G{r},IF(B{r}=\"SELL\",-K{r}*G{r}*D{r},0))")
        # I: 数量 = 金额 / 价格
        ws.cell(row=r, column=9, value=f"=IFERROR(IF(B{r}=\"BUY\",H{r}/D{r},IF(B{r}=\"SELL\",-K{r}*G{r},0)),0)")
        # J: 平均成本 (首次=价格)
        ws.cell(row=r, column=10, value=f"=IFERROR(IF(B{r}=\"BUY\",D{r},0),0)")
        # K: 累计持仓 = 数量
        ws.cell(row=r, column=11, value=f"=I{r}")
        # L: 累计投入 = ABS(金额)
        ws.cell(row=r, column=12, value=f"=IF(B{r}=\"BUY\",H{r},0)")
    else:
        # 后续行
        # E: 涨跌% = (当前价 - 上一行平均成本) / 上一行平均成本
        ws.cell(row=r, column=5, value=f"=IFERROR(IF(OR(B{r}=\"BUY\",B{r}=\"SELL\"),IF(J{prev_row}>0,(D{r}-J{prev_row})/J{prev_row},0),\"\"),\"\")")
        # F: 建议% 
        #   BUY: 跌幅(取正) * 买入倍率
        #   SELL: 涨幅 * 卖出倍率
        ws.cell(row=r, column=6, value=(
            f'=IFERROR('
            f'IF(B{r}="BUY",MAX(0,-E{r})*$F$3,'
            f'IF(B{r}="SELL",MAX(0,E{r})*$H$3,0)),0)'
        ))
        # G: 实际投入% (默认=建议%, 用户可改)
        c_pct = ws.cell(row=r, column=7, value=f"=F{r}")
        c_pct.fill = input_fill
        c_pct.font = input_font
        # H: 金额
        #   BUY: 本金 * 实际投入%
        #   SELL: -(累计持仓上行 * 实际投入% * 价格)
        ws.cell(row=r, column=8, value=(
            f'=IFERROR('
            f'IF(B{r}="BUY",$B$3*G{r},'
            f'IF(B{r}="SELL",-K{prev_row}*G{r}*D{r},0)),0)'
        ))
        # I: 数量
        #   BUY: H/D
        #   SELL: -(累计持仓上行 * 实际投入%)
        ws.cell(row=r, column=9, value=(
            f'=IFERROR('
            f'IF(B{r}="BUY",H{r}/D{r},'
            f'IF(B{r}="SELL",-K{prev_row}*G{r},0)),0)'
        ))
        # J: 平均成本
        #   BUY: (上行平均成本*上行累计 + 本次金额)/(上行累计+本次数量)
        #   SELL: 保持上行成本
        ws.cell(row=r, column=10, value=(
            f'=IFERROR('
            f'IF(B{r}="BUY",IF((K{prev_row}+I{r})>0,(J{prev_row}*K{prev_row}+H{r})/(K{prev_row}+I{r}),0),'
            f'IF(B{r}="SELL",J{prev_row},J{prev_row})),J{prev_row})'
        ))
        # K: 累计持仓 = 上行 + 本次数量
        ws.cell(row=r, column=11, value=f"=K{prev_row}+I{r}")
        # L: 累计投入 (BUY加金额, SELL不减 用于追踪总投入)
        ws.cell(row=r, column=12, value=f"=L{prev_row}+IF(B{r}=\"BUY\",H{r},0)")
    
    # 格式化
    ws.cell(row=r, column=5).number_format = "0.00%"
    ws.cell(row=r, column=6).number_format = "0.00%"
    ws.cell(row=r, column=7).number_format = "0.00%"
    ws.cell(row=r, column=8).number_format = "$#,##0.00"
    ws.cell(row=r, column=9).number_format = "0.00000000"
    ws.cell(row=r, column=10).number_format = "#,##0.00"
    ws.cell(row=r, column=11).number_format = "0.00000000"
    ws.cell(row=r, column=12).number_format = "$#,##0.00"
    
    # 公式列样式
    for col_idx in [1, 5, 6, 8, 9, 10, 11, 12]:
        cell = ws.cell(row=r, column=col_idx)
        cell.alignment = center
        cell.border = border
        if col_idx not in [1]:
            cell.font = formula_font
            if cell.fill.fgColor.rgb != "00FFF2CC":
                cell.fill = formula_fill
    
    # 实际投入% 是可编辑 黄色
    ws.cell(row=r, column=7).alignment = center
    ws.cell(row=r, column=7).border = border
    
    # BUY/SELL 列
    ws.cell(row=r, column=2).border = border
    ws.cell(row=r, column=3).border = border
    ws.cell(row=r, column=4).border = border

# ===== 汇总区 =====
summary_start = START_ROW + MAX_ROWS + 1  # 28

# 汇总标题
ws.merge_cells(start_row=summary_start, start_column=1, end_row=summary_start, end_column=12)
ws.cell(row=summary_start, column=1, value="当前持仓汇总")
ws.cell(row=summary_start, column=1).font = title_font
ws.cell(row=summary_start, column=1).fill = title_fill
ws.cell(row=summary_start, column=1).alignment = center
ws.row_dimensions[summary_start].height = 24

sr = summary_start + 1

# 汇总行 1: 累计买入次数 / 累计卖出次数 / 当前持仓数量 / 平均成本
labels1 = ["累计买入次数", "累计卖出次数", "当前持仓数量", "当前平均成本"]
formulas1 = [
    f'=COUNTIF(B{START_ROW}:B{START_ROW+MAX_ROWS-1},"BUY")',
    f'=COUNTIF(B{START_ROW}:B{START_ROW+MAX_ROWS-1},"SELL")',
    f'=IFERROR(LOOKUP(2,1/(K{START_ROW}:K{START_ROW+MAX_ROWS-1}<>""),K{START_ROW}:K{START_ROW+MAX_ROWS-1}),0)',
    f'=IFERROR(LOOKUP(2,1/(J{START_ROW}:J{START_ROW+MAX_ROWS-1}<>""),J{START_ROW}:J{START_ROW+MAX_ROWS-1}),0)'
]
fmts1 = ["0", "0", "0.00000000", "#,##0.00"]

for i, (lbl, fml, fmt) in enumerate(zip(labels1, formulas1, fmts1)):
    col_lbl = i * 3 + 1
    col_val = i * 3 + 2
    
    cl = ws.cell(row=sr, column=col_lbl, value=lbl)
    cl.font = header_font
    cl.fill = header_fill
    cl.alignment = center
    cl.border = border
    
    cv = ws.cell(row=sr, column=col_val, value=fml)
    cv.font = formula_font
    cv.fill = formula_fill
    cv.alignment = center
    cv.border = border
    cv.number_format = fmt

# 合并空白列
for i in range(4):
    merge_col = i * 3 + 3
    ws.merge_cells(start_row=sr, start_column=merge_col, end_row=sr, end_column=merge_col)

# 汇总行 2: 累计投入 / 当前市值 / 浮动盈亏 / 浮动收益率
sr2 = sr + 1
labels2 = ["累计投入 $", "当前市值 $", "浮动盈亏 $", "浮动收益率"]
formulas2 = [
    f'=SUMIF(B{START_ROW}:B{START_ROW+MAX_ROWS-1},"BUY",H{START_ROW}:H{START_ROW+MAX_ROWS-1})',
    f'=B{sr}*$J$3',  # 当前持仓 * 当前市价 —— 错误 应该是 B{sr}（持仓）在第3列
    f'=0',
    f'=0'
]
# 正确引用: 持仓数量在 B{sr} 是错的, 看上面 col_val=2 所以是 B{sr}
# 累计买入次数: B{sr}, 累计卖出次数: E{sr}, 持仓数量: H{sr}, 平均成本: K{sr}

# 重新定义:
holding_cell = f"H{sr}"   # 持仓数量
avgcost_cell = f"K{sr}"   # 平均成本

formulas2 = [
    f'=SUMIF(B{START_ROW}:B{START_ROW+MAX_ROWS-1},"BUY",H{START_ROW}:H{START_ROW+MAX_ROWS-1})+SUMIF(B{START_ROW}:B{START_ROW+MAX_ROWS-1},"SELL",H{START_ROW}:H{START_ROW+MAX_ROWS-1})',
    f'={holding_cell}*$J$3',
    f'={holding_cell}*($J$3-{avgcost_cell})',
    f'=IFERROR(({holding_cell}*($J$3-{avgcost_cell}))/SUMIF(B{START_ROW}:B{START_ROW+MAX_ROWS-1},"BUY",H{START_ROW}:H{START_ROW+MAX_ROWS-1}),0)'
]
fmts2 = ["$#,##0.00", "$#,##0.00", "$#,##0.00", "0.00%"]

for i, (lbl, fml, fmt) in enumerate(zip(labels2, formulas2, fmts2)):
    col_lbl = i * 3 + 1
    col_val = i * 3 + 2
    
    cl = ws.cell(row=sr2, column=col_lbl, value=lbl)
    cl.font = header_font
    cl.fill = header_fill
    cl.alignment = center
    cl.border = border
    
    cv = ws.cell(row=sr2, column=col_val, value=fml)
    cv.font = Font(name="微软雅黑", size=11, bold=True, color="1F4E78")
    cv.fill = formula_fill
    cv.alignment = center
    cv.border = border
    cv.number_format = fmt

# 汇总行 3: 已用资金% / 剩余可用 / 首次建仓价 / 距当前价涨跌
sr3 = sr + 2

labels3 = ["已用资金占比", "剩余可用资金", "首次建仓价", "相对首仓涨跌"]
formulas3 = [
    f'=IFERROR(SUMIF(B{START_ROW}:B{START_ROW+MAX_ROWS-1},"BUY",H{START_ROW}:H{START_ROW+MAX_ROWS-1})/$B$3,0)',
    f'=$B$3-SUMIF(B{START_ROW}:B{START_ROW+MAX_ROWS-1},"BUY",H{START_ROW}:H{START_ROW+MAX_ROWS-1})',
    f'=IFERROR(INDEX(D{START_ROW}:D{START_ROW+MAX_ROWS-1},MATCH("BUY",B{START_ROW}:B{START_ROW+MAX_ROWS-1},0)),0)',
    f'=IFERROR(($J$3-INDEX(D{START_ROW}:D{START_ROW+MAX_ROWS-1},MATCH("BUY",B{START_ROW}:B{START_ROW+MAX_ROWS-1},0)))/INDEX(D{START_ROW}:D{START_ROW+MAX_ROWS-1},MATCH("BUY",B{START_ROW}:B{START_ROW+MAX_ROWS-1},0)),0)'
]
fmts3 = ["0.00%", "$#,##0.00", "#,##0.00", "0.00%"]

for i, (lbl, fml, fmt) in enumerate(zip(labels3, formulas3, fmts3)):
    col_lbl = i * 3 + 1
    col_val = i * 3 + 2
    
    cl = ws.cell(row=sr3, column=col_lbl, value=lbl)
    cl.font = header_font
    cl.fill = header_fill
    cl.alignment = center
    cl.border = border
    
    cv = ws.cell(row=sr3, column=col_val, value=fml)
    cv.font = Font(name="微软雅黑", size=11, bold=True, color="1F4E78")
    cv.fill = formula_fill
    cv.alignment = center
    cv.border = border
    cv.number_format = fmt

# ===== 列宽 =====
widths = [5, 9, 12, 11, 10, 10, 11, 12, 12, 11, 12, 13]
for i, w in enumerate(widths, 1):
    ws.column_dimensions[get_column_letter(i)].width = w

# 冻结首6行
ws.freeze_panes = "A7"

# ===== 条件格式 =====
# BUY 行绿色
buy_rule = FormulaRule(formula=[f'$B{START_ROW}="BUY"'], fill=PatternFill("solid", fgColor="E2EFDA"))
sell_rule = FormulaRule(formula=[f'$B{START_ROW}="SELL"'], fill=PatternFill("solid", fgColor="FCE4D6"))
ws.conditional_formatting.add(f"A{START_ROW}:L{START_ROW+MAX_ROWS-1}", buy_rule)
ws.conditional_formatting.add(f"A{START_ROW}:L{START_ROW+MAX_ROWS-1}", sell_rule)

# 盈利红绿
profit_cell = f"H{sr2}"
ws.conditional_formatting.add(profit_cell, 
    CellIsRule(operator="greaterThan", formula=["0"], fill=PatternFill("solid", fgColor="C6EFCE"), font=Font(color="006100", bold=True)))
ws.conditional_formatting.add(profit_cell, 
    CellIsRule(operator="lessThan", formula=["0"], fill=PatternFill("solid", fgColor="FFC7CE"), font=Font(color="9C0006", bold=True)))

roi_cell = f"K{sr2}"
ws.conditional_formatting.add(roi_cell, 
    CellIsRule(operator="greaterThan", formula=["0"], fill=PatternFill("solid", fgColor="C6EFCE"), font=Font(color="006100", bold=True)))
ws.conditional_formatting.add(roi_cell, 
    CellIsRule(operator="lessThan", formula=["0"], fill=PatternFill("solid", fgColor="FFC7CE"), font=Font(color="9C0006", bold=True)))

# ===== 示例数据 Sheet2 =====
ws2 = wb.create_sheet("示例演示")
example_rows = [
    ["#", "操作", "日期", "成交价", "涨跌%", "建议%", "实际投入%", "金额$", "数量", "平均成本", "累计持仓", "累计投入$"],
    [1, "BUY",  "2025-01-10", 3000, "—",       "10%",     "10%",     1000,  0.3333, 3000, 0.3333, 1000],
    [2, "BUY",  "2025-02-15", 2400, "-20.0%",  "20.0%",   "20.0%",   2000,  0.8333, 2571, 1.1667, 3000],
    [3, "BUY",  "2025-03-20", 1800, "-30.0%",  "30.0%",   "30.0%",   3000,  1.6667, 2117, 2.8333, 6000],
    [4, "SELL", "2025-04-10", 2540, "+20.0%",  "20.0%",   "20.0%",   1290,  0.5667, 2117, 2.2666, 6000],
    [5, "SELL", "2025-05-05", 3176, "+50.0%",  "50.0%",   "50.0%",   3599,  1.1333, 2117, 1.1333, 6000],
]
for r_idx, row in enumerate(example_rows, 1):
    for c_idx, val in enumerate(row, 1):
        c = ws2.cell(row=r_idx, column=c_idx, value=val)
        c.alignment = center
        c.border = border
        if r_idx == 1:
            c.font = header_font
            c.fill = header_fill
        else:
            c.font = Font(name="微软雅黑", size=10)
            if row[1] == "BUY":
                c.fill = PatternFill("solid", fgColor="E2EFDA")
            else:
                c.fill = PatternFill("solid", fgColor="FCE4D6")

ws2.merge_cells("A8:L8")
ws2["A8"] = "说明：本示例展示 ETH 10000本金 DCA 流程 - 首次10%建仓 → 跌20%加仓20% → 跌30%加仓30% → 涨20%卖20% → 涨50%卖50%"
ws2["A8"].font = Font(name="微软雅黑", size=10, italic=True, color="666666")
ws2["A8"].alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
ws2.row_dimensions[8].height = 30

for i, w in enumerate(widths, 1):
    ws2.column_dimensions[get_column_letter(i)].width = w

# ===== 使用说明 Sheet3 =====
ws3 = wb.create_sheet("使用说明")
help_text = [
    ["DCA 持仓计算器 使用说明"],
    [""],
    ["【输入区 黄色格子】"],
    ["  B3  初始本金（默认 10000）"],
    ["  D3  首次建仓占本金% （默认 10%）"],
    ["  F3  买入倍率：跌幅 × 此倍率 = 本次买入占本金%（1.0=跌30%买30%）"],
    ["  H3  卖出倍率：涨幅 × 此倍率 = 本次卖出占持仓%（1.0=涨20%卖20%）"],
    ["  J3  当前市价（用于实时计算浮动盈亏）"],
    ["  L3  币种名称"],
    [""],
    ["【交易表格 B7:D26 黄色为必填】"],
    ["  B列 操作：输入 BUY 或 SELL"],
    ["  C列 日期：交易日期"],
    ["  D列 成交价：实际成交价格"],
    ["  G列 实际投入%：默认=建议%，你可以手动改成实际执行的比例"],
    [""],
    ["【自动计算列 浅蓝色】"],
    ["  E列 涨跌%    相对上一次平均成本的涨跌幅"],
    ["  F列 建议%    系统根据规则自动建议的仓位比例"],
    ["  H列 金额    本次交易美元金额（SELL为负）"],
    ["  I列 数量    本次交易币数（SELL为负）"],
    ["  J列 平均成本  本次交易后的持仓均价"],
    ["  K列 累计持仓  本次交易后的总币数"],
    ["  L列 累计投入  历史所有BUY的累加金额"],
    [""],
    ["【汇总区】"],
    ["  28行起显示：买入次数 / 卖出次数 / 当前持仓 / 平均成本"],
    ["  累计投入 / 当前市值 / 浮动盈亏 / 浮动收益率"],
    ["  已用资金% / 剩余可用 / 首次建仓价 / 相对首仓涨跌"],
    [""],
    ["【使用流程】"],
    ["  1. 设定初始本金和规则参数（第3行）"],
    ["  2. TradingView 出现 BUY 信号 → 在表格填 BUY/日期/价格"],
    ["  3. 查看 G列建议% → 可以按建议下单，也可以手动覆盖比例"],
    ["  4. 出现 SELL 信号同理填入"],
    ["  5. 修改 J3 当前市价 → 实时看到浮动盈亏"],
    [""],
    ["【示例规则】"],
    ["  首次 BUY @ 3000  买 10% = $1000 → 0.333 ETH"],
    ["  跌 20% BUY @ 2400 买 20% = $2000 → 0.833 ETH（均价 2571）"],
    ["  跌 30%（距2571）BUY @ 1800 买 30% = $3000 → 1.667 ETH（均价 2117）"],
    ["  涨 20%（距2117）SELL @ 2540 卖 20% 持仓"],
    ["  涨 50%（距2117）SELL @ 3176 卖 50% 持仓"],
]

for r_idx, row in enumerate(help_text, 1):
    c = ws3.cell(row=r_idx, column=1, value=row[0])
    if r_idx == 1:
        c.font = Font(name="微软雅黑", size=16, bold=True, color="1F4E78")
    elif row[0].startswith("【"):
        c.font = Font(name="微软雅黑", size=12, bold=True, color="C00000")
    else:
        c.font = Font(name="微软雅黑", size=11, color="333333")

ws3.column_dimensions["A"].width = 80

# 保存
output_path = "/projects/sandbox/MING/DCA持仓计算器.xlsx"
wb.save(output_path)
print(f"Saved: {output_path}")
