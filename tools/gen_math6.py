#!/usr/bin/env python3
"""Генератор задач ЕГЭ-2027 по профильной математике, №6 (случайная величина — новое задание 2027 года),
для банка stackly.

    python3 tools/gen_math6.py > /tmp/m6.json      # 36 задач: 26 повышенных, 10 высоких

В банке ФИПИ таких задач ещё нет; темы — по спецификации и кодификатору 2027 года и демоверсии (матожидание
выигрыша лотереи): матожидание и дисперсия по таблице распределения (в том числе с пропущенной вероятностью),
стандартное отклонение, число успехов в серии испытаний (биномиальное распределение), свойства E(aX + b)
и D(aX + b), равномерное распределение на отрезке, симметрия нормального распределения. Описание <!--spec:…-->
— распределение; tests/test_bank_math.py пересчитывает ответ перебором исходов.
"""
import random, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathkit import F, ans, n, item, emit, is_dec, plural

SEED = 20270106
TOPIC = 'Случайная величина'
PLAN = ([('П', 'lottery')] * 5 + [('П', 'tableE')] * 5 + [('П', 'tableP')] * 4 + [('П', 'binE')] * 4 + [('П', 'linear')] * 4
        + [('П', 'uniform')] * 4 + [('В', 'tableD')] * 4 + [('В', 'std')] * 2 + [('В', 'binD')] * 2 + [('В', 'normal')] * 2)


def table(xs, ps, head='X'):
    return ('<div class="tblwrap"><table class="mtx"><tr><th>$' + head + '$</th>' + ''.join(f'<td>${n(x)}$</td>' for x in xs)
            + '</tr><tr><th>$P$</th>' + ''.join(f'<td>{"?" if p is None else "$" + n(p) + "$"}</td>' for p in ps) + '</tr></table></div>')


def rand_dist(rng, k):
    """k вероятностей в сотых (или десятых), сумма 1."""
    unit = rng.choice([10, 20, 100])
    cuts = sorted(rng.sample(range(1, unit), k - 1))
    ps = [F(b - a, unit) for a, b in zip([0] + cuts, cuts + [unit])]
    return ps if all(p > 0 for p in ps) else None


