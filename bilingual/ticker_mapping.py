"""
中英文 Ticker 映射表 - 在所有图表/Excel 中使用
"""

TICKER_MAP = {
    # AI / 电力主题 ETF
    "AIPO": "AIPO (AI电力基础设施ETF)",
    "POWR": "POWR (美国电力基建ETF)",
    "GRID": "GRID (智能电网ETF)",
    "PAVE": "PAVE (美国基建ETF)",
    "VOLT": "VOLT (电气化主动ETF)",
    
    # 核能主题 ETF
    "NLR": "NLR (铀矿与核能ETF)",
    "URA": "URA (全球铀矿ETF)",
    "URNM": "URNM (纯铀矿ETF)",
    "URAN": "URAN (Themes铀核ETF)",
    "SMRF": "SMRF (小型核反应堆ETF)",
    "NUKZ": "NUKZ (核能复兴ETF)",
    
    # 公用事业 ETF
    "XLU": "XLU (美国公用事业ETF)",
    "VPU": "VPU (先锋公用事业ETF)",
    "UTES": "UTES (公用事业主动ETF)",
    "FXU": "FXU (公用事业Alpha)",
    "UTG": "UTG (公用事业封闭基金)",
    
    # AI / 科技 / 大盘 ETF
    "QQQ": "QQQ (纳斯达克100ETF)",
    "SPY": "SPY (标普500ETF)",
    "ARKQ": "ARKQ (方舟自动化机器人ETF)",
    "ARKK": "ARKK (方舟创新ETF)",
    "ARKW": "ARKW (方舟下一代互联网)",
    "ARKG": "ARKG (方舟基因革命)",
    "ARKF": "ARKF (方舟金融科技)",
    "ARKX": "ARKX (方舟太空国防)",
    "BOTZ": "BOTZ (机器人AI ETF)",
    "TSPA": "TSPA (普信股票研究ETF)",
    "DTCR": "DTCR (数据中心ETF)",
    
    # 清洁能源
    "VCLN": "VCLN (清洁能源主动ETF)",
    "ICLN": "ICLN (全球清洁能源ETF)",
    
    # 个股
    "GEV": "GEV (GE维诺瓦/燃气轮机)",
    "ETN": "ETN (伊顿电气)",
    "PWR": "PWR (匡塔服务/电力施工)",
    "VRT": "VRT (维谛技术/数据中心)",
    "EMR": "EMR (艾默生电气)",
    "POWL": "POWL (鲍威尔工业)",
    "BELFB": "BELFB (贝尔福电子)",
    "MTZ": "MTZ (玛斯泰克)",
    "JCI": "JCI (江森自控)",
    "ABB": "ABB (瑞士ABB)",
    "BE": "BE (布鲁姆能源/燃料电池)",
    "KGS": "KGS (科迪亚克天然气)",
    "CEG": "CEG (星座能源/核电)",
    "VST": "VST (维斯特拉/核电+燃气)",
    "TLN": "TLN (塔伦能源/核电)",
    "D": "D (多明尼资源)",
    "NEE": "NEE (新纪元能源)",
    "SO": "SO (南方电力)",
    "DUK": "DUK (杜克能源)",
    "AEP": "AEP (美国电力公司)",
    "XEL": "XEL (埃克塞尔能源)",
    "CNP": "CNP (中点能源)",
    "PEG": "PEG (公共服务企业)",
    "ETR": "ETR (安特吉)",
    "OKLO": "OKLO (奥克洛/SMR)",
    "SMR": "SMR (NuScale电力)",
    "CCJ": "CCJ (卡梅科铀业)",
    "BWXT": "BWXT (BWX技术)",
    "LEU": "LEU (中心能源/浓缩铀)",
    "UEC": "UEC (铀能源公司)",
    "NXE": "NXE (下一代能源)",
    "UUUU": "UUUU (能源燃料)",
    "BEP": "BEP (布鲁克菲尔德可再生)",
    "NVDA": "NVDA (英伟达)",
    "AVGO": "AVGO (博通)",
    "TSM": "TSM (台积电)",
    "AMD": "AMD (超威半导体)",
    "TER": "TER (泰瑞达)",
    "AAPL": "AAPL (苹果)",
    "MSFT": "MSFT (微软)",
    "AMZN": "AMZN (亚马逊)",
    "GOOGL": "GOOGL (谷歌A)",
    "GOOG": "GOOG (谷歌C)",
    "META": "META (Meta元宇宙)",
    "TSLA": "TSLA (特斯拉)",
    "KTOS": "KTOS (克拉托斯国防)",
    "TRMB": "TRMB (天宝公司)",
    "PATH": "PATH (UiPath自动化)",
    "CAT": "CAT (卡特彼勒)",
    "IRDM": "IRDM (铱星通信)",
    "ACHR": "ACHR (阿彻航空)",
}

def label(ticker):
    """获取 ticker 的中英文双语标签"""
    return TICKER_MAP.get(ticker, ticker)

def short_label(ticker):
    """简短版（用于图表轴）"""
    full = TICKER_MAP.get(ticker, ticker)
    if "(" in full:
        return ticker + "\n" + full.split("(")[1].rstrip(")")
    return ticker
