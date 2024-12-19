"""
Модуль chrom
============

Модуль chrom - предназначен для расчета хроматографических параметров на основе
файлов с экспериментальными данными

В качестве файлов с экспериментальными данными понимаются файлы формата .txt,
имеющие в своей структуре начальные строки, характеризующие имя файла, дату и
время анализа, и три столбца табулированных данных:
Values Xxxxxx, DD.MM.YYYY HH.MM
"Time, s"       FID A, pA	OvenTemp, °C
"00"00"         11.615	        30.000

Глобоальные переменные
----------------------
chrom содержит набор глобальных переменных, которые могут быть использованы
для вывода/расчета/изучения иных характеристик, не рассчитываемых
в данном модуле

* Значения определяют диапазон координат графического отображения

        ymin (int): начало координат по оси y
        ymax (int): конечная точка координат по оси y
        xmax (int): конечная точка координат по оси x
        
* Словарь с данными хроматографирования, где: key - время (сек),
  value - сигнал (рА)
  Заполняется при запуске функции datachrom(filename)

        ddict = {}
        
* Словарь, содержащий сведения об обнаруженных компонентах хроматограммы.
  По-умолчанию принимается, что хроматограмма может содержать либо 'Этанол',
  либо 'Ацетонитрил', либо оба компонента, либо ниодного компонента.
  key - компонент('Этанол', 'Ацетонитрил'),
  value - словарь параметров со значениями 

        components = {}

* Времена выхода пиков
  По-умолчанию  - ориентировочные времена выхода пиков в секундах

        time_ethanol = 190
        time_acn = 210

* Значения ширины плечей пиков

        wing_L (int): ширина левого плеча, сек
        wing_R (int): ширина правого плеча, сек

* Диапазон окна расчета фонового шума [сек, сек]
  Участок хроматограммы, на котором проводится определение фонового шума прибора
  В зависимости от условий хроматографирования, при обработке данных можно
  изменить участок, задав начальную и конечную координату диапазона в секундах
  
        wing_noise [int, int]
        
* Величина (амплитуда) фонового шума, определенная на участке wing_noise
  По-умолчанию = 0. Автоматически определяется в функции findpeaks(filename)
  через запуск функции gcnoise(filename)
  
        noise (float)

*  Дата и время проведения анализа

        date_injection (str): дата анализа
        time_injection (str): время анализа

Основные функции
----------------
        datachrom(file) -> dict
        findpeaks(file) -> dict
        integration(int, file=None) -> float
        gcnoise(file) -> float
        gchrom_time(file) -> list
        gchrom_sec(file) -> list
        peak_xy(int) -> list
        peakheight(list) -> float
        fpeaks(file=None) -> None, components.update(key=value)
        assym(list, float=None) -> float
        plates(list, float=None) -> float
        resolution(list, list, float=None, float=None) -> float
        Wx(list, float, float=None) -> float
        myround(float) -> float

"""

import re
import time
import datetime
import math
from statistics import mean
from sympy.geometry import *
from scipy.interpolate import InterpolatedUnivariateSpline
from scipy.signal import find_peaks

ymin = 0
ymax = 1
xmax = 1

# данные хроматографирования, где: key - время (сек), value - сигнал (рА)
ddict = {}

# компоненты хроматрограммы, где: key - компонент('Этанол', 'Ацетонитрил'),
# value - список параметров [t-comp, H-comp, s/n]
components = {}

# ориентировочные времена выхода пиков
time_ethanol = 190
time_acn = 210

# значения ширины левого (wing_L) и правого (wing_R) крыла пика
wing_L = 15
wing_R = 40

# диапазон окна расчета фонового шума [сек, сек]
wing_noise = [40, 60]
# величина фонового шума, пА
noise = 0

# дата и время хроматографирования
date_injection = str()
time_injection = str()

def datachrom(filename):
        """
        Принимает в качестве аргумента filename путь к файлу с данными
        Определяет дату и время проведения анализа(date_injection, time_injection)
        Усредняет значения данных до частоты 1 Гц и заполняет словарь ddict

        Возвращаемое значение:
                ddict (dict): словарь, где ключ - время, значение - сигнал

        """
        L = []
        ddict.clear()
        try:
                with open(filename, 'r') as inf:
                        for line in inf:
                                L.append(line.strip())
                        global date_injection, time_injection
                        date_time = re.search(r"\d\d.\d\d.\d{4} \d\d.\d\d",
                                              L[0]).group()
                        date_injection = date_time.split()[0]
                        time_injection = date_time.split()[1]
                
                        for i in range(2, len(L)-2, 10):
                                signal_average = []
                                for j in range(10):
                                        a = [_.start() for _ in re.finditer('\t', L[i+j])]
                                        signal_average.append(float((L[i+j][a[0]+1:a[1]])))
                                signal_average = round(sum(signal_average)/10, 3)
                                m_s_format = int((i - 2) / 10)
                                ddict[m_s_format] = signal_average
                print('Экспериментальные данные успешно получены')
                return ddict
        except FileNotFoundError:
                print('Выбранный файл отсутствует')
                return
        
