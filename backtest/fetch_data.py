"""拉取 ETH 历史 K 线(多数据源备选)"""
import requests
import pandas as pd
import time
import os

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# OKX 的 bar 名映射
OKX_INTERVAL = {"1h": "1H", "4h": "4H", "1d": "1D"}

def fetch_okx(instId="ETH-USDT", bar="1H", limit=300, after=None):
    """OKX 历史 K 线,每次最多 300 根"""
    url = "https://www.okx.com/api/v5/market/history-candles"
    params = {"instId": instId, "bar": bar, "limit": limit}
    if after:
        params["after"] = after
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "0":
        raise RuntimeError(f"OKX error: {j}")
    return j["data"]

def fetch_history_okx(instId, bar, bars_needed):
    all_rows = []
    after = None
    while len(all_rows) < bars_needed:
        data = fetch_okx(instId, bar, 300, after)
        if not data:
            break
        all_rows.extend(data)
        after = data[-1][0]  # 最旧那根的时间戳
        time.sleep(0.15)
        if len(data) < 300:
            break
    # OKX 返回 [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
    cols = ["ts","open","high","low","close","volume","volCcy","volCcyQuote","confirm"]
    df = pd.DataFrame(all_rows, columns=cols)
    df["timestamp"] = pd.to_datetime(df["ts"].astype(int), unit="ms")
    for c in ["open","high","low","close","volume"]:
        df[c] = df[c].astype(float)
    df = df[["timestamp","open","high","low","close","volume"]]
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
    return df

if __name__ == "__main__":
    # OKX 对历史 K 线有限制,尽量多拉
    targets = [
        ("1h", "1H", 8000),   # 约 11 个月
        ("4h", "4H", 4000),   # 约 1.8 年
        ("1d", "1D", 1500),   # 约 4 年
    ]
    for short, bar, bars in targets:
        print(f"Fetching ETH {bar} (~{bars} bars)...")
        try:
            df = fetch_history_okx("ETH-USDT", bar, bars)
            out = os.path.join(OUT_DIR, f"ethusdt_{short}.csv")
            df.to_csv(out, index=False)
            print(f"  {len(df)} rows: {df['timestamp'].min()} -> {df['timestamp'].max()}")
        except Exception as e:
            print(f"  FAILED: {e}")
