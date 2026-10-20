#!/usr/bin/env python3
"""Генератор задач ЕГЭ №3 (реляционная база данных: «Движение товаров», «Товар», «Магазин») для банка stackly.

    python3 tools/gen_task3.py > /tmp/task3.json      # 100 задач: 55 базовых, 30 средних, 15 сложных

У каждой задачи своя база: магазины по районам, товары по отделам, движение товаров за период (поступления и
продажи; продаётся не больше, чем есть в магазине). Справочники показаны в условии таблицами, движение — файлом
3.txt (табуляция, первая строка — заголовок). Вопрос задаёт spec: семейство (продано единиц, поступило упаковок,
выручка, изменение количества, фильтр по датам, масса/объём, лучший магазин/товар/день, разница выручки районов,
остаток) и параметры. Ответ — целое число (там, где нужны килограммы или литры, данные подбираются так, чтобы
ответ вышел целым), ID магазина или артикул. Решение на Python из задачи запускается на её файле и должно вывести
ответ. Spec хранится в задаче комментарием <!--spec:…--> — tests/test_bank_task3.py пересчитывает
ответ своим способом по таблицам из условия и файлу. Генерация детерминирована (seed).
"""
import json, os, random, subprocess, sys, tempfile
from fractions import Fraction as Fr

SEED = 20261024
HEAD = ['ID операции', 'Дата', 'ID магазина', 'Артикул', 'Тип операции', 'Количество упаковок', 'Цена, руб./шт.']
DISTRICTS = ['Заречный', 'Центральный', 'Октябрьский', 'Ленинский', 'Северный', 'Южный', 'Кировский', 'Советский',
             'Первомайский', 'Приморский', 'Нагорный', 'Речной']
STREETS = ['ул. Лесная', 'пр. Мира', 'ул. Речная', 'ул. Садовая', 'ул. Ленина', 'ул. Гагарина', 'ул. Школьная',
           'ул. Победы', 'ул. Полевая', 'ул. Советская', 'пер. Почтовый', 'ул. Набережная', 'ул. Молодёжная',
           'пр. Строителей', 'ул. Заводская', 'ул. Кирова', 'ул. Пушкина', 'ул. Луговая', 'ул. Озёрная', 'ул. Мичурина']
# отдел: единица измерения и товары (название, количество единиц в упаковке, цена упаковки в рублях)
CATALOG = {
    'Молочная продукция': ('л', [('Молоко 3,2%', '1', 95), ('Молоко 2,5%', '0.9', 82), ('Кефир 1%', '0.5', 58),
                                  ('Ряженка 4%', '0.5', 64), ('Снежок', '0.5', 61), ('Простокваша', '0.9', 77)]),
    'Сыры': ('кг', [('Сыр гауда', '0.3', 290), ('Сыр российский', '0.25', 230), ('Сыр моцарелла', '0.125', 160),
                    ('Сыр творожный', '0.2', 175), ('Сыр сулугуни', '0.3', 310), ('Брынза', '0.25', 220)]),
    'Бакалея': ('кг', [('Сахар', '1', 85), ('Гречка', '0.8', 110), ('Рис круглый', '0.9', 105), ('Мука пшеничная', '2', 120),
                       ('Макароны', '0.45', 70), ('Соль', '1', 25), ('Пшено', '0.8', 60)]),
    'Мясная гастрономия': ('кг', [('Колбаса варёная', '0.5', 280), ('Ветчина', '0.4', 260), ('Сосиски', '0.45', 240),
                                  ('Колбаса сырокопчёная', '0.25', 330), ('Сардельки', '0.6', 300), ('Бекон', '0.2', 210)]),
    'Кондитерские изделия': ('кг', [('Печенье овсяное', '0.3', 95), ('Зефир', '0.25', 140), ('Шоколад молочный', '0.1', 120),
                                    ('Пряники', '0.4', 110), ('Вафли', '0.2', 80), ('Мармелад', '0.3', 150)]),
    'Напитки': ('л', [('Сок яблочный', '1', 130), ('Вода минеральная', '1.5', 65), ('Морс клюквенный', '0.9', 115),
                      ('Квас', '2', 120), ('Лимонад', '0.5', 70), ('Сок томатный', '1', 135)]),
    'Яйцо': ('шт', [('Яйцо С0', '10', 140), ('Яйцо С1', '10', 120), ('Яйцо перепелиное', '20', 150), ('Яйцо С2', '6', 70)]),
    'Хлеб': ('шт', [('Хлеб ржаной', '1', 55), ('Батон нарезной', '1', 50), ('Лаваш', '3', 75), ('Хлебцы', '2', 90),
                    ('Булочка с маком', '4', 120)]),
}
UNITW = {'л': ('литров', 'объём', 'в литрах'), 'кг': ('килограммов', 'масса', 'в килограммах'), 'шт': ('штук', '', '')}
MONTHS = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']


