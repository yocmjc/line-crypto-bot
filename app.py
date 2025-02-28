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

app = Flask(__name__)

# 設定 Line Bot API
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

FEAR_GREED_API = 'https://api.alternative.me/fng/'

@app.route('/')
def home():
    return 'Line Bot is running!'

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
                'value': value,
                'classification': classification,
                'date': date.strftime('%Y-%m-%d %H:%M:%S')
            }
    except Exception as e:
        print(f"獲取恐懼貪婪指數時發生錯誤: {e}")
        return None

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
    text = event.message.text.lower()
    
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
        message = TextSendMessage(text="您好！我是加密貨幣恐懼貪婪指數機器人\n輸入「指數」查看最新數據\n輸入「說明」查看使用說明")
    
    line_bot_api.reply_message(event.reply_token, message)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port) 