# -*- coding: utf-8 -*-

# LineBot to search nearest GoStation, calculate ETA and distance.

import ast

from flask import Flask, request
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.models import (
    LocationSendMessage, TextSendMessage
)

import gogoro_scraper

app = Flask(__name__)

line_bot_api = LineBotApi('') # YOUR_CHANNEL_ACCESS_TOKEN
handler = WebhookHandler('') # YOUR_CHANNEL_SECRET


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    json_body = ast.literal_eval(body)
    print(json_body)
    user_id = json_body['events'][0]['source']['userId']
    display_name = line_bot_api.get_profile(user_id).display_name
    message = json_body['events'][0]['message']
    address = message.get('address')
    lat = message.get('latitude')
    lon = message.get('longitude')
    reply_token = json_body['events'][0]['replyToken']
    # print(display_name, address, lat, lon)

    app.logger.info("Request body: " + body)

    # handle webhook body
    if lat and lon:
        nerest_vm_info = gogoro_scraper.vm_finder(gogoro_scraper.gogoro_gf_id, lat, lon)
        if nerest_vm_info:
            # print(nerest_vm_info)
            nerest_vm_name = nerest_vm_info[0]
            nerest_vm_add = nerest_vm_info[1]
            nerest_vm_lat = nerest_vm_info[2]
            nerest_vm_lon = nerest_vm_info[3]
            nerest_vm_eta = nerest_vm_info[4]
            nerest_vm_dot = nerest_vm_info[5]
            nerest_vm_maneuvers = nerest_vm_info[6]
            body = (TextSendMessage(
                text='親愛的{}：已為您找到最接近的GoStation為「{}」，車程約{}。'.format(display_name, nerest_vm_name, nerest_vm_eta)),
                    LocationSendMessage(
                        title=nerest_vm_name, address=nerest_vm_add, latitude=nerest_vm_lat, longitude=nerest_vm_lon
                    ), TextSendMessage(
                text='路徑規劃：https://wego.here.com/directions/mix/{},{}/{},{}'.format(lat, lon, nerest_vm_lat,
                                                                                    nerest_vm_lon)))
            line_bot_api.reply_message(reply_token, body)
        else:
            line_bot_api.reply_message(reply_token, TextSendMessage(
                text='很抱歉，找不到附近的GoStation或您不在GoStation的服務範圍內。'))
    else:
        line_bot_api.reply_message(reply_token, TextSendMessage(text='請傳送「位置資訊」來查詢最近的GoStation，謝謝！'))
    return 'ok'


if __name__ == "__main__":
    app.run()
