import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

def main():
    # .env 파일 로드
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
    
    slack_token = os.getenv("SLACK_BOT_TOKEN")
    channel_id = os.getenv("SLACK_CHANNEL")
    
    if not slack_token or not channel_id:
        print("슬랙 토큰이나 채널 이름이 .env 파일에 없습니다.")
        return

    client = WebClient(token=slack_token)
    
    tmp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.tmp')
    report_path = os.path.join(tmp_dir, 'report.html')
    
    if not os.path.exists(report_path):
        print("업로드할 리포트 파일(report.html)이 존재하지 않습니다.")
        return

    try:
        # 슬랙 파일 업로드 API 호출
        print(f"{channel_id} 채널에 리포트를 전송합니다...")
        # 채널 이름으로 ID 조회 (Slack API v2는 ID를 요구함)
        channel_name = channel_id.replace('#', '')
        actual_channel_id = None
        
        try:
            for page in client.conversations_list(types="public_channel,private_channel"):
                for channel in page["channels"]:
                    if channel["name"] == channel_name:
                        actual_channel_id = channel["id"]
                        break
                if actual_channel_id:
                    break
        except Exception as e:
            print(f"채널 목록 조회 에러: {e}")
            
        if not actual_channel_id:
            print(f"'{channel_name}' 채널을 찾지 못했습니다. 봇이 해당 채널에 초대되어 있는지 확인하세요.")
            # 폴백: 입력된 값을 그대로 시도 (직접 ID를 넣은 경우 대비)
            actual_channel_id = channel_name
            
        result = client.chat_postMessage(
            channel=actual_channel_id,
            text=f"📈 *오늘의 주식 시장 심층 리포트가 완성되었습니다!*\n아래 링크를 클릭하여 예쁜 화면으로 확인하세요.\n\n🔗 https://zauberer1324-netizen.github.io/antigravity_work/"
        )
        print(f"슬랙 전송 성공! (TS: {result.get('ts')})")
        
    except SlackApiError as e:
        print(f"슬랙 파일 업로드 에러: {e.response['error']}")

if __name__ == "__main__":
    main()
