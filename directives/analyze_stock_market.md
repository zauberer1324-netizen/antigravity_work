# Directive: Analyze Stock Market

## Goal
한국(KOSPI, KOSDAQ) 및 미국(S&P 500, NASDAQ) 주식 시장의 주요 지표를 수집하고, 전체적인 시장 흐름 분석, 섹터별 요약, 상세 내역 및 추천 분야/종목을 마크다운 형태의 보고서로 생성합니다.

## Inputs
이 작업은 분석할 데이터가 필요합니다.
- 한국 증시 및 미국 증시의 주요 지수, 환율, VIX 등 거시 경제 지표 데이터
- 추천 섹터 및 관련 종목 리스트

## Execution Tools
다음 실행 스크립트를 순서대로 사용하여 데이터를 확보하고 보고서를 작성해야 합니다.

**1. Data Fetching**
- 스크립트: `execution/fetch_market_data.py`
- 역할: 최근 주식 시장 데이터(미국/한국 시장 지표, 환율 등)를 가져와 `.tmp/market_data.json` 에 저장합니다.

**2. Orchestration & Analysis Pipeline**
- 스크립트: `execution/generate_report_llm.py`
- 환각을 방지하고 정확한 정보를 제공하기 위해 다음 4단계 파이프라인으로 보고서를 생성합니다:
  1. **데이터 수집 (Orchestrator)**: Gemini Search를 활용하여 지정된 시간 범위(전일 07:00~금일 07:00, 월요일은 지난주 월요일 07:00~금일 07:00)의 시황, 뉴스, 종목 후보(섹터별 3종목 중 2종목 국내/1종목 미국)를 JSON 형태로 수집합니다.
  2. **검증 (Validator)**: Python `yfinance` 라이브러리와 Gemini 보조 프롬프트를 사용하여 종목의 실제 상장 여부(종목코드, 현재가)를 검증합니다.
  3. **정리 (Summarizer)**: 검증된 데이터(상장 확인된 종목만 포함)를 바탕으로 프리미엄 HTML 형태의 보고서를 생성합니다.
  4. **최종 검수 (Reviewer)**: 출처 유무, 상장 미확인 종목 포함 여부, 데이터 최신성 등을 엄격히 평가하여 통과 여부를 결정하고 검토 결과를 보고서에 반영합니다.

**3. Report Generation**
- `generate_report_llm.py` 실행 시 `.tmp/report.html`에 결과가 자동 생성됩니다.
- 생성된 보고서는 모던한 CSS가 적용된 HTML 양식이어야 합니다.
- (필요 시) 에이전트는 스크립트 실행 결과를 확인하여 정상 생성되었는지 검토할 수 있습니다.

## Edge Cases
- 만약 `fetch_market_data.py`가 실패할 경우 기초 지표 없이 Gemini Search 데이터만으로 1단계를 진행합니다.
- 최종 검수 단계에서 `pass: false`가 반환되더라도 보고서 상단에 경고 배너를 띄워 내용을 확인할 수 있도록 합니다.
- API 호출 제한이나 타임아웃 발생 시 에러 로그를 확인하고 조치합니다.
