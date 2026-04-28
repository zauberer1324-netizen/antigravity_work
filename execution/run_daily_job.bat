@echo off
echo =======================================
echo 주식 시장 리포트 생성 작업을 시작합니다.
echo =======================================

cd /d "%~dp0"

echo [1/3] 시장 기초 지표를 가져오는 중...
python fetch_market_data.py

echo [2/3] Gemini API를 통해 AI HTML 리포트를 생성하는 중 (시간이 소요됩니다)...
python generate_report_llm.py

echo [3/3] 슬랙으로 리포트를 전송하는 중...
python send_to_slack.py

echo =======================================
echo 모든 작업이 완료되었습니다.
echo =======================================
