#!/usr/bin/env python3
"""Генератор задач ЕГЭ-2027 по профильной математике, №16 (неравенство, часть 2, 2 балла).

    python3 tools/gen_math16.py > /tmp/m16.json      # 24 задачи: 16 повышенных, 8 высоких

Как в демоверсии и банке ФИПИ: логарифмическое и показательное неравенства, сводящиеся к квадратному заменой,
метод интервалов с показательной функцией в числителе, сумма логарифмов с учётом области определения.
Ответ — объединение промежутков. В описании <!--spec:…--> — левая часть g(x) на Python (неравенство g(x) ∨ 0),
знак и ответ-промежутки; tests/test_bank_math.py проверяет ответ в сотнях точек, включая концы промежутков.
"""
import random, sys, os, math
from fractions import Fraction as F
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathkit import n, item2, emit, poly

SEED = 20270116
TOPIC = 'Неравенство'
PLAN = [('П', 'logq')] * 6 + [('П', 'expq')] * 6 + [('П', 'logsum')] * 4 + [('В', 'ratexp')] * 8
INF = None
def xm(a):
    """x − a в формуле: x, x − 4, x + 2."""
    return 'x' if a == 0 else f'x - {a}' if a > 0 else f'x + {-a}'


REL_TX = {'<=': '\\le', '>=': '\\ge', '<': '<', '>': '>'}


def ival_tex(iv):
    out = []
    for lo, hi, lc, hc in iv:
        a = '-\\infty' if lo is INF else n(lo)
        b = '+\\infty' if hi is INF else n(hi)
        out.append(f'{"[" if lc else "("}{a}; {b}{"]" if hc else ")"}')
    return ' \\cup '.join(out)


def ival_txt(iv):
    out = []
    for lo, hi, lc, hc in iv:
        a = '−∞' if lo is INF else n(lo).replace('-', '−')
        b = '+∞' if hi is INF else n(hi).replace('-', '−')
        if lo is not INF and hi is not INF and lo == hi:
            out.append('{' + a + '}')
        else:
            out.append(f'{"[" if lc else "("}{a}; {b}{"]" if hc else ")"}')
    return ' ∪ '.join(out)