def findpeaks(filename):
        """
        Функция автоматического поиска присутствия пиков Этанола и Ацетонитрила
        По-умолчанию времена удерживания:
        Этанол - 190 сек (3'10")
        Ацетонитрил - 210 сек (3'30")
        
        Возвращаемое значение:
        
                dict = {'k': [{'t': t},
                              {'H': H},
                              {'S': S},
                              {'S/N': S/N},
                              {'A[sub]s[/sub]': A},
                              {'N, тарелок': N},
                              {'R[sub]s[/sub]': Rs}]
                        }
        
        """
        global noise, time_ethanol, time_acn
        # получение набора экспериментальных данных
        datachrom(filename)
        components.clear()
        # определение присутствующих компонентов
        fpeaks()
        # определение величины фонового шума
        noise = myround(gcnoise(filename))
        
        if str('Этанол') not in components:
                print('Пик этанола не обнаружен')
                time_ethanol = None
        else:
                ethanol_coo = peak_xy(time_ethanol)
                ethanol_H = peakheight(ethanol_coo)
                A = assym(ethanol_coo, ethanol_H)
                N = plates(ethanol_coo, ethanol_H)
                components['Этанол'] = [{'t, c': time_ethanol},
                                        {'H, пA': myround(ethanol_H)},
                                        {'S, пA*с': myround(integration(time_ethanol))},
                                        {'S/N': myround(2 * ethanol_H / noise)},
                                        {'A[sub]s[/sub]': myround(A)},
                                        {'N, тарелок': round(N)},
                                        {'R[sub]s[/sub]': str(' - ')}]
        if str('Ацетонитрил') not in components:
                print('Пик ацетонитрила не обнаружен')
                time_acn = None
        else:
                acn_coo = peak_xy(time_acn)
                acn_H = peakheight(acn_coo)
                A = assym(acn_coo, acn_H)
                N = plates(acn_coo, acn_H)
                if time_ethanol is not None:
                        Rs = myround(resolution(ethanol_coo,
                                                acn_coo,
                                                ethanol_H,
                                                acn_H))
                else:
                        Rs = str(' - ')
                components['Ацетонитрил'] = [{'t, c': time_acn},
                                             {'H, пA': myround(acn_H)},
                                             {'S, пA*с': myround(integration(time_acn))},
                                             {'S/N': myround(2 * acn_H / noise)},
                                             {'A[sub]s[/sub]': myround(A)},
                                             {'N, тарелок': round(N)},
                                             {'R[sub]s[/sub]': Rs}]
        return components
        
        
def integration(peaktime, filename=None):
        """
        Функция интегрирования пиков хроматограммы
        Принимает в качестве аргументов:
        filename - путь к файлу с данными (default - None)
        peaktime - время удерживания компонента

        Возвращаемое значение:

              S (float): площадь пика

        """
        if filename is not None:
                datachrom(filename)

        if peaktime is not None:
                
                points = peak_xy(peaktime)
                start_point = [points[0], points[1]]
                end_point = [points[4], points[5]]
                x = []
                y = []
                x2 = [start_point[0], end_point[0]]
                y2 = [start_point[1], end_point[1]]
                for k, v in ddict.items():
                        while k in [i for i in range(start_point[0],
                                                     end_point[0] + 1)]:  
                                x.append(k)
                                y.append(v)
                                break
                S1 = InterpolatedUnivariateSpline(x, y, k=1)
                S2 = InterpolatedUnivariateSpline(x2, y2, k=1)
                S_all = S1.integral(x[0], x[-1])
                S_down = S2.integral(x2[0], x2[-1])
                S = S_all - S_down
                return S
        

def gcnoise(filename):
        """
        Функция расчета величины шума по экспериментальным данным.
        Принимает в качестве аргумента путь к файлу с данными - filename

        Возвращаемое значение:

                noise (float): величина (амплитуда) фонового шума
        
        """
        L = []
        datas = []
        with open(filename, 'r') as inf:
                for line in inf:
                        L.append(line.strip())
                        
                # шум определяется на выбранно участке wing_noise:[start, end]
                for i in L[wing_noise[0] * 10:wing_noise[1] * 10]:               
                       a = [_.start() for _ in re.finditer('\t', i)]
                       datas.append(float(i[(a[0]+1):(a[1])]))
        # удаляем статистические выбросы макс и мин сигнала
        datas.remove(max(datas))
        datas.remove(min(datas))
        
        # значение шума хроматограммы - амплитуда шумовых колебаний
        noise = max(datas) - min(datas)
        return noise