def plural(n, one, few, many):
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def num(n):
    return f'{n:,}'.replace(',', ' ')


def gen(name):
    """Заречный → Заречного (район в родительном падеже)."""
    return name[:-2] + 'ого'


def dec(s):
    return s.replace('.', ',')


def listing(xs):
    xs = list(xs)
    return xs[0] if len(xs) == 1 else ', '.join(xs[:-1]) + ' и ' + xs[-1]


# ------------------------------------------------------------------ база данных
def rand_db(rng, rows):
    """Справочники и движение товаров. Остатки не уходят в минус: продать можно только то, что поступило."""
    dists = rng.sample(DISTRICTS, rng.randint(3, 4))
    nshop = rng.randint(5, 7)
    names = dists + [rng.choice(dists) for _ in range(nshop - len(dists))]
    rng.shuffle(names)
    addr = rng.sample(STREETS, nshop)
    shops = [[f'M{i + 1}', d, f'{a}, {rng.randint(1, 60)}'] for i, (d, a) in enumerate(zip(names, addr))]
    goods = []
    for d in rng.sample(list(CATALOG), 3):
        unit, items = CATALOG[d]
        for name, per, price in rng.sample(items, rng.randint(3, 4)):
            goods.append([0, d, name, unit, per, price])
    rng.shuffle(goods)
    for g, a in zip(goods, sorted(rng.sample(range(1, 61), len(goods)))):
        g[0] = a
    goods.sort(key=lambda g: g[0])
    month = rng.randint(1, 12)
    days = rng.randint(6, 10)
    sale = {g[0]: g[5] + rng.choice([-5, 0, 0, 5, 10]) for g in goods}
    buy = {a: round(p * rng.choice([0.6, 0.65, 0.7, 0.75])) for a, p in sale.items()}
    # ассортимент: каждый магазин торгует частью товаров; в первый день всё это поступает
    assort = [(s[0], a) for s in shops for a in rng.sample([g[0] for g in goods], rng.randint(4, 6))]
    stock, ops = {}, []
    for shop, art in assort:
        q = rng.choice([20, 24, 25, 30, 36, 40, 48, 50, 60])
        ops.append([1, shop, art, 'Поступление', q, buy[art]])
        stock[(shop, art)] = q
    per_day = max(3, (rows - len(ops)) / days)
    for day in range(1, days + 1):
        n = max(3, round(per_day * rng.uniform(0.8, 1.2)))
        for shop, art in rng.sample(assort, min(n, len(assort))):
            have = stock[(shop, art)]
            if have < 6 or (day > 1 and rng.random() < .1):
                q = rng.choice([10, 12, 15, 20, 24, 25, 30, 36, 40])
                ops.append([day, shop, art, 'Поступление', q, buy[art]])
                stock[(shop, art)] = have + q
            else:
                q = rng.randint(1, min(have, 25))
                ops.append([day, shop, art, 'Продажа', q, sale[art]])
                stock[(shop, art)] = have - q
    ops.sort(key=lambda o: (o[0], int(o[1][1:]), o[2], o[3] == 'Продажа'))
    return {'shops': shops, 'goods': [g[:5] for g in goods], 'month': month, 'days': days, 'ops': ops}


def date(db, day):
    return f'{day:02d}.{db["month"]:02d}.2026'


