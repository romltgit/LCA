from defs import *
import json
import datetime
import os
import time
import threading

now = datetime.datetime.now()
last_minute = int(now.minute)

# Создание директорий, если их нет
if not(os.path.isdir('dataset/bars')):
    os.mkdir('dataset')
    os.mkdir('dataset/bars')
if not(os.path.isdir('ext_data')):
    os.mkdir('ext_data')
if not(os.path.isdir('images')):
    os.mkdir('images')

def search_coin_level_cascade(coin):

    global settings
    data = update_dataset(coin)     # обновляем датасет 
    high_array = []     # Массив хаев
    low_array = []     # Массив лоев 
    last_high = data[-1]['high']     # Последний хай
    last_low = data[-1]['low']     # Последний лой
    bar = len(data)-1   # Поиск начинаеться с конца датасета

    while (bar > 0 and ((len(high_array) <4 and len(low_array) <4)  or  len(high_array) < 2  or len(low_array) < 2) ):     
        # Поиск экстремумов закончить, 
        # как только найдется 4 экстремума одного типа, но при этом необходимо, чтобы экстремумов другого типа было найдено минимум 2

        # Поиск хаев
        if(data[bar]['high'] > last_high):
            last_high = data[bar]['high']

            if(bar >= settings['search_radius'] and bar <= len(data) -1 - settings['search_radius']):

                local_bars = data[bar - settings['search_radius']:bar + settings['search_radius']+1]
                local_ext = True
                for local_bar in local_bars:    # Проверяем, является ли хай текущей свечи экстремумом в радиусе settings['search_radius']
                    if(local_bar['high'] > last_high):
                        local_ext = False
                        break
                if(local_ext):  # Если является, то добавляем его в массив экстремумов
                    high_array.append(last_high)
                    
        # Поиск лоев
        if(data[bar]['low'] < last_low):
            last_low = data[bar]['low']

            if(bar >= settings['search_radius'] and bar <= len(data) -1 - settings['search_radius']):
                local_bars = data[bar - settings['search_radius']:bar + settings['search_radius']+1]
                local_ext = True
                for local_bar in local_bars:    # Проверяем, является ли лой текущей свечи экстремумом в радиусе settings['search_radius']
                    if(local_bar['low'] < last_low):
                        local_ext = False
                        break
                if(local_ext):  # Если является, то добавляем его в массив экстремумов
                    low_array.append(last_low)
        bar = bar - 1

    # Обрезаем датасет до нужного размера (bar - индекс свечи, на которой закончился поиск )
    if(bar-10 >= 0):
        data=data[bar-10:len(data)]
    else:
        data=data[bar:len(data)]

    ext_data = {    
            'high_array': high_array,
            'low_array': low_array,
            'was_sent': False
    }
    path_ext = 'ext_data/' + str(coin) + '_ext.json'

    # Если нет файла с экстремумами, сохраняем массивы экстремумов в файл JSON
    if(not(os.path.exists(path_ext))):
        with open(path_ext, "w") as write_file:
            json.dump(ext_data, write_file,indent=4)

    # Загружаем прошлые массивы экстремумов 
    with open(path_ext, "r") as read_file:
        previous_extremums_array = json.load(read_file)

    # Изменились ли массивы экстремумов
    extremums_array_changed = (ext_data['high_array'] != previous_extremums_array['high_array'] or ext_data['low_array'] != previous_extremums_array['low_array'])    
    
    # Проверяем на каскад если изменились массивы экстремумов либо они не изменились, но не было сигнала в прошлый раз
    if ( extremums_array_changed or (not(extremums_array_changed) and not(previous_extremums_array['was_sent'])) ): 
    
        current_price = data[-1]['close']   # Текущая цена тикера

        # Если до 3 экстремом вверх ближе чем до 2х вниз, то сигнал в лонг
        if(len(ext_data['high_array']) >= 3 and len(ext_data['low_array']) >= 2):
            if(abs(current_price - ext_data['high_array'][1]) < abs(current_price - ext_data['low_array'][1]) ):
                drow_bars_and_send_telegram(data,coin,ext_data,"long")
                ext_data['was_sent'] = True

        # Если до 3 экстремом вниз ближе чем до 2х вверх, то сигнал в шорт
        if(len(ext_data['low_array']) >= 3 and len(ext_data['high_array']) >= 2):  
            if(abs(current_price - ext_data['low_array'][1]) < abs(current_price - ext_data['high_array'][1]) ):
                drow_bars_and_send_telegram(data,coin,ext_data,"short")
                ext_data['was_sent'] = True
        
        # Сохраняем массивы экстремумов в файл JSON
        with open(path_ext, "w") as write_file:
            json.dump(ext_data, write_file,indent=4)

connection = True   # Есть ли соединение с биржей
while(True):
    now = datetime.datetime.now()
    minute = int(now.minute)
    if(minute % 5 == 0 and minute != last_minute):  # Каждые 5 мин выполнять скрипт
        time.sleep(2)
        try:
            status = client.get_system_status()     # Проверка статуса биржи 
            connection = True
        except:
            if(connection):
                log.error("Нет подключения к Binance")
                connection = False
            continue

        if(connection and not(status['status'])):   # Проверка соеденения и статуса биржи (status: (0: normal，1：system maintenance))
            threads = []
            for coin in settings["coin_list"]:
                # Превышение лимита (12) потоков
                # Из-за ограничения Binance на кол-ва запросов в секунду максимум может быть только 10 потоков для запроса данных, 1 поток основной, 1 поток получает тикеры
                while(threading.active_count() >= 12):
                    time.sleep(0.05)

                # На каждую монету создаем поток функции search_coin_level_cascade
                t = threading.Thread(target=search_coin_level_cascade, args=(coin,))
                threads.append(t)
                t.start()
                # Ждем завершения работы всех потоков этой итерации
            for t in threads:
                t.join()
    last_minute = minute
    

