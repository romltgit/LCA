from binance.client import Client
from settings import *
from defs import *
import json
import time
import pandas as pd
import surrogates
import datetime
import os.path
import plotly.graph_objects as go
import copy
import telebot
import logging

# Логирование
logfile = 'errors.log'
log = logging.getLogger("my_log")
log.setLevel(logging.ERROR)
FH = logging.FileHandler(logfile, encoding='utf-8')
basic_formater = logging.Formatter('%(asctime)s : [%(levelname)s] : %(message)s')
FH.setFormatter(basic_formater)
log.addHandler(FH)

# Инициализация Телеграм-бота
bot = telebot.TeleBot(settings['telegram_token'])

# Инициализация клиента Binance-api
client = Client(settings['binance_keys']['api_key'], settings['binance_keys']['secret_key'],{"timeout": 5})

# Отправка изображений в телеграм-канал
def send_telegram(coin,text: str,img):
    try:
        with open(img, 'rb') as photo:
            bot.send_photo(settings['channel_id'], photo, caption=text)
    except:
        log.error(coin + ": ошибка отправки изображения")

# Обновление или создание датасета
def update_dataset(coin):
    global settings

    # Если датасет существует
    if(os.path.exists("dataset/bars/"+ coin + ".json")):

        # Загружаем датасет в массив data
        try:
            with open("dataset/bars/"+ coin + ".json", "r") as read_file:
                data = json.load(read_file)
        except:
            log.error(coin + ": ошибка чтения датасета")
            return

        # Определяем нужные значения времени, чтобы получить недостающие свечи 
        now_time = int(time.time())
        start_time = int(data[-1]['open_time'] + 5*60)*1000     # К Времени открытия последней свечи в датасете прибавляем 5 минут
        end_time = int(((now_time) // 60)*60)*1000

        # Если датасет очень давно не обновлялся (больше чем кол-во дней, указаных в settings['chart_days'), то меняем начальное время
        if(end_time - start_time > int(60*60*24*settings['chart_days'])):
            start_time = int(((now_time - 60*60*24*settings['chart_days']) // 60)*60*1000)
            
            # Переменная updating отвечает, необходимо ли удалять старые свечи в датасете 
            # (это необходимо только при обновлении, чтобы в датасете были свечи только за последние settings['chart_days'] дней) 
            updating = False
        else:
            updating = True

    # Если датасета нет
    else:
        # Определяем нужные значения времени, чтобы получить все свечи за последние settings['chart_days'] дней
        now_time = int(time.time())
        start_time = int(((now_time - 60*60*24*settings['chart_days']) // 60)*60*1000)
        end_time = int(((now_time) // 60)*60)*1000

        data = []
        updating = False

    # Получаем данные с Binance
    try:
        info = client.futures_historical_klines(coin,"5m",start_time,end_time)
    except:
        log.error(coin + ": ошибка запроса")
        return

    # Удаляем самую новую свечку, т.к она только открылась и нам она не нужна
    info.pop(len(info)-1)

    # Добавляем свечи в датасет (массив data)
    for j in info:
        open_date = int(j[0] // 1000)   # Из мсек. в сек.
        open_date_time = datetime.datetime.fromtimestamp(open_date).strftime('%Y-%m-%d %H:%M:%S')    # Из сек. в дату
        bar = {
            "open_time":open_date,  # Время открытия свечи (сек.)
            "open_time_date":open_date_time, # Время открытия свечи (дата)
            "open":float(j[1]),  
            "high":float(j[2]),   
            "low":float(j[3]),
            "close":float(j[4]),
            "volume":float(j[5]),
            "taker_buy":float(j[9]),
            }
        data.append(bar)

        # Если это обновление датасета, то после добавления новой свечи удаляем самую старую свечу в датасете
        if(updating):
            data.pop(0)

    # Сохраняем обновленный (или созданный) датасет (массив data) в файл JSON
    try:
        with open("dataset/bars/"+ coin + ".json", "w") as write_file:
            json.dump(data, write_file, indent=4)
    except:
        log.error(coin + ": ошибка сохранения датасета")
        return
    # Возвращаем датасет для дальнейшей работы
    return data
    
# Отрисовка изображений и вызов отправки в телеграм
def drow_bars_and_send_telegram(data,coin,ext_data,text):

    # Делаем копии датасета и массивов экстремумов
    data_copy = copy.deepcopy(data)
    ext_data_copy = copy.deepcopy(ext_data)

    # Текст сигнала
    if(text == 'long'):
        text = '%s %s Каскад уровней сверху:\n' %(surrogates.decode('\ud83d\udfe2'),coin)
        for high in ext_data_copy['high_array']:
            text = "{} \n {} (+{}%)".format(text,high,str(round(abs(high/data_copy[-1]['close'] - 1)*100,2)))

    elif(text == 'short'):
        text = '%s %s Каскад уровней снизу:\n' %(surrogates.decode('\ud83d\udd34'),coin)
        for low in ext_data_copy['low_array']:
            text = "{} \n {} (-{}%)".format(text,low,str(round(abs(low/data_copy[-1]['close'] - 1)*100,2)))

    # Отрисовка свечей
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

    # Отрисовка уровней
    current_x_array  = [] 
    for bar in reversed(data_copy):
        current_x_array.append(bar['open_time_date'])

        if(bar['high'] in ext_data_copy['high_array']):
            fig.add_trace(go.Scatter(x=current_x_array, y=[bar['high'] for j in current_x_array], mode ="lines",line=dict(color="#B22222")))
            ext_data_copy['high_array'].remove(bar['high'])

        if(bar['low'] in ext_data_copy['low_array']):
            fig.add_trace(go.Scatter(x=current_x_array, y=[bar['low'] for j in current_x_array], mode ="lines",line=dict(color="#228B22")))
            ext_data_copy['low_array'].remove(bar['low'])

    # Сохраняем изображение в файл и освобождаем память
    img = 'images/' + coin + '.png'
    fig.write_image(img)
    fig.data = []
    fig.layout = {}
    del fig

    # Вызов отправки изображения и текста в телеграм-канал
    send_telegram(coin,text,img)