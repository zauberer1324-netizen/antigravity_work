import os
import json
from datetime import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv

def main():
    # .env 파일 로드
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY가 설정되지 않았습니다.")
        return

    client = genai.Client(api_key=api_key)

    # 기초 시장 데이터 로드
    tmp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.tmp')
    market_data_path = os.path.join(tmp_dir, 'market_data.json')
    
    try:
        with open(market_data_path, 'r', encoding='utf-8') as f:
            market_data = json.load(f)
    except Exception as e:
        print(f"시장 데이터를 불러오는데 실패했습니다: {e}")
        market_data = "데이터 없음"

    print("Gemini API로 리포트 생성을 시작합니다. (Google Search 연동 중...)")

    now = datetime.now()
    is_monday = now.weekday() == 0

    if is_monday:
        timeframe_instruction = f"[시간 요건] 현재 시각은 {now.strftime('%Y년 %m월 %d일 %H시 %M분')}입니다. 오늘은 월요일이므로, 주말을 포함하여 지난 일주일(최근 7일) 동안의 핵심 뉴스 및 증시 동향을 종합해서 분석해 주세요."
    else:
        timeframe_instruction = f"[시간 요건] 현재 시각은 {now.strftime('%Y년 %m월 %d일 %H시 %M분')}입니다. 반드시 작성 시점 기준 최근 24시간 이내의 실시간 뉴스 및 증시 데이터를 바탕으로 분석해 주세요."

    prompt = f"""
다음은 오늘 주식 시장의 기초 지표 데이터입니다.
{json.dumps(market_data, ensure_ascii=False, indent=2)}

{timeframe_instruction}
이를 바탕으로, 구글 검색 기능을 적극 활용하여 주식 시장에 대한 3페이지 분량의 심층 보고서를 만들어주세요.

[디자인 요구사항]
- 보고서 양식은 무조건 HTML 파일 형태로 작성되어야 합니다.
- 내부에 `<style>` 태그를 사용하여 아주 예쁘고 모던한 프리미엄 디자인(그라데이션 배경, 그림자 효과를 넣은 카드 UI, 가독성 높은 폰트 등)을 적용해 주세요.
- CSS를 활용해 시각적으로 유려하게 만들어야 하며, 마크다운(Markdown) 문법을 사용하지 말고 순수 HTML 태그만 반환하세요.
- 출력 시작과 끝에 ```html 등의 코드블록 문법을 넣지 마세요. 오직 HTML 태그만 반환하세요.

[내용 요구사항]
1. 주식 시장을 움직일만한 최신 핵심 뉴스
2. 주요 증권사 및 기관/외국인 매매 동향 요약
3. 테마 강세 분석 및 주요 섹터 동향
4. 위의 분석을 기반으로 하는 추천 섹터 2개와 각 섹터별 추천 종목 3개 (총 6개 종목). 단, 분석 과정에서 모든 동향이나 미국 증시를 반영하더라도 추천 종목 자체는 국내 주식을 위주로 선정하세요. 각 섹터별 3개의 추천 종목 중 2개는 국내 주식, 1개는 미국 주식으로 구성해 주세요.
5. 추천 근거 자료를 시각적인 표(HTML Table)와 그래프(HTML/CSS로 구현한 바 차트 등) 형태로 제시
6. 각 추천 종목에 대한 상세한 추천 이유, 최근 재무제표 핵심 요약, 그리고 향후 성장성 등 회사 분석 포함
"""

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7
        )
    )

    output_html = response.text
    
    # 만약 AI가 마크다운 코드블록을 넣었다면 제거
    if output_html.strip().startswith("```html"):
        output_html = output_html.strip()[7:]
    if output_html.strip().endswith("```"):
        output_html = output_html.strip()[:-3]

    report_path = os.path.join(tmp_dir, 'report.html')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(output_html.strip())
        
    print(f"프리미엄 HTML 리포트가 성공적으로 생성되었습니다: {report_path}")

if __name__ == "__main__":
    main()