def make(rng, fam):
    if fam == 'logq':
        p = rng.choice([2, 3, 5])
        a, b = sorted(rng.sample(range(-2, 4), 2))
        op = rng.choice(['<=', '>='])
        s, m = a + b, a * b
        eq = (f'\\log_{{{p}}}^{{2}} x {"-" if s >= 0 else "+"} {abs(s) if abs(s) != 1 else ""}\\log_{{{p}}} x '
              f'{"+" if m >= 0 else "-"} {abs(m)} {REL_TX[op]} 0').replace(' + 0 ', ' ').replace(' - 0 ', ' ').replace('- \\log', '- \\log')
        if s == 0:
            eq = f'\\log_{{{p}}}^{{2}} x {"+" if m >= 0 else "-"} {abs(m)} {REL_TX[op]} 0'
        g = f'math.log(x, {p})**2 - ({s})*math.log(x, {p}) + ({m})'
        A, B = F(p) ** a, F(p) ** b
        iv = [(A, B, True, True)] if op == '<=' else [(F(0), A, False, True), (B, INF, True, False)]
        sol = (f'Область определения: $x > 0$. Замена $t = \\log_{{{p}}} x$: $t^{{2}} {"-" if s >= 0 else "+"} {abs(s)}t {"+" if m >= 0 else "-"} {abs(m)} {REL_TX[op]} 0$, '
               f'то есть $(t - ({a}))(t - ({b})) {REL_TX[op]} 0$, ' + (f'$ {a} \\le t \\le {b}$.' if op == '<=' else f'$t \\le {a}$ или $t \\ge {b}$.')
               + f' Возвращаясь к $x$ (основание ${p} > 1$, знак сохраняется): ' + (f'${n(A)} \\le x \\le {n(B)}$.' if op == '<=' else f'$0 < x \\le {n(A)}$ или $x \\ge {n(B)}$.'))
        dom = 'x > 0'
    elif fam == 'expq':
        p = rng.choice([2, 3, 5])
        a, b = sorted(rng.sample(range(-2, 4), 2))
        op = rng.choice(['<=', '>='])
        u, v = F(p) ** a, F(p) ** b
        s, m = u + v, u * v
        if s.denominator != 1 or m.denominator != 1:
            return None
        eq = f'{p * p if p < 4 else p}^{{x}} - {s} \\cdot {p}^{{x}} + {m} {REL_TX[op]} 0' if False else f'{p}^{{2x}} - {s} \\cdot {p}^{{x}} + {m} {REL_TX[op]} 0'
        g = f'{p}**(2*x) - {s}*{p}**x + {m}'
        iv = [(F(a), F(b), True, True)] if op == '<=' else [(INF, F(a), False, True), (F(b), INF, True, False)]
        sol = (f'Замена $t = {p}^{{x}} > 0$: $t^{{2}} - {s}t + {m} {REL_TX[op]} 0$, корни $t = {n(u)}$ и $t = {n(v)}$. '
               + (f'${n(u)} \\le {p}^{{x}} \\le {n(v)}$, откуда ${a} \\le x \\le {b}$.' if op == '<=' else
                  f'${p}^{{x}} \\le {n(u)}$ или ${p}^{{x}} \\ge {n(v)}$, откуда $x \\le {a}$ или $x \\ge {b}$.'))
        dom = 'True'
    elif fam == 'logsum':
        # log_p(x − a) + log_p(x − b) ≤ log_p c  ⇔  x > max(a, b), (x − a)(x − b) ≤ c
        p = rng.choice([2, 3, 5, 7])
        a, b = sorted(rng.sample(range(-6, 8), 2))
        r = rng.randint(b + 1, b + 8)                       # правый корень (x − a)(x − b) = c
        c = (r - a) * (r - b)
        iv = [(F(b), F(r), False, True)]
        arg = lambda v: f'({xm(v)})' if v else ' x'
        eq = f'\\log_{{{p}}}{arg(a)} + \\log_{{{p}}}{arg(b)} \\le \\log_{{{p}}} {c}'
        g = f'math.log(x - ({a}), {p}) + math.log(x - ({b}), {p}) - math.log({c}, {p})'
        op = '<='
        other = a + b - r
        sol = (f'Область определения: $x > {b}$. На ней сумма логарифмов — логарифм произведения, и неравенство равносильно '
               f'${"x" if a == 0 else "(" + xm(a) + ")"}({xm(b)}) \\le {c}$, то есть ${poly([1, -(a + b), a * b - c])} \\le 0$; корни ${other}$ и ${r}$, '
               f'решение ${other} \\le x \\le {r}$. С учётом области определения: ${b} < x \\le {r}$.')
        dom = f'x > {b}'
    else:
        # (p^x − p^a) / (x − c) ≥ 0 (или ≤): метод интервалов, нули a (входит), c (не входит)
        p = rng.choice([2, 3, 4, 5])
        a = rng.randint(-3, 4)
        c = rng.choice([x for x in range(-4, 6) if x != a])
        op = rng.choice(['>=', '<='])
        lo, hi = sorted([a, c])
        lc, hc = (lo == a), (hi == a)
        # p^x − p^a имеет знак (x − a): дробь имеет знак (x − a)(x − c)
        if op == '>=':
            iv = [(INF, F(lo), False, lc), (F(hi), INF, hc, False)]
        else:
            iv = [(F(lo), F(hi), lc, hc)]
        pa = F(p) ** a
        eq = f'\\frac{{{p}^{{x}} - {n(pa)}}}{{{xm(c)}}} {REL_TX[op]} 0'
        g = f'({p}**x - {float(pa)})/(x - ({c}))'
        sol = (f'${p}^{{x}} - {n(pa)} = {p}^{{x}} - {p}^{{{a}}}$ имеет тот же знак, что ${xm(a)}$ (функция ${p}^{{x}}$ возрастает). '
               f'Значит, неравенство равносильно $\\frac{{{xm(a)}}}{{{xm(c)}}} {REL_TX[op]} 0$. Метод интервалов: нуль числителя ${a}$ '
               f'входит в ответ, нуль знаменателя ${c}$ — нет.')
        dom = f'x != {c}'
    text = f'Решите неравенство ${eq}$.'
    sol = f'<p>{sol}</p><p>Ответ: ${ival_tex(iv)}$.</p>'
    spec = {'fam': fam, 'g': g, 'op': op, 'dom': dom,
            'iv': [['-inf' if lo is INF else str(lo), 'inf' if hi is INF else str(hi), lc, hc] for lo, hi, lc, hc in iv]}
    return spec, eq, text, sol, ival_txt(iv)


def main():
    rng = random.Random(SEED)
    out, seen = [], set()
    for k, (level, fam) in enumerate(PLAN, 1):
        for _ in range(20000):
            r = make(rng, fam)
            if r is None:
                continue
            spec, eq, text, sol, ans = r
            title = 'Неравенство: ' + eq.replace('\\le', '≤').replace('\\ge', '≥').replace('\\log_', 'log_').replace('\\frac', '').replace('\\cdot', '·').replace('\\', '').replace('{', '').replace('}', '')
            if title in seen:
                continue
            seen.add(title)
            break
        else:
            raise SystemExit(f'№16, {fam}: не удалось подобрать задачу')
        out.append(item2(16, k, level, TOPIC, title[:100], text, sol, ans, spec))
    emit(out)


if __name__ == '__main__':
    main()
