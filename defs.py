from binance.client import Client
from settings import *
from defs import *
import json
import time
import numpy as np
import pandas as pd
import surrogates
import datetime
import os.path
import plotly.graph_objects as go
import plotly as plotly
import plotly.express as px

import telebot

# Инициализация Телеграм-бота
bot = telebot.TeleBot(settings['telegram_token'])

# Инициализация клиента Binance-api
client = Client(settings['binance_keys']['api_key'], settings['binance_keys']['secret_key'])

def send_telegram(text: str,img):
    
    channel_id = settings['channel_id']
    with open(img, 'rb') as photo:
        bot.send_photo(channel_id, photo, caption=text)


def update_dataset(coin):
    global settings
    if(os.path.exists("dataset/bars/"+ coin + ".json")):
        with open("dataset/bars/"+ coin + ".json", "r") as read_file:
            data = json.load(read_file)
        now_time = int(time.time())
        start_time = int(data[-1]['open_time'] + 60)*1000
        end_time = int(((now_time) // 60)*60)*1000

        if(end_time - start_time > int(60*60*24*settings['chart_days'])):
            start_time = int(((now_time - 60*60*24*settings['chart_days']) // 60)*60*1000)
        info = []
        while(info == []):
            try:
                info = client.futures_historical_klines(coin,"5m",start_time,end_time)
            except:
                print(coin + ": ошибка запроса")
        info.pop(len(info)-1)
        for j in info:
            open_date = int(j[0] // 1000)
            open_date = datetime.datetime.fromtimestamp(open_date).strftime('%Y-%m-%d %H:%M:%S')
            bar = {
                "open_time":int(j[0] // 1000),
                "open_time_date":open_date,
                "open":float(j[1]),
                "high":float(j[2]),
                "low":float(j[3]),
                "close":float(j[4]),
                "volume":float(j[5]),
                "taker_buy":float(j[9]),
                }
            data.append(bar)
            data.pop(0)
        with open("dataset/bars/"+ coin + ".json", "w") as write_file:
            json.dump(data, write_file, indent=4)
        return data
    else:
        now_time = int(time.time())
        start_time = int(((now_time - 60*60*24*settings['chart_days']) // 60)*60*1000)
        end_time = int(((now_time) // 60)*60)*1000
        info = []
        while(info == []):
            try:
                info = client.futures_historical_klines(coin,"5m",start_time,end_time)
            except:
                print(coin + ": ошибка запроса")
        info.pop(len(info)-1)
        data = []
        for j in info:
            open_date = int(j[0] // 1000)
            open_date = datetime.datetime.fromtimestamp(open_date).strftime('%Y-%m-%d %H:%M:%S')
            bar = {
                "open_time":int(j[0] // 1000),
                "open_time_date":open_date,
                "open":float(j[1]),
                "high":float(j[2]),
                "low":float(j[3]),
                "close":float(j[4]),
                "volume":float(j[5]),
                "taker_buy":float(j[9]),
                }
            data.append(bar)
        with open("dataset/bars/"+ coin + ".json", "w") as write_file:
            json.dump(data, write_file, indent=4)
        return data
    

def drow_bars_and_send_telegram(data,coin,text):
    df = pd.DataFrame(data) 
    fig = go.Figure(data=[go.Candlestick(
        x=df['open_time_date'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        increasing_line_color= 'gray', 
        decreasing_line_color = 'black'
        )]
    )
    fig.update_layout(xaxis_rangeslider_visible=False,showlegend=False)

    img = 'images/' + coin + '.png'
    fig.write_image(img)
    fig.data = []
    fig.layout = {}
    send_telegram(text,img)