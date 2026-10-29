#!/usr/bin/env python3
"""Генератор задач ЕГЭ-2027 по профильной математике, №14 (уравнение с отбором корней, часть 2, 2 балла).

    python3 tools/gen_math14.py > /tmp/m14.json      # 24 задачи: 16 повышенных, 8 высоких

Как в демоверсии: а) решите тригонометрическое уравнение; б) найдите корни на отрезке. Виды: квадратное относительно
sin x или cos x (один корень вспомогательного уравнения может быть посторонним, |t| > 1), то же через cos 2x,
вынесение общего множителя после формулы синуса двойного угла. Отрезок — длиной 3π/2 с концами, кратными π/2.
Ответ а) — серии x = aπ + dπk, ответ б) — список корней. Описание <!--spec:…--> хранит уравнение на Python
(«py»), серии и отрезок в долях π; tests/test_bank_math.py численно находит все корни на [−4π; 4π] и сверяет.
"""
import random, sys, os, math
from fractions import Fraction as F
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathkit import n, item2, emit, poly

SEED = 20270114
TOPIC = 'Уравнение с отбором корней'
PLAN = [('П', 'sinq')] * 6 + [('П', 'cosq')] * 5 + [('П', 'cos2x')] * 5 + [('В', 'factor')] * 8

H = F(1, 2)
SIN_SER = {F(0): [(F(0), F(1))], F(1): [(H, F(2))], F(-1): [(-H, F(2))], H: [(F(1, 6), F(2)), (F(5, 6), F(2))],
           -H: [(F(-1, 6), F(2)), (F(-5, 6), F(2))]}
COS_SER = {F(0): [(H, F(1))], F(1): [(F(0), F(2))], F(-1): [(F(1), F(2))], H: [(F(1, 3), F(2)), (F(-1, 3), F(2))],
           -H: [(F(2, 3), F(2)), (F(-2, 3), F(2))]}
# значения с корнями: ключ — (знак, корень из чего) → значение √m/2
ROOT_SIN = {(1, 2): [(F(1, 4), F(2)), (F(3, 4), F(2))], (-1, 2): [(F(-1, 4), F(2)), (F(-3, 4), F(2))],
            (1, 3): [(F(1, 3), F(2)), (F(2, 3), F(2))], (-1, 3): [(F(-1, 3), F(2)), (F(-2, 3), F(2))],
            (1, 1): SIN_SER[H], (-1, 1): SIN_SER[-H]}
ROOT_COS = {(1, 2): [(F(1, 4), F(2)), (F(-1, 4), F(2))], (-1, 2): [(F(3, 4), F(2)), (F(-3, 4), F(2))],
            (1, 3): [(F(1, 6), F(2)), (F(-1, 6), F(2))], (-1, 3): [(F(5, 6), F(2)), (F(-5, 6), F(2))],
            (1, 1): COS_SER[H], (-1, 1): COS_SER[-H]}


def pi_tex(a):
    """aπ в формуле: 0, π, −π, 2π, \\frac{π}{6}, −\\frac{5π}{6}."""
    a = F(a)
    if a == 0:
        return '0'
    sgn = '-' if a < 0 else ''
    p, q = abs(a.numerator), a.denominator
    num = ('' if p == 1 else str(p)) + '\\pi'
    return sgn + (num if q == 1 else f'\\frac{{{num}}}{{{q}}}')


def pi_txt(a):
    a = F(a)
    if a == 0:
        return '0'
    sgn = '−' if a < 0 else ''
    p, q = abs(a.numerator), a.denominator
    return sgn + ('' if p == 1 else str(p)) + 'π' + ('' if q == 1 else f'/{q}')


def series_tex(ser):
    out = []
    for a, d in ser:
        per = ('' if d == 1 else str(d)) + '\\pi k'
        out.append(f'x = {pi_tex(a)} + {per}' if a != 0 else f'x = {per}')
    return ', '.join(out).replace('+ -', '- ') + ', k \\in Z'


