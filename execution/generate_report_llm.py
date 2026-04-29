import os
import json
import re
import time
from datetime import datetime, timedelta
import yfinance as yf
from google import genai
from google.genai import types
from dotenv import load_dotenv

def get_time_range():
    now = datetime.now()
    # 당일 07:00 계산
    today_7am = now.replace(hour=7, minute=0, second=0, microsecond=0)
    
    # 만약 현재 시각이 07:00 이전이라면, "오늘" 07:00은 어제의 07:00이 되어야 함
    if now < today_7am:
        today_7am = today_7am - timedelta(days=1)
        
    is_monday = today_7am.weekday() == 0
    
    if is_monday:
        # 월요일인 경우: 지난주 월요일 아침 7시부터
        start_time = today_7am - timedelta(days=7)
    else:
        # 그 외: 전날 아침 7시부터
        start_time = today_7am - timedelta(days=1)
        
    return start_time, today_7am, is_monday

def generate_with_retry(client, model, contents, config, retries=5):
    for attempt in range(retries):
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
        except Exception as e:
            print(f"API 호출 에러 발생 (시도 {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                wait_time = 60 * (2 ** attempt)
                print(f"{wait_time}초 대기 후 재시도합니다...")
                time.sleep(wait_time)
            else:
                raise

def get_yfinance_news():
    # 주요 지수의 최근 뉴스 수집 (외부 뉴스 API 연동 역할)
    news_items = []
    try:
        tickers = ["^KS11", "^GSPC"]
        for t in tickers:
            ticker = yf.Ticker(t)
            news = ticker.news
            if news:
                for n in news[:3]: # 각 지수당 최신 3개 뉴스
                    news_items.append({
                        "title": n.get("title", ""),
                        "publisher": n.get("provider", {}).get("displayName", ""),
                        "link": n.get("link", n.get("providerContentUrl", ""))
                    })
    except Exception as e:
        print("Yahoo Finance 뉴스 수집 실패:", e)
    return news_items

def main():
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY가 설정되지 않았습니다.")
        return

    client = genai.Client(api_key=api_key)
    
    tmp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.tmp')
    os.makedirs(tmp_dir, exist_ok=True)
    
    # fetch_market_data.py 에서 수집한 기본 시세 데이터 로드
    try:
        with open(os.path.join(tmp_dir, 'market_data.json'), 'r', encoding='utf-8') as f:
            base_market_data = json.load(f)
    except Exception as e:
        base_market_data = {"error": "시장 데이터를 찾을 수 없음"}

    start_time, end_time, is_monday = get_time_range()
    time_str = f"수집 범위: {start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}"
    print(time_str)

    api_news = get_yfinance_news()

    # 1. 데이터 수집 (Orchestrator)
    print("1단계: 데이터 수집 중 (Google Search 및 외부 News API 연동)...")
    
    orchestrator_prompt = f"""
당신은 주식시장 보고서 작성용 오케스트레이터이다.
목표는 “그럴듯한 투자 보고서”가 아니라, 수집된 자료 안에서 검증 가능한 사실만 사용하여 신뢰도 높은 보고서를 만드는 것이다.

다음 원칙을 반드시 따른다.
1. 제공된 자료에 없는 사실은 절대 추론해서 만들지 않는다.
2. 모든 시장 수치, 뉴스, 종목명, 재무 수치, 추천 근거에는 반드시 출처 URL과 작성일 또는 기준일이 있어야 한다.
3. 출처가 없거나 날짜가 불명확한 정보는 사용하지 않는다.
4. 종목 추천 전 반드시 해당 기업이 실제 상장사인지 확인한다.
5. 상장 여부 확인에는 종목코드, 거래소, 공식 종목명, 국가, 시장 구분을 포함해야 한다.
6. 실제 상장사로 확인되지 않은 기업은 추천종목에서 제외하고 “상장 여부 확인 실패”로 분류한다.
7. 동일한 핵심 주장에 대해 가능하면 2개 이상의 독립 출처를 요구한다.
8. 공식 출처를 최우선으로 사용한다. (거래소, 공시, 규제기관 우선)
9. 최신성 기준을 명시한다.
   - 지수/환율/시세: 당일 또는 직전 거래일
   - 뉴스: 최근 7일 이내 우선
   - 재무제표: 최근 분기 또는 연간 공시 기준
   - 산업 전망: 최근 6개월 이내 자료 우선
10. 불확실한 내용은 확정적으로 쓰지 말고 “확인 불가”, “자료 부족”, “추가 검증 필요”, “상장사로 확인되지 않아 제외”로 표시한다.
11. 추천종목은 투자 권유가 아니라 분석 후보로 표현한다.
12. 보고서 마지막에는 반드시 “엄격 검토” 섹션을 포함한다.
13. 엄격 검토 섹션에는 출처 없는 주장, 기준일 불명확 수치, 상장여부 미확인 종목, 뉴스와 시장 해석 연결 과도 여부, 최종 신뢰도 등급을 포함한다.
14. 모든 정보들에는 정보의 발단 시간(최초 뉴스보고 등)을 같이 적어준다.

절대 금지:
- 존재하지 않는 기업명 생성
- 임의의 현재가, 시가총액, 매출액, 영업이익 생성
- 출처 없는 “전망”, “수혜”, “급등 예상” 작성
- “AI”, “반도체”, “친환경” 같은 테마만 보고 종목을 추천
- 이름이 비슷한 회사를 같은 회사로 간주
- 미확인 기업을 실제 상장사처럼 설명

[수집 및 분석 요구사항]
1. 시간 범위: {start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}
해당 기간 내의 주요 뉴스 및 증시 동향을 구글 검색을 활용하여 수집하라.
아래 외부 API(Yahoo Finance)로 수집된 기초 시장 데이터와 뉴스도 함께 참고하라.
기초 시장 데이터: {json.dumps(base_market_data, ensure_ascii=False)}
외부 API 최신 뉴스: {json.dumps(api_news, ensure_ascii=False)}

2. 2개의 테마(섹터)를 선정하고, 각 섹터별 3개의 추천 종목(총 6개 종목)을 발굴하라.
섹터별 3개 종목 중 2개는 한국 국내 주식, 1개는 미국 주식으로 반드시 맞출 것.

반드시 아래의 JSON 형식으로만 응답하라 (다른 마크다운 텍스트 불가).
{{
  "run_date": "{end_time.strftime('%Y-%m-%d')}",
  "market_data": [
    {{
      "type": "index",
      "name": "KOSPI",
      "value": 2600.00,
      "change_percent": 0.5,
      "date": "2026-04-28",
      "source_name": "KRX",
      "source_url": "...",
      "source_id": "market_001"
    }}
  ],
  "news": [
    {{
      "title": "뉴스 제목",
      "published_at": "YYYY-MM-DDTHH:MM:SS",
      "source_name": "출처",
      "source_url": "...",
      "summary": "...",
      "related_sectors": ["반도체"],
      "source_id": "news_001"
    }}
  ],
  "stocks": [
    {{
      "input_name": "검색된 종목명",
      "official_name": "공식 종목명",
      "ticker": "종목코드(예: 005930 또는 AAPL)",
      "exchange": "KRX/NASDAQ/NYSE 등",
      "country": "KR/US 등",
      "verified_listed": true,
      "verification_source": "출처",
      "verification_url": "...",
      "price": 0,
      "price_date": "...",
      "reason": "추천 사유",
      "risk": "리스크 요소",
      "source_id": "stock_001"
    }}
  ]
}}
"""

    response_1 = generate_with_retry(
        client=client,
        model='gemini-2.5-flash',
        contents=orchestrator_prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            top_p=0.3,
            tools=[{"google_search": {}}]
        )
    )

    try:
        data = json.loads(response_1.text)
    except Exception as e:
        print("JSON 파싱 에러:", e)
        json_match = re.search(r'```json\n(.*?)\n```', response_1.text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(1))
        else:
            print("응답이 올바른 JSON이 아닙니다.")
            return

    # 2. 검증 (Validation)
    print("2단계: 외부 거래소 API(Yahoo Finance)를 통한 종목 상장 여부 검증 중...")
    stocks = data.get("stocks", [])
    for stock in stocks:
        ticker = stock.get("ticker")
        if not ticker:
            stock["verified_listed"] = False
            stock["reason"] = "종목코드 없음"
            continue
            
        yf_ticker = str(ticker)
        if stock.get("country") == "KR":
            # yfinance 한국 종목 티커 처리
            if not (yf_ticker.endswith(".KS") or yf_ticker.endswith(".KQ")):
                if stock.get("exchange") in ["KOSDAQ", "코스닥"]:
                    yf_ticker += ".KQ"
                else:
                    yf_ticker += ".KS"
        
        # yfinance 확인
        try:
            info = yf.Ticker(yf_ticker).info
            if "shortName" in info or "longName" in info:
                stock["verified_listed"] = True
                if "currentPrice" in info:
                    stock["price"] = info["currentPrice"]
            else:
                stock["verified_listed"] = False
                stock["reason"] = f"yfinance에서 {yf_ticker}에 대한 이름 정보 없음"
        except Exception:
            stock["verified_listed"] = False
            stock["reason"] = f"yfinance 티커({yf_ticker}) 조회 실패"

    # LLM을 통한 2차 검증 (배치 처리)
    stocks_to_verify = [s for s in stocks if s.get("ticker")]
    if stocks_to_verify:
        print("LLM을 통한 2차 검증 진행 중 (배치 처리)...")
        verify_prompt = f"""
다음 종목들이 실제 상장사인지 검증하라.
입력 종목 목록:
{json.dumps(stocks_to_verify, ensure_ascii=False, indent=2)}

검증 기준:
1. 공식 종목명
2. 종목코드 또는 티커
3. 거래소
4. 국가
5. 상장 여부 확인 출처
6. 회사명 유사성 위험

출력 규칙:
- 정확히 일치하는 상장사가 있으면 verified_listed = true
- 이름이 비슷하지만 다른 회사이면 verified_listed = false
- 검색 결과가 불충분하면 verified_listed = unknown

절대 금지:
- 이름이 비슷하다는 이유만으로 같은 회사로 판단
- 비상장사, 자회사, 브랜드, 제품명을 상장사로 판단
- 종목코드 없는 기업을 추천종목으로 사용

결과를 아래 JSON 배열로 반환하라.
[
  {{
    "ticker": "입력받은 종목코드",
    "verified_listed": true/false,
    "reason": "사유"
  }}
]
"""
        response_v = generate_with_retry(
            client=client,
            model='gemini-2.5-flash',
            contents=verify_prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                top_p=0.3,
                response_mime_type="application/json"
            )
        )
        try:
            v_data_list = json.loads(response_v.text)
            v_data_map = {{item.get("ticker"): item for item in v_data_list if isinstance(item, dict)}}
            
            for stock in stocks:
                ticker = stock.get("ticker")
                if ticker and ticker in v_data_map:
                    v_item = v_data_map[ticker]
                    if str(v_item.get("verified_listed")).lower() != "true":
                        stock["verified_listed"] = False
                        stock["reason"] = v_item.get("reason", "LLM 검증 실패")
        except Exception as e:
            print("LLM 배치 검증 실패:", e)

    # 3. Gemini 정리 단계
    print("3단계: 보고서 정리 중...")
    summary_prompt = f"""
아래 입력 데이터만 사용하여 주식시장 보고서를 작성하라.

입력 데이터:
{json.dumps(data, ensure_ascii=False, indent=2)}

중요:
- 제공된 입력 데이터에 없는 사실은 절대 생성하지 마라.
- 모든 수치와 주장은 반드시 입력 데이터의 source_id를 인용하라.
- source_id가 없는 정보는 사용하지 마라.
- 날짜가 없는 정보는 최신 정보로 취급하지 마라.
- 상장 여부가 verified_listed = true 인 종목만 분석 후보에 포함하라.
- verified_listed = false 또는 unknown인 종목은 추천 후보에서 제외하라.

보고서 구조:
1. 작성 기준 (작성일, 시장 데이터 기준일, 뉴스 기준 기간, 사용한 주요 출처 수)
2. 시장 요약 (국내/미국 지수, 환율, 금리/원자재 - 각 수치 기준일 및 출처 표시)
3. 핵심 뉴스 (제목, 작성일, 출처, 시장 영향, 관련 섹터, 확실도)
4. 수급 및 섹터 분석 (외국인/기관/개인 수급, 강세/약세 섹터, 출처 표시)
5. 분석 후보 종목 (공식 종목명, 종목코드, 거래소, 상장 여부 출처, 현재가 기준일, 선정 근거, 리스크, 사용된 출처 목록)
6. 제외 종목 (상장 확인 실패, 출처 부족 등 사유 명시)
7. 엄격 검토 (출처 없는 주장 여부, 기준일 없는 수치 여부, 상장 미확인 종목 포함 여부, 뉴스 연결 과도성, 최종 신뢰도 등급)

[디자인 요구사항]
- 보고서 양식은 무조건 HTML 파일 형태로 작성되어야 합니다.
- 내부에 `<style>` 태그를 사용하여 그라데이션 배경, 그림자 효과를 넣은 카드 UI 등 매우 예쁘고 모던한 프리미엄 디자인을 적용해 주세요.
- CSS를 활용해 시각적으로 유려하게 만들어야 하며, 마크다운 문법 대신 순수 HTML 태그만 반환하세요.
- 출력에 ```html 등 코드블록을 넣지 마세요.
"""
    response_3 = generate_with_retry(
        client=client,
        model='gemini-2.5-flash',
        contents=summary_prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            top_p=0.3
        )
    )
    
    html_report = response_3.text
    if html_report.strip().startswith("```html"):
        html_report = html_report.strip()[7:]
    if html_report.strip().endswith("```"):
        html_report = html_report.strip()[:-3]

    # 4. 최종 검수
    print("4단계: 최종 검수 중...")
    review_prompt = f"""
작성된 보고서를 검수하라.

보고서 내용:
{html_report}

다음 항목을 엄격히 확인하라.
1. 모든 지수·환율·주가 수치에 기준일이 있는가?
2. 모든 뉴스에 작성일과 URL이 있는가?
3. 추천종목이 모두 실제 상장사인가?
4. 추천종목마다 종목코드와 거래소가 있는가?
5. 출처 없는 재무 수치가 있는가?
6. 존재하지 않는 회사명이나 가상의 회사명이 포함되었는가?
7. 시장 해석이 뉴스 근거보다 과장되었는가?
8. 투자 권유처럼 표현된 문장이 있는가?

문제가 있으면 아래 형식으로 반환하라.

{{
  "pass": true/false,
  "critical_errors": [],
  "minor_errors": [],
  "remove_sections": [],
  "required_fixes": [],
  "final_trust_grade": "A/B/C/D/F"
}}

통과 기준:
- 미상장 또는 확인 불가 종목이 추천종목에 있으면 무조건 fail
- 출처 없는 현재가·시가총액·재무수치가 있으면 무조건 fail
- 작성일이 없는 뉴스가 핵심 근거로 쓰이면 fail
"""
    response_4 = generate_with_retry(
        client=client,
        model='gemini-2.5-flash',
        contents=review_prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            top_p=0.3,
            response_mime_type="application/json"
        )
    )

    try:
        review_data = json.loads(response_4.text)
        is_pass = review_data.get("pass", False)
        print("검수 통과 여부:", is_pass)
        
        # 검수 실패 시 경고 배너 삽입
        if str(is_pass).lower() != "true":
            warning_banner = f"""
            <div style="background-color: #ffdddd; color: #cc0000; padding: 20px; margin: 20px; border-left: 6px solid #cc0000; border-radius: 8px; font-family: sans-serif;">
                <h2 style="margin-top: 0;">⚠️ 엄격 검토 경고 (통과 실패)</h2>
                <p><strong>최종 신뢰도 등급: {review_data.get('final_trust_grade', 'F')}</strong></p>
                <p><strong>치명적 오류:</strong> {', '.join(review_data.get('critical_errors', []))}</p>
                <p><strong>권장 수정 사항:</strong> {', '.join(review_data.get('required_fixes', []))}</p>
                <p>주의: 이 보고서는 검증 요건을 완전히 충족하지 못했습니다.</p>
            </div>
            """
            html_report = warning_banner + html_report
            
    except Exception as e:
        print("최종 검수 파싱 에러:", e)

    report_path = os.path.join(tmp_dir, 'report.html')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html_report.strip())
        
    print(f"보고서가 생성되었습니다: {report_path}")

if __name__ == "__main__":
    main()
