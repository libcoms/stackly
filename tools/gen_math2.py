#!/usr/bin/env python3
"""Генератор задач ЕГЭ-2027 по профильной математике, №2 (векторы), для банка stackly.

    python3 tools/gen_math2.py > /tmp/m2.json      # 32 задачи базового уровня

Как в банке ФИПИ: длина вектора-комбинации по координатам, скалярное произведение, косинус угла между
векторами, скалярное произведение по длинам и углу, длина суммы по длинам и углу, координаты комбинации.
Описание <!--spec:…--> — координаты (или длины и угол); tests/test_bank_math.py пересчитывает ответ.
"""
import random, sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathkit import F, ans, n, item, emit, is_dec, tex_plain

SEED = 20270102
TOPIC = 'Векторы'
PLAN = [('Б', 'len')] * 7 + [('Б', 'dot')] * 6 + [('Б', 'cos')] * 6 + [('Б', 'dotang')] * 5 + [('Б', 'lensum')] * 4 + [('Б', 'coord')] * 4


def v(name, x, y):
    return f'\\vec{{{name}}}({n(x)}; {n(y)})'


def sqr(x):
    """Квадрат координаты в формуле: (-3)^{2}, 4^{2}."""
    return f'({n(x)})^{{2}}' if x < 0 else f'{n(x)}^{{2}}'


def comb(k1, k2):
    """k1·a + k2·b в записи формулы."""
    a = '' if k1 == 1 else '-' if k1 == -1 else n(k1)
    b = ('+ ' if k2 > 0 else '- ') + ('' if abs(k2) == 1 else n(abs(k2)))
    return f'{a}\\vec{{a}} {b}\\vec{{b}}'