def gchrom_time(filename):
# представление данных хроматограммы в формате: [мин:сек, сигнал]
        L = []
        time_signal = []
        
        with open(filename, 'r') as inf:
                for line in inf:
                        L.append(line.strip())
                
                for i in range(2, len(L)-2, 10):
                        signal_average = []
                        for j in range(10):
                                a = [_.start() for _ in re.finditer('\t', L[i+j])]
                                signal_average.append(float((L[i+j][a[0]+1:a[1]])))
                        
                        signal_average = round(sum(signal_average)/10, 3)
                        
                        try:    m_s_format = datetime.time(minute=int((i-2)/10)//60, second=int((i-2)/10)%60).strftime('%M:%S')
                                
                        except ValueError:
                                print('Хроматограмма более часа')
                        time_signal.append([m_s_format, signal_average])
        return time_signal


def gchrom_sec(filename):
        """
        Функция представления данных в виде многомерного массива формата:
        [t, s], где:
        t - время в секундах
        s - значение сигнала
        Принимает в качестве аргумента путь к файлу с данными
        Устанавливает значения глобальных переменных: ymin, ymax, xmax

        Возвращаемое значение:
        
                seconds_signal (list): список координат графика [int, float]

        """
        global ymin, ymax, xmax
        L = []
        seconds_signal = []
        signal_list = []
        try:
                with open(filename, 'r') as inf:
                        for line in inf:
                                L.append(line.strip())
                
                        for i in range(2, len(L)-2, 10):
                                signal_average = []
                                for j in range(10):
                                        a = [_.start() for _ in re.finditer('\t', L[i+j])]
                                        signal_average.append(float((L[i+j][a[0]+1:a[1]])))
                                        
                                signal_average = round(sum(signal_average)/10, 3)
                                m_s_format = int((i - 2) / 10)
                                signal_list.append(signal_average)
                                seconds_signal.append([m_s_format, signal_average])
                        ymin = min(signal_list)
                        ymax = max(signal_list)
                        xmax = len(signal_list)
                return seconds_signal
        
        except FileNotFoundError:
                print('Файл не выбран')
                return [[0, 0]]

def peak_xy(peaktime):
        """
        Функция определения хроматографических параметров пика
        Принимает в качестве аргумента: peaktime - время удерживания (сек)

        Возвращаемое значение:
        
                [start_peak_t, start_peak_s, peak_t,
                peak_s, end_peak_t, end_peak_s] - список значений
                координат точек пика в формате:
        [t1, s1, t2, s2, t3, s3], где:
        t1 - время начала пика, сек
        s1 - начальный сигнал (первая точка базовой линии пика)
        t2 - время удерживания
        s2 - максимальное значение пика
        t3 - время окончания пика, сек
        s3 - конечный сигнал (конечная точка базовой линии пика)

        """
        # определение начальной точки левого крыла пика
        peak_wing_left = [i for i in range(peaktime, peaktime - 15, -1)]
        start_peak_s = min([ddict[i] for i in peak_wing_left])
        for i in peak_wing_left:
                if start_peak_s == ddict[i]:
                        start_peak_t = i

        # определение конечной точки пика, правое крыло
        if len(components) == 1:
                # обнаружен только один компонент
                peak_wing_right = [i for i in range(peaktime, 240, 1)]
                end_peak_s = min([ddict[i] for i in peak_wing_right])
                for i in peak_wing_right:
                        if end_peak_s == ddict[i]:
                                end_peak_t = i
        else:
                # для двухкомпонентной смеси
                peak_wing_right = [i for i in range(peaktime, peaktime + 20, 1)]
                end_peak_s = min([ddict[i] for i in peak_wing_right])
                for i in peak_wing_right:
                        if end_peak_s == ddict[i]:
                                end_peak_t = i
        peak_t = peaktime
        peak_s = ddict[peaktime]

        return [start_peak_t, start_peak_s, peak_t,
                peak_s, end_peak_t, end_peak_s]

def peakheight(p):
        """
        Функция определения высоты пика
        Принимает в качестве аргумента список координат трех точек
        Расчет ординаты базовой линии по абсциссе пика проводится
        исходя из подобия треугольников

        Возвращаемое значение:
                H (float): высота аналитического сигнала 

        """
        startpeak = Point(p[0], p[1]) 
        toppeak = Point(p[2], p[3])
        endpeak = Point(p[4], p[5])
        
        if (startpeak == toppeak or
            toppeak == endpeak or
            startpeak == endpeak):
                return 0
        else:
                global wing_L, wing_R
                wing_L = toppeak[0] - startpeak[0]
                wing_R = endpeak[0] - toppeak[0]
                h = (endpeak[1] - startpeak[1]) * wing_L / (wing_L + wing_R)
                ordinate_h =  h + startpeak[1]
                H = float(toppeak[1] - ordinate_h)
                return H

def fpeaks(filename=None):
        """
        Функция поиска пиков в установленном диапазоне
        Заполняет словарь components с обнаруженными компонентами, где:
        ключ - имя компонента,
        значние - словарь с параметрами
        Заполняется параметр времени выхода компонента

        """
        global components, time_ethanol, time_acn
        time_ethanol = 190
        time_acn = 210
        if filename is not None:
                datachrom(filename)
        peaks, heights = find_peaks([x for x in ddict.values()],
                                    height=0,
                                    prominence=.05,
                                    distance=15,
                                    threshold=.005
                                    )
        t = [i for i in range(175, 235) if i in peaks]
        for i in t:
                if abs(time_ethanol - i) < abs(time_acn - i):
                        time_ethanol = i
                        components.update(Этанол={'t, c': time_ethanol})
                elif abs(time_ethanol - i) == abs(time_acn - i):
                        components.update(Компонент={})
                        print('Необходимо уточнение компонента')
                else:
                        time_acn = i
                        components.update(Ацетонитрил={'t, c': time_acn})
        return

def assym(p, H=None):
        """
        Функция определения асимметрии пика
        в качестве аругмента принимаются:
        p - список координат трех точек пика [x1, y1, x2, y2, x3, y3]
        H - величина высоты пика, по-умолчанию - None

        Возвращаемое значение:

                A (float): фактор асимметрии пика

        """
        if H is None:
                H = peakheight(p)
                
        pp = Wx(p, .05, H)
        w005 = pp[0]
        f = p[2] - pp[1]
        A = w005 / (2 * f)
        return A

def plates(p, H=None):
        """
        Функция определения числа теоретических тарелок разделения
        в качестве аругмента принимаются:
        p - список координат трех точек пика [x1, y1, x2, y2, x3, y3]
        H - величина высоты пика, по-умолчанию - None

        Возвращаемое значение:

                N (float): количество теоретических тарелок 

        """
        if H is None:
                H = peakheight(p)
        N = 5.54 * (p[2] / Wx(p, .5, H)[0]) ** 2
        return N

def resolution(p1, p2, H1=None, H2=None):
        """
        Функция определения разрешения пиков
        в качестве аргументов принимаются:
        p1 - координаты первого пика
        p2 - координаты второго пика
        H1 - высота первого пика, по-умолчанию - None
        H2 - высота второго пика, по-умолчанию - None
        Возвращаемое значение:

                Rs (float): разрешение двух пиков

        """
        if H1 is None:
                H1 = peakheight(p)
        if H2 is None:
                H2 = peakheight(p)
        tr1 = p1[2]
        tr2 = p2[2]
        w051 = Wx(p1, .5, H1)[0]
        w052 = Wx(p2, .5, H2)[0]
        Rs = 1.18 * (tr2 - tr1) / (w051 + w052)
        return Rs

def Wx(p, x, H=None):
        """
        Функция определения ширины пика на заданной высоте пика
        в качестве аргументов принимается:
        p - список координат трех точек пика [x1, y1, x2, y2, x3, y3]
        x - доля высоты от основания (% / 100)
        H - высота пика, по-умолчанию - None

        Возвращаемое значение:
        
                list(Wx, lpoint, rpoint) где:
        Wx - ширина пика на заданной высоте
        lpoint - координата крайней левой точки пика на заданной высоте
        rpoint - координата крайней правой точки пика на заданной высоте

        """
        if H is None:
                H = peakheight(p)
        h = H * x
        lpoint = p[0]
        rpoint = p[4]

        def line(x):
              y = ((x - p[0])/(p[4] - p[0])) * (p[5] - p[1]) + p[1]
              return y

        for x, y in ddict.items():
                while x in [i for i in range(p[0], p[2])]:
                        if ((ddict[x - 1] - line(x - 1)) < h
                                <= (y - line(x))):
                                lpoint = x
                        break
        for x, y in ddict.items():
                while x in [i for i in range(p[2], p[4])]:
                        if  ((ddict[x - 1] - line(x - 1)) >= h
                             > (y - line(x))):
                                rpoint = x
                        break
        Wx = rpoint - lpoint
        return [Wx, lpoint, rpoint]
        

def myround(x):
        """
        Функция округления аргумента до 3-х значащих цифр

        """
        if not int(x):
                return round(x, 3)
        if len(str(abs(int(x)))) >= 3:
                x = int(round(x))
        return round(x, 3 - len(str(abs(int(x)))))


