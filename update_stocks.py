import requests
import json

def fetch_and_filter_stocks():
    print("🏹 正在從 TradingView 獲取優質港股名單...")
    
    # TradingView 港股篩選器 API 網址
    url = "https://scanner.tradingview.com/hongkong/scan"
    
    # 設定篩選 Payload (這就是你在 TV 網頁版設定的條件)
    payload = {
        "filter": [
            # 條件 1: 市值 > 10,000,000,000 (100億)
            {"left": "market_cap_basic", "operation": "greater", "right": 10000000000},
            # 條件 2: 每股收益 (TTM) > 0
            {"left": "earnings_per_share_basic_ttm", "operation": "greater", "right": 0},
            # 條件 3: 標的類型必須是股票 (Stock) 或 普通股 (Common Stock)
            {"left": "type", "operation": "in_range", "right": ["stock", "outright"]},
            {"left": "subtype", "operation": "in_range", "right": ["common", "foreign-issuers"]}
        ],
        "options": {"lang": "zh"},
        "markets": ["hongkong"],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["name", "description", "market_cap_basic", "earnings_per_share_basic_ttm"],
        "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
        "range": [0, 1000] # 一次最多抓取 1000 隻符合條件的標的
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        raw_results = data.get('data', [])
        stock_list = []

        for item in raw_results:
            # TV 回傳的代碼通常是 "700" 或 "1211"
            # 我們需要轉換成 yfinance 格式 "0700.HK"
            ticker_num = item['s'].split(':')[-1]
            
            # 港股代碼補零邏輯 (例如 700 -> 0700)
            if ticker_num.isdigit() and len(ticker_num) < 5:
                formatted_ticker = f"{ticker_num.zfill(4)}.HK"
            else:
                # 處理一些特殊的非數字代碼 (如果有)
                formatted_ticker = f"{ticker_num}.HK"
                
            name = item['d'][1] # 取得公司名稱
            stock_list.append(f"{formatted_ticker} # {name}")

        # 寫入 stocks.txt
        if stock_list:
            with open('stocks.txt', 'w', encoding='utf-8') as f:
                for s in stock_list:
                    f.write(s + '\n')
            
            print("-" * 30)
            print(f"✅ 成功更新！")
            print(f"📊 篩選結果：共 {len(stock_list)} 隻港股符合條件。")
            print(f"📁 已寫入到：stocks.txt")
            print("-" * 30)
        else:
            print("⚠️ 找不到符合條件的股票，請檢查篩選參數。")

    except Exception as e:
        print(f"❌ 發生錯誤: {e}")

if __name__ == "__main__":
    fetch_and_filter_stocks()
