#!/usr/bin/env python3
"""Генератор задач ЕГЭ №11 (количество информации: пароли, идентификаторы, номера) для банка stackly.

    python3 tools/gen_task11.py > /tmp/task11.json    # 100 задач: 55 базовых, 30 средних, 15 сложных

Задача описывается spec: семейство (объём для K записей, доп. сведения, наибольший алфавит, длина, число записей,
запись из нескольких полей, наименьшая длина для M разных кодов…), алфавит из частей и числа. По spec строятся
условие, решение на Python, ответ и решение «руками» в пояснении. Решение запускается и должно вывести ответ.
Spec хранится в задаче HTML-комментарием <!--spec:…--> — по нему tests/test_bank_task11.py пересчитывает ответ
своим способом. Генерация детерминирована (seed).
"""
import json, math, os, random, subprocess, sys

SEED = 20261022
UNIT = {'байт': 1, 'Кбайт': 2 ** 10, 'Мбайт': 2 ** 20}
POW = {'байт': '1', 'Кбайт': '2**10', 'Мбайт': '2**20'}
# части алфавита: (как написать в условии, сколько символов)
PARTS = {
    'LAT': ('заглавные латинские буквы', 26),
    'lat': ('строчные латинские буквы', 26),
    'RUS': ('заглавные буквы русского алфавита', 33),
    'RUS32': ('заглавные буквы русского алфавита (кроме Ё)', 32),
    'DIG': ('десятичные цифры', 10),
}
SPECIAL = ['@#$%&', '!?*', '+-*/', '@#$', '!@#$%^&*', '_-', '$%&@#!']
LETTERS = 'АБВГДЕЖИКЛМНОПРСТУФХЦЧШЭЮЯ'
LATIN = 'ABCDEFGHKLMNPRSTUVWXYZ'
# контекст: что кодируется и чьё оно. lead — начало условия, {L} — «из 11 символов», {A} — алфавит.
# Формы: in_each — «в каждом пароле», many — «паролей», all — «пароли»; владелец: gen — «пользователя»,
# prep — «об одном пользователе», prep_pl — «о 120 пользователях», gen_pl — «120 пользователей»
CTX = [
    {'name': 'пароль', 'in_each': 'в каждом пароле', 'many': 'паролей', 'all': 'пароли',
     'gen': 'пользователя', 'prep': 'пользователе', 'prep_pl': 'пользователях', 'gen_pl': 'пользователей',
     'lead': 'При регистрации в компьютерной системе каждому пользователю выдаётся пароль, состоящий из {L} и содержащий только {A}.'},
    {'name': 'идентификатор', 'in_each': 'в каждом идентификаторе', 'many': 'идентификаторов', 'all': 'идентификаторы',
     'gen': 'объекта', 'prep': 'объекте', 'prep_pl': 'объектах', 'gen_pl': 'объектов',
     'lead': 'При регистрации в компьютерной системе каждому объекту сопоставляется идентификатор, состоящий из {L} и содержащий только {A}.'},
    {'name': 'автомобильный номер', 'in_each': 'в каждом номере', 'many': 'номеров', 'all': 'номера',
     'gen': 'автомобиля', 'prep': 'автомобиле', 'prep_pl': 'автомобилях', 'gen_pl': 'автомобилей',
     'lead': 'В некоторой стране автомобильный номер состоит из {L} и может содержать только {A}.'},
    {'name': 'серийный номер', 'in_each': 'в каждом номере', 'many': 'номеров', 'all': 'номера',
     'gen': 'изделия', 'prep': 'изделии', 'prep_pl': 'изделиях', 'gen_pl': 'изделий',
     'lead': 'На предприятии каждое изделие маркируется серийным номером, который состоит из {L} и может содержать только {A}.'},
    {'name': 'личный код', 'in_each': 'в каждом коде', 'many': 'кодов', 'all': 'коды',
     'gen': 'участника', 'prep': 'участнике', 'prep_pl': 'участниках', 'gen_pl': 'участников',
     'lead': 'Каждому участнику олимпиады присваивается личный код, который состоит из {L} и может содержать только {A}.'},
    {'name': 'номер заказа', 'in_each': 'в каждом номере', 'many': 'номеров', 'all': 'номера',
     'gen': 'заказа', 'prep': 'заказе', 'prep_pl': 'заказах', 'gen_pl': 'заказов',
     'lead': 'Каждому заказу в интернет-магазине присваивается номер, который состоит из {L} и может содержать только {A}.'},
]
# второе поле записи для сложных задач: (что хранится, наибольшее значение)
FIELDS = {
    'пароль': [('номер отдела — целое число от 0 до', [15, 30, 63, 100, 200, 500]),
               ('уровень доступа — целое число от 0 до', [3, 7, 9, 12, 20])],
    'идентификатор': [('код типа объекта — целое число от 0 до', [31, 50, 99, 127, 255, 999])],
    'автомобильный номер': [('пробег в километрах — целое число от 0 до', [99999, 500000, 999999])],
    'серийный номер': [('количество изделий на складе — целое число от 0 до', [1000, 4095, 5000, 65535])],
    'личный код': [('набранные баллы — целое число от 0 до', [100, 300, 400, 1000])],
    'номер заказа': [('сумма заказа в рублях — целое число от 0 до', [10000, 50000, 100000, 1000000])],
}


