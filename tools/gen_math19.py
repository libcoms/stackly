#!/usr/bin/env python3
"""Генератор задач ЕГЭ-2027 по профильной математике, №19 (задача с параметром, часть 2, 4 балла).

    python3 tools/gen_math19.py > /tmp/m19.json      # 20 задач высокого уровня

Найти все значения параметра a, при каждом из которых уравнение (система) имеет ровно N решений или корни
удовлетворяют условию. Виды: |x² − 2mx| = a, x³ − 3m²x = a, x + k/x = a, окружность x² + y² = 2m² и прямая
y = x + a, оба корня x² − 2ax + a² − d² = 0 на отрезке. Решение — графический метод (сколько раз горизонтальная
прямая пересекает график) или расположение корней. В описании <!--spec:…--> — вид, параметры, N и ответ-множество;
tests/test_bank_math.py для сотен значений a точно считает число решений и сравнивает с ответом.
"""
import random, sys, os
from fractions import Fraction as F
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathkit import n, item2, emit

SEED = 20270119
TOPIC = 'Параметр'
KINDS = ['absq', 'cubic', 'hyp', 'circle', 'roots']
PLAN = [('В', k) for k in KINDS for _ in range(4)]
INF = None
NUMW = {1: 'ровно один', 2: 'ровно два', 3: 'ровно три', 4: 'ровно четыре'}


def roots_phrase(N):
    return f'{NUMW[N]} {"корень" if N == 1 else "корня"}'


def ival_tex(iv):
    if all(lo is not INF and lo == hi for lo, hi, _, _ in iv):          # только точки: {−54; 54}
        return r'\{' + '; '.join(n(lo) for lo, _, _, _ in iv) + r'\}'
    out = []
    for lo, hi, lc, hc in iv:
        if lo is not INF and lo == hi:
            out.append(f'\\left\\{{{n(lo)}\\right\\}}'.replace('\\left\\{', '\\{').replace('\\right\\}', '\\}'))
            continue
        a = '-\\infty' if lo is INF else n(lo)
        b = '+\\infty' if hi is INF else n(hi)
        out.append(f'{"[" if lc else "("}{a}; {b}{"]" if hc else ")"}')
    return ' \\cup '.join(out)


def ival_txt(iv):
    if all(lo is not INF and lo == hi for lo, hi, _, _ in iv):
        return 'a ∈ {' + '; '.join(n(lo).replace('-', '−') for lo, _, _, _ in iv) + '}'
    out = []
    for lo, hi, lc, hc in iv:
        if lo is not INF and lo == hi:
            out.append('{' + n(lo).replace('-', '−') + '}')
            continue
        a = '−∞' if lo is INF else n(lo).replace('-', '−')
        b = '+∞' if hi is INF else n(hi).replace('-', '−')
        out.append(f'{"[" if lc else "("}{a}; {b}{"]" if hc else ")"}')
    return 'a ∈ ' + ' ∪ '.join(out)


