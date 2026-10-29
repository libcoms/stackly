#!/usr/bin/env python3
"""Генератор задач ЕГЭ-2027 по профильной математике, №12 (графики функций), для банка stackly.

    python3 tools/gen_math12.py > /tmp/m12.json      # 36 задач повышенного уровня

Как в демоверсии и банке ФИПИ: на клетчатом чертеже график функции известного вида, проходящий через узлы
сетки (они отмечены точками); нужно восстановить коэффициенты и найти значение функции в другой точке или
абсциссу второй точки пересечения двух графиков. Виды: kx + b, k/x, k/x + a, ax² + bx + c, a√x, aˣ, logₐx,
пересечение двух прямых, параболы и прямой. Описание <!--spec:…--> — отмеченные узлы и вопрос:
tests/test_bank_math.py восстанавливает функцию по узлам сама и считает ответ.
"""
import random, sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathkit import F, ans, n, item, emit, is_dec, grid_plot, poly

SEED = 20270112
TOPIC = 'Графики функций'
PLAN = ([('П', 'lin')] * 4 + [('П', 'hyp')] * 4 + [('П', 'hypa')] * 3 + [('П', 'quad')] * 5 + [('П', 'sqrt')] * 4
        + [('П', 'exp')] * 4 + [('П', 'log')] * 4 + [('П', 'lines')] * 4 + [('П', 'quadline')] * 4)
XR, YR = (-6, 6), (-6, 6)


def lat_on(f, xs):
    """Узлы сетки (x, f(x)) в поле чертежа."""
    out = []
    for x in xs:
        try:
            y = f(F(x))
        except (ZeroDivisionError, ValueError):
            continue
        if y is not None and y.denominator == 1 and YR[0] + 1 <= y <= YR[1] - 1:
            out.append((x, int(y)))
    return out


def plot(fs, marks):
    curves = [(lambda x, f=f: float(f(F(x))) if not isinstance(f, tuple) else f[0](x), cls, rng_) for f, cls, rng_ in fs]
    return grid_plot(XR, YR, curves, marks=marks)[0]


