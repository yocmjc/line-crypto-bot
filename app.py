import os
import json
import requests
from datetime import datetime
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    TemplateSendMessage, ButtonsTemplate, MessageAction
)
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

app = Flask(__name__)

# 設定 Line Bot API
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

FEAR_GREED_API = 'https://api.alternative.me/fng/'
USER_ID = os.getenv('LINE_USER_ID', '')  # 您的 Line User ID
taiwan_tz = pytz.timezone('Asia/Taipei')

# 儲存前一次的指數值
last_index_value = None
last_check_time = None
last_notification_date = None

def get_fear_greed_index():
    """獲取恐懼貪婪指數"""
    try:
        response = requests.get(FEAR_GREED_API)
        data = response.json()
        
        if data['data']:
            latest = data['data'][0]
            value = latest['value']
            classification = latest['value_classification']
            timestamp = latest['timestamp']
            date = datetime.fromtimestamp(int(timestamp))
            
            return {
                'value': float(value),
                'classification': classification,
                'date': date.strftime('%Y-%m-%d %H:%M:%S')
            }
    except Exception as e:
        print(f"獲取恐懼貪婪指數時發生錯誤: {e}")
        return None

def send_index_notification():
    """定時發送恐懼貪婪指數"""
    global last_notification_date
    
    if not USER_ID:
        print("未設定 USER_ID，無法發送通知")
        return

    current_date = datetime.now(taiwan_tz).date()
    
    # 檢查是否已經在今天發送過通知
    if last_notification_date == current_date:
        return

    data = get_fear_greed_index()
    if data:
        message = f"⏰ 定時恐懼貪婪指數更新\n數值: {data['value']}\n狀態: {data['classification']}\n時間: {data['date']}"
        try:
            line_bot_api.push_message(USER_ID, TextSendMessage(text=message))
            last_notification_date = current_date
        except Exception as e:
            print(f"發送通知時發生錯誤: {e}")

def check_index_change():
    """檢查指數變化並發送警報"""
    global last_index_value, last_check_time
    
    if not USER_ID:
        return

    current_data = get_fear_greed_index()
    if not current_data:
        return

    current_value = current_data['value']
    current_time = datetime.now(taiwan_tz)

    if last_index_value is not None and last_check_time is not None:
        # 計算變化值
        change = abs(current_value - last_index_value)
        
        # 如果變化超過20，發送警報
        if change >= 20:
            message = (f"⚠️ 恐懼貪婪指數大幅波動！\n"
                      f"當前數值: {current_value}\n"
                      f"前次數值: {last_index_value}\n"
                      f"變化幅度: {change:.1f}\n"
                      f"狀態: {current_data['classification']}\n"
                      f"時間: {current_data['date']}")
            try:
                line_bot_api.push_message(USER_ID, TextSendMessage(text=message))
            except Exception as e:
                print(f"發送警報時發生錯誤: {e}")

    # 更新上次的值和時間
    last_index_value = current_value
    last_check_time = current_time

# 設定定時任務
scheduler = BackgroundScheduler(timezone=taiwan_tz)
# 每天1點、9點、17點發送指數
scheduler.add_job(send_index_notification, CronTrigger(hour='1,9,17', minute='0', timezone=taiwan_tz))
# 每2小時檢查一次指數變化
scheduler.add_job(check_index_change, 'interval', hours=2)
scheduler.start()

@app.route('/')
def home():
    return 'Line Bot is running!'

@app.route('/health')
def health_check():
    return 'OK'

@app.route("/callback", methods=['POST'])
def callback():
    # 獲取 X-Line-Signature header
    signature = request.headers['X-Line-Signature']

    # 獲取請求內容
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global USER_ID
    text = event.message.text.lower()
    
    # 儲存用戶ID（當用戶發送訊息時）
    if not USER_ID:
        USER_ID = event.source.user_id
    
    if text in ['指數', '現在指數', 'index']:
        data = get_fear_greed_index()
        if data:
            message = TextSendMessage(text=f"加密貨幣恐懼貪婪指數\n數值: {data['value']}\n狀態: {data['classification']}\n時間: {data['date']}")
        else:
            message = TextSendMessage(text="抱歉，無法獲取指數資訊，請稍後再試。")
            
    elif text in ['說明', 'help', '幫助']:
        message = TemplateSendMessage(
            alt_text='功能說明',
            template=ButtonsTemplate(
                title='加密貨幣恐懼貪婪指數機器人',
                text='您可以使用以下功能：',
                actions=[
                    MessageAction(
                        label='查看現在指數',
                        text='指數'
                    ),
                    MessageAction(
                        label='顯示說明',
                        text='說明'
                    )
                ]
            )
        )
    else:
        message = TextSendMessage(text="您好！我是加密貨幣恐懼貪婪指數機器人\n輸入「指數」查看最新數據\n輸入「說明」查看使用說明\n\n已開啟功能：\n✅ 每天1點、9點、17點自動發送指數\n✅ 指數大幅波動(≧20)自動警報")
    
    line_bot_api.reply_message(event.reply_token, message)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True) 