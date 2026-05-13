"""
升级版可视化 Excel - 加入 Wyckoff 阶段分析
Sheets:
  1. 总览
  2. 美股 AI 能源 (含 Wyckoff)
  3. A 股 存储 AI (含 Wyckoff)
  4. 信号汇总
  5. Wyckoff 详细分析(新增)
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.formatting.rule import DataBarRule, ColorScaleRule, FormulaRule
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.chart.label import DataLabelList

from portfolio_alloc import analyze_one, composite_score
from wyckoff_analyzer import analyze_wyckoff

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
LEFT   = Alignment(horizontal='left',   vertical='center', wrap_text=True)


def fetch_all():
    us = ["NRG", "VST", "SMR", "STEM", "EXE", "CEG", "PEG", "OKLO"]
    cn = ["603160.SS", "002230.SZ", "603690.SS", "603893.SS"]

    print("拉取美股 + Wyckoff 分析...")
    us_data = []
    for i, s in enumerate(us, 1):
        print(f"  [{i}/{len(us)}] {s}", end=" ... ", flush=True)
        try:
            r = analyze_one(s)
            if r:
                r["composite_score"] = composite_score(r)
                w = analyze_wyckoff(s, r.get("name", s))
                if w:
                    r.update({f"wy_{k}": v for k, v in w.items() if k not in ("symbol", "name", "price")})
                us_data.append(r)
                print(f"OK {r.get('wy_phase', '')}")
            else:
                print("✗")
        except Exception as e:
            print(f"✗ {e}")

    print("拉取 A 股 + Wyckoff 分析...")
    cn_data = []
    for i, s in enumerate(cn, 1):
        print(f"  [{i}/{len(cn)}] {s}", end=" ... ", flush=True)
        try:
            r = analyze_one(s)
            if r:
                r["composite_score"] = composite_score(r)
                w = analyze_wyckoff(s, r.get("name", s))
                if w:
                    r.update({f"wy_{k}": v for k, v in w.items() if k not in ("symbol", "name", "price")})
                cn_data.append(r)
                print(f"OK {r.get('wy_phase', '')}")
            else:
                print("✗")
        except Exception as e:
            print(f"✗ {e}")

    return us_data, cn_data


def calc_alloc(rows):
    """根据 Wyckoff first_batch_pct 调整分配
    最终金额 = 该股票分配比例 × 资金 × Wyckoff 首批比例
    """
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


def write_overview(wb, us, cn):
    ws = wb.create_sheet("📊 总览", 0)
    ws.column_dimensions['A'].width = 22
    ws.column_dimensions['B'].width = 60

    ws['A1'] = "📊 资金分配 + Wyckoff 形态分析 - 总览"
    ws['A1'].font = Font(name='微软雅黑', size=18, color='1F4E78', bold=True)
    ws.merge_cells('A1:E1')

    ws['A2'] = "数据来源: yfinance | Wyckoff 阶段: A/B/C/D/E (吸筹/派发) | 主力推断: OBV+CMF+涨跌量比"
    ws['A2'].font = SUBTITLE_FONT
    ws.merge_cells('A2:E2')

    # 组合汇总
    ws['A4'] = "组合"; ws['B4'] = "股票数"; ws['C4'] = "强建仓"; ws['D4'] = "试探仓"; ws['E4'] = "禁止建仓"
    for cell in ws[4]:
        cell.font = HEADER_FONT; cell.fill = HEADER_FILL; cell.alignment = CENTER

    def count(rows, *kws):
        c = 0
        for r in rows:
            act = r.get("wy_action", "")
            if any(k in act for k in kws):
                c += 1
        return c

    ws['A5'] = "🇺🇸 美股 AI 能源"
    ws['B5'] = len(us)
    ws['C5'] = count(us, "强烈建仓", "趋势确认")
    ws['D5'] = count(us, "试探", "趋势中")
    ws['E5'] = count(us, "暂不", "不建仓", "观望")

    ws['A6'] = "🇨🇳 A 股 存储 AI"
    ws['B6'] = len(cn)
    ws['C6'] = count(cn, "强烈建仓", "趋势确认")
    ws['D6'] = count(cn, "试探", "趋势中")
    ws['E6'] = count(cn, "暂不", "不建仓", "观望")

    ws['A5'].fill = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')
    ws['A6'].fill = PatternFill(start_color='FFEB9C', end_color='FFEB9C', fill_type='solid')

    for row in ws.iter_rows(min_row=5, max_row=6, max_col=5):
        for cell in row:
            cell.alignment = CENTER
            cell.font = Font(name='微软雅黑', size=11, bold=True)
            cell.border = THIN_BORDER

    # Wyckoff 阶段说明
    ws['A8'] = "📚 Wyckoff 阶段说明"
    ws['A8'].font = TITLE_FONT
    ws.merge_cells('A8:E8')

    explanation = [
        ("吸筹周期 A 阶段(止跌)", "长期下跌后初步止跌,价格停止创新低。⚠️ 还不能建仓"),
        ("吸筹周期 B 阶段(吸筹震荡)", "横盘震荡,主力低位吸筹。🟡 可小仓位试探(20-30%)"),
        ("吸筹周期 C 阶段(Spring 假跌破)", "短暂跌破前低后强力收回。✅ 最佳建仓点(60% 重仓)"),
        ("吸筹周期 D 阶段(SOS 强势)", "Sign of Strength,放量上涨突破。✅ 趋势确认建仓(70%)"),
        ("吸筹周期 E 阶段(上升趋势)", "脱离吸筹区进入上升通道。🟢 已在趋势中,回踩加仓"),
        ("派发周期 A 阶段(派发开始)", "高位放量但 OBV 走弱。🚫 不建仓"),
        ("派发周期 B 阶段(派发震荡)", "高位横盘,主力派发。🚫 不建仓"),
        ("派发周期 C 阶段(UTAD 假突破)", "短暂突破前高后回落。🚫 顶部信号,远离"),
        ("派发周期 D 阶段(SOW 弱势)", "Sign of Weakness,跌破支撑。🚫 等待跌至 MA200 再评估"),
        ("派发周期 E 阶段(下跌趋势)", "进入下降通道。🚫 等止跌信号"),
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
        "1. Wyckoff 阶段判断结合: 52W 位置 + MA200/MA60 趋势 + 振幅收敛 + OBV + Spring/UTAD 检测",
        "2. 平均筹码价格 用 60 日 VWAP 代理 — 严格的'持仓成本'需要 Tick 数据,本表近似",
        "3. 主力资金/庄家 用 OBV+CMF+涨跌量比 推断 — 准确判断需要 L2 主力净流入数据",
        "4. 本报告为按规则的资金分配,不构成任何投资建议",
        "5. 风险提示: 跌破止损位强制止损,Spring 失败立即清仓",
    ]
    for i, n in enumerate(notes, note_row+1):
        c = ws.cell(row=i, column=1, value=n)
        c.font = Font(name='微软雅黑', size=10, color='C00000')
        ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=5)


def write_market(wb, rows, sheet_name, market_label, total_capital, currency):
    ws = wb.create_sheet(sheet_name)

    widths = [9, 24, 9, 9, 11, 9, 9, 9, 9, 9, 9, 11, 22, 13, 11, 30, 11]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws['A1'] = f"💰 {market_label} - 资金分配 + Wyckoff 形态"
    ws['A1'].font = TITLE_FONT
    ws.merge_cells('A1:Q1')
    ws['A2'] = f"总资金 {currency}{total_capital:,} | 首批仓位按 Wyckoff 阶段调整"
    ws['A2'].font = SUBTITLE_FONT
    ws.merge_cells('A2:Q2')

    headers = ["代码", "名称", "综合分", "分配 %", "理论金额", "股价",
               "市值", "PE", "营收增长", "利润率", "ROE", "位置 %",
               "Wyckoff 阶段", "首批 %", "首批金额", "第二批触发", "止损"]
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=4, column=i, value=h)
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.alignment = CENTER
        c.border = THIN_BORDER

    for ri, r in enumerate(rows, 5):
        amt = total_capital * r["alloc_pct"]
        first_pct = (r.get("wy_first_batch_pct") or 0) / 100
        first_amt = amt * first_pct
        cells = [
            r["symbol"],
            (r.get("name") or r["symbol"])[:22],
            r["composite_score"],
            r["alloc_pct"],
            amt,
            r["price"],
            r.get("market_cap"),
            r.get("pe_ttm"),
            r.get("rev_growth"),
            r.get("profit_margin"),
            r.get("roe"),
            r.get("position_pct"),
            r.get("wy_phase", ""),
            first_pct,
            first_amt,
            r.get("wy_second_trigger_desc", ""),
            r.get("wy_stop_loss"),
        ]
        for ci, v in enumerate(cells, 1):
            c = ws.cell(row=ri, column=ci, value=v)
            c.border = THIN_BORDER
            c.font = Font(name='微软雅黑', size=10)
            c.alignment = CENTER if ci in (1, 3, 4, 6, 7, 8, 9, 10, 11, 12, 14, 17) else LEFT

    for r in range(5, 5 + len(rows)):
        ws.cell(row=r, column=4).number_format = '0.0%'
        ws.cell(row=r, column=5).number_format = f'"{currency}"#,##0'
        ws.cell(row=r, column=7).number_format = '#,##0'
        ws.cell(row=r, column=8).number_format = '0.0'
        ws.cell(row=r, column=9).number_format = '0.0%'
        ws.cell(row=r, column=10).number_format = '0.0%'
        ws.cell(row=r, column=11).number_format = '0.0%'
        ws.cell(row=r, column=12).number_format = '0.0"%"'
        ws.cell(row=r, column=14).number_format = '0%'
        ws.cell(row=r, column=15).number_format = f'"{currency}"#,##0'
        ws.cell(row=r, column=17).number_format = '0.00'

    last_row = 4 + len(rows)

    # ========== 条件格式 ==========
    ws.conditional_formatting.add(f"C5:C{last_row}",
        ColorScaleRule(start_type='num', start_value=0, start_color='F8696B',
                       mid_type='num', mid_value=40, mid_color='FFEB84',
                       end_type='num', end_value=80, end_color='63BE7B'))
    ws.conditional_formatting.add(f"D5:D{last_row}",
        DataBarRule(start_type='min', end_type='max', color='5B9BD5'))
    ws.conditional_formatting.add(f"E5:E{last_row}",
        DataBarRule(start_type='min', end_type='max', color='70AD47'))
    ws.conditional_formatting.add(f"I5:I{last_row}",
        ColorScaleRule(start_type='num', start_value=-0.3, start_color='F8696B',
                       mid_type='num', mid_value=0, mid_color='FFFFFF',
                       end_type='num', end_value=0.5, end_color='63BE7B'))
    ws.conditional_formatting.add(f"J5:J{last_row}",
        ColorScaleRule(start_type='num', start_value=-0.1, start_color='F8696B',
                       mid_type='num', mid_value=0, mid_color='FFFFFF',
                       end_type='num', end_value=0.3, end_color='63BE7B'))
    ws.conditional_formatting.add(f"K5:K{last_row}",
        ColorScaleRule(start_type='num', start_value=-0.1, start_color='F8696B',
                       mid_type='num', mid_value=0, mid_color='FFFFFF',
                       end_type='num', end_value=0.3, end_color='63BE7B'))
    ws.conditional_formatting.add(f"L5:L{last_row}",
        ColorScaleRule(start_type='num', start_value=0, start_color='63BE7B',
                       mid_type='num', mid_value=50, mid_color='FFEB84',
                       end_type='num', end_value=100, end_color='F8696B'))
    # 首批 % 数据条
    ws.conditional_formatting.add(f"N5:N{last_row}",
        DataBarRule(start_type='num', start_value=0, end_type='num', end_value=1, color='00B050'))
    # 首批金额数据条
    ws.conditional_formatting.add(f"O5:O{last_row}",
        DataBarRule(start_type='min', end_type='max', color='00B050'))

    # Wyckoff 阶段着色(整行)
    # 强烈建仓 - 绿色
    ws.conditional_formatting.add(f"A5:Q{last_row}",
        FormulaRule(formula=[f'ISNUMBER(SEARCH("Spring",$M5))'],
                    fill=PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')))
    # SOS - 浅绿
    ws.conditional_formatting.add(f"A5:Q{last_row}",
        FormulaRule(formula=[f'ISNUMBER(SEARCH("SOS",$M5))'],
                    fill=PatternFill(start_color='E2EFDA', end_color='E2EFDA', fill_type='solid')))
    # E 上升 - 浅绿
    ws.conditional_formatting.add(f"A5:Q{last_row}",
        FormulaRule(formula=[f'ISNUMBER(SEARCH("E (",$M5))'],
                    fill=PatternFill(start_color='E2EFDA', end_color='E2EFDA', fill_type='solid')))
    # B 吸筹 - 浅黄
    ws.conditional_formatting.add(f"A5:Q{last_row}",
        FormulaRule(formula=[f'ISNUMBER(SEARCH("吸筹",$M5))'],
                    fill=PatternFill(start_color='FFF2CC', end_color='FFF2CC', fill_type='solid')))
    # 派发/UTAD/SOW - 红色
    ws.conditional_formatting.add(f"A5:Q{last_row}",
        FormulaRule(formula=[f'OR(ISNUMBER(SEARCH("UTAD",$M5)),ISNUMBER(SEARCH("派发",$M5)),ISNUMBER(SEARCH("SOW",$M5)),ISNUMBER(SEARCH("顶部",$M5)))'],
                    fill=PatternFill(start_color='FFE6E6', end_color='FFE6E6', fill_type='solid')))

    # ========== 总计行 ==========
    total_row = last_row + 2
    ws.cell(row=total_row, column=1, value="💰 总计").font = Font(name='微软雅黑', size=11, bold=True, color='FFFFFF')
    ws.cell(row=total_row, column=1).fill = HEADER_FILL
    ws.cell(row=total_row, column=4, value=f"=SUM(D5:D{last_row})").number_format = '0.0%'
    ws.cell(row=total_row, column=5, value=f"=SUM(E5:E{last_row})").number_format = f'"{currency}"#,##0'
    ws.cell(row=total_row, column=15, value=f"=SUM(O5:O{last_row})").number_format = f'"{currency}"#,##0'
    for c in range(1, 18):
        cell = ws.cell(row=total_row, column=c)
        cell.font = Font(name='微软雅黑', size=11, bold=True)
        cell.fill = PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')
        cell.border = THIN_BORDER
        cell.alignment = CENTER

    # 备注
    note_row = total_row + 2
    ws.cell(row=note_row, column=1, value="说明:").font = Font(name='微软雅黑', size=10, bold=True, color='C00000')
    ws.cell(row=note_row, column=2,
            value="理论金额=综合分加权;首批金额=理论金额×Wyckoff首批比例;余下资金等第二批触发条件").font = Font(name='微软雅黑', size=10, color='C00000')
    ws.merge_cells(start_row=note_row, start_column=2, end_row=note_row, end_column=17)

    # ========== 图表 ==========
    pie = PieChart()
    pie.title = f"{market_label} - 首批资金分配"
    labels = Reference(ws, min_col=1, min_row=5, max_row=last_row)
    data   = Reference(ws, min_col=15, min_row=4, max_row=last_row)
    pie.add_data(data, titles_from_data=True)
    pie.set_categories(labels)
    pie.height = 11
    pie.width = 16
    pie.dataLabels = DataLabelList(showPercent=True, showCatName=True)
    ws.add_chart(pie, f"S4")

    bar = BarChart()
    bar.type = "bar"
    bar.style = 11
    bar.title = "Wyckoff 首批仓位 %"
    cat = Reference(ws, min_col=1, min_row=5, max_row=last_row)
    val = Reference(ws, min_col=14, min_row=4, max_row=last_row)
    bar.add_data(val, titles_from_data=True)
    bar.set_categories(cat)
    bar.height = 11
    bar.width = 16
    bar.dataLabels = DataLabelList(showVal=True)
    ws.add_chart(bar, f"S26")

    ws.freeze_panes = "A5"


def write_wyckoff_detail(wb, all_data):
    ws = wb.create_sheet("🌊 Wyckoff 详细")
    widths = [11, 24, 13, 11, 22, 30, 9, 11, 13, 11, 9, 9, 9, 30, 11]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws['A1'] = "🌊 Wyckoff 形态详细分析(12 只)"
    ws['A1'].font = TITLE_FONT
    ws.merge_cells('A1:O1')

    headers = ["代码", "名称", "市场", "周期", "Wyckoff 阶段", "形态详情",
               "可信度", "位置 %", "MA60 斜率", "振幅比", "OBV变化",
               "涨跌量比", "Spring/UTAD", "操作建议", "首批 %"]
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=3, column=i, value=h)
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.alignment = CENTER
        c.border = THIN_BORDER

    ri = 4
    for market, rows in all_data:
        for r in rows:
            spring_or_utad = ""
            if r.get("wy_has_spring"):
                spring_or_utad = f"Spring @ {r.get('wy_spring_low')}"
            elif r.get("wy_has_utad"):
                spring_or_utad = f"UTAD @ {r.get('wy_utad_high')}"
            else:
                spring_or_utad = "—"

            cells = [
                r["symbol"],
                (r.get("name") or "")[:22],
                market,
                r.get("wy_cycle", ""),
                r.get("wy_phase", ""),
                r.get("wy_phase_detail", ""),
                r.get("wy_confidence", ""),
                r.get("wy_pos_pct"),
                r.get("wy_ma60_slope_pct"),
                r.get("wy_range_ratio"),
                r.get("wy_obv_change_60"),
                r.get("wy_up_dn_vol_ratio"),
                spring_or_utad,
                r.get("wy_action", ""),
                (r.get("wy_first_batch_pct") or 0) / 100,
            ]
            for ci, v in enumerate(cells, 1):
                c = ws.cell(row=ri, column=ci, value=v)
                c.border = THIN_BORDER
                c.font = Font(name='微软雅黑', size=10)
                c.alignment = CENTER if ci in (1, 3, 4, 7, 8, 9, 10, 11, 12, 15) else LEFT
            ri += 1

    last = ri - 1

    for r in range(4, last + 1):
        ws.cell(row=r, column=8).number_format = '0.0"%"'
        ws.cell(row=r, column=9).number_format = '+0.00"%";-0.00"%"'
        ws.cell(row=r, column=15).number_format = '0%'

    # 阶段着色
    ws.conditional_formatting.add(f"A4:O{last}",
        FormulaRule(formula=[f'ISNUMBER(SEARCH("Spring",$E4))'],
                    fill=PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')))
    ws.conditional_formatting.add(f"A4:O{last}",
        FormulaRule(formula=[f'ISNUMBER(SEARCH("SOS",$E4))'],
                    fill=PatternFill(start_color='E2EFDA', end_color='E2EFDA', fill_type='solid')))
    ws.conditional_formatting.add(f"A4:O{last}",
        FormulaRule(formula=[f'OR(ISNUMBER(SEARCH("UTAD",$E4)),ISNUMBER(SEARCH("派发",$E4)),ISNUMBER(SEARCH("SOW",$E4)))'],
                    fill=PatternFill(start_color='FFE6E6', end_color='FFE6E6', fill_type='solid')))
    ws.conditional_formatting.add(f"A4:O{last}",
        FormulaRule(formula=[f'ISNUMBER(SEARCH("吸筹",$E4))'],
                    fill=PatternFill(start_color='FFF2CC', end_color='FFF2CC', fill_type='solid')))

    # 首批 % 数据条
    ws.conditional_formatting.add(f"O4:O{last}",
        DataBarRule(start_type='num', start_value=0, end_type='num', end_value=1, color='00B050'))

    ws.freeze_panes = "C4"


def write_signals(wb, all_data):
    ws = wb.create_sheet("⚡ 操作信号")
    widths = [11, 22, 9, 22, 13, 36, 11, 11]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws['A1'] = "⚡ 操作信号汇总(分批建仓策略)"
    ws['A1'].font = TITLE_FONT
    ws.merge_cells('A1:H1')

    headers = ["代码", "名称", "市场", "Wyckoff 阶段", "建议操作",
               "第二批触发条件", "止损价", "首批 %"]
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=3, column=i, value=h)
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.alignment = CENTER
        c.border = THIN_BORDER

    ri = 4
    for market, rows in all_data:
        # 按首批仓位降序
        sorted_rows = sorted(rows, key=lambda x: -(x.get("wy_first_batch_pct") or 0))
        for r in sorted_rows:
            cells = [
                r["symbol"],
                (r.get("name") or "")[:22],
                market,
                r.get("wy_phase", ""),
                r.get("wy_action", ""),
                r.get("wy_second_trigger_desc", ""),
                r.get("wy_stop_loss"),
                (r.get("wy_first_batch_pct") or 0) / 100,
            ]
            for ci, v in enumerate(cells, 1):
                c = ws.cell(row=ri, column=ci, value=v)
                c.border = THIN_BORDER
                c.font = Font(name='微软雅黑', size=10)
                c.alignment = CENTER if ci in (1, 3, 7, 8) else LEFT
            ri += 1

    last = ri - 1
    for r in range(4, last + 1):
        ws.cell(row=r, column=7).number_format = '0.00'
        ws.cell(row=r, column=8).number_format = '0%'

    # 着色 - 按操作类型
    ws.conditional_formatting.add(f"A4:H{last}",
        FormulaRule(formula=[f'ISNUMBER(SEARCH("强烈建仓",$E4))'],
                    fill=PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')))
    ws.conditional_formatting.add(f"A4:H{last}",
        FormulaRule(formula=[f'OR(ISNUMBER(SEARCH("趋势确认",$E4)),ISNUMBER(SEARCH("趋势中",$E4)))'],
                    fill=PatternFill(start_color='E2EFDA', end_color='E2EFDA', fill_type='solid')))
    ws.conditional_formatting.add(f"A4:H{last}",
        FormulaRule(formula=[f'ISNUMBER(SEARCH("试探",$E4))'],
                    fill=PatternFill(start_color='FFF2CC', end_color='FFF2CC', fill_type='solid')))
    ws.conditional_formatting.add(f"A4:H{last}",
        FormulaRule(formula=[f'ISNUMBER(SEARCH("不建仓",$E4))'],
                    fill=PatternFill(start_color='FFE6E6', end_color='FFE6E6', fill_type='solid')))

    ws.conditional_formatting.add(f"H4:H{last}",
        DataBarRule(start_type='num', start_value=0, end_type='num', end_value=1, color='00B050'))

    ws.freeze_panes = "A4"


def main():
    us, cn = fetch_all()
    us = calc_alloc(us)
    cn = calc_alloc(cn)

    wb = Workbook()
    if 'Sheet' in wb.sheetnames:
        del wb['Sheet']

    write_overview(wb, us, cn)
    write_market(wb, us, "🇺🇸 美股 AI 能源", "美股 AI 能源 (8 只)", 100000, "$")
    write_market(wb, cn, "🇨🇳 A股 存储与AI", "A 股 存储 AI (4 只)", 100000, "¥")
    write_wyckoff_detail(wb, [("🇺🇸 美股", us), ("🇨🇳 A 股", cn)])
    write_signals(wb, [("🇺🇸 美股", us), ("🇨🇳 A 股", cn)])

    out = os.path.join(BASE_DIR, "资金分配可视化.xlsx")
    wb.save(out)
    print(f"\n✅ 已生成: {out}")
    print(f"   文件大小: {os.path.getsize(out)/1024:.1f} KB")


if __name__ == "__main__":
    main()