def data_text(db):
    lines = ['\t'.join(HEAD)]
    for i, (day, shop, art, typ, q, price) in enumerate(db['ops'], 1):
        lines.append('\t'.join(map(str, [i, date(db, day), shop, art, typ, q, price])))
    return '\n'.join(lines)


# ------------------------------------------------------------------ ответ по spec
def rows_of(db, sp, typ=None, days=None):
    """Строки движения, подходящие под район/отдел/товар из spec."""
    dist = {s[0]: s[1] for s in db['shops']}
    dept = {g[0]: g[1] for g in db['goods']}
    d1, d2 = days or (sp.get('d1', 1), sp.get('d2', db['days']))
    out = []
    for o in db['ops']:
        day, shop, art, t, q, price = o
        if typ and t != typ:
            continue
        if not d1 <= day <= d2:
            continue
        if 'R' in sp and dist[shop] != sp['R']:
            continue
        if 'D' in sp and dept[art] != sp['D']:
            continue
        if 'X' in sp and art != sp['X']:
            continue
        out.append(o)
    return out


def per(db):
    return {g[0]: Fr(g[4]) for g in db['goods']}


def argmax_unique(d):
    best = max(d.values())
    keys = [k for k, v in d.items() if v == best]
    return keys[0] if len(keys) == 1 else None


def answer(sp, db):
    f = sp['f']
    P = per(db)
    if f == 'qty':
        return sum(o[4] * P[o[2]] for o in rows_of(db, sp, 'Продажа'))
    if f == 'packsIn':
        return sum(o[4] for o in rows_of(db, sp, 'Поступление'))
    if f == 'revenue':
        return sum(o[4] * o[5] for o in rows_of(db, sp, 'Продажа'))
    if f == 'change':
        return sum(o[4] if o[3] == 'Поступление' else -o[4] for o in rows_of(db, sp))
    if f == 'dates':
        return sum(o[4] for o in rows_of(db, sp, 'Продажа'))
    if f == 'weight':
        return sum(o[4] * P[o[2]] for o in rows_of(db, sp, 'Продажа'))
    if f == 'profit':
        return sum(o[4] * o[5] * (1 if o[3] == 'Продажа' else -1) for o in rows_of(db, sp))
    if f == 'maxShop':
        tot = {s[0]: 0 for s in db['shops']}
        for o in rows_of(db, sp, 'Продажа'):
            tot[o[1]] += o[4]
        return argmax_unique(tot)
    if f == 'topProduct':
        tot = {g[0]: 0 for g in db['goods'] if g[1] == sp['D']}
        for o in rows_of(db, sp, 'Продажа'):
            tot[o[2]] += o[4] * o[5]
        return argmax_unique(tot)
    if f == 'bestDay':
        tot = {d: 0 for d in range(1, db['days'] + 1)}
        for o in rows_of(db, sp, 'Продажа'):
            tot[o[0]] += o[4] * o[5]
        return argmax_unique(tot)
    if f == 'compare':
        a = sum(o[4] * o[5] for o in rows_of(db, {**sp, 'R': sp['R']}, 'Продажа'))
        b = sum(o[4] * o[5] for o in rows_of(db, {**sp, 'R': sp['R2']}, 'Продажа'))
        return a - b
    if f == 'stock':
        return sum(o[4] * P[o[2]] * (1 if o[3] == 'Поступление' else -1) for o in rows_of(db, sp, days=(1, sp['d2'])))
    raise ValueError(f)