def make(rng, kind):
    xs = range(XR[0] + 1, XR[1])
    if kind == 'lin':
        k = F(rng.choice([-3, -2, -1, 1, 2, 3, 4]), rng.choice([1, 1, 2, 3, 4]))
        b = rng.randint(-4, 4)
        f = lambda x: k * x + b
        pts = lat_on(f, xs)
        if len(pts) < 2:
            return None
        x0 = rng.choice([-12, -10, -8, 8, 10, 12, 15, 20])
        res = f(F(x0))
        marks = [pts[0], pts[-1]]
        text = f'На рисунке изображён график функции вида $f(x) = kx + b$. Найдите значение $f({x0})$.'
        sol = (f'График проходит через точки $({marks[0][0]}; {marks[0][1]})$ и $({marks[1][0]}; {marks[1][1]})$: '
               f'$k = \\frac{{{marks[1][1] - marks[0][1]}}}{{{marks[1][0] - marks[0][0]}}} = {n(k)}$, $b = {b}$. '
               f'$f({x0}) = {n(k)} \\cdot ({x0}) + ({b}) = {n(res)}$.').replace('+ (-', '- (').replace('(-', '(-')
        return {'kind': kind, 'marks': marks, 'x0': x0}, res, text, sol, plot([(f, 'cv', XR)], marks), f'Прямая через ({marks[0][0]}; {marks[0][1]}), ({marks[1][0]}; {marks[1][1]}), f({x0})'
    if kind in ('hyp', 'hypa'):
        k = rng.choice([-6, -4, -3, -2, 2, 3, 4, 5, 6])
        a = rng.randint(-3, 3) if kind == 'hypa' else 0
        if kind == 'hypa' and a == 0:
            return None
        f = lambda x: (F(k) / x + a) if x != 0 else None
        pts = [p for p in lat_on(f, xs) if p[0] != 0]
        if len(pts) < (2 if kind == 'hypa' else 1):
            return None
        x0 = rng.choice([-8, -5, -4, 4, 5, 8, 10, 16, 20, 25, -10])
        res = f(F(x0))
        if not is_dec(res):
            return None
        marks = [pts[rng.randrange(len(pts))]] if kind == 'hyp' else [pts[0], pts[-1]]
        if kind == 'hypa' and marks[0] == marks[1]:
            return None
        text = (f'На рисунке изображён график функции вида $f(x) = \\frac{{k}}{{x}}{" + a" if kind == "hypa" else ""}$. '
                f'Найдите значение $f({x0})$.')
        sol = (f'Точка $({marks[0][0]}; {marks[0][1]})$ на графике: ' + (f'$k = {marks[0][0]} \\cdot {marks[0][1]} = {k}$.' if kind == 'hyp'
               else f'по двум отмеченным точкам $k = {k}$, $a = {a}$ (горизонтальная асимптота $y = {a}$).')
               + f' $f({x0}) = \\frac{{{k}}}{{{x0}}}{" + " + str(a) if kind == "hypa" else ""} = {n(res)}$.').replace('+ -', '- ')
        curves = [(lambda x: (k / x + a) if abs(x) > 1e-9 else None, 'cv', (XR[0], -0.05)), (lambda x: (k / x + a) if abs(x) > 1e-9 else None, 'cv', (0.05, XR[1]))]
        svg = grid_plot(XR, YR, curves, marks=marks)[0]
        return {'kind': kind, 'marks': marks, 'x0': x0}, res, text, sol, svg, f'Гипербола{" со сдвигом" if a else ""}: точки {marks}, f({x0})'.replace('[', '').replace(']', '')
    if kind == 'quad':
        a = F(rng.choice([-2, -1, 1, 2]), rng.choice([1, 1, 2]))
        p, q = rng.randint(-3, 3), rng.randint(-4, 4)          # вершина
        f = lambda x: a * (x - p) ** 2 + q
        pts = lat_on(f, xs)
        if len(pts) < 3:
            return None
        marks = [pts[0], (p, q), pts[-1]] if (p, q) in pts else pts[:3]
        marks = sorted(set(marks))
        if len(marks) < 3:
            return None
        x0 = rng.choice([-9, -8, 7, 8, 9, 10, -10])
        res = f(F(x0))
        cs = [a, -2 * a * p, a * p * p + q]
        text = f'На рисунке изображён график функции вида $f(x) = ax^{{2}} + bx + c$. Найдите значение $f({x0})$.'
        sol = (f'Вершина параболы $({p}; {q})$, поэтому $f(x) = a(x - ({p}))^{{2}} + ({q})$; по ещё одной отмеченной точке $a = {n(a)}$. '
               f'Значит, $f(x) = {poly(cs)}$ и $f({x0}) = {n(res)}$.')
        return {'kind': kind, 'marks': marks, 'x0': x0}, res, text, sol, plot([(f, 'cv', XR)], marks), f'Парабола с вершиной ({p}; {q}) через ({marks[-1][0]}; {marks[-1][1]}), f({x0})'
    if kind == 'sqrt':
        a = F(rng.choice([-3, -2, -1, 1, 2, 3]), rng.choice([1, 1, 2]))
        f = lambda x: a * F(math.isqrt(int(x))) if x >= 0 and math.isqrt(int(x)) ** 2 == x else None
        pts = [(x, int(f(F(x)))) for x in (1, 4) if f(F(x)) is not None and f(F(x)).denominator == 1 and abs(f(F(x))) <= 5]
        if not pts:
            return None
        x0 = rng.choice([9, 16, 25, 36, 49, 64, 81, 100, 6.25, 2.25])
        x0 = F(str(x0))
        res = a * F(math.isqrt(int(x0 * 4)), 2)
        if res * res != a * a * x0:
            return None
        marks = [pts[-1]]
        text = f'На рисунке изображён график функции вида $f(x) = a\\sqrt{{x}}$. Найдите значение $f({n(x0)})$.'
        sol = (f'Точка $({marks[0][0]}; {marks[0][1]})$ на графике: $a\\sqrt{{{marks[0][0]}}} = {marks[0][1]}$, $a = {n(a)}$. '
               f'$f({n(x0)}) = {n(a)} \\cdot \\sqrt{{{n(x0)}}} = {n(res)}$.')
        svg = grid_plot(XR, YR, [(lambda x: float(a) * math.sqrt(x) if x >= 0 else None, 'cv', (0, XR[1]))], marks=marks)[0]
        return {'kind': kind, 'marks': marks, 'x0': str(x0)}, res, text, sol, svg, f'Корень: точка ({marks[0][0]}; {marks[0][1]}), f({n(x0)})'
    if kind == 'exp':
        a = rng.choice([2, 3, F(1, 2), F(1, 3), 4])
        f = lambda x: F(a) ** int(x)
        pts = [(x, int(f(x))) for x in range(-3, 4) if f(x).denominator == 1 and 1 <= f(x) <= 5]
        if not pts:
            return None
        mark = max(pts, key=lambda p: abs(p[0]))
        if mark[0] == 0:
            return None
        x0 = rng.choice([-3, -2, 3, 4, 5]) if a in (2, F(1, 2)) else rng.choice([-2, 3, 4])
        res = F(a) ** x0
        if not is_dec(res):
            return None
        text = f'На рисунке изображён график функции вида $f(x) = a^{{x}}$. Найдите значение $f({x0})$.'
        sol = f'Точка $({mark[0]}; {mark[1]})$ на графике: $a^{{{mark[0]}}} = {mark[1]}$, $a = {n(a)}$. $f({x0}) = {n(a)}^{{{x0}}} = {n(res)}$.'
        svg = grid_plot(XR, YR, [(lambda x: float(a) ** x, 'cv', XR)], marks=[mark, (0, 1)])[0]
        return {'kind': kind, 'marks': [mark], 'x0': x0}, res, text, sol, svg, f'Показательная: точка ({mark[0]}; {mark[1]}), f({x0})'
    if kind == 'log':
        a = rng.choice([2, 3, 4, 5, F(1, 2), F(1, 3)])
        pts = [(int(F(a) ** k), k) for k in range(-3, 4) if (F(a) ** k).denominator == 1 and 2 <= F(a) ** k <= 5]
        if not pts:
            return None
        mark = pts[-1]
        x0 = rng.choice([F(a) ** k for k in (-2, -1, 3, 4) if is_dec(F(a) ** k) and F(a) ** k != mark[0]])
        res = F(round(math.log(float(x0), float(a))))
        if F(a) ** int(res) != x0:
            return None
        text = f'На рисунке изображён график функции вида $f(x) = \\log_{{a}} x$. Найдите значение $f({n(x0)})$.'
        sol = (f'Точка $({mark[0]}; {mark[1]})$ на графике: $\\log_{{a}} {mark[0]} = {mark[1]}$, $a = {n(a)}$. '
               f'$f({n(x0)}) = \\log_{{{n(a)}}} {n(x0)} = {n(res)}$.')
        svg = grid_plot(XR, YR, [(lambda x: math.log(x, float(a)) if x > 1e-6 else None, 'cv', (0.01, XR[1]))], marks=[mark, (1, 0)])[0]
        return {'kind': kind, 'marks': [mark], 'x0': str(x0)}, res, text, sol, svg, f'Логарифм: точка ({mark[0]}; {mark[1]}), f({n(x0)})'
    if kind == 'lines':
        k1 = F(rng.choice([-3, -2, -1, 1, 2, 3]), rng.choice([1, 2, 3]))
        k2 = F(rng.choice([-3, -2, -1, 1, 2, 3]), rng.choice([1, 2, 3]))
        b1, b2 = rng.randint(-4, 4), rng.randint(-4, 4)
        if k1 == k2:
            return None
        f1, f2 = (lambda x: k1 * x + b1), (lambda x: k2 * x + b2)
        p1, p2 = lat_on(f1, xs), lat_on(f2, xs)
        xi = F(b2 - b1) / (k1 - k2)
        if len(p1) < 2 or len(p2) < 2 or not is_dec(xi) or xi.denominator == 1 or abs(xi) > 30:
            return None
        ask = rng.choice(['x', 'y'])
        res = xi if ask == 'x' else f1(xi)
        if not is_dec(res):
            return None
        marks = [p1[0], p1[-1], p2[0], p2[-1]]
        text = (f'На рисунке изображены графики двух линейных функций, пересекающиеся в точке $A$. Найдите '
                f'{"абсциссу" if ask == "x" else "ординату"} точки $A$.')
        sol = (f'По отмеченным точкам: первая прямая $y = {poly([k1, b1])}$, вторая $y = {poly([k2, b2])}$. '
               f'${poly([k1, b1])} = {poly([k2, b2])}$, $x = {n(xi)}$' + (f', $y = {n(f1(xi))}$.' if ask == 'y' else '.'))
        svg = plot([(f1, 'cv', XR), (f2, 'cv2', XR)], marks)
        return {'kind': kind, 'm1': [p1[0], p1[-1]], 'm2': [p2[0], p2[-1]], 'ask': ask}, res, text, sol, svg, f'Две прямые через ({p1[0][0]}; {p1[0][1]}) и ({p2[0][0]}; {p2[0][1]}), {"абсцисса" if ask == "x" else "ордината"} точки A'
    # quadline: парабола и прямая, точка A видна, найти абсциссу B
    a = rng.choice([-1, 1, 2, -2, F(1, 2)])
    p, q = rng.randint(-2, 2), rng.randint(-4, 3)
    f = lambda x: a * (x - p) ** 2 + q
    xa = rng.randint(-3, 3)
    k = F(rng.choice([-3, -2, -1, 1, 2, 3]))
    b = f(F(xa)) - k * xa
    g = lambda x: k * x + b
    # второй корень: a(x − p)² + q − kx − b = 0, сумма корней = (2ap + k)/a
    xb = (2 * a * p + k) / a - xa
    if xb == xa or not is_dec(xb) or abs(xb) <= 6 or abs(xb) > 20 or not -5 <= f(F(xa)) <= 5:
        return None
    pf = lat_on(f, xs)
    pg = lat_on(g, xs)
    if len(pf) < 3 or len(pg) < 2:
        return None
    mf = sorted(set([(p, q)] + [pt for pt in pf if pt[0] != p][:2]))[:3]
    if len(mf) < 3:
        return None
    mg = [pg[0], pg[-1]]
    text = ('На рисунке изображены графики функций $f(x) = ax^{2} + bx + c$ и $g(x) = kx + d$, пересекающиеся в точках '
            '$A$ и $B$. Найдите абсциссу точки $B$.')
    sol = (f'По отмеченным точкам $f(x) = {poly([a, -2 * a * p, a * p * p + q])}$, $g(x) = {poly([k, b])}$. Абсциссы точек '
           f'пересечения — корни уравнения $f(x) = g(x)$; один из них ${xa}$ (точка $A$), по теореме Виета второй $x_{{B}} = {n(xb)}$.')
    svg = grid_plot(XR, YR, [(lambda x: float(f(F(x))), 'cv', XR), (lambda x: float(g(F(x))), 'cv2', XR)],
                    marks=mf + mg, labels=[(xa + 0.45, float(f(F(xa))) + 0.5, 'A')])[0]
    return {'kind': kind, 'mf': mf, 'mg': mg, 'xa': xa}, xb, text, sol, svg, f'Парабола и прямая: вершина ({p}; {q}), A({xa}; …)'


def main():
    rng = random.Random(SEED)
    out, titles = [], set()
    for k, (level, kind) in enumerate(PLAN, 1):
        for _ in range(50000):
            r = make(rng, kind)
            if r is None:
                continue
            sp, x, text, sol, svg, title = r
            if title in titles or not is_dec(x):
                continue
            titles.add(title)
            break
        else:
            raise SystemExit(f'№12, {kind}: не удалось подобрать задачу')
        sp = {k2: ([list(map(int, m)) for m in v] if k2 in ('marks', 'm1', 'm2', 'mf', 'mg') else v) for k2, v in sp.items()}
        out.append(item(12, k, level, TOPIC, title, text, sol.replace('+ -', '- '), ans(x), sp, extra=svg))
    emit(out)


if __name__ == '__main__':
    main()
