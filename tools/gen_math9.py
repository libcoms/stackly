#!/usr/bin/env python3
"""Генератор задач ЕГЭ-2027 по профильной математике, №9 (производная, экстремум, первообразная), для банка stackly.

    python3 tools/gen_math9.py > /tmp/m9.json      # 44 задачи: 32 базовых, 12 повышенных

Как в демоверсии и банке ФИПИ. По чертежу: значение производной в точке касания (касательная проходит через
отмеченные узлы сетки); по графику производной — число точек максимума/минимума на отрезке, точка экстремума,
точка наибольшего значения на отрезке; по графику функции — в скольких отмеченных точках производная
отрицательна (положительна). По формуле: точка максимума/минимума, наибольшее/наименьшее значение на отрезке
(в 2027 году экстремум вошёл в №9), мгновенная скорость по закону движения, площадь под графиком через
первообразную. В описании <!--spec:…--> — многочлен (коэффициенты от старшего) или узлы касательной;
tests/test_bank_math.py проверяет ответ численно: знаки производной, перебор по сетке, формула Симпсона.
"""
import random, sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathkit import F, ans, n, item, emit, is_dec, grid_plot, poly, seg, lab, svg

SEED = 20270109
TOPIC = 'Производная и первообразная'
PLAN = ([('Б', 'tangent')] * 6 + [('Б', 'dcount')] * 6 + [('Б', 'dpoint')] * 3 + [('Б', 'dmaxon')] * 3 + [('Б', 'fsign')] * 5
        + [('Б', 'ext3')] * 5 + [('Б', 'motion')] * 4 + [('П', 'extlog')] * 3 + [('П', 'segval')] * 5 + [('П', 'area')] * 4)


def pval(cs, x):
    r = F(0)
    for c in cs:
        r = r * x + c
    return r


def pder(cs):
    d = len(cs) - 1
    return [c * (d - i) for i, c in enumerate(cs[:-1])]


def pmul(a, b):
    out = [F(0)] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            out[i + j] += x * y
    return out


def from_roots(rs, lead=1):
    cs = [F(lead)]
    for r in rs:
        cs = pmul(cs, [F(1), F(-r)])
    return cs


def pint(cs):
    d = len(cs) - 1
    return [c / (d - i + 1) for i, c in enumerate(cs)] + [F(0)]