def make(rng, fam):
    if fam == 'lottery':
        N = rng.choice([1000, 10000, 5000, 2000])
        k = rng.randint(3, 5)
        vals = sorted(rng.sample([50, 100, 200, 500, 1000, 2000, 5000, 10000, 50000], k))
        cnts = sorted(rng.sample(range(1, N // 20), k), reverse=True)
        cnts = [c - c % 5 or 5 for c in cnts]
        if len(set(cnts)) < k:
            return None
        E = F(sum(v * c for v, c in zip(vals, cnts)), N)
        tbl = ('<div class="tblwrap"><table class="mtx"><tr><th>Выигрыш (в рублях)</th>' + ''.join(f'<td>{v:,}</td>'.replace(',', ' ') for v in vals)
               + '</tr><tr><th>Число выигрышных билетов</th>' + ''.join(f'<td>{c}</td>' for c in cnts) + '</tr></table></div>')
        text = (f'Организаторы лотереи выпустили {N:,} билетов. Выигрыши распределены следующим образом.'.replace(',', ' ')
                + tbl + 'Найдите математическое ожидание величины «выигрыш на один билет». Ответ дайте в рублях.')
        sol = ('Остальные билеты дают выигрыш 0. Матожидание — сумма «выигрыш × вероятность»: $E = \\frac{'
               + ' + '.join(f'{v} \\cdot {c}' for v, c in zip(vals, cnts)) + f'}}{{{N}}} = {n(E)}$ руб.')
        return {'fam': fam, 'xs': [0] + vals, 'ps': [str(F(N - sum(cnts), N))] + [str(F(c, N)) for c in cnts], 'q': 'E'}, E, text, sol, f'Лотерея: {N} билетов, {k} {plural(k, "вид", "вида", "видов")} выигрыша'
    if fam in ('tableE', 'tableP', 'tableD'):
        k = rng.randint(3, 5) if fam != 'tableD' else rng.randint(3, 4)
        ps = rand_dist(rng, k)
        if ps is None:
            return None
        xs = sorted(rng.sample(range(-5, 11), k))
        E = sum(x * p for x, p in zip(xs, ps))
        D = sum(x * x * p for x, p in zip(xs, ps)) - E * E
        if fam == 'tableE':
            text = 'Случайная величина $X$ имеет распределение, заданное таблицей.' + table(xs, ps) + 'Найдите математическое ожидание $E(X)$.'
            sol = '$E(X) = ' + ' + '.join(f'{n(x) if x >= 0 else "(" + n(x) + ")"} \\cdot {n(p)}' for x, p in zip(xs, ps)) + f' = {n(E)}$.'
            return {'fam': fam, 'xs': xs, 'ps': [str(p) for p in ps], 'q': 'E'}, E, text, sol, 'Матожидание по таблице: ' + ', '.join(map(str, xs))
        if fam == 'tableP':
            i = rng.randrange(k)
            shown = [None if j == i else p for j, p in enumerate(ps)]
            text = ('Случайная величина $X$ имеет распределение, заданное таблицей; одна вероятность неизвестна.'
                    + table(xs, shown) + 'Найдите математическое ожидание $E(X)$.')
            sol = (f'Сумма вероятностей равна 1, поэтому $P(X = {n(xs[i])}) = 1 - ' + ' - '.join(n(p) for p in shown if p is not None)
                   + f' = {n(ps[i])}$. Тогда $E(X) = ' + ' + '.join(f'{n(x) if x >= 0 else "(" + n(x) + ")"} \\cdot {n(p)}' for x, p in zip(xs, ps)) + f' = {n(E)}$.')
            return {'fam': fam, 'xs': xs, 'ps': [str(p) for p in ps], 'q': 'E'}, E, text, sol, 'Пропущенная вероятность: ' + ', '.join(map(str, xs))
        text = 'Случайная величина $X$ имеет распределение, заданное таблицей.' + table(xs, ps) + 'Найдите дисперсию $D(X)$.'
        sol = (f'$E(X) = {n(E)}$, $E(X^{{2}}) = ' + ' + '.join(f'{x * x} \\cdot {n(p)}' for x, p in zip(xs, ps))
               + f' = {n(E * E + D)}$. $D(X) = E(X^{{2}}) - (E(X))^{{2}} = {n(E * E + D)} - {n(E * E)} = {n(D)}$.')
        return {'fam': fam, 'xs': xs, 'ps': [str(p) for p in ps], 'q': 'D'}, D, text, sol, 'Дисперсия по таблице: ' + ', '.join(map(str, xs))
    if fam == 'std':
        c, a = rng.randint(-5, 10), rng.randint(1, 9)
        p = F(1, 2)
        xs, ps = [c - a, c + a], [p, p]
        text = ('Случайная величина $X$ принимает два значения с равными вероятностями.' + table(xs, ps)
                + 'Найдите стандартное отклонение $\\sigma(X)$.')
        sol = (f'$E(X) = \\frac{{{n(c - a)} + {n(c + a)}}}{{2}} = {c}$. Каждое значение отстоит от среднего на {a}, '
               f'поэтому $D(X) = {a}^{{2}} = {a * a}$ и $\\sigma(X) = \\sqrt{{D(X)}} = {a}$.')
        return {'fam': fam, 'xs': xs, 'ps': [str(p) for p in ps], 'q': 'S'}, F(a), text, sol, f'Стандартное отклонение: {c - a} и {c + a}'
    if fam in ('binE', 'binD'):
        m = rng.randint(4, 20)
        p = F(rng.randint(1, 9), 10)
        what = rng.choice([('Стрелок делает {m} выстрелов по мишени, вероятность попадания при каждом выстреле равна ${p}$, '
                            'выстрелы независимы. Случайная величина $X$ — число попаданий.', 'Стрелок'),
                           ('Баскетболист бросает мяч в кольцо {m} раз, вероятность попадания при каждом броске равна ${p}$, '
                            'броски независимы. Случайная величина $X$ — число попаданий.', 'Баскетболист'),
                           ('Проверяют {m} деталей; каждая независимо от других оказывается бракованной с вероятностью ${p}$. '
                            'Случайная величина $X$ — число бракованных деталей.', 'Детали')])
        base = what[0].format(m=m, p=n(p))
        if fam == 'binE':
            E = m * p
            text = base + ' Найдите математическое ожидание $E(X)$.'
            sol = f'$X$ — число успехов в {m} независимых испытаниях с вероятностью ${n(p)}$: $E(X) = np = {m} \\cdot {n(p)} = {n(E)}$.'
            return {'fam': fam, 'm': m, 'p': str(p), 'q': 'E'}, E, text, sol, f'{what[1]}: {m} испытаний, p = {n(p)}, E'
        D = m * p * (1 - p)
        text = base + ' Найдите дисперсию $D(X)$.'
        sol = f'Для числа успехов в {m} независимых испытаниях $D(X) = np(1 - p) = {m} \\cdot {n(p)} \\cdot {n(1 - p)} = {n(D)}$.'
        return {'fam': fam, 'm': m, 'p': str(p), 'q': 'D'}, D, text, sol, f'{what[1]}: {m} испытаний, p = {n(p)}, D'
    if fam == 'linear':
        E, D = F(rng.randint(-20, 30), rng.choice([1, 2, 10])), F(rng.randint(1, 40), rng.choice([1, 4, 10]))
        a, b = rng.choice([-3, -2, 2, 3, 4, 5]), rng.randint(-10, 10)
        q = rng.choice(['E', 'D'])
        res = a * E + b if q == 'E' else a * a * D
        expr = f'{a}X {"+" if b >= 0 else "-"} {abs(b)}'
        text = (f'Известно, что $E(X) = {n(E)}$ и $D(X) = {n(D)}$. Найдите '
                + (f'математическое ожидание $E({expr})$.' if q == 'E' else f'дисперсию $D({expr})$.'))
        sol = (f'$E(aX + b) = aE(X) + b = {a} \\cdot {n(E) if E >= 0 else "(" + n(E) + ")"} {"+" if b >= 0 else "-"} {abs(b)} = {n(res)}$.' if q == 'E'
               else f'Сдвиг на число не меняет разброс, а множитель выносится в квадрате: $D(aX + b) = a^{{2}}D(X) = {a * a} \\cdot {n(D)} = {n(res)}$.')
        return {'fam': fam, 'E': str(E), 'D': str(D), 'a': a, 'b': b, 'q': q}, res, text, sol, f'Свойства {q}: {expr}, E = {n(E)}, D = {n(D)}'
    if fam == 'uniform':
        a = rng.randint(-5, 10)
        L = rng.choice([2, 4, 5, 8, 10, 20, 25])
        b = a + L
        q = rng.choice(['P', 'E', 'D'])
        if q == 'P':
            c, dd = sorted(rng.sample(range(a, b + 1), 2))
            res = F(dd - c, L)
            text = (f'Случайная величина $X$ равномерно распределена на отрезке $[{a}; {b}]$. Найдите вероятность '
                    f'$P({c} \\le X \\le {dd})$.')
            sol = f'Для равномерного распределения вероятность пропорциональна длине: $\\frac{{{dd} - ({c})}}{{{b} - ({a})}} = \\frac{{{dd - c}}}{{{L}}} = {n(res)}$.'.replace('- (', '- (')
            return {'fam': fam, 'a': a, 'b': b, 'c': c, 'd': dd, 'q': q}, res, text, sol, f'Равномерное [{a}; {b}]: P от {c} до {dd}'
        if q == 'E':
            res = F(a + b, 2)
            text = f'Случайная величина $X$ равномерно распределена на отрезке $[{a}; {b}]$. Найдите математическое ожидание $E(X)$.'
            sol = f'Матожидание равномерного распределения — середина отрезка: $\\frac{{{a} + {b}}}{{2}} = {n(res)}$.'.replace('+ -', '- ')
            return {'fam': fam, 'a': a, 'b': b, 'q': q}, res, text, sol, f'Равномерное [{a}; {b}]: E'
        res = F(L * L, 12)
        text = f'Случайная величина $X$ равномерно распределена на отрезке $[{a}; {b}]$. Найдите дисперсию $D(X)$.'
        sol = f'Для равномерного распределения на отрезке длины $L$ дисперсия равна $\\frac{{L^{{2}}}}{{12}} = \\frac{{{L * L}}}{{12}} = {n(res)}$.'
        return {'fam': fam, 'a': a, 'b': b, 'q': q}, res, text, sol, f'Равномерное [{a}; {b}]: D'
    # normal: симметрия относительно среднего
    mu = rng.randint(10, 200)
    h = rng.randint(1, 15)
    p = F(rng.randint(2, 30), 100)
    q = rng.choice(['mirror', 'inside'])
    res = p if q == 'mirror' else 1 - 2 * p
    text = (f'Случайная величина $X$ имеет нормальное распределение с математическим ожиданием ${mu}$. Известно, что '
            f'$P(X < {mu - h}) = {n(p)}$. Найдите ' + (f'$P(X > {mu + h})$.' if q == 'mirror' else f'$P({mu - h} < X < {mu + h})$.'))
    sol = (f'График плотности нормального распределения симметричен относительно $x = {mu}$, поэтому '
           + (f'$P(X > {mu + h}) = P(X < {mu - h}) = {n(p)}$.' if q == 'mirror'
              else f'$P(X > {mu + h}) = {n(p)}$ и $P({mu - h} < X < {mu + h}) = 1 - 2 \\cdot {n(p)} = {n(res)}$.'))
    return {'fam': fam, 'p': str(p), 'q': q}, res, text, sol, f'Нормальное: μ = {mu}, ±{h}, {"симметрия" if q == "mirror" else "середина"}'


def main():
    rng = random.Random(SEED)
    out, titles = [], set()
    for k, (level, fam) in enumerate(PLAN, 1):
        for _ in range(5000):
            r = make(rng, fam)
            if r is None:
                continue
            sp, v, text, sol, title = r
            if title in titles or not is_dec(v):
                continue
            titles.add(title)
            break
        else:
            raise SystemExit(f'№6, {fam}: не удалось подобрать задачу')
        out.append(item(6, k, level, TOPIC, title, text, sol, ans(v), sp))
    emit(out)


if __name__ == '__main__':
    main()
