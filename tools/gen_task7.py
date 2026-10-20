#!/usr/bin/env python3
"""Генератор задач ЕГЭ №7 (кодирование изображений и звука, передача файлов) для банка stackly.

    python3 tools/gen_task7.py > /tmp/task7.json      # 100 задач: 55 базовых, 30 средних, 15 сложных

Задача описывается spec: семейство (объём изображения, число цветов, звук, передача по каналу, перекодировка,
повторная оцифровка, сжатие, видео…) и числа. По spec строятся условие, решение на Python, ответ (точной
целочисленной арифметикой) и решение «руками» в пояснении. Числа подбираются так, чтобы ответ был целым там,
где условие не просит округлять. Решение запускается и должно вывести ответ. Spec хранится в задаче
HTML-комментарием <!--spec:…--> — по нему tests/test_bank_task7.py пересчитывает ответ своим способом.
Генерация детерминирована (seed).
"""
import json, math, os, random, subprocess, sys
from fractions import Fraction as Fr

SEED = 20261021
UNIT = {'байт': 8, 'Кбайт': 8 * 2 ** 10, 'Мбайт': 8 * 2 ** 20, 'Гбайт': 8 * 2 ** 30}
POW = {'Кбайт': '2**10', 'Мбайт': '2**20', 'Гбайт': '2**30'}
SIDES = [128, 160, 192, 240, 256, 320, 384, 400, 480, 512, 600, 640, 720, 768, 800, 960, 1024, 1080, 1200, 1280,
         1440, 1536, 1600, 1920, 2048, 2400, 2560, 3072, 4096]
PALETTE = [3, 5, 6, 10, 12, 20, 25, 30, 50, 60, 100, 120, 200, 250, 300, 500, 1000, 1500, 2000, 3000, 5000,
           10000, 30000, 50000, 100000, 1000000]
FREQ = [8000, 11025, 16000, 22050, 24000, 32000, 44100, 48000, 64000, 96000]
CHAN = {1: 'одноканальная (моно)', 2: 'двухканальная (стерео)', 4: 'четырёхканальная (квадро)'}
CHAN_SHORT = {1: 'моно', 2: 'стерео', 4: 'квадро'}
SPEED = [2 ** k for k in range(10, 24)] + [16000, 32000, 64000, 128000, 256000, 512000, 1000000, 2048000]


def bits(n):
    """Минимальное число бит, чтобы закодировать n разных значений: ⌈log₂ n⌉."""
    return (n - 1).bit_length()