def make(rng, fam):
    a = (rng.randint(-15, 15), rng.randint(-15, 15))
    b = (rng.randint(-9, 9), rng.randint(-9, 9))
    if fam in ('len', 'coord'):
        k1, k2 = rng.choice([1, 2, 3, -1]), rng.choice([1, -1, 2, -2, 3, -3, 4, -4])
        c = (k1 * a[0] + k2 * b[0], k1 * a[1] + k2 * b[1])
        if fam == 'len':
            L2 = c[0] ** 2 + c[1] ** 2
            if math.isqrt(L2) ** 2 != L2 or L2 == 0:
                return None
            L = math.isqrt(L2)
            text = f'Даны векторы ${v("a", *a)}$ и ${v("b", *b)}$. Найдите длину вектора ${comb(k1, k2)}$.'
            sol = (f'Координаты вектора ${comb(k1, k2)}$: $({n(c[0])}; {n(c[1])})$. Длина $\\sqrt{{{sqr(c[0])} + {sqr(c[1])}}} = '
                   f'\\sqrt{{{L2}}} = {L}$.')
            return {'fam': fam, 'a': a, 'b': b, 'k1': k1, 'k2': k2}, F(L), text, sol, f'Длина {tex_plain(comb(k1, k2))}: a({a[0]}; {a[1]}), b({b[0]}; {b[1]})'
        which = rng.choice(['абсциссу', 'ординату', 'сумму координат'])
        r = c[0] if which == 'абсциссу' else c[1] if which == 'ординату' else c[0] + c[1]
        text = f'Даны векторы ${v("a", *a)}$ и ${v("b", *b)}$. Найдите {which} вектора ${comb(k1, k2)}$.'
        sol = f'Координаты умножаются на числа и складываются: ${comb(k1, k2)} = ({n(c[0])}; {n(c[1])})$, ответ: ${n(r)}$.'
        return {'fam': fam, 'a': a, 'b': b, 'k1': k1, 'k2': k2, 'which': which}, F(r), text, sol, f'Координаты {tex_plain(comb(k1, k2))}: a({a[0]}; {a[1]}), b({b[0]}; {b[1]}), {which}'
    if fam == 'dot':
        d = a[0] * b[0] + a[1] * b[1]
        text = f'Даны векторы ${v("a", *a)}$ и ${v("b", *b)}$. Найдите скалярное произведение $\\vec{{a}} \\cdot \\vec{{b}}$.'
        sol = f'$\\vec{{a}} \\cdot \\vec{{b}} = x_{{1}}x_{{2}} + y_{{1}}y_{{2}} = {n(a[0])} \\cdot {n(b[0])} + {n(a[1])} \\cdot {n(b[1])} = {d}$.'
        return {'fam': fam, 'a': a, 'b': b}, F(d), text, sol, f'Скалярное: a({a[0]}; {a[1]}), b({b[0]}; {b[1]})'
    if fam == 'cos':
        tri = [(3, 4, 5), (5, 12, 13), (8, 6, 10), (6, 8, 10), (4, 3, 5), (12, 5, 13), (0, 5, 5), (7, 24, 25), (24, 7, 25)]
        (x1, y1, l1), (x2, y2, l2) = rng.choice(tri), rng.choice(tri)
        a = (x1 * rng.choice([1, -1]), y1 * rng.choice([1, -1]))
        b = (x2 * rng.choice([1, -1]), y2 * rng.choice([1, -1]))
        if rng.random() < 0.5:
            b = (b[1], b[0])
        d = a[0] * b[0] + a[1] * b[1]
        c = F(d, l1 * l2)
        if not is_dec(c) or abs(c) == 1:
            return None
        text = f'Даны векторы ${v("a", *a)}$ и ${v("b", *b)}$. Найдите косинус угла между ними.'
        sol = (f'$\\cos \\varphi = \\frac{{\\vec{{a}} \\cdot \\vec{{b}}}}{{|\\vec{{a}}| \\cdot |\\vec{{b}}|}} = \\frac{{{d}}}{{{l1} \\cdot {l2}}} = {n(c)}$.')
        return {'fam': fam, 'a': a, 'b': b}, c, text, sol, f'Косинус угла: a({a[0]}; {a[1]}), b({b[0]}; {b[1]})'
    la, lb = rng.randint(2, 12), rng.randint(2, 12)
    ang, cs = rng.choice([(60, F(1, 2)), (120, F(-1, 2)), (90, F(0)), (180, F(-1)), (0, F(1))])
    if fam == 'dotang':
        d = la * lb * cs
        text = (f'Длины векторов $\\vec{{a}}$ и $\\vec{{b}}$ равны ${la}$ и ${lb}$, а угол между ними равен ${ang}^\\circ$. '
                f'Найдите скалярное произведение $\\vec{{a}} \\cdot \\vec{{b}}$.')
        sol = f'$\\vec{{a}} \\cdot \\vec{{b}} = |\\vec{{a}}| \\cdot |\\vec{{b}}| \\cdot \\cos {ang}^\\circ = {la} \\cdot {lb} \\cdot {n(cs)} = {n(d)}$.'
        return {'fam': fam, 'la': la, 'lb': lb, 'ang': ang}, d, text, sol, f'Скалярное по длинам: {la}, {lb}, {ang}°'
    sq = la * la + lb * lb + 2 * la * lb * cs
    if ang in (0, 180) or math.isqrt(int(sq)) ** 2 != sq:
        return None
    L = math.isqrt(int(sq))
    text = (f'Длины векторов $\\vec{{a}}$ и $\\vec{{b}}$ равны ${la}$ и ${lb}$, а угол между ними равен ${ang}^\\circ$. '
            f'Найдите длину вектора $\\vec{{a}} + \\vec{{b}}$.')
    sol = (f'$|\\vec{{a}} + \\vec{{b}}|^{{2}} = |\\vec{{a}}|^{{2}} + 2\\vec{{a}} \\cdot \\vec{{b}} + |\\vec{{b}}|^{{2}} = {la * la} + {n(2 * la * lb * cs)} + {lb * lb} = {n(sq)}$, '
           f'длина равна ${L}$.').replace('+ -', '- ')
    return {'fam': fam, 'la': la, 'lb': lb, 'ang': ang}, F(L), text, sol, f'Длина суммы: {la}, {lb}, {ang}°'


def main():
    rng = random.Random(SEED)
    out, titles = [], set()
    for k, (level, fam) in enumerate(PLAN, 1):
        for _ in range(20000):
            r = make(rng, fam)
            if r is None:
                continue
            sp, x, text, sol, title = r
            if title in titles or not is_dec(x):
                continue
            titles.add(title)
            break
        else:
            raise SystemExit(f'№2, {fam}: не удалось подобрать задачу')
        out.append(item(2, k, level, TOPIC, title, text, sol.replace('+ -', '- '), ans(x), sp))
    emit(out)


if __name__ == '__main__':
    main()
