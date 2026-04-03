import requests
import json

def update_hk_stocks():
    print("🚀 正在從 TradingView 獲取符合條件的港股清單...")
    
    # TradingView 篩選器 API URL
    url = "https://scanner.tradingview.com/hongkong/scan"
    
    # 設定篩選條件 (Scan JSON Payload)
    payload = {
        "filter": [
            {"left": "market_cap_basic", "operation": "greater", "right": 10000000000}, # 市值 > 10B
            {"left": "earnings_per_share_basic_ttm", "operation": "greater", "right": 0}, # EPS > 0
            {"left": "type", "operation": "in_range", "right": ["stock", "outright"]}, # 主要上市股票
            {"left": "subtype", "operation": "in_range", "right": ["common"]} # 普通股
        ],
        "options": {"lang": "zh"},
        "markets": ["hongkong"],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["logoid", "name", "description", "market_cap_basic", "earnings_per_share_basic_ttm"],
        "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
        "range": [0, 500] # 最多抓取前 500 隻符合條件的股票
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        stocks_found = []
        for item in data.get('data', []):
            # TradingView 的格式是 "HKEX:700"，我們需要轉換成 "0700.HK"
            raw_ticker = item['s'].split(':')[-1]
            
            # 格式化代碼：如果是數字且長度小於 4，補零至 4 位 (例如 5 -> 0005)
            if raw_ticker.isdigit():
                formatted_ticker = f"{raw_ticker.zfill(4)}.HK"
            else:
                formatted_ticker = f"{raw_ticker}.HK"
                
            company_name = item['d'][2] # description
            stocks_found.append(f"{formatted_ticker} # {company_name}")

        # 寫入 stocks.txt
        if stocks_found:
            with open('stocks.txt', 'w', encoding='utf-8') as f:
                for s in stocks_found:
                    f.write(s + '\n')
            print(f"✅ 成功更新！共找到 {len(stocks_found)} 隻符合條件的股票。")
            print("📁 已儲存至 stocks.txt")
        else:
            print("⚠️ 未找到符合條件的股票。")

    except Exception as e:
        print(f"❌ 發生錯誤: {e}")

if __name__ == "__main__":
    update_hk_stocks()