def ceil_div(a, b):
    return -(-a // b)


def plural(n, one, few, many):
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def num(n):
    """Число с разделителем тысяч для пояснений: 9 437 184."""
    return f'{n:,}'.replace(',', ' ')


def frac(x):
    x = Fr(x)
    return str(x.numerator) if x.denominator == 1 else f'{x.numerator}/{x.denominator}'


def khz(f):
    return f'{f // 1000} кГц' if f % 1000 == 0 else str(f / 1000).replace('.', ',') + ' кГц'


def dur(t):
    if t % 60 == 0 and t >= 60:
        m = t // 60
        return f'{m} {plural(m, "минуту", "минуты", "минут")}'
    return f'{t} {plural(t, "секунду", "секунды", "секунд")}'


def cnt(n, one, few, many):
    return f'{n} {plural(n, one, few, many)}'


def colors(sp):
    """Глубина цвета по spec: задана числом бит или размером палитры."""
    return sp['i'] if 'i' in sp else bits(sp['N'])


def color_text(sp, lead=True):
    """«Глубина цвета — 12 бит на пиксель.» или «В изображении используется палитра из 4096 цветов.»"""
    if 'i' in sp:
        t = f'глубина цвета — <b>{cnt(sp["i"], "бит", "бита", "бит")}</b> на пиксель'
    else:
        t = f'в изображении используется палитра из <b>{sp["N"]} {plural(sp["N"], "цвета", "цветов", "цветов")}</b>'
    return t[0].upper() + t[1:] + '.' if lead else t


def dec(x, nd=2):
    """Приближённое значение с отброшенными (не округлёнными) знаками: 645,996 — а не 646,00 рядом с «вверх: 646»."""
    x = Fr(x)
    whole = math.floor(x * 10 ** nd)
    return f'{whole // 10 ** nd},{whole % 10 ** nd:0{nd}d}'


def color_code(sp):
    if 'i' in sp:
        return f'i = {sp["i"]}                     # бит на пиксель'
    return f'i = math.ceil(math.log2({sp["N"]}))   # бит на пиксель'


def color_note(sp):
    i = colors(sp)
    if 'i' in sp:
        return f'на пиксель {cnt(i, "бит", "бита", "бит")}'
    return f'{sp["N"]} ≤ 2<sup>{i}</sup>, значит на пиксель нужно {cnt(i, "бит", "бита", "бит")}'


PIC = 'Для кодирования цвета каждого пикселя используется одинаковое количество бит, коды пикселей записываются ' \
      'в файл один за другим без промежутков.'


# ------------------------------------------------------------------ ответы
def answer(sp):
    f = sp['f']
    if f == 'img':
        return Fr(sp['W'] * sp['H'] * colors(sp) * sp['n'], UNIT[sp['u']])
    if f in ('imgN', 'compress'):
        keep = Fr(100 - sp.get('p', 0), 100)
        i = max(i for i in range(1, 33) if sp['W'] * sp['H'] * i * keep <= sp['V'] * UNIT[sp['vu']])
        return 2 ** i
    if f == 'snd':
        return ceil_div(sp['fr'] * sp['i'] * sp['k'] * sp['t'], UNIT[sp['u']])
    if f == 'sndT':
        t = Fr(sp['X'] * UNIT[sp['u']], sp['fr'] * sp['i'] * sp['k'])
        return t / 60 if sp['tu'] == 'мин' else t
    if f == 'send':
        if sp['q'] == 'time':
            return Fr(sp['X'] * UNIT[sp['u']], sp['v'])
        return Fr(sp['t'] * sp['v'], UNIT[sp['u']])
    if f == 'send2':
        return Fr(sp['X'] * sp['v2'], sp['v1'])
    if f == 'imgK':
        return sp['X'] * UNIT[sp['u']] // (sp['W'] * sp['H'] * colors(sp) + 8 * sp.get('svc', 0))
    if f == 'imgSvc':
        i = max(i for i in range(1, 33) if sp['K'] * (sp['W'] * sp['H'] * i + 8 * sp['svc']) <= sp['X'] * UNIT[sp['u']])
        return 2 ** i
    if f == 'recode':
        i1, i2 = bits(sp['N1']), bits(sp['N2'])
        old = Fr(sp['D'] * i1, i1 - i2)
        return old if sp['q'] == 'old' else old - sp['D']
    if f == 'redig':
        return sp['X'] * Fr(sp['k2'], sp['k1']) * Fr(sp['rf']) * Fr(sp['ff'])
    if f == 'sendSnd':
        return ceil_div(sp['fr'] * sp['i'] * sp['k'] * sp['t'], sp['v'])
    if f == 'video':
        per_sec = sp['F'] * sp['W'] * sp['H'] * colors(sp) + sp.get('fr', 0) * sp.get('si', 0) * sp.get('k', 0)
        if sp['q'] == 'size':
            return ceil_div(per_sec * sp['t'], UNIT['Мбайт'])
        return sp['X'] * UNIT[sp['u']] // per_sec
    if f == 'stream':
        keep = Fr(100 - sp['p'], 100)
        i = max(i for i in range(1, 33) if sp['W'] * sp['H'] * i * keep <= sp['v'] * sp['T'])
        return 2 ** i
    if f == 'sndMax':
        return (sp['X'] * UNIT[sp['u']] - 8 * sp['hdr']) // (sp['i'] * sp['k'] * sp['t'])
    if f == 'redig2':
        return sp['T1'] * Fr(sp['k2'], sp['k1']) * Fr(sp['rf']) * Fr(sp['ff']) / Fr(sp['c'])
    raise ValueError(f)


# ------------------------------------------------------------------ случайные spec
def pick_color(rng, lo=1, hi=24):
    if rng.random() < .45:
        return {'i': rng.randint(lo, hi)}
    if rng.random() < .5:
        return {'N': 2 ** rng.randint(max(lo, 1), hi)}
    return {'N': rng.choice([n for n in PALETTE if lo <= bits(n) <= hi])}


def ratio(rng):
    return rng.choice(['2', '3', '4', '1/2', '1/3', '1/4', '3/2', '2/3'])


def rand_spec(rng, fam):
    W, H = sorted(rng.sample(SIDES, 2), reverse=True)
    if fam == 'img':
        n = 1 if rng.random() < .55 else rng.choice([2, 4, 8, 10, 16, 20, 25, 32, 50, 64, 100, 128, 256])
        sp = {'f': fam, 'W': W, 'H': H, **pick_color(rng), 'n': n,
              'u': 'Кбайт' if n == 1 or rng.random() < .3 else 'Мбайт'}
        return sp if answer(sp).denominator == 1 and answer(sp) >= 2 else None
    if fam == 'imgN':
        size = W * H
        i = rng.randint(2, 24)
        V = ceil_div(size * i, UNIT['Кбайт']) + rng.randint(0, max(1, size // UNIT['Кбайт']))
        return {'f': fam, 'W': W, 'H': H, 'V': V, 'vu': 'Кбайт'}
    if fam == 'snd':
        sp = {'f': fam, 'fr': rng.choice(FREQ), 'i': rng.choice([8, 16, 16, 24, 24, 32]), 'k': rng.choice([1, 2, 2, 4]),
              't': rng.choice([15, 20, 30, 45, 60, 64, 90, 120, 128, 150, 180, 240, 256, 300, 360, 480, 600]), 'u': 'Мбайт'}
        return sp if 2 <= answer(sp) <= 4000 else None
    if fam == 'sndT':
        sp = {'f': fam, 'fr': rng.choice(FREQ), 'i': rng.choice([8, 16, 24, 32]), 'k': rng.choice([1, 2, 4]),
              'u': rng.choice(['Кбайт', 'Мбайт']), 'tu': rng.choice(['с', 'мин'])}
        t = rng.choice([30, 60, 64, 120, 128, 180, 240, 256, 300, 512, 600, 960, 1024, 1200])
        X = Fr(sp['fr'] * sp['i'] * sp['k'] * t, UNIT[sp['u']])
        if X.denominator != 1 or not 2 <= X <= 100000:
            return None
        sp['X'] = int(X)
        return sp if answer(sp).denominator == 1 else None
    if fam == 'send':
        v = rng.choice(SPEED)
        u = rng.choice(['Кбайт', 'Кбайт', 'Мбайт'])
        if rng.random() < .55:
            sp = {'f': fam, 'q': 'time', 'v': v, 'u': u, 'X': rng.choice([8, 16, 20, 25, 32, 40, 50, 60, 64, 80, 100,
                                                                             120, 125, 128, 200, 250, 256, 500, 512, 625, 1000, 1250, 2000, 2048, 3000, 4096])}
        else:
            sp = {'f': fam, 'q': 'size', 'v': v, 'u': u, 't': rng.choice([4, 8, 10, 16, 15, 20, 30, 32, 40, 60, 64, 90, 120, 128, 256])}
        a = answer(sp)
        return sp if a.denominator == 1 and 2 <= a <= 100000 else None
    if fam == 'send2':
        v1, v2 = rng.sample(SPEED, 2)
        sp = {'f': fam, 'v1': v1, 'v2': v2, 'X': rng.choice([10, 12, 16, 20, 24, 30, 32, 40, 48, 60, 64, 80, 96, 100, 120,
                                                             128, 160, 200, 250, 256, 320, 500, 512, 640, 1000, 1024])}
        a = answer(sp)
        return sp if a.denominator == 1 and 2 <= a <= 100000 and v1 / v2 not in (1,) else None
    if fam == 'imgK':
        sp = {'f': fam, 'W': W, 'H': H, **pick_color(rng, 4, 24), 'u': rng.choice(['Мбайт', 'Гбайт']),
              'X': rng.choice([16, 32, 50, 64, 100, 128, 200, 256, 500, 512, 1000])}
        if rng.random() < .5:
            sp['svc'] = rng.choice([128, 256, 512, 1000, 1024, 2048, 4096])
        if sp['u'] == 'Гбайт':
            sp['X'] = rng.choice([1, 2, 4, 8, 16, 32])
        a = answer(sp)
        return sp if 5 <= a <= 50000 else None
    if fam == 'imgSvc':
        i = rng.randint(3, 24)
        K = rng.choice([10, 16, 20, 25, 32, 40, 50, 64, 100, 128, 200, 256])
        svc = rng.choice([64, 128, 256, 512, 1024, 2048, 4096])
        need = K * (W * H * i + 8 * svc)
        u = rng.choice(['Мбайт', 'Мбайт', 'Гбайт'])
        X = ceil_div(need, UNIT[u])
        if X > 4000 or X < 2:
            return None
        sp = {'f': fam, 'W': W, 'H': H, 'K': K, 'svc': svc, 'X': X, 'u': u}
        if answer(sp) > 2 ** 24:
            return None
        # служебная информация должна что-то менять: без неё ответ был бы больше
        if answer(sp) == answer({**sp, 'svc': 0}):
            return None if rng.random() < .7 else sp
        return sp
    if fam == 'recode':
        N1 = rng.choice([2 ** rng.randint(4, 24), rng.choice(PALETTE)])
        N2 = rng.choice([2 ** rng.randint(1, 10), rng.choice(PALETTE[:12])])
        if bits(N2) >= bits(N1):
            return None
        sp = {'f': fam, 'N1': N1, 'N2': N2, 'D': rng.choice(range(5, 1500)), 'q': rng.choice(['old', 'old', 'new'])}
        a = answer(sp)
        if a.denominator != 1 or a < 2:
            return None
        if Fr(sp['D'] * UNIT['Кбайт'], bits(N1) - bits(N2)).denominator != 1:      # число пикселей целое
            return None
        return sp
    if fam in ('redig', 'redig2'):
        k1, k2 = rng.choice([(1, 2), (2, 1), (1, 4), (4, 1), (2, 4), (4, 2), (1, 1), (2, 2)])
        rf, ff = ratio(rng), ratio(rng)
        sp = {'f': fam, 'k1': k1, 'k2': k2, 'rf': rf, 'ff': ff}
        if fam == 'redig':
            sp['X'] = rng.choice(range(6, 241))
        else:
            sp['T1'] = rng.choice(range(10, 241))
            sp['c'] = ratio(rng)
            if sp['c'] in ('3/2', '2/3'):
                return None
        a = answer(sp)
        base = sp.get('X') or sp.get('T1')
        return sp if a.denominator == 1 and 2 <= a <= 5000 and a != base else None
    if fam == 'sendSnd':
        sp = {'f': fam, 'fr': rng.choice(FREQ), 'i': rng.choice([8, 16, 24]), 'k': rng.choice([1, 2]),
              't': rng.choice([10, 15, 20, 30, 45, 60, 90, 120]), 'v': rng.choice(SPEED[4:])}
        return sp if 3 <= answer(sp) <= 3000 else None
    if fam == 'compress':
        i = rng.randint(2, 24)
        p = rng.choice([10, 15, 20, 25, 30, 35, 40, 50, 60, 70, 75, 80])
        V = ceil_div(int(W * H * i * Fr(100 - p, 100)), UNIT['Кбайт']) + rng.randint(0, 20)
        sp = {'f': fam, 'W': W, 'H': H, 'V': V, 'vu': 'Кбайт', 'p': p}
        # без учёта сжатия ответ должен быть другим — иначе сжатие ничего не решает
        return sp if answer(sp) != answer({**sp, 'p': 0}) else None
    if fam == 'video':
        W, H = rng.choice([(320, 240), (640, 480), (800, 600), (1024, 768), (1280, 720), (1920, 1080), (480, 360), (256, 192)])
        sp = {'f': fam, 'W': W, 'H': H, 'F': rng.choice([10, 12, 15, 24, 25, 30, 50, 60]), **pick_color(rng, 4, 24),
              'q': rng.choice(['size', 'time'])}
        if rng.random() < .6:
            sp.update({'fr': rng.choice(FREQ), 'si': rng.choice([16, 24]), 'k': rng.choice([1, 2])})
        if sp['q'] == 'size':
            sp['t'] = rng.choice([5, 10, 12, 15, 20, 30, 45, 60, 90, 120])
            return sp if 10 <= answer(sp) <= 100000 else None
        sp.update({'X': rng.choice([1, 2, 4, 8, 16, 32, 64]), 'u': 'Гбайт'})
        return sp if 5 <= answer(sp) <= 20000 else None
    if fam == 'stream':
        sp = {'f': fam, 'W': W, 'H': H, 'T': rng.choice([2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 30]),
              'p': rng.choice([0, 0, 20, 25, 40, 50, 60, 75]), 'v': rng.choice(SPEED[3:])}
        a = answer(sp) if sp['W'] * sp['H'] * Fr(100 - sp['p'], 100) <= sp['v'] * sp['T'] else None
        return sp if a and 4 <= a <= 2 ** 24 else None
    if fam == 'sndMax':
        sp = {'f': fam, 'i': rng.choice([8, 16, 24, 32]), 'k': rng.choice([1, 2, 4]), 't': rng.choice([10, 20, 30, 60, 64, 90, 120, 128, 180, 300]),
              'u': 'Мбайт', 'X': rng.choice([1, 2, 3, 4, 5, 8, 10, 12, 16, 20, 25, 32, 40, 50, 64, 100]),
              'hdr': rng.choice([0, 0, 512, 1024, 2048, 4096, 10000])}
        a = answer(sp)
        return sp if 4000 <= a <= 200000 else None
    raise ValueError(fam)


# ------------------------------------------------------------------ условие, решение, пояснение
def to_unit_code(var, u):
    return f'{var} // 8' if u == 'байт' else f'{var} // 8 // {POW[u]}'


def build(sp, ans, rng):
    """(условие, решение на Python, пояснение, заголовок)."""
    f = sp['f']
    if f == 'img':
        W, H, n, u, i = sp['W'], sp['H'], sp['n'], sp['u'], colors(sp)
        intro = rng.choice(['Автоматическая камера производит растровые изображения размером',
                            'Растровое изображение имеет размер', 'Сканер создаёт растровые изображения размером',
                            'Графический редактор сохраняет растровые рисунки размером'])
        ask = (f'Сколько <b>{u}</b> занимает одно изображение?' if n == 1 else
               f'Сколько <b>{u}</b> нужно для хранения <b>{n}</b> таких изображений?')
        text = f'{intro} <b>{W} × {H}</b> пикселей. {PIC} {color_text(sp)} Сжатие не производится, размер заголовка файла не учитывается. {ask}'
        code = ('import math\n\n' if 'N' in sp else '') + (
            f'W, H = {W}, {H}\n{color_code(sp)}\n' + (f'n = {n}                     # изображений\n' if n > 1 else '') +
            f'bits = W * H * i{" * n" if n > 1 else ""}\nprint({to_unit_code("bits", u)})   # {u}')
        total = W * H * i * n
        note = (f'Вручную: {color_note(sp)}. Объём: {W} · {H} · {i}' + (f' · {n}' if n > 1 else '') +
                f' = {num(total)} бит = {num(total // 8)} байт = {num(ans)} {u}.')
        title = f'Изображение {W}×{H}, ' + (f'{sp["i"]} бит' if 'i' in sp else f'{sp["N"]} цветов') + \
                (f', {n} шт.' if n > 1 else '') + f' → {u}'
        return text, code, note, title
    if f in ('imgN', 'compress'):
        W, H, V = sp['W'], sp['H'], sp['V']
        if f == 'imgN':
            text = (f'Какое максимальное количество цветов можно использовать в палитре растрового изображения размером '
                    f'<b>{W} × {H}</b> пикселей, если для его хранения отведено <b>{V} Кбайт</b> памяти без учёта размера '
                    f'заголовка файла? {PIC} Сжатие не производится.')
            code = (f'W, H = {W}, {H}\nlimit = {V} * 2**10 * 8         # {V} Кбайт в битах\n'
                    f'i = limit // (W * H)            # бит на пиксель — округляем вниз\nprint(2 ** i)')
            i = int(math.log2(ans))
            note = (f'Вручную: в {V} Кбайт = {num(V * UNIT["Кбайт"])} бит, на пиксель приходится {num(V * UNIT["Кбайт"])} / '
                    f'{num(W * H)} ≈ {dec(Fr(V * UNIT["Кбайт"], W * H))} бита. Глубина цвета — целое число бит, округляем вниз: '
                    f'i = {i}, цветов 2<sup>{i}</sup> = {num(ans)}.')
            return text, code, note, f'Наибольшая палитра: {W}×{H} в {V} Кбайт'
        p = sp['p']
        text = (f'Для хранения произвольного растрового изображения размером <b>{W} × {H}</b> пикселей отведено '
                f'<b>{V} Кбайт</b> памяти без учёта размера заголовка файла. Для кодирования цвета каждого пикселя '
                'используется битовая маска одинаковой длины, коды пикселей записываются в файл один за другим без '
                'промежутков. После сохранения информации о цвете каждого пикселя изображение сжимается, размер итогового '
                f'файла становится на <b>{p}%</b> меньше исходного. Какое максимальное количество цветов можно использовать '
                'в изображении?')
        code = (f'W, H = {W}, {H}\nlimit = {V} * 2**10 * 8         # {V} Кбайт в битах\n\nbest = 0\n'
                f'for i in range(1, 33):           # бит на пиксель\n'
                f'    if W * H * i * (100 - {p}) <= limit * 100:   # после сжатия остаётся {100 - p}%\n'
                '        best = i\nprint(2 ** best)')
        i = int(math.log2(ans))
        room = V * UNIT['Кбайт'] * 100 // (100 - p)
        note = (f'Вручную: после сжатия остаётся {100 - p}% исходного объёма, поэтому до сжатия файл может занимать '
                f'{V} Кбайт · 100 / {100 - p} ≈ {dec(Fr(V * 100, 100 - p), 1)} Кбайт ≈ {num(room)} бит. '
                f'На пиксель: {num(room)} / {num(W * H)} ≈ '
                f'{dec(Fr(V * UNIT["Кбайт"] * 100, (100 - p) * W * H))}, округляем вниз: i = {i}, цветов 2<sup>{i}</sup> = {num(ans)}. '
                'Ловушка: сжатие уменьшает файл, значит до сжатия места больше, а не меньше.')
        return text, code, note, f'Сжатие на {p}%: палитра для {W}×{H} в {V} Кбайт'
    if f in ('snd', 'sndT', 'sendSnd', 'sndMax'):
        fr, i, k = sp.get('fr'), sp['i'], sp['k']
        if f == 'snd':
            t = sp['t']
            total = fr * i * k * t
            exact = total % UNIT['Мбайт'] == 0
            text = (f'Производилась {CHAN[k]} звукозапись с частотой дискретизации <b>{khz(fr)}</b> и '
                    f'<b>{i}-битным</b> разрешением. Запись длилась <b>{dur(t)}</b>, её результаты записываются в файл, '
                    'сжатие данных не производится. Определите размер полученного файла в <b>Мбайт</b>.' +
                    ('' if exact else ' В ответе запишите ближайшее к размеру файла целое число, <b>не меньшее</b> его.'))
            code = (('' if exact else 'import math\n\n') +
                    f'f, i, k, t = {fr}, {i}, {k}, {t}   # частота, разрешение, каналы, секунды\nbits = f * i * k * t\n' +
                    ('print(bits // 8 // 2**20)        # Мбайт' if exact else 'print(math.ceil(bits / 8 / 2**20))   # Мбайт, вверх'))
            note = f'Вручную: I = f · i · k · t = {fr} · {i} · {k} · {t} = {num(total)} бит = ' + (
                f'{ans} Мбайт.' if exact else f'{dec(Fr(total, UNIT["Мбайт"]), 3)} Мбайт, округляем вверх: {ans}.')
            return text, code, note, f'Звук: {khz(fr)}, {i} бит, {CHAN_SHORT[k]}, {t} с'
        if f == 'sndT':
            X, u, tu = sp['X'], sp['u'], sp['tu']
            text = (f'Производилась {CHAN[k]} звукозапись с частотой дискретизации <b>{khz(fr)}</b> и <b>{i}-битным</b> '
                    f'разрешением. В результате был получен файл размером <b>{X} {u}</b>, сжатие данных не производилось. '
                    f'Сколько {"<b>секунд</b>" if tu == "с" else "<b>минут</b>"} длилась запись?')
            code = (f'f, i, k = {fr}, {i}, {k}          # частота, разрешение, каналы\n'
                    f'bits = {X} * {POW[u]} * 8           # {X} {u} в битах\n'
                    f'print(bits // (f * i * k){" // 60" if tu == "мин" else ""})   # {"минуты" if tu == "мин" else "секунды"}')
            sec = X * UNIT[u] // (fr * i * k)
            note = (f'Вручную: t = I / (f · i · k) = {num(X * UNIT[u])} / ({fr} · {i} · {k}) = {sec} с'
                    + (f' = {ans} мин.' if tu == 'мин' else '.'))
            return text, code, note, f'Длительность записи: {X} {u}, {khz(fr)}, {i} бит, {CHAN_SHORT[k]}'
        if f == 'sendSnd':
            t, v = sp['t'], sp['v']
            total = fr * i * k * t
            exact = total % v == 0
            text = (f'Музыкальный фрагмент длительностью <b>{t} с</b> оцифрован в формате {CHAN_SHORT[k]} с частотой '
                    f'дискретизации <b>{khz(fr)}</b> и разрешением <b>{i} бит</b>, сжатие не производится. Полученный файл '
                    f'передаётся по каналу связи со скоростью <b>{v} бит/с</b>. Сколько секунд длится передача?' +
                    ('' if exact else ' В ответе укажите ближайшее целое число, <b>не меньшее</b> времени передачи.'))
            code = (('' if exact else 'import math\n\n') + f'f, i, k, t = {fr}, {i}, {k}, {t}\nbits = f * i * k * t\n'
                    f'v = {v}                    # бит/с\n' +
                    ('print(bits // v)' if exact else 'print(math.ceil(bits / v))'))
            note = (f'Вручную: объём I = {fr} · {i} · {k} · {t} = {num(total)} бит, время {num(total)} / {v} '
                    + (f'= {ans} с.' if exact else f'≈ {dec(Fr(total, v), 3)} с, округляем вверх: {ans}.'))
            return text, code, note, f'Передача звука: {khz(fr)}, {i} бит, {CHAN_SHORT[k]}, {t} с, {v} бит/с'
        X, u, t, hdr = sp['X'], sp['u'], sp['t'], sp['hdr']
        text = (f'Звуковой фрагмент длительностью <b>{t} с</b> записывается в формате {CHAN_SHORT[k]} с разрешением '
                f'<b>{i} бит</b> и сохраняется в файл без сжатия. ' +
                (f'Кроме звуковых данных, файл содержит заголовок размером <b>{hdr} байт</b>. ' if hdr else '') +
                f'Размер файла не должен превышать <b>{X} {u}</b>. С какой наибольшей частотой дискретизации (в Гц) можно '
                'записать фрагмент? В ответе запишите целое число.')
        code = (f'i, k, t = {i}, {k}, {t}       # разрешение, каналы, секунды\n'
                f'limit = {X} * {POW[u]} * 8 - {hdr} * 8   # место под звук, бит\n'
                'print(limit // (i * k * t))     # наибольшая частота, Гц')
        free = X * UNIT[u] - 8 * hdr
        note = (f'Вручную: под звук остаётся {num(X * UNIT[u])}' + (f' − {hdr} · 8' if hdr else '') + f' = {num(free)} бит; '
                f'f ≤ {num(free)} / ({i} · {k} · {t}) ≈ {dec(Fr(free, i * k * t))}, округляем вниз: {ans} Гц.')
        return text, code, note, f'Наибольшая частота: {X} {u}, {i} бит, {CHAN_SHORT[k]}, {t} с' + (f', заголовок {hdr} байт' if hdr else '')
    if f == 'send':
        v, u = sp['v'], sp['u']
        if sp['q'] == 'time':
            X = sp['X']
            text = (f'Файл размером <b>{X} {u}</b> передаётся через соединение со скоростью <b>{v} бит в секунду</b>. '
                    'Сколько секунд длится передача? В ответе укажите одно число.')
            code = f'bits = {X} * {POW[u]} * 8   # {X} {u} в битах\nv = {v}               # бит/с\nprint(bits // v)'
            note = f'Вручную: t = I / v = {X} · {num(UNIT[u])} / {v} = {num(X * UNIT[u])} / {v} = {ans} с.'
            return text, code, note, f'Время передачи: {X} {u} при {v} бит/с'
        t = sp['t']
        text = (f'Скорость передачи данных через некоторое соединение равна <b>{v} бит/с</b>. Передача файла через это '
                f'соединение заняла <b>{dur(t)}</b>. Определите размер файла в <b>{u}</b>.')
        code = f'v, t = {v}, {t}           # бит/с, секунды\nbits = v * t\nprint({to_unit_code("bits", u)})   # {u}'
        note = f'Вручную: I = v · t = {v} · {t} = {num(v * t)} бит = {ans} {u}.'
        return text, code, note, f'Размер файла: {v} бит/с за {t} с → {u}'
    if f == 'send2':
        X, v1, v2 = sp['X'], sp['v1'], sp['v2']
        text = (f'Файл размером <b>{X} Кбайт</b> передаётся через некоторое соединение со скоростью <b>{v1} бит в секунду</b>. '
                f'Определите размер файла (в Кбайт), который можно передать за то же время через другое соединение со '
                f'скоростью <b>{v2} бит в секунду</b>. В ответе укажите одно число — размер файла в Кбайт.')
        code = (f'v1, v2 = {v1}, {v2}       # бит/с\n'
                f'size = {X} * v2 // v1      # время одно и то же — размер растёт вместе со скоростью\nprint(size)   # Кбайт')
        note = f'Вручную: время одно и то же, поэтому размер меняется во столько же раз, что и скорость: {X} · {v2} / {v1} = {ans} Кбайт.'
        return text, code, note, f'Тот же срок, другой канал: {X} Кбайт, {v1} → {v2} бит/с'
    if f == 'imgK':
        W, H, X, u, svc, i = sp['W'], sp['H'], sp['X'], sp['u'], sp.get('svc', 0), colors(sp)
        text = (f'Фотоаппарат делает снимки размером <b>{W} × {H}</b> пикселей. {PIC} {color_text(sp)} ' +
                (f'Кроме того, к каждому снимку записывается <b>{svc} байт</b> служебной информации. ' if svc else '') +
                f'Снимки хранятся без сжатия. Какое наибольшее количество снимков поместится на карту памяти объёмом <b>{X} {u}</b>?')
        code = (('import math\n\n' if 'N' in sp else '') + f'W, H = {W}, {H}\n{color_code(sp)}\n'
                f'photo = W * H * i{f" + {svc} * 8" if svc else ""}   # бит на снимок\n'
                f'card = {X} * {POW[u]} * 8        # {X} {u} в битах\nprint(card // photo)')
        per = W * H * i + 8 * svc
        note = (f'Вручную: {color_note(sp)}; один снимок — {W} · {H} · {i}' + (f' + {svc} · 8' if svc else '') +
                f' = {num(per)} бит. На карте {num(X * UNIT[u])} бит, {num(X * UNIT[u])} / {num(per)} ≈ '
                f'{dec(Fr(X * UNIT[u], per))} — целых снимков {ans}.')
        return text, code, note, f'Снимков на карте {X} {u}: {W}×{H}, ' + (f'{sp["i"]} бит' if 'i' in sp else f'{sp["N"]} цветов') + (f', +{svc} байт' if svc else '')
    if f == 'imgSvc':
        W, H, K, svc, X, u = sp['W'], sp['H'], sp['K'], sp['svc'], sp['X'], sp['u']
        text = (f'Камера делает снимки размером <b>{W} × {H}</b> пикселей. Для каждого снимка дополнительно записывается '
                f'<b>{svc} байт</b> служебной информации. Изображения хранятся без сжатия, на каждый пиксель отводится '
                f'одинаковое число бит. Для хранения <b>{K}</b> снимков выделено <b>{X} {u}</b>. Какое максимальное '
                'количество цветов можно использовать в палитре?')
        code = (f'W, H, K = {W}, {H}, {K}         # размер и число снимков\nlimit = {X} * {POW[u]} * 8      # {X} {u} в битах\n'
                f'service = {svc} * 8               # служебная информация на снимок, бит\n'
                'i = (limit // K - service) // (W * H)   # бит на пиксель\nprint(2 ** i)')
        i = int(math.log2(ans))
        per = Fr(X * UNIT[u], K) - 8 * svc
        note = (f'Вручную: на один снимок приходится {num(X * UNIT[u])} / {K} бит, без служебной информации — '
                f'{num(int(per))} бит. На пиксель: {num(int(per))} / {num(W * H)} ≈ {dec(per / (W * H))}' +
                f', округляем вниз: i = {i}, цветов 2<sup>{i}</sup> = {num(ans)}.')
        return text, code, note, f'Палитра для {K} снимков {W}×{H} в {X} {u}, +{svc} байт'
    if f == 'recode':
        N1, N2, D, q = sp['N1'], sp['N2'], sp['D'], sp['q']
        i1, i2 = bits(N1), bits(N2)
        text = (f'Растровое изображение было сохранено в файле, при этом на каждый пиксель отводилось одинаковое минимально '
                f'возможное число бит, а палитра содержала <b>{N1} {plural(N1, "цвет", "цвета", "цветов")}</b>. Затем изображение было преобразовано: '
                f'количество цветов уменьшили до <b>{N2}</b>, размер изображения в пикселях не изменился. В результате размер '
                f'файла уменьшился на <b>{D} Кбайт</b>. Сколько Кбайт {"занимал исходный файл" if q == "old" else "занимает файл после преобразования"}? '
                'Размер заголовка файла не учитывается.')
        code = (f'import math\n\ni1 = math.ceil(math.log2({N1}))   # бит на пиксель до\n'
                f'i2 = math.ceil(math.log2({N2}))   # бит на пиксель после\n'
                f'pixels = {D} * 2**10 * 8 // (i1 - i2)   # {D} Кбайт — это pixels · (i1 − i2) бит\n'
                f'print(pixels * {"i1" if q == "old" else "i2"} // 8 // 2**10)   # Кбайт')
        old = int(Fr(D * i1, i1 - i2))
        note = (f'Вручную: было {cnt(i1, "бит", "бита", "бит")} на пиксель, стало {i2}. Разница {cnt(i1 - i2, "бит", "бита", "бит")} на пиксель — это {D} Кбайт, значит '
                f'один бит на пиксель «стоит» {frac(Fr(D, i1 - i2))} Кбайт. Исходный файл: {frac(Fr(D, i1 - i2))} · {i1} = {old} Кбайт'
                + (f', новый: {old} − {D} = {ans} Кбайт.' if q == 'new' else '.'))
        return text, code, note, f'Перекодировка {N1} → {N2} цветов, −{D} Кбайт: {"исходный" if q == "old" else "новый"} размер'
    if f in ('redig', 'redig2'):
        k1, k2, rf, ff = sp['k1'], sp['k2'], Fr(sp['rf']), Fr(sp['ff'])

        def times(x, more, less):
            y = x if x > 1 else 1 / x
            return f'в {frac(y) if y.denominator == 1 else dec(y, 1)} раза {more if x > 1 else less}'

        how = (f'с разрешением {times(rf, "выше", "ниже")} и частотой дискретизации {times(ff, "больше", "меньше")}, '
               'чем в первый раз')
        fmt = (f'Музыкальный фрагмент был записан в формате {CHAN_SHORT[k1]}, оцифрован и сохранён в виде файла без '
               'использования сжатия данных. ')
        again = (f'Затем тот же музыкальный фрагмент был записан повторно в формате {CHAN_SHORT[k2]} и оцифрован {how}. '
                 'Сжатие данных не производилось.')
        total = Fr(k2, k1) * rf * ff
        chans = CHAN_SHORT[k1] if k1 == k2 else f'{CHAN_SHORT[k1]} → {CHAN_SHORT[k2]}'
        chan_code = lambda v: f'{v} *= F({k2}, {k1})            # каналы: {chans}\n' if k1 != k2 else ''
        fac =' · '.join(x for x in [f'{k2}/{k1}' if k1 != k2 else '', frac(rf) if rf != 1 else '', frac(ff) if ff != 1 else ''] if x)
        if f == 'redig':
            X = sp['X']
            text = fmt + f'Размер полученного файла — <b>{X} Мбайт</b>. ' + again + ' Укажите размер файла в Мбайт, полученного при повторной записи.'
            code = (f'from fractions import Fraction as F\n\nsize = {X}                  # Мбайт\n'
                    + chan_code('size') +
                    f'size *= F({rf.numerator}, {rf.denominator})            # разрешение\n'
                    f'size *= F({ff.numerator}, {ff.denominator})            # частота дискретизации\nprint(size)')
            note = (f'Вручную: объём пропорционален числу каналов, разрешению и частоте, поэтому множители просто перемножаются: '
                    f'{X} · {fac} = {X} · {frac(total)} = {ans} Мбайт.')
            return text, code, note, f'Повторная оцифровка: {X} Мбайт, {chans}, ×{frac(rf)} разр., ×{frac(ff)} част.'
        T1, c = sp['T1'], Fr(sp['c'])
        ch = times(c, 'выше', 'ниже')
        text = (fmt + f'Получившийся файл был передан в город А по каналу связи за <b>{dur(T1)}</b>. ' + again +
                f' Полученный файл был передан в город Б; пропускная способность канала связи с городом Б <b>{ch}</b>, '
                'чем канала связи с городом А. Сколько секунд длилась передача файла в город Б? В ответе запишите только целое число.')
        code = (f'from fractions import Fraction as F\n\nt = {T1}                    # секунд до города А\n'
                + chan_code('t') +
                f't *= F({rf.numerator}, {rf.denominator})            # разрешение\n'
                f't *= F({ff.numerator}, {ff.denominator})            # частота дискретизации\n'
                f't /= F({c.numerator}, {c.denominator})            # канал в город Б\nprint(t)')
        note = (f'Вручную: время передачи пропорционально объёму файла и обратно пропорционально скорости канала: '
                f'{T1} · {fac} / {frac(c)} = {ans} с. Ловушка: более быстрый канал уменьшает время, а не увеличивает.')
        return text, code, note, f'Передача в город Б: {T1} с, {chans}, ×{frac(rf)}, ×{frac(ff)}, канал ×{frac(c)}'
    if f == 'video':
        W, H, F, i = sp['W'], sp['H'], sp['F'], colors(sp)
        snd = 'fr' in sp
        per_sec = F * W * H * i + (sp['fr'] * sp['si'] * sp['k'] if snd else 0)
        intro = (f'Камера снимает видео без сжатия с частотой <b>{F} кадров в секунду</b>. Размер кадра — <b>{W} × {H}</b> '
                 f'пикселей, каждый кадр кодируется отдельно, {color_text(sp, False).replace("в изображении используется", "используется")}. ')
        if snd:
            intro += (f'Одновременно записывается звук: {CHAN_SHORT[sp["k"]]}, частота дискретизации <b>{khz(sp["fr"])}</b>, '
                      f'разрешение <b>{sp["si"]} бит</b>, тоже без сжатия. ')
        sound_code = (f'sound = {sp["fr"]} * {sp["si"]} * {sp["k"]}    # бит звука в секунду\n' if snd else '')
        head = (('import math\n\n' if 'N' in sp or sp['q'] == 'size' else '') + f'W, H, F = {W}, {H}, {F}\n{color_code(sp)}\n' +
                sound_code + f'per_sec = F * W * H * i{" + sound" if snd else ""}   # бит в секунду\n')
        if sp['q'] == 'size':
            t = sp['t']
            text = intro + f'Сколько <b>Мбайт</b> займёт ролик длительностью <b>{t} с</b>? В ответе запишите ближайшее целое число, не меньшее размера ролика.'
            code = head + f'print(math.ceil(per_sec * {t} / 8 / 2**20))   # Мбайт, вверх'
            note = (f'Вручную: {color_note(sp)}; за секунду записывается {F} · {W} · {H} · {i}' +
                    (f' + {sp["fr"]} · {sp["si"]} · {sp["k"]}' if snd else '') + f' = {num(per_sec)} бит. За {t} с — '
                    f'{num(per_sec * t)} бит ≈ {dec(Fr(per_sec * t, UNIT["Мбайт"]))} Мбайт, округляем вверх: {ans}.')
            return text, code, note, f'Видео {W}×{H}, {F} к/с' + (' со звуком' if snd else '') + f', {t} с → Мбайт'
        X, u = sp['X'], sp['u']
        text = intro + f'Какое наибольшее целое число секунд видео поместится на носитель объёмом <b>{X} {u}</b>?'
        code = head + f'print({X} * 2**30 * 8 // per_sec)   # целых секунд'
        note = (f'Вручную: {color_note(sp)}; одна секунда — {F} · {W} · {H} · {i}' +
                (f' + {sp["fr"]} · {sp["si"]} · {sp["k"]}' if snd else '') + f' = {num(per_sec)} бит. '
                f'{X} {u} = {num(X * UNIT[u])} бит, {num(X * UNIT[u])} / {num(per_sec)} ≈ {dec(Fr(X * UNIT[u], per_sec))}'
                f' — целых секунд {ans}.')
        return text, code, note, f'Видео {W}×{H}, {F} к/с' + (' со звуком' if snd else '') + f': секунд на {X} {u}'
    if f == 'stream':
        W, H, T, p, v = sp['W'], sp['H'], sp['T'], sp['p'], sp['v']
        text = (f'Камера каждые <b>{dur(T)}</b> делает снимок размером <b>{W} × {H}</b> пикселей и передаёт его по '
                f'каналу связи со скоростью <b>{v} бит/с</b>; передача снимка должна заканчиваться не позже, чем будет сделан '
                f'следующий. {PIC} ' + (f'Перед передачей снимок сжимается, его размер уменьшается на <b>{p}%</b>. ' if p else
                                         'Сжатие не используется. ') +
                'Какое наибольшее количество цветов может быть в палитре?')
        test = f'W * H * i * (100 - {p}) <= v * T * 100' if p else 'W * H * i <= v * T'
        code = (f'W, H, T, v = {W}, {H}, {T}, {v}   # размер, секунды между снимками, бит/с\n\nbest = 0\n'
                f'for i in range(1, 33):             # бит на пиксель\n'
                f'    if {test}:   # снимок успевает уйти за T секунд\n        best = i\nprint(2 ** best)')
        i = int(math.log2(ans))
        room = v * T * Fr(100, 100 - p)
        note = (f'Вручную: за {T} с канал передаёт {v} · {T} = {num(v * T)} бит' +
                (f'; это {100 - p}% исходного снимка, значит до сжатия снимок может занимать {num(v * T)} · 100 / {100 - p} ≈ {num(int(room))} бит' if p else '') +
                f'. На пиксель: {num(int(room))} / {num(W * H)} ≈ {dec(room / (W * H))}' +
                f', округляем вниз: i = {i}, цветов {num(ans)}.')
        return text, code, note, f'Поток снимков {W}×{H} каждые {T} с по {v} бит/с' + (f', сжатие {p}%' if p else '')
    raise ValueError(f)


PLAN = (
    # базовый: одна формула — объём изображения, звука, время передачи
    [('Б', 'img')] * 14 + [('Б', 'imgN')] * 9 + [('Б', 'snd')] * 10 + [('Б', 'sndT')] * 6 + [('Б', 'send')] * 8 +
    [('Б', 'send2')] * 8 +
    # средний: служебная информация, перекодировка, повторная оцифровка, звук по каналу
    [('П', 'imgK')] * 6 + [('П', 'imgSvc')] * 6 + [('П', 'recode')] * 6 + [('П', 'redig')] * 7 + [('П', 'sendSnd')] * 5 +
    # сложный: сжатие, видео со звуком, поток снимков, наибольшая частота, передача после оцифровки
    [('В', 'compress')] * 4 + [('В', 'video')] * 4 + [('В', 'stream')] * 3 + [('В', 'sndMax')] * 2 + [('В', 'redig2')] * 2
)


def make(rng, fam):
    for _ in range(200000):
        sp = rand_spec(rng, fam)
        if not sp:
            continue
        a = answer(sp)
        if isinstance(a, Fr):
            if a.denominator != 1:
                continue
            a = int(a)
        if a < 2:
            continue
        return sp, a
    raise RuntimeError(f'не удалось собрать {fam}')


def main():
    rng = random.Random(SEED)
    out = []
    for k, (level, fam) in enumerate(PLAN, 1):
        while True:
            sp, ans = make(rng, fam)
            text, code, note, ttl = build(sp, ans, rng)
            if ttl not in {p['title'] for p in out}:
                break
        meta = json.dumps(sp, ensure_ascii=False, separators=(',', ':'))
        out.append({'id': f'7-g{k:03d}', 'task': 7, 'level': level, 'title': ttl, 'text': text,
                    'extra': f'<!--spec:{meta}-->', 'code': code, 'answer': str(ans), 'data': '', 'dname': '',
                    'note': note})
    for p in out:
        r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=60,
                           encoding='utf-8', env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        if r.stdout.strip() != p['answer']:
            raise SystemExit(f"{p['id']}: решение даёт «{r.stdout.strip()}», ответ «{p['answer']}»\n{r.stderr}\n{p['code']}")
    stat = {}
    for p in out:
        stat[p['level']] = stat.get(p['level'], 0) + 1
    print(json.dumps(stat, ensure_ascii=False), file=sys.stderr)
    sys.stdout.reconfigure(encoding='utf-8')
    json.dump(out, sys.stdout, ensure_ascii=False)


if __name__ == '__main__':
    main()