def series_txt(ser):
    out = []
    for a, d in ser:
        per = ('' if d == 1 else str(d)) + 'πk'
        out.append(f'{pi_txt(a)} + {per}' if a != 0 else per)
    return '; '.join(out).replace('+ −', '− ') + ', k ∈ Z'


def roots_on(ser, L, R):
    rs = set()
    for a, d in ser:
        k = math.floor((L - a) / d) - 1
        while a + d * k <= R:
            x = a + d * k
            if L <= x <= R:
                rs.add(x)
            k += 1
    return sorted(rs)


def quad_from(t1, t2, scale=2):
    """Целые коэффициенты c·(t − t1)(t − t2) с наименьшим подходящим множителем."""
    for c in range(scale, 30):
        cs = [F(c), -c * (t1 + t2), c * t1 * t2]
        if all(x.denominator == 1 for x in cs):
            return [int(x) for x in cs]
    return None


def make(rng, fam):
    valid = [F(0), H, -H, F(1), F(-1)]
    bad = [F(2), F(-2), F(3, 2), F(-3, 2), F(3), F(-3), F(5, 2)]
    if fam in ('sinq', 'cosq', 'cos2x'):
        t1 = rng.choice(valid)
        t2 = rng.choice(bad + [v for v in valid if v != t1 and v != -t1])
        fn = 'sin' if fam != 'cosq' else 'cos'
        SER = SIN_SER if fn == 'sin' else COS_SER
        ok = [t for t in (t1, t2) if abs(t) <= 1]
        if fam == 'cos2x':
            # cos 2x + p sin x + q = 0  ⇔  2s² − p s − (1 + q) = 0 = 2(s − t1)(s − t2)
            p, q = 2 * (t1 + t2), -2 * t1 * t2 - 1
            if p.denominator != 1 or q.denominator != 1 or p == 0:
                return None
            eq = f'\\cos 2x {"+" if p > 0 else "-"} {abs(p) if abs(p) != 1 else ""}\\sin x {"+" if q >= 0 else "-"} {abs(q)} = 0'.replace(' + 0 = 0', ' = 0').replace(' - 0 = 0', ' = 0')
            py = f'math.cos(2*x) + ({p})*math.sin(x) + ({q})'
            step = (f'По формуле $\\cos 2x = 1 - 2\\sin^{{2}} x$ уравнение принимает вид $2\\sin^{{2}} x {"-" if p > 0 else "+"} '
                    f'{abs(p) if abs(p) != 1 else ""}\\sin x {"-" if 1 + q >= 0 else "+"} {abs(1 + q)} = 0$. ').replace(' - 0 = 0', ' = 0').replace(' + 0 = 0', ' = 0')
            cs = [2, -int(p), -int(1 + q)]
        else:
            cs = quad_from(t1, t2)
            if cs is None:
                return None
            terms = []
            a, b, c = cs
            eq = (f'{a}\\{fn}^{{2}} x {"+" if b >= 0 else "-"} {abs(b) if abs(b) != 1 else ""}\\{fn} x {"+" if c >= 0 else "-"} {abs(c)} = 0'
                  .replace(' + 0\\' + fn + ' x', '').replace(' - 0\\' + fn + ' x', '').replace(' + 0 = 0', ' = 0').replace(' - 0 = 0', ' = 0'))
            py = f'{a}*math.{fn}(x)**2 + ({b})*math.{fn}(x) + ({c})'
            step = ''
        ser = [s for t in sorted(set(ok)) for s in SER[t]]
        sv = 'sin' if fn == 'sin' or fam == 'cos2x' else 'cos'
        ser = [s for t in sorted(set(ok)) for s in (SIN_SER if sv == 'sin' else COS_SER)[t]]
        roots_t = ', '.join(f'$t = {n(t)}$' for t in sorted({t1, t2}))
        drop = [t for t in (t1, t2) if abs(t) > 1]
        sol_a = (step + f'Замена $t = \\{sv} x$: ${poly(cs, "t")} = 0$, корни {roots_t}. '
                 + (f'Корень ${n(drop[0])}$ не подходит: $|\\{sv} x| \\le 1$. ' if drop else '')
                 + ' и '.join(f'$\\{sv} x = {n(t)}$' for t in sorted(set(ok))) + (' даёт $' if len(set(ok)) == 1 else ' дают $')
                 + series_tex(ser) + '$.')
    else:
        # sin 2x = k cos x  ⇒  cos x (2 sin x − k) = 0;   sin 2x = k sin x  ⇒  sin x (2 cos x − k) = 0
        sign, m = rng.choice([1, -1]), rng.choice([1, 2, 3])
        kt = ('' if m == 1 else f'\\sqrt{{{m}}}')
        kpy = f'{sign}*math.sqrt({m})'
        form = rng.choice(['cos', 'sin'])
        if form == 'cos':
            eq = f'\\sin 2x {"=" if sign > 0 else "= -"} {kt}\\cos x'.replace('=  ', '= ')
            py = f'math.sin(2*x) - ({kpy})*math.cos(x)'
            ser = COS_SER[F(0)] + ROOT_SIN[(sign, m)]
            sol_a = (f'$2\\sin x\\cos x {"-" if sign > 0 else "+"} {kt}\\cos x = 0$, $\\cos x(2\\sin x {"-" if sign > 0 else "+"} {kt or "1"}) = 0$. '
                     f'Либо $\\cos x = 0$, либо $\\sin x = {"-" if sign < 0 else ""}\\frac{{{kt or "1"}}}{{2}}$: $' + series_tex(ser) + '$.')
        else:
            eq = f'\\sin 2x {"=" if sign > 0 else "= -"} {kt}\\sin x'.replace('=  ', '= ')
            py = f'math.sin(2*x) - ({kpy})*math.sin(x)'
            ser = SIN_SER[F(0)] + ROOT_COS[(sign, m)]
            sol_a = (f'$2\\sin x\\cos x {"-" if sign > 0 else "+"} {kt}\\sin x = 0$, $\\sin x(2\\cos x {"-" if sign > 0 else "+"} {kt or "1"}) = 0$. '
                     f'Либо $\\sin x = 0$, либо $\\cos x = {"-" if sign < 0 else ""}\\frac{{{kt or "1"}}}{{2}}$: $' + series_tex(ser) + '$.')
        eq = eq.replace('= -  ', '= -').replace('= - ', '= -')
    m0 = rng.randint(-8, 6)
    L, R = F(m0, 2), F(m0, 2) + F(3, 2)
    rs = roots_on(ser, L, R)
    if not rs:
        return None
    text = (f'а) Решите уравнение ${eq}$.<br>б) Укажите корни этого уравнения, принадлежащие отрезку '
            f'$\\left[{pi_tex(L)}; {pi_tex(R)}\\right]$.')
    sol = (f'<p><b>а)</b> {sol_a}</p><p><b>б)</b> Отберём корни на отрезке $\\left[{pi_tex(L)}; {pi_tex(R)}\\right]$ с помощью '
           f'единичной окружности (или двойного неравенства для каждой серии): подходят $' + '; '.join(pi_tex(r) for r in rs) + '$.</p>')
    ans = f'а) {series_txt(ser)}; б) ' + '; '.join(pi_txt(r) for r in rs)
    spec = {'py': py, 'series': [[str(a), str(d)] for a, d in ser], 'seg': [str(L), str(R)], 'roots': [str(r) for r in rs]}
    return spec, eq, text, sol, ans


def main():
    rng = random.Random(SEED)
    out, seen = [], set()
    for k, (level, fam) in enumerate(PLAN, 1):
        for _ in range(20000):
            r = make(rng, fam)
            if r is None:
                continue
            spec, eq, text, sol, ans = r
            title = 'Уравнение: ' + eq.replace('\\', '').replace('{', '').replace('}', '') + ', отрезок ' + spec['seg'][0] + '…' + spec['seg'][1] + ' π'
            if title in seen:
                continue
            seen.add(title)
            break
        else:
            raise SystemExit(f'№14, {fam}: не удалось подобрать задачу')
        spec['fam'] = fam
        out.append(item2(14, k, level, TOPIC, title, text, sol, ans, spec))
    emit(out)


if __name__ == '__main__':
    main()