# ------------------------------------------------------------------ вопросы
def rand_q(rng, fam, db):
    dists = sorted({s[1] for s in db['shops']})
    depts = sorted({g[1] for g in db['goods']})
    R, D = rng.choice(dists), rng.choice(depts)
    X = rng.choice(db['goods'])[0]
    n = db['days']
    d1 = rng.randint(1, n - 3)
    d2 = rng.randint(d1 + 2, n)
    sp = {'f': fam}
    if fam in ('qty', 'packsIn', 'revenue'):
        sp.update({'R': R, 'X': X} if fam == 'qty' else {'R': R, 'D': D})
    elif fam in ('change', 'dates'):
        sp.update({'R': R, 'X': X, 'd1': d1, 'd2': d2})
    elif fam == 'weight':
        D = rng.choice([d for d in depts if CATALOG[d][0] != 'шт'] or [None])
        if not D:
            return None
        sp.update({'R': R, 'D': D, 'd1': d1, 'd2': d2})
    elif fam in ('maxShop', 'topProduct'):
        sp.update({'D': D} if fam == 'maxShop' else {'D': D, 'R': R})
    elif fam == 'profit':
        sp.update({'R': R, 'D': D})
    elif fam == 'bestDay':
        sp.update({'R': R, 'D': D})
    elif fam == 'compare':
        R2 = rng.choice([d for d in dists if d != R])
        sp.update({'R': R, 'R2': R2, 'D': D, 'd1': d1, 'd2': d2})
    elif fam == 'stock':
        D = rng.choice([d for d in depts if CATALOG[d][0] != 'шт'] or [None])
        if not D:
            return None
        sp.update({'R': R, 'D': D, 'd2': rng.randint(3, n - 1)})
    return sp


def good_answer(sp, a):
    f = sp['f']
    if a is None:
        return False
    if f in ('maxShop', 'topProduct', 'bestDay'):
        return True
    a = Fr(a)
    if a.denominator != 1:
        return False
    if f == 'change':
        return a != 0
    if f == 'profit':
        return a != 0
    return a > 1


def support(sp, db):
    """Сколько строк движения попадает под условие: в ответе должно сойтись несколько строк."""
    f = sp['f']
    typ = 'Поступление' if f == 'packsIn' else None if f in ('change', 'profit', 'stock') else 'Продажа'
    days = (1, sp['d2']) if f == 'stock' else None
    if f == 'compare':
        return min(len(rows_of(db, {**sp, 'R': r}, typ)) for r in (sp['R'], sp['R2']))
    return len(rows_of(db, sp, typ, days))


def make(rng, fam, rows, need):
    for _ in range(20000):
        db = rand_db(rng, rows)
        for _ in range(10):
            sp = rand_q(rng, fam, db)
            if not sp:
                continue
            if fam == 'compare' and answer(sp, db) < 0:
                sp['R'], sp['R2'] = sp['R2'], sp['R']
            a = answer(sp, db)
            if good_answer(sp, a) and support(sp, db) >= need:
                return sp, db, (a if isinstance(a, str) else int(a))
    raise RuntimeError(fam)


