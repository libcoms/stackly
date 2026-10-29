#!/usr/bin/env python3
"""Генератор задач ЕГЭ-2027 по профильной математике, №4 (вероятность случайного события), для банка stackly.

    python3 tools/gen_math4.py > /tmp/m4.json      # 36 задач базового уровня

Классическое определение вероятности, как в банке ФИПИ: брак в партии, порядок выступлений, жребий, монеты,
игральные кости (в том числе «известно, что шестёрка не выпала»), доклады по дням конференции. Числа подбираются
так, чтобы ответ был конечной десятичной дробью. Описание <!--spec:…--> — модель опыта; tests/test_bank_math.py
перебирает исходы и считает вероятность заново.
"""
import random, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathkit import F, ans, n, item, emit, is_dec, rnd, plural

SEED = 20270104
TOPIC = 'Вероятность случайного события'
PLAN = ([('Б', 'defect')] * 6 + [('Б', 'order')] * 6 + [('Б', 'lot')] * 4 + [('Б', 'coins')] * 6
        + [('Б', 'dice')] * 6 + [('Б', 'dice_no6')] * 4 + [('Б', 'conf')] * 4)
# товар (кто), род. мн. для «из N …», «k … имеют дефект», состояние «годного», «бракованного» (творит. падеж)
GOODS = [('Сумки', 'сумок', 'имеют скрытый дефект', 'без скрытого дефекта', 'со скрытым дефектом'),
         ('Садовые насосы', 'садовых насосов', 'подтекают', 'исправным', 'неисправным'),
         ('Фонарики', 'фонариков', 'неисправны', 'исправным', 'неисправным'),
         ('Ручки', 'ручек', 'пишут плохо', 'качественной', 'бракованной')]
COUNTRIES = [('России', 'Китая', 'Японии', 'Кореи'), ('Норвегии', 'Швеции', 'Финляндии', 'Дании'), ('Бразилии', 'Аргентины', 'Чили', 'Перу')]
WORD = {2: 'два', 3: 'три', 4: 'четыре'}


