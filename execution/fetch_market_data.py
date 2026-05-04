import yfinance as yf
import json
import os
from datetime import datetime, timedelta

def get_recent_data(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        # 5일치 데이터를 가져와 가장 최근의 유효한 종가를 사용 (주말, 휴일 등 고려)
        hist = ticker.history(period="5d")
        if hist.empty:
            return None
        
        last_close = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2]
        
        change = last_close - prev_close
        change_percent = (change / prev_close) * 100
        
        return {
            "price": round(last_close, 2),
            "change": round(change, 2),
            "change_percent": round(change_percent, 2),
            "date": hist.index[-1].strftime('%Y-%m-%d')
        }
    except Exception as e:
        print(f"Error fetching data for {ticker_symbol}: {e}")
        return None

def fetch_market_data():
    tickers = {
        "S&P500": "^GSPC",
        "NASDAQ": "^IXIC",
        "KOSPI": "^KS11",
        "KOSDAQ": "^KQ11",
        "VIX": "^VIX",
        "USD_KRW": "KRW=X", # USD/KRW 환율
        "WTI_CRUDE_OIL": "CL=F", # 서부텍사스산 원유
        "GOLD": "GC=F", # 금
        "US_10Y_TREASURY": "^TNX" # 미국 10년물 국채 금리
    }

    market_data = {}
    
    for name, symbol in tickers.items():
        data = get_recent_data(symbol)
        if data:
            market_data[name] = data
            
    # 결과를 .tmp 디렉토리에 저장
    tmp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.tmp')
    os.makedirs(tmp_dir, exist_ok=True)
    
    output_file = os.path.join(tmp_dir, 'market_data.json')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(market_data, f, ensure_ascii=False, indent=4)
        
    print(f"Market data successfully saved to {output_file}")

if __name__ == "__main__":
    fetch_market_data()
