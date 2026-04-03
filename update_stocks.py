import requests
import json
import argparse
import sys
from datetime import datetime

# ── 設定 ──────────────────────────────────────────────────────────────────────
TV_SCREENER_URL = "https://scanner.tradingview.com/hongkong/scan"

HKD_PER_USD   = 7.8           # 大約匯率，TV 市值單位是 USD
MIN_MARKET_CAP_HKD = 10_000_000_000          # 100 億港元
MIN_MARKET_CAP_USD = MIN_MARKET_CAP_HKD / HKD_PER_USD  # ≈ 12.82 億 USD

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
    "Origin":  "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
}

# ── TradingView Screener Payload ───────────────────────────────────────────────
def build_payload(offset: int = 0, limit: int = 500) -> dict:
    return {
        "filter": [
            # 市值 > 100 億港元（USD 計）
            {
                "left": "market_cap_basic",
                "operation": "greater",
                "right": MIN_MARKET_CAP_USD
            },
            # EPS TTM > 0（盈利公司）
            {
                "left": "earnings_per_share_basic_ttm",
                "operation": "greater",
                "right": 0
            },
            # 主要上市（排除 H 股在香港的二次上市）
            {
                "left": "is_primary",
                "operation": "equal",
                "right": True
            },
        ],
        "options": {
            "lang": "en"
        },
        "markets": ["hongkong"],
        "symbols": {
            "query": {"types": ["stock"]},
            "tickers": []
        },
        "columns": [
            "name",                          # 代碼 e.g. "700"
            "description",                   # 公司名稱
            "close",                         # 現價 (HKD)
            "market_cap_basic",              # 市值 (USD)
            "earnings_per_share_basic_ttm",  # EPS TTM
            "exchange",                      # 交易所
            "is_primary",                    # 主要上市
            "sector",                        # 行業
        ],
        "sort": {
            "sortBy": "market_cap_basic",
            "sortOrder": "desc"
        },
        "range": [offset, offset + limit]
    }

# ── 抓取所有結果（自動翻頁）─────────────────────────────────────────────────
def fetch_all(max_results: int = 2000) -> list[dict]:
    all_rows = []
    batch    = 500
    offset   = 0

    print(f"🔍 連接 TradingView Screener...")
    print(f"   篩選：主要上市 HK | 市值 > {MIN_MARKET_CAP_HKD/1e8:.0f} 億港元 | EPS > 0\n")

    while offset < max_results:
        payload = build_payload(offset=offset, limit=batch)
        try:
            resp = requests.post(
                TV_SCREENER_URL,
                headers=HEADERS,
                json=payload,
                timeout=20
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"❌ 請求失敗（offset={offset}）：{e}")
            break

        data       = resp.json()
        total      = data.get("totalCount", 0)
        rows       = data.get("data", [])

        if not rows:
            break

        all_rows.extend(rows)
        fetched = len(all_rows)
        print(f"   已取得 {fetched}/{total} 筆...")

        if fetched >= total:
            break
        offset += batch

    return all_rows

# ── 解析 & 轉換 ───────────────────────────────────────────────────────────────
def parse_rows(rows: list[dict]) -> list[dict]:
    results = []
    for row in rows:
        d = row.get("d", [])
        if len(d) < 8:
            continue

        name, desc, close, mktcap_usd, eps, exchange, is_primary, sector = (
            d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7]
        )

        # 代碼補零到 4 位並加 .HK（TV 給的是純數字字串如 "700"）
        try:
            ticker_hk = f"{int(name):04d}.HK"
        except (ValueError, TypeError):
            ticker_hk = f"{name}.HK"

        mktcap_hkd = (mktcap_usd or 0) * HKD_PER_USD

        results.append({
            "ticker":      ticker_hk,
            "name":        desc or "",
            "price":       round(close or 0, 3),
            "mktcap_hkd":  round(mktcap_hkd / 1e8, 1),  # 億港元
            "eps":         round(eps or 0, 4),
            "sector":      sector or "",
        })

    return results

# ── 寫入 stocks.txt ──────────────────────────────────────────────────────────
def write_stocks_txt(results: list[dict], path: str = "stocks.txt"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# 自動生成 by update_stocks.py  |  更新時間：{now}",
        f"# 篩選：主要上市 HK | 市值 > {MIN_MARKET_CAP_HKD/1e8:.0f} 億港元 | EPS TTM > 0",
        f"# 共 {len(results)} 隻",
        "",
    ]
    for r in results:
        lines.append(
            f"{r['ticker']:<12}"
            f"# {r['name']:<30} "
            f"市值:{r['mktcap_hkd']:>8.1f}億  "
            f"EPS:{r['eps']:>8.4f}  "
            f"現價:{r['price']:>8.3f}  "
            f"{r['sector']}"
        )

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\n✅ 已寫入 {path}（{len(results)} 隻股票）")

# ── 主程式 ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="更新港股清單 via TradingView Screener")
    parser.add_argument("--dry-run", action="store_true", help="只印出結果，不寫檔案")
    parser.add_argument("--limit",   type=int, default=2000, help="最多取幾隻（預設 2000）")
    parser.add_argument("--output",  default="stocks.txt",   help="輸出檔案路徑")
    args = parser.parse_args()

    rows    = fetch_all(max_results=args.limit)
    results = parse_rows(rows)

    if not results:
        print("⚠️  沒有取得任何結果，請檢查網路或 TradingView 是否更改了 API")
        sys.exit(1)

    # 印出摘要
    print(f"\n{'─'*60}")
    print(f"{'代碼':<12} {'公司':<28} {'市值(億)':<10} {'EPS':>8}  {'現價':>8}")
    print(f"{'─'*60}")
    for r in results[:20]:  # 只預覽前 20 筆
        print(
            f"{r['ticker']:<12} {r['name'][:26]:<28} "
            f"{r['mktcap_hkd']:>8.1f}億  "
            f"{r['eps']:>8.4f}  "
            f"{r['price']:>8.3f}"
        )
    if len(results) > 20:
        print(f"  ... 還有 {len(results)-20} 隻（完整列表見 {args.output}）")
    print(f"{'─'*60}")
    print(f"合計：{len(results)} 隻符合條件")

    if args.dry_run:
        print("\n[dry-run 模式] 不寫入檔案")
    else:
        write_stocks_txt(results, path=args.output)

if __name__ == "__main__":
    main()