def make(rng, fam):
    if fam == 'defect':
        g = rng.choice(GOODS)
        N = rng.choice([20, 25, 40, 50, 80, 100, 125, 200, 250, 400, 500, 1000])
        k = rng.randint(2, N // 8)              # «1 имеют дефект» — не по-русски
        good = rng.random() < 0.6
        p = F(N - k, N) if good else F(k, N)
        what = g[3] if good else g[4]
        thing = 'ручка' if g[0] == 'Ручки' else 'товар'
        text = (f'В среднем из {N} {g[1]}, поступивших в продажу, {k} {g[2]}. Найдите вероятность того, что случайно '
                f'{"выбранная" if thing == "ручка" else "выбранный"} для проверки {thing} окажется {what}.')
        sol = (f'Благоприятных исходов {"N − k = " + str(N - k) if good else str(k)} из {N}: $P = \\frac{{{N - k if good else k}}}{{{N}}} = {n(p)}$.')
        return {'fam': fam, 'N': N, 'k': k, 'good': good}, p, text, sol, f'{g[0]}: {k} из {N}, {"годный" if good else "брак"}'
    if fam == 'order':
        cs = rng.choice(COUNTRIES)
        m = rng.randint(3, 4)
        cnt = [rng.randint(3, 14) for _ in range(m)]
        N = sum(cnt)
        i = rng.randrange(m)
        pos = rng.choice(['первым', 'последним', f'{rng.randint(2, 9)}-м'])
        p = F(cnt[i], N)
        if not is_dec(p):
            return None
        lst = ', '.join(f'{c} из {cs[j]}' for j, c in enumerate(cnt))
        text = (f'В соревнованиях участвуют {N} {plural(N, "спортсмен", "спортсмена", "спортсменов")}: {lst}. Порядок выступлений определяется жребием. '
                f'Найдите вероятность того, что спортсмен, выступающий {pos}, окажется из {cs[i]}.')
        sol = (f'На любом месте с равными шансами может оказаться любой из {N} спортсменов, из {cs[i]} их {cnt[i]}: '
               f'$P = \\frac{{{cnt[i]}}}{{{N}}} = {n(p)}$.')
        return {'fam': fam, 'cnt': cnt, 'i': i}, p, text, sol, f'Жребий: {N} спортсменов, {pos} из {cs[i]}'
    if fam == 'lot':
        N = rng.choice([4, 5, 8, 10, 16, 20, 25, 40, 50])
        k = rng.randint(1, min(N - 1, 6))
        p = F(k, N)
        text = (f'В группе туристов {N} человек. С помощью жребия они выбирают {k} человек, которые должны идти в село '
                f'за продуктами. Турист А. хотел бы сходить в магазин, но он подчиняется жребию. Какова вероятность того, '
                f'что А. пойдёт в магазин?')
        sol = (f'Выбранных мест {k}, каждое из {N} человек с равными шансами занимает одно из них: $P = \\frac{{{k}}}{{{N}}} = {n(p)}$.')
        return {'fam': fam, 'N': N, 'k': k}, p, text, sol, f'Жребий: {k} из {N} туристов'
    if fam == 'coins':
        m = rng.choice([2, 3, 4])
        k = rng.randint(0, m)
        what = rng.choice(['exact', 'atleast'])
        from math import comb
        fav = comb(m, k) if what == 'exact' else sum(comb(m, j) for j in range(k, m + 1))
        p = F(fav, 2 ** m)
        if k == 0 and what == 'atleast':
            return None
        kk = {0: 'ни разу не выпадет', 1: 'выпадет ровно один раз', 2: 'выпадет ровно два раза', 3: 'выпадет ровно три раза', 4: 'выпадет ровно четыре раза'}[k] \
            if what == 'exact' else f'выпадет не меньше {k} {"раза" if k < 5 else "раз"}'
        text = f'В случайном эксперименте симметричную монету бросают {WORD[m]} раза. Найдите вероятность того, что орёл {kk}.'
        sol = (f'Всего исходов $2^{{{m}}} = {2 ** m}$, все равновозможны. Подходящих: {fav} '
               f'(число способов выбрать броски с орлом). $P = \\frac{{{fav}}}{{{2 ** m}}} = {n(p)}$.')
        return {'fam': fam, 'm': m, 'k': k, 'what': what}, p, text, sol, f'Монета {m} раза, орёл: {kk}'
    if fam in ('dice', 'dice_no6'):
        s = rng.randint(3, 11)
        op = rng.choice(['=', '≥', '≤']) if fam == 'dice' else '='
        out = [(a, b) for a in range(1, 7) for b in range(1, 7)]
        if fam == 'dice_no6':
            out = [(a, b) for a, b in out if a != 6 and b != 6]
        good = [o for o in out if {'=': sum(o) == s, '≥': sum(o) >= s, '≤': sum(o) <= s}[op]]
        p = F(len(good), len(out))
        if not good or len(good) == len(out):
            return None
        rel = {'=': 'равна', '≥': 'не меньше', '≤': 'не больше'}[op]
        if fam == 'dice':
            # из 36 исходов конечная дробь выходит редко — как в банке ФИПИ, ответ округляется до сотых
            text = (f'Игральную кость бросают дважды. Найдите вероятность того, что сумма выпавших очков {rel} {s}. '
                    'Результат округлите до сотых.')
            sol = (f'Исходов $6 \\cdot 6 = 36$. Подходящих пар — {len(good)}, поэтому $P = \\frac{{{len(good)}}}{{36}} '
                   f'\\approx {n(rnd(p))}$.')
            return {'fam': fam, 's': s, 'op': op, 'round': 2}, rnd(p), text, sol, f'Две кости: сумма {op} {s}'
        else:
            text = (f'Игральную кость бросили два раза. Известно, что шесть очков не выпало ни разу. Найдите при этом условии '
                    f'вероятность события «сумма выпавших очков равна {s}».')
            sol = (f'Раз шестёрки не было, исходов $5 \\cdot 5 = 25$. Сумму {s} дают {len(good)} из них: '
                   f'$P = \\frac{{{len(good)}}}{{25}} = {n(p)}$.')
        return {'fam': fam, 's': s, 'op': op}, p, text, sol, f'Две кости{", без шестёрок" if fam == "dice_no6" else ""}: сумма {op} {s}'
    # conf: N докладов, d дней, в первый день k, остальные поровну; доклад М. — в день j
    d = rng.randint(3, 5)
    rest = rng.randint(2, 12) * (d - 1)
    k = rng.randint(2, 30)
    N = k + rest
    j = rng.randint(2, d)
    p = F(rest // (d - 1), N)
    if not is_dec(p):
        return None
    text = (f'Конференция длится {d} {plural(d, "день", "дня", "дней")}. Всего запланировано {N} {plural(N, "доклад", "доклада", "докладов")}: в первый день {k}, остальные распределены '
            f'поровну между оставшимися днями. Порядок докладов определяется жеребьёвкой. Какова вероятность, что доклад '
            f'профессора М. окажется запланированным на {j}-й день конференции?')
    sol = (f'На {j}-й день приходится $({N} - {k}) : {d - 1} = {rest // (d - 1)}$ докладов. Доклад М. равновозможно '
           f'занимает любое из {N} мест: $P = \\frac{{{rest // (d - 1)}}}{{{N}}} = {n(p)}$.')
    return {'fam': fam, 'd': d, 'N': N, 'k': k, 'j': j}, p, text, sol, f'Конференция: {N} {plural(N, "доклад", "доклада", "докладов")}, {d} {plural(d, "день", "дня", "дней")}, день {j}'


def main():
    rng = random.Random(SEED)
    out = []
    titles = set()
    for k, (level, fam) in enumerate(PLAN, 1):
        for tries in range(5000):
            r = make(rng, fam)
            if r is None:
                continue
            sp, p, text, sol, title = r
            if title in titles or not is_dec(p) or p in (0, 1):
                continue
            titles.add(title)
            break
        else:
            raise SystemExit(f'№4, {fam}: не удалось подобрать задачу')
        out.append(item(4, k, level, TOPIC, title, text, sol, ans(p), sp))
    emit(out)


if __name__ == '__main__':
    main()