# ------------------------------------------------------------------ текст, код, пояснение
def html_table(head, rows, cls='db'):
    return (f'<div class="tblwrap"><table class="{cls}"><tr>' + ''.join(f'<th>{h}</th>' for h in head) + '</tr>'
            + ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>' for r in rows) + '</table></div>')


PREVIEW = 6


def extra_html(db):
    shops = html_table(['ID магазина', 'Район', 'Адрес'], db['shops'])
    goods = html_table(['Артикул', 'Отдел', 'Наименование', 'Ед. изм.', 'Количество в упаковке'],
                       [[g[0], g[1], g[2], g[3], dec(g[4])] for g in db['goods']])
    ops = [[i, date(db, o[0]), o[1], o[2], o[3], o[4], o[5]] for i, o in enumerate(db['ops'][:PREVIEW], 1)]
    return (f'<div class="dbgrid"><div><p class="cap">Магазин</p>{shops}</div><div><p class="cap">Товар</p>{goods}</div></div>'
            f'<p class="cap">Движение товаров</p>{html_table(HEAD, ops, "db small")}'
            f'<p class="muted" style="font-size:13px">Первые {PREVIEW} строк из {len(db["ops"])}. Весь файл 3.txt — '
            'кнопками «Показать» и «Скопировать».</p>')


def period(db, d1=1, d2=None):
    d2 = d2 or db['days']
    return f'с {d1} по {d2} {MONTHS[db["month"] - 1]} 2026 г.'


def intro(db):
    return ('В файле 3.txt приведён фрагмент базы данных «Продукты» о поставках товаров в магазины районов города. '
            'База данных состоит из трёх таблиц. Таблица «Движение товаров» содержит записи о поступлениях товаров в '
            f'магазины и о продажах {period(db)}: дату операции, ID магазина, артикул товара, тип операции '
            '(«Поступление» или «Продажа»), количество упаковок и цену одной упаковки в рублях. Таблица «Товар» '
            'содержит артикул, отдел, наименование, единицу измерения и количество единиц в упаковке. Таблица '
            '«Магазин» содержит ID магазина, район и адрес. ')


def goods_by(db):
    return {g[0]: g for g in db['goods']}


def py_dict(d, quote_key=False, indent=8):
    def k(x):
        return f"'{x}'" if quote_key else str(x)

    def v(x):
        return f"'{x}'" if isinstance(x, str) else str(x)

    items = [f'{k(a)}: {v(b)}' for a, b in d.items()]
    lines, cur = [], ''
    for it in items:
        if len(cur) + len(it) > 92:
            lines.append(cur.rstrip())
            cur = ''
        cur += it + ', '
    lines.append(cur.rstrip(', '))
    return '{' + ('\n' + ' ' * indent).join(lines) + '}'


LOOP = '''
with open('3.txt', encoding='utf-8') as f:
    next(f)                                       # строка заголовка
    for line in f:
        oid, date, shop, art, typ, q, price = line.strip().split('\\t')
        art, q, price = int(art), int(q), int(price)
'''


def code_for(sp, db):
    f = sp['f']
    G = goods_by(db)
    dist = {s[0]: s[1] for s in db['shops']}
    head = f'district = {py_dict(dist, True, 12)}  # «Магазин»: ID → район\n'
    if 'D' in sp:
        head += f'dept = {py_dict({a: g[1] for a, g in G.items()})}  # «Товар»: артикул → отдел\n'
    if f in ('qty', 'weight', 'stock'):
        head += 'per_pack = ' + py_dict({a: (int(Fr(g[4])) if Fr(g[4]).denominator == 1 else float(g[4]))
                                         for a, g in G.items()}, indent=12) + '  # единиц в упаковке\n'
    conds = []
    if 'R' in sp and f != 'compare':
        conds.append(f"district[shop] == '{sp['R']}'")
    if 'D' in sp:
        conds.append(f"dept[art] == '{sp['D']}'")
    if 'X' in sp:
        conds.append(f'art == {sp["X"]}')
    if 'd1' in sp:
        conds.append(f'{sp["d1"]} <= int(date[:2]) <= {sp["d2"]}')
    if f == 'stock':
        conds.append(f'int(date[:2]) <= {sp["d2"]}')
    sale = "typ == 'Продажа'"
    inc = "typ == 'Поступление'"
    cond = lambda *extra: ' and '.join(list(extra) + conds)
    if f in ('qty', 'weight'):
        body = f'''total = 0{LOOP}        if {cond(sale)}:
            total += q * per_pack[art]
print(round(total))                               # round убирает погрешность дробных чисел'''
    elif f in ('packsIn', 'dates'):
        body = f'''total = 0{LOOP}        if {cond(inc if f == 'packsIn' else sale)}:
            total += q
print(total)'''
    elif f == 'revenue':
        body = f'''total = 0{LOOP}        if {cond(sale)}:
            total += q * price
print(total)'''
    elif f == 'change':
        body = f'''total = 0{LOOP}        if {cond()}:
            total += q if typ == 'Поступление' else -q
print(total)'''
    elif f == 'profit':
        body = f'''total = 0{LOOP}        if {cond()}:
            total += q * price if typ == 'Продажа' else -q * price
print(total)'''
    elif f == 'stock':
        body = f'''total = 0{LOOP}        if {cond()}:
            total += q * per_pack[art] if typ == 'Поступление' else -q * per_pack[art]
print(round(total))                               # round убирает погрешность дробных чисел'''
    elif f == 'maxShop':
        body = f'''packs = {{}}{LOOP}        if {cond(sale)}:
            packs[shop] = packs.get(shop, 0) + q
print(max(packs, key=packs.get))'''
    elif f == 'topProduct':
        body = f'''money = {{}}{LOOP}        if {cond(sale)}:
            money[art] = money.get(art, 0) + q * price
print(max(money, key=money.get))'''
    elif f == 'bestDay':
        body = f'''money = {{}}{LOOP}        if {cond(sale)}:
            day = int(date[:2])
            money[day] = money.get(day, 0) + q * price
print(max(money, key=money.get))'''
    elif f == 'compare':
        body = f'''money = {{}}{LOOP}        if {cond(sale)}:
            money[district[shop]] = money.get(district[shop], 0) + q * price
print(money['{sp['R']}'] - money['{sp['R2']}'])'''
    return head + '\n' + body + '\n'


def qtext(sp, db):
    f = sp['f']
    G = goods_by(db)
    R = sp.get('R')
    where = f'в магазинах {gen(R)} района' if R else ''
    if 'X' in sp:
        g = G[sp['X']]
        what = f'товара «{g[2]}»'
    if 'D' in sp:
        dw = f'товаров отдела «{sp["D"]}»'
    per_ = period(db, sp.get('d1', 1), sp.get('d2'))
    if f == 'qty':
        u = UNITW[g[3]][0]
        return (f'Используя информацию из приведённой базы данных, определите, сколько <b>{u}</b> {what} было '
                f'<b>продано</b> {where} за весь период. В ответе запишите только число.')
    if f == 'packsIn':
        return (f'Определите, сколько упаковок {dw} <b>поступило</b> в магазины {gen(R)} района за весь период. В ответе запишите только число.')
    if f == 'revenue':
        return (f'Определите <b>выручку</b> (в рублях) от продажи {dw} {where} за весь период. '
                'В ответе запишите только число.')
    if f == 'change':
        return (f'Определите, на сколько упаковок <b>изменилось</b> количество {what} {where} {per_} (поступления '
                'минус продажи). Если количество уменьшилось, запишите ответ со знаком минус.')
    if f == 'dates':
        return f'Определите, сколько упаковок {what} было <b>продано</b> {where} {per_} В ответе запишите только число.'
    if f == 'weight':
        u = CATALOG[sp['D']][0]
        return (f'Определите общую {"<b>массу</b>" if u == "кг" else "<b>объём</b>"} (в {"килограммах" if u == "кг" else "литрах"}) '
                f'{dw}, проданных {where} {per_} В ответе запишите только число.').replace('общую <b>объём</b>', 'общий <b>объём</b>')
    if f == 'maxShop':
        return (f'Определите <b>ID магазина</b>, в котором за весь период было продано больше всего упаковок {dw}. '
                'Такой магазин один.')
    if f == 'topProduct':
        return (f'Какой товар отдела «{sp["D"]}» принёс <b>наибольшую выручку</b> {where} за весь период? '
                'В ответе запишите его <b>артикул</b>. Такой товар один.')
    if f == 'profit':
        return (f'Определите, на сколько рублей выручка от продажи {dw} {where} за весь период больше суммы, '
                'потраченной на поступившие упаковки этих товаров (цена поступления указана в той же таблице). '
                'Если потрачено больше, чем выручено, запишите ответ со знаком минус.')
    if f == 'bestDay':
        return (f'В какой день выручка от продажи {dw} {where} была <b>наибольшей</b>? В ответе запишите только '
                'число месяца. Такой день один.')
    if f == 'compare':
        return (f'На сколько рублей выручка от продажи {dw} в магазинах {gen(R)} района {per_} больше, чем в '
                f'магазинах {gen(sp["R2"])} района за те же дни? В ответе запишите только число.')
    if f == 'stock':
        u = CATALOG[sp['D']][0]
        return (f'В начале периода {dw} в магазинах не было. Сколько {UNITW[u][0]} {dw} осталось {where} к концу '
                f'дня {sp["d2"]} {MONTHS[db["month"] - 1]}? В ответе запишите только число.')
    raise ValueError(f)


def fr_text(x):
    x = Fr(x)
    if x.denominator == 1:
        return num(x.numerator)
    return str(float(x)).replace('.', ',')


def note_for(sp, db, ans):
    f = sp['f']
    G = goods_by(db)
    parts = []
    if 'R' in sp and f != 'compare':
        ids = [s[0] for s in db['shops'] if s[1] == sp['R']]
        parts.append(f'Магазины {gen(sp["R"])} района: {", ".join(ids)}.')
    if 'D' in sp:
        arts = [str(a) for a, g in G.items() if g[1] == sp['D']]
        parts.append(f'Артикулы отдела «{sp["D"]}»: {", ".join(arts)}.')
    if 'X' in sp:
        g = G[sp['X']]
        parts.append(f'«{g[2]}» — артикул {g[0]}, в упаковке {dec(g[4])} {g[3]}.')
    P = per(db)
    if f in ('qty', 'weight'):
        rs = rows_of(db, sp, 'Продажа')
        packs = {}
        for o in rs:
            packs[o[2]] = packs.get(o[2], 0) + o[4]
        parts.append(f'Подходящих строк «Продажа»: {len(rs)}. Упаковки × количество в упаковке: ' +
                     ' + '.join(f'{fr_text(q)}·{dec(G[a][4])}' for a, q in sorted(packs.items())) + f' = {num(ans)}.')
    elif f in ('packsIn', 'dates'):
        rs = rows_of(db, sp, 'Поступление' if f == 'packsIn' else 'Продажа')
        parts.append(f'Подходящих строк: {len(rs)}, сумма упаковок — {num(ans)}.')
    elif f == 'revenue':
        rs = rows_of(db, sp, 'Продажа')
        parts.append(f'Подходящих строк «Продажа»: {len(rs)}. Для каждой — упаковки × цена, сумма: {num(ans)} руб.')
    elif f == 'change':
        rs = rows_of(db, sp)
        inc = sum(o[4] for o in rs if o[3] == 'Поступление')
        out = sum(o[4] for o in rs if o[3] == 'Продажа')
        parts.append(f'Поступило {num(inc)} упак., продано {num(out)}: {num(inc)} − {num(out)} = {ans}.')
    elif f == 'profit':
        rs = rows_of(db, sp)
        a = sum(o[4] * o[5] for o in rs if o[3] == 'Продажа')
        b = sum(o[4] * o[5] for o in rs if o[3] == 'Поступление')
        parts.append(f'Выручка {num(a)} руб., на поступления потрачено {num(b)} руб.: {num(a)} − {num(b)} = {ans}.')
    elif f == 'maxShop':
        tot = {}
        for o in rows_of(db, sp, 'Продажа'):
            tot[o[1]] = tot.get(o[1], 0) + o[4]
        parts.append('Продано упаковок по магазинам: ' + ', '.join(f'{k} — {v}' for k, v in sorted(tot.items(), key=lambda x: int(x[0][1:]))) + f'. Больше всего — {ans}.')
    elif f == 'topProduct':
        tot = {}
        for o in rows_of(db, sp, 'Продажа'):
            tot[o[2]] = tot.get(o[2], 0) + o[4] * o[5]
        parts.append('Выручка по товарам: ' + ', '.join(f'{k} — {num(v)}' for k, v in sorted(tot.items()))
                     + f' руб. Больше всего — у артикула {ans}.')
    elif f == 'bestDay':
        tot = {}
        for o in rows_of(db, sp, 'Продажа'):
            tot[o[0]] = tot.get(o[0], 0) + o[4] * o[5]
        parts.append('Выручка по дням: ' + ', '.join(f'{k}-е — {num(v)}' for k, v in sorted(tot.items())) + f'. Наибольшая — {ans}-го числа.')
    elif f == 'compare':
        a = sum(o[4] * o[5] for o in rows_of(db, {**sp}, 'Продажа'))
        b = sum(o[4] * o[5] for o in rows_of(db, {**sp, 'R': sp['R2']}, 'Продажа'))
        ia = [s[0] for s in db['shops'] if s[1] == sp['R']]
        ib = [s[0] for s in db['shops'] if s[1] == sp['R2']]
        parts.insert(0, f'Магазины {gen(sp["R"])} района: {", ".join(ia)}; {gen(sp["R2"])}: {", ".join(ib)}.')
        parts.append(f'Выручка за эти дни: {num(a)} и {num(b)} руб., разница {num(ans)}.')
    elif f == 'stock':
        rs = rows_of(db, sp, days=(1, sp['d2']))
        inc = sum(o[4] * P[o[2]] for o in rs if o[3] == 'Поступление')
        out = sum(o[4] * P[o[2]] for o in rs if o[3] == 'Продажа')
        parts.append(f'С 1 по {sp["d2"]} число поступило {fr_text(inc)}, продано {fr_text(out)} '
                     f'(упаковки × количество в упаковке); осталось {fr_text(inc)} − {fr_text(out)} = {num(ans)}.')
    parts.append('В таблице удобно добавить к «Движению товаров» столбцы с районом и отделом через ВПР и включить фильтр.')
    return ' '.join(parts)


TITLE = {'qty': 'Продано {u}: «{x}», {r} район', 'packsIn': 'Поступление: {d}, {r} район',
         'revenue': 'Выручка: {d}, {r} район', 'change': 'Изменение: «{x}», {r} район, {d1}–{d2}',
         'dates': 'Продажи «{x}» {d1}–{d2}, {r} район', 'weight': '{W}: {d}, {r} район, {d1}–{d2}',
         'maxShop': 'Лучший магазин: {d}', 'topProduct': 'Лучший товар: {d}, {r} район',
         'profit': 'Выручка минус закупка: {d}, {r} район', 'bestDay': 'Лучший день: {d}, {r} район',
         'compare': 'Районы {r} и {r2}: {d}', 'stock': 'Остаток на {d2}-е: {d}, {r} район'}


def title(sp, db):
    G = goods_by(db)
    x = G[sp['X']] if 'X' in sp else None
    D = sp.get('D')
    return TITLE[sp['f']].format(u=UNITW[x[3]][0] if x else '', x=x[2] if x else '', r=sp.get('R', ''),
                                 r2=sp.get('R2', ''), d=D or '', d1=sp.get('d1'), d2=sp.get('d2'),
                                 W=('Масса' if D and CATALOG[D][0] == 'кг' else 'Объём'))


PLAN = (
    # базовый: продано в единицах, поступило упаковок, выручка, изменение количества, продажи за дни
    [('Б', 'qty', 80)] * 12 + [('Б', 'packsIn', 80)] * 10 + [('Б', 'revenue', 80)] * 12 +
    [('Б', 'change', 80)] * 11 + [('Б', 'dates', 80)] * 10 +
    # средний: масса/объём за дни, лучший магазин, лучший товар, выручка минус закупка
    [('П', 'weight', 100)] * 8 + [('П', 'maxShop', 100)] * 8 + [('П', 'topProduct', 100)] * 7 + [('П', 'profit', 100)] * 7 +
    # сложный: лучший день, сравнение районов за дни, остаток к дате
    [('В', 'bestDay', 120)] * 5 + [('В', 'compare', 120)] * 5 + [('В', 'stock', 120)] * 5
)


def main():
    rng = random.Random(SEED)
    out = []
    for k, (level, fam, rows) in enumerate(PLAN, 1):
        while True:
            sp, db, ans = make(rng, fam, rows, 3 if level == 'Б' else 5)
            ttl = title(sp, db)
            if ttl not in {p['title'] for p in out}:
                break
        meta = json.dumps(sp, ensure_ascii=False, separators=(',', ':'))
        out.append({'id': f'3-g{k:03d}', 'task': 3, 'level': level, 'title': ttl, 'text': intro(db) + qtext(sp, db),
                    'extra': f'<!--spec:{meta}-->' + extra_html(db), 'code': code_for(sp, db), 'answer': str(ans),
                    'data': data_text(db), 'dname': '3.txt', 'note': note_for(sp, db, ans)})
    with tempfile.TemporaryDirectory() as d:
        for p in out:
            open(os.path.join(d, '3.txt'), 'w', encoding='utf-8').write(p['data'] + '\n')
            r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=60, cwd=d,
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