def make(rng, kind):
    if kind == 'absq':
        m = rng.randint(1, 4)
        h = m * m
        N = rng.choice([2, 3, 4])
        iv = {2: [(F(0), F(0), True, True), (F(h), INF, False, False)], 3: [(F(h), F(h), True, True)], 4: [(F(0), F(h), False, False)]}[N]
        eq = f'|x^{{2}} - {2 * m}x| = a'
        text = f'Найдите все значения $a$, при каждом из которых уравнение ${eq}$ имеет {roots_phrase(N)}.'
        sol = (f'Построим график $y = |x^{{2}} - {2 * m}x|$: парабола $y = x^{{2}} - {2 * m}x$ с корнями $0$ и ${2 * m}$ и вершиной '
               f'$({m}; -{h})$; часть под осью отражаем вверх — получается «горб» высотой ${h}$ над отрезком $[0; {2 * m}]$. '
               f'Число корней — число точек пересечения с прямой $y = a$: при $a < 0$ — нет, при $a = 0$ — два ($0$ и ${2 * m}$), '
               f'при $0 < a < {h}$ — четыре, при $a = {h}$ — три, при $a > {h}$ — два.')
        return {'kind': kind, 'm': m, 'N': N}, iv, eq, text, sol
    if kind == 'cubic':
        m = rng.randint(1, 3)
        top = 2 * m ** 3
        N = rng.choice([1, 2, 3])
        iv = {1: [(INF, F(-top), False, False), (F(top), INF, False, False)], 2: [(F(-top), F(-top), True, True), (F(top), F(top), True, True)],
              3: [(F(-top), F(top), False, False)]}[N]
        eq = f'x^{{3}} - {3 * m * m}x = a'
        text = f'Найдите все значения $a$, при каждом из которых уравнение ${eq}$ имеет {roots_phrase(N)}.'
        sol = (f'$f(x) = x^{{3}} - {3 * m * m}x$, $f\'(x) = 3x^{{2}} - {3 * m * m} = 3(x - {m})(x + {m})$: максимум $f(-{m}) = {top}$, '
               f'минимум $f({m}) = -{top}$. Горизонтальная прямая $y = a$ пересекает график трижды при $-{top} < a < {top}$, '
               f'дважды при $a = \\pm {top}$, один раз при $|a| > {top}$.')
        return {'kind': kind, 'm': m, 'N': N}, iv, eq, text, sol
    if kind == 'hyp':
        r = rng.randint(1, 4)
        k = r * r
        N = rng.choice([0, 1, 2])
        t = 2 * r
        iv = {0: [(F(-t), F(t), False, False)], 1: [(F(-t), F(-t), True, True), (F(t), F(t), True, True)],
              2: [(INF, F(-t), False, False), (F(t), INF, False, False)]}[N]
        eq = f'x + \\frac{{{k}}}{{x}} = a'
        what = {0: 'не имеет корней', 1: 'имеет ровно один корень', 2: 'имеет ровно два корня'}[N]
        text = f'Найдите все значения $a$, при каждом из которых уравнение ${eq}$ {what}.'
        sol = (f'При $x \\ne 0$ уравнение равносильно $x^{{2}} - ax + {k} = 0$ (корень $x = 0$ невозможен, так как свободный член ${k} \\ne 0$). '
               f'Дискриминант $D = a^{{2}} - {4 * k}$: при $|a| > {t}$ — два корня, при $a = \\pm {t}$ — один, при $|a| < {t}$ — нет. '
               f'Это видно и по графику $y = x + \\frac{{{k}}}{{x}}$: его значения — $(-\\infty; -{t}] \\cup [{t}; +\\infty)$.')
        return {'kind': kind, 'k': k, 'N': N}, iv, eq, text, sol
    if kind == 'circle':
        m = rng.randint(1, 4)
        N = rng.choice([0, 1, 2])
        t = 2 * m
        iv = {0: [(INF, F(-t), False, False), (F(t), INF, False, False)], 1: [(F(-t), F(-t), True, True), (F(t), F(t), True, True)],
              2: [(F(-t), F(t), False, False)]}[N]
        eq = f'\\left\\{{ x^{{2}} + y^{{2}} = {2 * m * m}; y = x + a \\right.'
        what = {0: 'не имеет решений', 1: 'имеет ровно одно решение', 2: 'имеет ровно два решения'}[N]
        text = f'Найдите все значения $a$, при каждом из которых система ${eq}$ {what}.'
        sol = (f'Первое уравнение — окружность с центром $O(0; 0)$ радиуса $\\sqrt{{{2 * m * m}}} = {m}\\sqrt{{2}}$, второе — прямая, '
               f'параллельная $y = x$. Расстояние от $O$ до прямой $x - y + a = 0$ равно $\\frac{{|a|}}{{\\sqrt{{2}}}}$. Прямая пересекает '
               f'окружность в двух точках, если $\\frac{{|a|}}{{\\sqrt{{2}}}} < {m}\\sqrt{{2}}$, то есть $|a| < {t}$; касается при $|a| = {t}$; '
               f'не имеет общих точек при $|a| > {t}$.')
        return {'kind': kind, 'm': m, 'N': N}, iv, eq, text, sol
    # roots: x² − 2ax + a² − d² = 0, корни a ± d; оба на [p; q]
    d = rng.randint(1, 3)
    p = rng.randint(-6, 2)
    q = p + 2 * d + rng.randint(1, 6)
    iv = [(F(p + d), F(q - d), True, True)]
    eq = f'x^{{2}} - 2ax + a^{{2}} - {d * d} = 0'
    text = f'Найдите все значения $a$, при каждом из которых оба корня уравнения ${eq}$ принадлежат отрезку $[{p}; {q}]$.'
    sol = (f'$x^{{2}} - 2ax + a^{{2}} = {d * d}$, $(x - a)^{{2}} = {d * d}$, корни $x = a - {d}$ и $x = a + {d}$. Оба на отрезке, если '
           f'${p} \\le a - {d}$ и $a + {d} \\le {q}$, то есть ${p + d} \\le a \\le {q - d}$.')
    return {'kind': 'roots', 'd': d, 'p': p, 'q': q, 'N': 2}, iv, eq, text, sol


def main():
    rng = random.Random(SEED)
    out, titles = [], set()
    for k, (level, kind) in enumerate(PLAN, 1):
        for _ in range(20000):
            sp, iv, eq, text, sol = make(rng, kind)
            title = 'Параметр: ' + eq.replace('\\left\\{', '{').replace('\\right.', '').replace('\\frac', '').replace('\\', '').replace('{', '').replace('}', '') + f', N = {sp["N"]}'
            if kind == 'roots':
                title = f'Параметр: корни a ± {sp["d"]} на [{sp["p"]}; {sp["q"]}]'
            if title in titles:
                continue
            titles.add(title)
            break
        else:
            raise SystemExit(f'№19, {kind}: не удалось подобрать задачу')
        sp['iv'] = [['-inf' if lo is INF else str(lo), 'inf' if hi is INF else str(hi), lc, hc] for lo, hi, lc, hc in iv]
        full = f'<p>{sol}</p><p>Ответ: $a \\in {ival_tex(iv)}$.</p>'
        out.append(item2(19, k, level, TOPIC, title, text, full, ival_txt(iv), sp))
    emit(out)


if __name__ == '__main__':
    main()