def make(rng, kind):
    if kind == 'tangent':
        # касательная через узлы (x1, y1), (x2, y2); кривая касается её в x0
        x1, x2 = sorted(rng.sample(range(-5, 6), 2))
        y1, y2 = rng.randint(-4, 4), rng.randint(-4, 4)
        k = F(y2 - y1, x2 - x1)
        if not is_dec(k) or k == 0 or abs(k) > 3:
            return None
        x0 = rng.choice([x for x in range(-3, 4) if x not in (x1, x2)])
        L = lambda x: y1 + k * (x - x1)
        c = rng.choice([-1, 1]) * F(rng.randint(1, 4), 10)
        dd = rng.choice([-1, 1]) * F(rng.randint(0, 2), 60)
        f = lambda x: float(L(F(x)) + c * (F(x) - x0) ** 2 + dd * (F(x) - x0) ** 3)
        y0 = float(L(F(x0)))
        if not -3.5 < y0 < 3.5:
            return None
        # кривая должна быть видна хотя бы на шести клетках вокруг точки касания
        if sum(1 for t in range(-60, 61) if abs(f(t / 10)) < 5.5) < 60:
            return None
        g, (W, H) = grid_plot((-6, 6), (-6, 6), [(f, 'cv', (-6, 6)), (lambda x: float(L(F(x))), 'cv2', (-6, 6))], marks=[(x1, y1), (x2, y2)])
        X, Y = lambda x: (x + 6) * 26, lambda y: (6 - y) * 26
        extra_svg = g.replace('</svg>', seg((X(x0), Y(0)), (X(x0), Y(y0)), 'hd') + lab((X(x0), Y(0) + 13), 'x<tspan font-size="10" dy="3">0</tspan>') + '</svg>')
        text = (f'На рисунке изображены график функции $y = f(x)$ и касательная к нему в точке с абсциссой $x_{{0}}$. '
                f'Найдите значение производной функции $f(x)$ в точке $x_{{0}}$.')
        sol = (f'Производная в точке касания равна угловому коэффициенту касательной. Касательная проходит через узлы '
               f'$({x1}; {y1})$ и $({x2}; {y2})$: $f\'(x_{{0}}) = \\frac{{{y2} - ({y1})}}{{{x2} - ({x1})}} = {n(k)}$.')
        return {'kind': kind, 'pts': [[x1, y1], [x2, y2]]}, k, text, sol, extra_svg, f'Касательная через ({x1}; {y1}) и ({x2}; {y2})'
    if kind in ('dcount', 'dpoint', 'dmaxon'):
        m = {'dcount': rng.randint(4, 6), 'dpoint': 1, 'dmaxon': rng.randint(1, 2)}[kind]
        rs = sorted(rng.sample(range(-7, 8), m))
        lead = rng.choice([-1, 1])
        wide = 4 if kind == 'dmaxon' else 2                 # «наибольшее на отрезке» — нужен отрезок без нулей f′
        a0, b0 = min(rs) - rng.randint(1, wide), max(rs) + rng.randint(1, wide)
        if a0 < -8 or b0 > 8 or b0 - a0 < 4:
            return None
        # f′ — полуволны синуса между соседними нулями, горбы похожей высоты (многочлен высокой степени
        # прижимается к нулю почти везде, и нули не видно); lead — знак f′ правее последнего нуля
        amps = [rng.uniform(2, 4) for _ in range(m + 1)]
        sgn = lambda x: lead * (-1) ** sum(1 for r in rs if r > x)

        def fp(x):
            s = sgn(x)
            i = sum(1 for r in rs if r <= x)                  # номер участка
            lo_, hi_ = ([a0] + rs)[i], (rs + [b0])[i]
            if i == 0:
                t = (rs[0] - x) / (rs[0] - a0) / 2           # от нуля к левому краю — четверть волны
            elif i == m:
                t = (x - rs[-1]) / (b0 - rs[-1]) / 2
            else:
                t = (x - lo_) / (hi_ - lo_)
            return s * amps[i] * math.sin(math.pi * t)
        maxs = [r for r in rs if sgn(r - F(1, 2)) > 0 > sgn(r + F(1, 2))]
        mins = [r for r in rs if sgn(r - F(1, 2)) < 0 < sgn(r + F(1, 2))]
        g = grid_plot((-8, 8), (-5, 5), [(fp, 'cv', (a0, b0))], marks=[], cell=22)[0]
        head = (f'На рисунке изображён график $y = f\'(x)$ — производной функции $f(x)$, определённой на интервале '
                f'$({a0}; {b0})$. ')
        if kind == 'dcount':
            what = rng.choice(['максимума', 'минимума'])
            lo, hi = sorted(rng.sample(range(a0 + 1, b0), 2))
            pool = maxs if what == 'максимума' else mins
            res = sum(1 for r in pool if lo <= r <= hi)
            if res == 0 and rng.random() < 0.7:
                return None
            text = head + f'Найдите количество точек {what} функции $f(x)$, принадлежащих отрезку $[{lo}; {hi}]$.'
            sol = (f'Точки {what} — нули производной, где она меняет знак с {"плюса на минус" if what == "максимума" else "минуса на плюс"}. '
                   f'Таких точек на отрезке $[{lo}; {hi}]$: {res}.')
            return ({'kind': kind, 'roots': rs, 'lead': lead, 'what': what, 'seg': [lo, hi]}, F(res), text, sol, g,
                    f'График f′ на ({a0}; {b0}): точки {what} на [{lo}; {hi}]')
        if kind == 'dpoint':
            r = rs[0]
            what = 'максимума' if r in maxs else 'минимума'
            text = head + f'Найдите точку {what} функции $f(x)$.'
            sol = f'Производная обращается в ноль и меняет знак только в точке ${r}$ — это и есть точка {what}.'
            return {'kind': kind, 'roots': rs, 'lead': lead, 'what': what}, F(r), text, sol, g, f'График f′ на ({a0}; {b0}): точка {what}'
        lo, hi = sorted(rng.sample(range(a0 + 1, b0), 2))
        if hi - lo < 3:
            return None
        if any(lo <= r <= hi for r in rs):
            return None                                   # как в ФИПИ: на отрезке производная одного знака
        best = hi if sgn(F(lo + hi, 2)) > 0 else lo
        text = head + f'В какой точке отрезка $[{lo}; {hi}]$ функция $f(x)$ принимает наибольшее значение?'
        sign = 'положительна' if sgn(F(lo + hi, 2)) > 0 else 'отрицательна'
        sol = f'На отрезке $[{lo}; {hi}]$ производная {sign}, функция {"возрастает" if sign == "положительна" else "убывает"}, поэтому наибольшее значение — в точке ${best}$.'
        return {'kind': kind, 'roots': rs, 'lead': lead, 'seg': [lo, hi]}, F(best), text, sol, g, f'График f′ на ({a0}; {b0}): наибольшее на [{lo}; {hi}]'
    if kind == 'fsign':
        # f — гладкая кривая с экстремумами в узлах ext (значения vals чередуются: максимум, минимум, …), между
        # ними — монотонные «косинусные» участки; отмеченные точки на оси x не совпадают с экстремумами
        ext = sorted(rng.sample(range(-4, 5), rng.randint(2, 4)))
        if min(b - a for a, b in zip(ext, ext[1:])) < 2:
            return None
        up = rng.choice([True, False])
        vals = []
        for i in range(len(ext)):
            hi_ = (i % 2 == 0) == up
            vals.append(rng.uniform(1, 4) if hi_ else rng.uniform(-4, -1))
        knots = [(-6, vals[0] - (2.5 if (0 % 2 == 0) == up else -2.5))] + list(zip(ext, vals)) + \
                [(6, vals[-1] - (2.5 if ((len(ext) - 1) % 2 == 0) == up else -2.5))]

        def fx(x):
            for (xa, ya), (xb, yb) in zip(knots, knots[1:]):
                if xa <= x <= xb:
                    t = (x - xa) / (xb - xa)
                    return ya + (yb - ya) * (1 - math.cos(math.pi * t)) / 2
            return None
        slope = lambda p: next((yb - ya) for (xa, ya), (xb, yb) in zip(knots, knots[1:]) if xa < p < xb)
        pts = sorted(rng.sample([F(k, 2) for k in range(-11, 12) if k % 2], rng.randint(6, 9)))
        neg = rng.random() < 0.5
        res = sum(1 for p in pts if (slope(float(p)) < 0) == neg)
        X, Y = lambda x: (x + 6) * 26, lambda y: (6 - y) * 26
        g, _ = grid_plot((-6, 6), (-6, 6), [(fx, 'cv', (-6, 6))], marks=[])
        ticks = ''.join(f'<circle class="dt" cx="{X(float(p)):.1f}" cy="{Y(0):.1f}" r="3"/>'
                        + lab((X(float(p)), Y(0) + (14 if i % 2 == 0 else 30)), f'x<tspan font-size="10" dy="3">{i + 1}</tspan>')
                        for i, p in enumerate(pts))                     # подписи через одну ниже — не наезжают
        g = g.replace('</svg>', ticks + '</svg>')
        text = (f'На рисунке изображён график функции $y = f(x)$. На оси абсцисс отмечены точки $x_{{1}}, \\ldots, x_{{{len(pts)}}}$. '
                f'В скольких из этих точек производная функции $f(x)$ {"отрицательна" if neg else "положительна"}?')
        sol = (f'Производная {"отрицательна" if neg else "положительна"} там, где функция {"убывает" if neg else "возрастает"}. '
               f'Смотрим, на каком участке графика лежит каждая отмеченная точка: таких точек {res}.')
        return {'kind': kind, 'knots': [[x, round(y, 4)] for x, y in knots], 'pts': [str(p) for p in pts], 'neg': neg}, F(res), text, sol, g, f'По графику f: {len(pts)} точек от {n(pts[0])} до {n(pts[-1])}, f′ {"< 0" if neg else "> 0"}'
    if kind == 'ext3':
        r1, r2 = sorted(rng.sample(range(-9, 10), 2))
        if (r1 + r2) % 2:
            return None
        c0 = rng.randint(-20, 20)
        cs = [F(1), F(-3 * (r1 + r2), 2), F(3 * r1 * r2), F(c0)]   # y′ = 3(x − r1)(x − r2)
        if rng.random() < 0.3:
            cs = [-c for c in cs]
        what = rng.choice(['максимума', 'минимума'])
        up = cs[0] > 0
        res = (r1 if up else r2) if what == 'максимума' else (r2 if up else r1)
        text = f'Найдите точку {what} функции $y = {poly(cs)}$.'
        sol = (f'$y\' = {poly(pder(cs))} = {n(3 * cs[0])}(x - ({r1}))(x - ({r2}))$. Производная меняет знак '
               f'{"с плюса на минус" if what == "максимума" else "с минуса на плюс"} в точке ${res}$.').replace('(x - (-', '(x + (').replace('- (', '- (')
        return {'kind': kind, 'f': [str(c) for c in cs], 'what': what}, F(res), text, sol, '', f'Точка {what}: y = {poly(cs).replace("^{", "^").replace("}", "")}'
    if kind == 'extlog':
        # y = kx − ln(x + a) + c: y′ = k − 1/(x + a) = 0 → x = 1/k − a, минимум
        k = rng.choice([1, 2, 4, 5])
        a = rng.randint(-5, 9)
        c = rng.randint(-9, 9)
        res = F(1, k) - a
        if not is_dec(res):
            return None
        arg = f'x {"+" if a >= 0 else "-"} {abs(a)}' if a else 'x'
        text = f'Найдите точку минимума функции $y = {k if k > 1 else ""}x - \\ln({arg}) {"+" if c >= 0 else "-"} {abs(c)}$.'
        sol = (f'$y\' = {k} - \\frac{{1}}{{{arg}}}$ при $x > {-a}$. $y\' = 0$ при ${arg} = {n(F(1, k))}$, то есть $x = {n(res)}$; '
               f'левее производная отрицательна, правее положительна — это минимум.')
        return {'kind': kind, 'k': k, 'a': a, 'c': c}, res, text, sol, '', f'Минимум с логарифмом: k = {k}, a = {a}, c = {c}'
    if kind == 'segval':
        r1, r2 = sorted(rng.sample(range(-6, 7), 2))
        if (r1 + r2) % 2:
            return None
        c0 = rng.randint(-15, 15)
        cs = [F(1), F(-3 * (r1 + r2), 2), F(3 * r1 * r2), F(c0)]
        lo = rng.randint(r1 - 2, r2)
        hi = rng.randint(max(lo + 1, r1), r2 + 2)
        what = rng.choice(['наибольшее', 'наименьшее'])
        cand = [lo, hi] + [r for r in (r1, r2) if lo < r < hi]
        vals = {t: pval(cs, F(t)) for t in cand}
        res = max(vals.values()) if what == 'наибольшее' else min(vals.values())
        text = f'Найдите {what} значение функции $y = {poly(cs)}$ на отрезке $[{lo}; {hi}]$.'
        sol = (f'$y\' = 3(x - ({r1}))(x - ({r2}))$, критические точки ${r1}$ и ${r2}$. Сравниваем значения в концах отрезка и '
               f'критических точках внутри него: ' + ', '.join(f'$y({t}) = {n(v)}$' for t, v in vals.items()) + f'. {what.capitalize()}: ${n(res)}$.')
        return {'kind': kind, 'f': [str(c) for c in cs], 'seg': [lo, hi], 'what': what}, res, text, sol, '', f'{what.capitalize()} на [{lo}; {hi}]: y = {poly(cs).replace("^{", "^").replace("}", "")}'
    if kind == 'motion':
        cs = [F(rng.choice([1, 2, 3])) * rng.choice([1, -1]) * F(1, rng.choice([1, 2, 3, 6])), F(rng.randint(-6, 6)), F(rng.randint(-20, 30)), F(rng.randint(-10, 40))]
        t0 = rng.randint(1, 9)
        v = pval(pder(cs), F(t0))
        if not is_dec(v) or not is_dec(cs[0]):
            return None
        text = (f'Материальная точка движется прямолинейно по закону $x(t) = {poly(cs, "t")}$, где $x$ — расстояние от точки отсчёта '
                f'в метрах, $t$ — время в секундах, измеренное с начала движения. Найдите её скорость (в метрах в секунду) в момент '
                f'времени $t = {t0}$ с.')
        sol = f'Скорость — производная координаты: $v(t) = x\'(t) = {poly(pder(cs), "t")}$, $v({t0}) = {n(v)}$ м/с.'
        return {'kind': kind, 'f': [str(c) for c in cs], 't0': t0}, v, text, sol, '', f'Скорость в момент {t0}: x(t) = {poly(cs, "t").replace("^{", "^").replace("}", "")}'
    # area: площадь под графиком положительного многочлена на [a; b]
    a, b = sorted(rng.sample(range(-3, 5), 2))
    cs = rng.choice([[F(rng.choice([1, 3])), F(0), F(rng.randint(0, 4))], [F(rng.choice([3, 6])), F(2 * rng.randint(-2, 2)), F(rng.randint(1, 5))],
                     [F(-3), F(0), F(rng.randint(28, 40))]])
    if any(pval(cs, F(x, 10)) <= 0 for x in range(a * 10, b * 10 + 1)):
        return None
    P = pint(cs)
    S = pval(P, F(b)) - pval(P, F(a))
    if not is_dec(S) or S.denominator != 1:
        return None
    text = (f'Найдите площадь фигуры, ограниченной графиком функции $y = {poly(cs)}$, прямыми $x = {a}$, $x = {b}$ и осью абсцисс.')
    sol = (f'На отрезке $[{a}; {b}]$ функция положительна, площадь равна $F({b}) - F({a})$, где $F(x) = {poly(P)}$ — первообразная: '
           f'${n(pval(P, F(b)))} - ({n(pval(P, F(a)))}) = {n(S)}$.')
    return {'kind': kind, 'f': [str(c) for c in cs], 'seg': [a, b]}, S, text, sol, '', f'Площадь: y = {poly(cs).replace("^{", "^").replace("}", "")} на [{a}; {b}]'


def main():
    rng = random.Random(SEED)
    out, titles = [], set()
    for k, (level, kind) in enumerate(PLAN, 1):
        for _ in range(50000):
            r = make(rng, kind)
            if r is None:
                continue
            sp, x, text, sol, extra, title = r
            if title in titles or not is_dec(x):
                continue
            titles.add(title)
            break
        else:
            raise SystemExit(f'№9, {kind}: не удалось подобрать задачу')
        out.append(item(9, k, level, TOPIC, title[:100], text, sol.replace('+ -', '- '), ans(x), sp, extra=extra))
    emit(out)


if __name__ == '__main__':
    main()
