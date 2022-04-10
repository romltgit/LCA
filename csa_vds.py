from defs import *
import json
import datetime
import os.path
import time
import telebot
import plotly.graph_objects as go
import threading
last_minute = -1

coin_list = [
 'ETHUSDT','ALICEUSDT','BTCUSDT','SOLUSDT',
 'FTMUSDT','BNBUSDT','AVAXUSDT','NEARUSDT','LUNAUSDT',
 'XRPUSDT','DOTUSDT'
]
def search_coin_level_cascade(coin):

    global settings
    data = update_dataset(coin)     # обновляем датасет 
    high_array = []     # Массив хаев
    low_array = []     # Массив лоев 
    last_high = data[-1]['high']     # Последний хай
    last_low = data[-1]['low']     # Последний лой
    bar = len(data)-1   # Поиск начинаеться с конца датасета

    while (bar >=0 and ((len(high_array) <4 and len(low_array) <4)  or  len(high_array) < 2  or len(low_array) < 2) ):     # 
        # поиск хаев
        if(data[bar]['high'] > last_high):
            last_high = data[bar]['high']

            if(bar >= settings['search_radius'] and bar <= len(data) -1 - settings['search_radius']):
                local_bars = data[bar - settings['search_radius']:bar + settings['search_radius']+1]
                local_ext = True
                for local_bar in local_bars:
                    if(local_bar['high'] > last_high):
                        local_ext = False
                        break
                if(local_ext):
                    high_array.append(last_high)
        # поиск лоев
        if(data[bar]['low'] < last_low):
            last_low = data[bar]['low']

            if(bar >= settings['search_radius'] and bar <= len(data) -1 - settings['search_radius']):
                local_bars = data[bar - settings['search_radius']:bar + settings['search_radius']+1]
                local_ext = True
                for local_bar in local_bars:
                    if(local_bar['low'] < last_low):
                        local_ext = False
                        break
                if(local_ext):
                    low_array.append(last_low)
        bar = bar - 1

    data=data[bar-10:len(data)]

    ext_data = {
            'high_array': high_array,
            'low_array': low_array,
            'was_sent': False
    }
    path_ext = 'ext_data/' + str(coin) + '_ext.json'

    if(not(os.path.exists(path_ext))):
        with open(path_ext, "w") as write_file:
            json.dump(ext_data, write_file,indent=4)

    # загружаем прошлые массивы экстремумов 
    with open(path_ext, "r") as read_file:
        previous_extremums_array = json.load(read_file)

    extremums_array_changed = (ext_data['high_array'] != previous_extremums_array['high_array'] or ext_data['low_array'] != previous_extremums_array['low_array'])    # Изменились ли массивы экстремумов

    if ( extremums_array_changed or (not(extremums_array_changed) and not(previous_extremums_array['was_sent'])) ): # Проверяем на каскад если изменились массивы экстремумов либо они не изменились, но не было сигнала в прошлый раз

        current_price = data[-1]['close']

        # Если до 3 экстремом вверх ближе чем до 2х вниз, то сигнал в лонг
        if(len(ext_data['high_array']) >= 3):
            if(abs(current_price - ext_data['high_array'][2]) < abs(current_price - ext_data['low_array'][1]) ):
                drow_bars_and_send_telegram(data,coin,ext_data,"long")
                ext_data['was_sent'] = True

        # Если до 3 экстремом вниз ближе чем до 2х вверх, то сигнал в шорт
        if(len(ext_data['low_array']) >= 3):  
            if(abs(current_price - ext_data['low_array'][2]) < abs(current_price - ext_data['high_array'][1]) ):
                drow_bars_and_send_telegram(data,coin,ext_data,"short")
                ext_data['was_sent'] = True
        
        with open(path_ext, "w") as write_file:
            json.dump(ext_data, write_file,indent=4)

while(True):
    now = datetime.datetime.now()
    minute = int(now.minute)
    if(minute % 5 == 0 and minute != last_minute):
        time.sleep(2)
        threads = []
        for coin in coin_list:
            # Превышение лимита (12) потоков
            # Из-за ограничения Binance на кол-ва запросов в секунду максимум может быть только 10 потоков для запроса данных, 1 поток основной, 1 поток получает тикеры
            while(threading.active_count() >= 12):
                time.sleep(0.05)

            # На каждую монету создаем поток функции get_bar
            t = threading.Thread(target=search_coin_level_cascade, args=(coin,))
            threads.append(t)
            t.start()
            # Ждем завершения работы всех потоков этой итерации
        for t in threads:
            t.join()
    last_minute = minute
    