def bits(n):
    """Минимальное число бит, чтобы закодировать n разных значений: ⌈log₂ n⌉."""
    return (n - 1).bit_length()


def ceil_div(a, b):
    return -(-a // b)


def plural(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def cnt(n, one, few, many):
    return f'{n} {plural(n, one, few, many)}'


def num(n):
    return f'{n:,}'.replace(',', ' ')


# ------------------------------------------------------------------ алфавит
def alpha_size(al):
    """al — список частей: имя из PARTS, ('set', строка символов) или ('n', мощность набора)."""
    n = 0
    for a in al:
        n += PARTS[a][1] if isinstance(a, str) else len(a[1]) if a[0] == 'set' else a[1]
    return n


def alpha_text(al):
    out = []
    for a in al:
        if isinstance(a, str):
            out.append(PARTS[a][0])
        elif a[0] == 'set':
            out.append(set_kind(a[1]) + ' ' + ', '.join(a[1]))
        else:
            out.append(f'символы из {a[1]}-символьного набора')
    if len(out) == 1:
        return out[0]
    return ', '.join(out[:-1]) + ' и ' + out[-1]


def alpha_code(al):
    """Мощность алфавита в решении: 26 + 10 + len('@#$')."""
    parts = []
    for a in al:
        if isinstance(a, str):
            parts.append(f'{PARTS[a][1]}')
        elif a[0] == 'set':
            parts.append(f"len('{a[1]}')" if len(a[1]) > 3 else str(len(a[1])))
        else:
            parts.append(str(a[1]))
    return ' + '.join(parts)


def set_kind(chars):
    return 'буквы' if chars.isalpha() else 'цифры' if chars.isdigit() else 'символы'


def alpha_comment(al):
    return ', '.join(PARTS[a][0] if isinstance(a, str) else (set_kind(a[1]) if a[0] == 'set' else f'{a[1]} символов')
                     for a in al)


def rand_alpha(rng, big=False):
    r = rng.random()
    if r < .25:      # буквы из списка: «А, Б, В, Г, Д»
        k = rng.randint(3, 12)
        src = LETTERS if rng.random() < .6 else LATIN
        return [('set', ''.join(sorted(rng.sample(src, k), key=src.index)))]
    if r < .4:
        return [('n', rng.choice([5, 7, 10, 12, 17, 20, 24, 30, 33, 40, 50, 60, 100, 120, 200, 250, 300, 500, 1000]))]
    parts = rng.sample(['LAT', 'lat', 'RUS', 'RUS32', 'DIG'], rng.choice([1, 2, 2, 3]))
    if 'RUS' in parts and 'RUS32' in parts:
        return None
    if 'lat' in parts and 'LAT' not in parts and rng.random() < .5:
        return None
    al = [p for p in ['LAT', 'lat', 'RUS', 'RUS32', 'DIG'] if p in parts]
    if rng.random() < .45:
        al.append(('set', rng.choice(SPECIAL)))
    return al


# ------------------------------------------------------------------ ответы
def rec_bytes(sp, L=None, N=None):
    """Байт на одну запись (без доп. сведений)."""
    L = sp['L'] if L is None else L
    N = alpha_size(sp['al']) if N is None else N
    b = L * bits(N)
    if sp.get('L2'):
        b += sp['L2'] * bits(alpha_size(sp['al2']))
    if sp.get('M'):
        b += bits(sp['M'] + 1)
    return ceil_div(b, 8)


def answer(sp):
    f = sp['f']
    if f in ('pw', 'multi', 'two'):
        return sp['K'] * (rec_bytes(sp) + sp.get('E', 0)) // UNIT[sp['u']]
    if f == 'extra':
        return sp['V'] // sp['K'] - rec_bytes(sp)
    if f in ('maxN', 'maxNbig'):
        lim = sp['X'] * UNIT[sp['u']]
        i = max(i for i in range(1, 40) if sp['K'] * (ceil_div(sp['L'] * i, 8) + sp.get('E', 0)) <= lim)
        return 2 ** i
    if f == 'maxL':
        lim = sp['X'] * UNIT[sp['u']]
        return max(L for L in range(1, 10000) if sp['K'] * (rec_bytes(sp, L=L) + sp.get('E', 0)) <= lim)
    if f == 'maxK':
        return sp['X'] * UNIT[sp['u']] // (rec_bytes(sp) + sp.get('E', 0))
    if f == 'minL':
        N, L = alpha_size(sp['al']), 1
        while N ** L < sp['need']:
            L += 1
        return sp['K'] * (rec_bytes(sp, L=L) + sp.get('E', 0))
    raise ValueError(f)


# ------------------------------------------------------------------ случайные spec
KS = [10, 12, 15, 16, 20, 24, 25, 30, 32, 35, 40, 48, 50, 60, 64, 75, 80, 90, 100, 120, 128, 150, 200, 250, 256,
      300, 400, 500, 512, 600, 640, 1000, 1024, 2000, 2048]


def good_k(k):
    # «о 21 пользователе» — не та форма; берём K, после которых годится «о K пользователях»
    return not (k % 10 == 1 and k % 100 != 11)


def rand_spec(rng, fam):
    ctx = rng.randrange(len(CTX))
    al = rand_alpha(rng)
    if not al:
        return None
    N = alpha_size(al)
    if N < 3:
        return None
    sp = {'f': fam, 'ctx': ctx, 'al': al, 'L': rng.randint(5, 30)}
    if CTX[ctx]['name'] == 'автомобильный номер':
        sp['L'] = rng.randint(5, 12)
    K = rng.choice(KS)
    if fam == 'pw':
        sp.update({'K': K, 'u': 'байт'})
        if rng.random() < .5:
            sp['E'] = rng.choice([5, 8, 10, 12, 15, 16, 20, 24, 25, 30, 32, 40, 50, 64])
        if rng.random() < .25:      # ответ в Кбайт — только если делится нацело
            sp['u'] = 'Кбайт'
            if answer({**sp, 'u': 'байт'}) % 1024:
                return None
    elif fam == 'extra':
        sp['K'] = K
        E = rng.choice(range(3, 70))
        sp['V'] = K * (rec_bytes(sp) + E)
    elif fam in ('maxN', 'maxNbig'):
        i = rng.randint(2, 12)
        if fam == 'maxN':
            sp.update({'K': K, 'u': rng.choice(['байт', 'Кбайт'])})
            sp['L'] = rng.randint(8, 300)
        else:
            sp.update({'K': rng.choice([4096, 8192, 10000, 32768, 65536, 100000, 131072]), 'u': 'Мбайт',
                       'L': rng.choice([100, 128, 150, 200, 250, 256, 300, 400, 500, 512, 1000]),
                       'E': rng.choice([0, 0, 16, 32, 64, 100, 128])})
        need = sp['K'] * (ceil_div(sp['L'] * i, 8) + sp.get('E', 0))
        sp['X'] = ceil_div(need, UNIT[sp['u']]) + rng.choice([0, 0, 1])
        del sp['al']
    elif fam == 'maxL':
        sp.update({'K': K, 'u': rng.choice(['байт', 'байт', 'Кбайт'])})
        if rng.random() < .4:
            sp['E'] = rng.choice([4, 8, 10, 12, 16, 20])
        need = K * (rec_bytes(sp) + sp.get('E', 0))
        sp['X'] = ceil_div(need, UNIT[sp['u']]) + rng.randint(0, 3)
        del sp['L']
    elif fam == 'maxK':
        sp.update({'u': rng.choice(['Кбайт', 'Кбайт', 'Мбайт'])})
        if rng.random() < .5:
            sp['E'] = rng.choice([4, 8, 10, 12, 16, 20, 24, 30])
        sp['X'] = rng.choice([1, 2, 3, 4, 5, 8, 10, 16, 20, 32, 50, 64, 100] if sp['u'] == 'Кбайт' else [1, 2, 4, 8])
    elif fam == 'multi':
        name = CTX[ctx]['name']
        what, ms = rng.choice(FIELDS[name])
        sp.update({'K': K, 'u': 'байт', 'M': rng.choice(ms), 'fw': what})
        if rng.random() < .5:
            sp['E'] = rng.choice([8, 10, 12, 16, 20, 32])
    elif fam == 'two':
        al1 = rng.choice([[('set', ''.join(sorted(rng.sample(LETTERS, rng.randint(4, 14)), key=LETTERS.index)))], ['RUS'], ['LAT']])
        al2 = rng.choice([['DIG'], [('set', '0123456789'[:rng.randint(3, 8)])]])
        sp.update({'al': al1, 'al2': al2, 'L': rng.randint(2, 6), 'L2': rng.randint(2, 8), 'K': K, 'u': 'байт'})
        if rng.random() < .5:
            sp['E'] = rng.choice([8, 10, 12, 16, 20, 32])
    elif fam == 'minL':
        sp.update({'K': K, 'need': rng.choice([1000, 5000, 10000, 50000, 100000, 500000, 1000000, 2000000, 10 ** 7, 10 ** 8])})
        del sp['L']
        if rng.random() < .5:
            sp['E'] = rng.choice([8, 10, 12, 16, 20])
    else:
        raise ValueError(fam)
    if not good_k(sp.get('K', 2)):
        return None
    a = answer(sp)
    if a < 2:
        return None
    if fam in ('pw', 'multi', 'two') and a > 10 ** 7:
        return None
    if fam == 'maxL' and not 3 <= a <= 500:
        return None
    if fam == 'maxK' and not 3 <= a <= 10 ** 6:
        return None
    if fam == 'multi' and rec_bytes(sp) == ceil_div(sp['L'] * bits(alpha_size(sp['al'])), 8):
        return None      # второе поле должно влиять на ответ
    if fam == 'two':
        # если кодировать весь номер одним алфавитом, ответ другой — иначе две части ничего не меняют
        one = ceil_div((sp['L'] + sp['L2']) * bits(alpha_size(sp['al']) + alpha_size(sp['al2'])), 8)
        if one == rec_bytes(sp):
            return None
    if fam == 'minL':
        N = alpha_size(sp['al'])
        if N ** 2 >= sp['need'] or N >= 200:
            return None
    return sp


# ------------------------------------------------------------------ условие, решение, пояснение
CODING = ('Каждый символ кодируется одинаковым и минимально возможным количеством бит, а каждый {name} — одинаковым '
          'и минимально возможным целым количеством байт.')


def symbols(L):
    return cnt(L, 'символа', 'символов', 'символов')


def cap(s):
    return s[0].upper() + s[1:]


def bit_word(n):
    return cnt(n, 'бит', 'бита', 'бит')


def byte_word(n):
    return f'{num(n)} {plural(n, "байт", "байта", "байт")}'


def extra_text(sp):
    c = CTX[sp['ctx']]
    return (f' Кроме того, для каждого {c["gen"]} хранятся дополнительные сведения, для которых отведено '
            f'<b>{cnt(sp["E"], "байт", "байта", "байт")}</b>.' if sp.get('E') else '')


def one_of(al):
    """Символ одной части номера: «заглавная латинская буква», «одна из букв А, Б, В», «одна из цифр 0, 1, 2»."""
    a = al[0]
    if isinstance(a, str):
        return {'LAT': 'заглавная латинская буква', 'RUS': 'заглавная буква русского алфавита', 'DIG': 'десятичная цифра'}[a]
    return ('одна из цифр ' if a[1][0].isdigit() else 'одна из букв ') + ', '.join(a[1])


def build(sp, ans):
    f = sp['f']
    c = CTX[sp['ctx']]
    name, K, E = c['name'], sp.get('K'), sp.get('E', 0)
    plus_e = f' + {E}' if E else ''
    times_per = f'(per + {E})' if E else 'per'
    if f in ('maxN', 'maxNbig'):
        L, X, u = sp['L'], sp['X'], sp['u']
        text = (f'{cap(name)} состоит из <b>{symbols(L)}</b>, все символы берутся из одного и того же алфавита. ' +
                CODING.format(name=name) + extra_text(sp) +
                f' Для хранения сведений о <b>{K}</b> {c["prep_pl"]} отведено не более <b>{X} {u}</b>. '
                'Какое наибольшее количество символов может быть в алфавите?')
        code = ('import math\n\n' f'L, K = {L}, {K}\nlimit = {X * UNIT[u] if u == "байт" else f"{X} * {POW[u]}"}' + (f'          # {X} {u} в байтах' if u != 'байт' else '') +
                '\n\nbest = 0\nfor i in range(1, 40):                # бит на символ\n'
                f'    if K * {f"(math.ceil(L * i / 8){plus_e})" if E else "math.ceil(L * i / 8)"} <= limit:\n        best = i\n'
                'print(2 ** best)                      # при i битах в алфавите не больше 2**i символов')
        i = ans.bit_length() - 1
        per, per2 = ceil_div(L * i, 8) + E, ceil_div(L * (i + 1), 8) + E
        note = (f'Вручную: на одну запись приходится не более {num(X * UNIT[u])} / {K} → {byte_word(X * UNIT[u] // K)}'
                + (f', из них {E} — доп. сведения' if E else '') +
                f'. При i = {i} бит на символ запись занимает ⌈{L} · {i} / 8⌉{plus_e} = {byte_word(per)} — помещается, '
                f'при i = {i + 1} — {byte_word(per2)}, уже нет. Значит, i = {i}, а в алфавите не больше 2<sup>{i}</sup> = {num(ans)} символов.')
        return text, code, note, f'Наибольший алфавит: {K} шт. по {L} символов в {X} {u}' + (f', +{E} байт' if E else '')
    N = alpha_size(sp['al'])
    i = bits(N)
    ac = alpha_code(sp['al'])
    ncode = f'N = {ac}' + ' ' * max(1, 34 - len(ac)) + f'# {alpha_comment(sp["al"])}'
    head = f'import math\n\n{ncode}\ni = math.ceil(math.log2(N))           # бит на символ\n'
    alpha_note = f'в алфавите {cnt(N, "символ", "символа", "символов")}, {N} ≤ 2<sup>{i}</sup> → {bit_word(i)} на символ'
    if f == 'two':
        L, L2 = sp['L'], sp['L2']
        N2 = alpha_size(sp['al2'])
        i2 = bits(N2)
        text = (f'{cap(name)} состоит из двух частей: сначала идут <b>{cnt(L, "символ", "символа", "символов")}</b>, каждый из которых — {one_of(sp["al"])}, '
                f'затем <b>{cnt(L2, "символ", "символа", "символов")}</b>, каждый из которых — {one_of(sp["al2"])}. Символы каждой части кодируются '
                f'одинаковым и минимально возможным для этой части количеством бит. Весь {name} записывается подряд, без '
                'промежутков, и занимает одинаковое и минимально возможное целое количество байт.' + extra_text(sp) +
                f' Сколько байт нужно для хранения сведений о <b>{K}</b> {c["prep_pl"]}?')
        code = (f'import math\n\nN1 = {alpha_code(sp["al"])}   # первая часть\nN2 = {alpha_code(sp["al2"])}   # вторая часть\n'
                'i1 = math.ceil(math.log2(N1))\ni2 = math.ceil(math.log2(N2))\n'
                f'per = math.ceil(({L} * i1 + {L2} * i2) / 8)   # байт на {name}\nprint({K} * {times_per})')
        b = L * i + L2 * i2
        per = ceil_div(b, 8)
        note = (f'Вручную: в первой части алфавит из {N} символов → {bit_word(i)} на символ, во второй — из {N2} → '
                f'{bit_word(i2)}. Весь {name}: {L} · {i} + {L2} · {i2} = {b} бит → ⌈{b} / 8⌉ = {byte_word(per)}'
                + (f', с доп. сведениями {byte_word(per + E)}' if E else '') + f'. Для {K} {c["gen_pl"]}: {K} · {per + E} = {num(ans)} байт.')
        return text, code, note, f'{cap(name)} из двух частей: {L} + {L2} символов, {K} шт.' + (f', +{E} байт' if E else '')
    if f == 'minL':
        need = sp['need']
        L = 1
        while N ** L < need:
            L += 1
        text = (f'{cap(name)} может содержать только {alpha_text(sp["al"])}; все {c["all"]} одинаковой длины. Длина выбрана '
                f'наименьшей, при которой можно составить не менее <b>{num(need)}</b> различных {c["many"]}. ' +
                CODING.format(name=name) + extra_text(sp) + f' Сколько байт нужно для хранения сведений о <b>{K}</b> {c["prep_pl"]}?')
        code = (f'import math\n\n{ncode}\nL = 1\nwhile N ** L < {need}:               # наименьшая длина\n    L += 1\n'
                'i = math.ceil(math.log2(N))           # бит на символ\n'
                f'per = math.ceil(L * i / 8)            # байт на {name}\nprint({K} * {times_per})')
        per = ceil_div(L * i, 8)
        note = (f'Вручную: из {N} символов можно составить {N}<sup>L</sup> разных строк длины L: {N}<sup>{L - 1}</sup> = '
                f'{num(N ** (L - 1))} < {num(need)}, а {N}<sup>{L}</sup> = {num(N ** L)} — хватает, значит, L = {L}. '
                f'На символ {bit_word(i)}, {name}: ⌈{L} · {i} / 8⌉ = {byte_word(per)}' +
                (f', с доп. сведениями {byte_word(per + E)}' if E else '') + f'. Всего {K} · {per + E} = {num(ans)} байт.')
        return text, code, note, f'Наименьшая длина для {num(need)} {c["many"]}, алфавит {N}: {K} шт.'
    if f == 'maxL':
        X, u = sp['X'], sp['u']
        text = (c['lead'].format(L='одинакового для всех количества символов', A=alpha_text(sp['al'])) + ' ' +
                CODING.format(name=name) + extra_text(sp) +
                f' Для хранения сведений о <b>{K}</b> {c["prep_pl"]} отведено <b>{X} {u}</b>. Какое наибольшее количество '
                f'символов может быть {c["in_each"]}?')
        code = (head + f'limit = {X * UNIT[u] if u == "байт" else f"{X} * {POW[u]}"}\n\nbest = 0\nfor L in range(1, 10000):\n'
                f'    if {K} * {f"(math.ceil(L * i / 8){plus_e})" if E else "math.ceil(L * i / 8)"} <= limit:\n        best = L\nprint(best)')
        room = X * UNIT[u] // K - E
        note = (f'Вручную: {alpha_note}. На одну запись приходится {num(X * UNIT[u])} / {K} → {num(X * UNIT[u] // K)} целых байт'
                + (f', без доп. сведений {room}' if E else '') + f' = {room * 8} бит. Длина: {room * 8} / {i} → {ans} '
                f'{plural(ans, "символ", "символа", "символов")} (проверка: ⌈{ans} · {i} / 8⌉ = {ceil_div(ans * i, 8)} ≤ {room}, '
                f'а ⌈{ans + 1} · {i} / 8⌉ = {ceil_div((ans + 1) * i, 8)} — уже больше).')
        return text, code, note, f'Наибольшая длина: {K} шт., алфавит {N}, {X} {u}' + (f', +{E} байт' if E else '')
    L = sp['L']
    base = c['lead'].format(L=f'<b>{symbols(L)}</b>', A=alpha_text(sp['al'])) + ' ' + CODING.format(name=name)
    per = ceil_div(L * i, 8)
    start = f'Вручную: {alpha_note}. Один {name}: {L} · {i} = {L * i} бит → ⌈{L * i} / 8⌉ = {byte_word(per)}'
    if f == 'pw':
        u = sp['u']
        text = base + extra_text(sp) + f' Определите объём памяти (в {"байтах" if u == "байт" else u}), необходимый для хранения сведений о <b>{K}</b> {c["prep_pl"]}.'
        code = (head + f'per = math.ceil({L} * i / 8)            # байт на {name}\n' +
                (f'print({K} * {times_per} // 2**10)   # Кбайт' if u == 'Кбайт' else f'print({K} * {times_per})'))
        note = (start + (f', с доп. сведениями {byte_word(per + E)}' if E else '') +
                f'. Для {K} {c["gen_pl"]}: {K} · {per + E} = {num(K * (per + E))} байт' + (f' = {ans} Кбайт.' if u == 'Кбайт' else '.') +
                ' Ловушка: округлять до целого байта нужно каждую запись, а не общий объём.')
        return text, code, note, (f'{cap(name)} из {L} символов, алфавит {N}: {K} шт.' + (f', +{E} байт' if E else '') +
                                  (' → Кбайт' if u == 'Кбайт' else ''))
    if f == 'extra':
        V = sp['V']
        text = (base + f' Кроме того, для каждого {c["gen"]} хранятся дополнительные сведения, для которых отведено одинаковое '
                f'целое число байт. Для хранения сведений о <b>{K}</b> {c["prep_pl"]} потребовалось <b>{V} байт</b>. '
                f'Сколько байт выделено для хранения дополнительных сведений об одном {c["prep"]}?')
        code = head + f'per = math.ceil({L} * i / 8)            # байт на {name}\nprint({V} // {K} - per)'
        note = start + f'. На одну запись — {V} / {K} = {V // K} байт, значит, на доп. сведения остаётся {V // K} − {per} = {byte_word(ans)}.'
        return text, code, note, f'Доп. сведения: {K} шт. по {L} символов, алфавит {N}, всего {V} байт'
    if f == 'maxK':
        X, u = sp['X'], sp['u']
        text = (base + extra_text(sp) + f' Сведения о скольких {c["prep_pl"]} поместятся в <b>{X} {u}</b> памяти? '
                'В ответе запишите наибольшее целое число.')
        code = head + f'per = math.ceil({L} * i / 8){plus_e}' + ' ' * 6 + f'# байт на запись\nprint({X} * {POW[u]} // per)'
        note = (start + (f', с доп. сведениями {byte_word(per + E)}' if E else '') +
                f'. {X} {u} = {num(X * UNIT[u])} байт, {num(X * UNIT[u])} / {per + E} → целых записей {num(ans)}.')
        return text, code, note, f'Сколько записей в {X} {u}: {name}, {L} символов, алфавит {N}' + (f', +{E} байт' if E else '')
    if f == 'multi':
        M, fw = sp['M'], sp['fw']
        j = bits(M + 1)
        text = (c['lead'].format(L=f'<b>{symbols(L)}</b>', A=alpha_text(sp['al'])) +
                f' Для каждого {c["gen"]} в базе данных хранится запись, в которую входят {name} и {fw} <b>{M}</b>. '
                'Каждый символ кодируется одинаковым и минимально возможным количеством бит, число — минимально возможным '
                'количеством бит. Поля записываются подряд, без промежутков; запись целиком занимает одинаковое и минимально '
                'возможное целое количество байт.' + extra_text(sp) +
                f' Сколько байт нужно для хранения сведений о <b>{K}</b> {c["prep_pl"]}?')
        code = (head + f'j = math.ceil(math.log2({M} + 1))      # бит на число от 0 до {M}\n'
                f'per = math.ceil(({L} * i + j) / 8)     # байт на запись\nprint({K} * {times_per})')
        b = L * i + j
        rec = ceil_div(b, 8)
        note = (f'Вручную: {alpha_note}; число от 0 до {M} — это {cnt(M + 1, "значение", "значения", "значений")} → {bit_word(j)}. '
                f'Запись: {L} · {i} + {j} = {b} бит → ⌈{b} / 8⌉ = {byte_word(rec)}' + (f', с доп. сведениями {byte_word(rec + E)}' if E else '') +
                f'. Для {K} {c["gen_pl"]}: {K} · {rec + E} = {num(ans)} байт. Ловушка: если округлить до байт отдельно {name} '
                f'(⌈{L * i} / 8⌉ = {ceil_div(L * i, 8)}) и число (⌈{j} / 8⌉ = {ceil_div(j, 8)}), получится другой ответ — '
                'поля здесь записаны подряд.')
        return text, code, note, f'Запись: {name} из {L} символов + число до {M}, {K} шт.'
    raise ValueError(f)


PLAN = (
    # базовый: прямой расчёт объёма для K записей, с доп. сведениями и без
    [('Б', 'pw')] * 55 +
    # средний: обратные задачи — доп. сведения, наибольший алфавит, длина, число записей
    [('П', 'extra')] * 8 + [('П', 'maxN')] * 7 + [('П', 'maxL')] * 7 + [('П', 'maxK')] * 8 +
    # сложный: запись из нескольких полей, две части с разными алфавитами, наименьшая длина, большие объёмы
    [('В', 'multi')] * 4 + [('В', 'two')] * 4 + [('В', 'minL')] * 4 + [('В', 'maxNbig')] * 3
)


def make(rng, fam):
    for _ in range(200000):
        sp = rand_spec(rng, fam)
        if sp:
            return sp, answer(sp)
    raise RuntimeError(f'не удалось собрать {fam}')


def main():
    rng = random.Random(SEED)
    out = []
    for k, (level, fam) in enumerate(PLAN, 1):
        while True:
            sp, ans = make(rng, fam)
            text, code, note, ttl = build(sp, ans)
            if ttl not in {p['title'] for p in out}:
                break
        meta = json.dumps(sp, ensure_ascii=False, separators=(',', ':'))
        out.append({'id': f'11-g{k:03d}', 'task': 11, 'level': level, 'title': ttl, 'text': text,
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
