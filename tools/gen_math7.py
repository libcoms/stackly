#!/usr/bin/env python3
"""Генератор задач ЕГЭ-2027 по профильной математике, №7 (простейшие уравнения), для банка stackly.

    python3 tools/gen_math7.py > /tmp/m7.json      # 40 задач: 28 базовых, 12 повышенных

Как в банке ФИПИ и демоверсии: показательные (в том числе с основанием-дробью), логарифмические, иррациональные,
линейные и дробно-рациональные уравнения; квадратное с выбором меньшего/большего корня; √(ax + b) = x
с посторонним корнем; логарифм с переменным основанием. Корни подбираются заранее — ответ всегда конечная
десятичная дробь. Описание в <!--spec:…-->, tests/test_bank_math.py проверяет корень подстановкой.
"""
import random, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathkit import F, ans, n, fr, poly, item, emit, tex_plain

SEED = 20270107
TOPIC = 'Простейшие уравнения'
PLAN = ([('Б', 'lin')] * 4 + [('Б', 'exp')] * 6 + [('Б', 'expfrac')] * 4 + [('Б', 'log')] * 6 + [('Б', 'sqrt')] * 5
        + [('Б', 'rat')] * 3 + [('П', 'quad')] * 5 + [('П', 'irrx')] * 4 + [('П', 'logbase')] * 3)
ASK = 'Найдите корень уравнения'


def make(rng, fam):
    if fam == 'lin':
        x = F(rng.randint(-40, 40), rng.choice([1, 1, 2, 4, 5]))
        a, c = rng.sample([k for k in range(-9, 10) if k], 2)
        b = rng.randint(-30, 30)
        d = a * x + b - c * x
        eq = f'{poly([a, b])} = {poly([c, d])}'
        sol = (f'Переносим слагаемые с $x$ влево, числа вправо: $({n(a)} - ({n(c)}))x = {n(d)} - ({n(b)})$, '
               f'$${n(a - c)}x = {n(d - b)}$, откуда $x = {n(x)}$.')
        return {'fam': fam, 'a': a, 'b': b, 'c': c, 'd': d}, x, eq, sol
    if fam == 'exp':
        p = rng.choice([2, 3, 5, 6, 7])
        x = rng.randint(-9, 9)
        b = rng.randint(-8, 8)
        k = rng.choice([1, -1, 2])
        e = k * x + b
        if not -4 <= e <= 6 or e == 0:
            return None
        rhs = F(p) ** e
        lhs = f'{p}^{{{poly([k, b])}}}'
        sol = (f'Запишем правую часть степенью с основанием ${p}$: ${n(rhs) if rhs.denominator == 1 else fr(rhs)} = {p}^{{{e}}}$. '
               f'Основания равны, значит, равны показатели: ${poly([k, b])} = {e}$, $x = {n(x)}$.')
        return {'fam': fam, 'p': p, 'k': k, 'b': b, 'rhs': str(rhs)}, F(x), f'{lhs} = {fr(rhs)}', sol
    if fam == 'expfrac':
        p = rng.choice([2, 3, 5, 7])
        x = rng.randint(-9, 9)
        b = rng.randint(-8, 8)
        e = x + b                                   # (1/p)^(x + b) = p^(−e)
        if not 1 <= abs(e) <= 4:
            return None
        rhs = F(p) ** (-e)
        sol = (f'$\\frac{{1}}{{{p}}} = {p}^{{-1}}$, поэтому левая часть равна ${p}^{{-({poly([1, b])})}}$, '
               f'а правая ${fr(rhs)} = {p}^{{{-e}}}$. Показатели равны: $-({poly([1, b])}) = {-e}$, $x = {x}$.')
        return ({'fam': fam, 'p': p, 'b': b, 'rhs': str(rhs)}, F(x),
                f'\\left(\\frac{{1}}{{{p}}}\\right)^{{{poly([1, b])}}} = {fr(rhs)}', sol)
    if fam == 'log':
        a = rng.choice([2, 3, 4, 5, 7])
        c = rng.choice([1, 2, 3]) if a < 5 else rng.choice([1, 2])
        k = rng.choice([1, 1, 2, 3, 4])
        b = rng.randint(-20, 20)
        x = F(a ** c - b, k)
        if not -60 < x < 60 or not ans_ok(x):
            return None
        sol = (f'По определению логарифма ${poly([k, b])} = {a}^{{{c}}} = {a ** c}$, откуда $x = {n(x)}$. '
               f'Проверка: аргумент логарифма ${a ** c} > 0$.')
        return {'fam': fam, 'a': a, 'c': c, 'k': k, 'b': b}, x, f'\\log_{{{a}}}({poly([k, b])}) = {c}', sol
    if fam == 'sqrt':
        c = rng.randint(2, 12)
        k = rng.choice([1, 2, 3, 4, 5, -1, -2])
        b = rng.randint(-30, 60)
        x = F(c * c - b, k)
        if not ans_ok(x) or abs(x) > 80:
            return None
        sol = (f'Возведём обе части в квадрат: ${poly([k, b])} = {c * c}$, откуда $x = {n(x)}$. '
               f'Правая часть ${c} \\ge 0$, поэтому посторонних корней нет.')
        return {'fam': fam, 'k': k, 'b': b, 'c': c}, x, f'\\sqrt{{{poly([k, b])}}} = {c}', sol
    if fam == 'rat':
        # (x + a) / (x + b) = d  →  x + a = d(x + b)
        a, b = rng.sample(range(-12, 13), 2)
        d = rng.choice([2, 3, 4, -1, -2, F(1, 2), F(1, 3)])
        if d == 1:
            return None
        x = F(d * b - a, 1 - d)
        if x + b == 0 or not ans_ok(x):
            return None
        sol = (f'При $x \\ne {n(-b)}$ умножим на знаменатель: ${poly([1, a])} = {n(d)}({poly([1, b])})$, '
               f'$x = {n(x)}$ — знаменатель при этом не равен нулю.')
        return {'fam': fam, 'a': a, 'b': b, 'd': str(d)}, x, f'\\frac{{{poly([1, a])}}}{{{poly([1, b])}}} = {n(d)}', sol
    if fam == 'quad':
        r1, r2 = rng.sample(range(-12, 13), 2)
        lead = rng.choice([1, 1, 2, -1])
        which = rng.choice(['меньший', 'больший'])
        x = min(r1, r2) if which == 'меньший' else max(r1, r2)
        cs = [lead, -lead * (r1 + r2), lead * r1 * r2]
        sol = (f'Корни уравнения ${poly(cs)} = 0$: по теореме Виета (или через дискриминант) $x_{{1}} = {min(r1, r2)}$, '
               f'$x_{{2}} = {max(r1, r2)}$. В ответ идёт {which} корень: ${x}$.')
        return ({'fam': fam, 'cs': cs, 'which': which}, F(x),
                f'{poly(cs)} = 0', sol)
    if fam == 'irrx':
        # √(px + q) = x: корни r (≥ 0) и s (< 0, посторонний)
        r = rng.randint(1, 12)
        s = rng.randint(-9, -1)
        p, q = r + s, -r * s
        sol = (f'Возведём в квадрат при условии $x \\ge 0$: $x^{{2}} = {poly([p, q])}$, $x^{{2}} {"-" if p >= 0 else "+"} '
               f'{abs(p) if abs(p) != 1 else ""}x {"-" if q >= 0 else "+"} {abs(q)} = 0$, корни ${r}$ и ${s}$. '
               f'Корень ${s} < 0$ посторонний: правая часть не может быть отрицательной. Ответ: ${r}$.')
        if p == 0:
            return None
        return {'fam': fam, 'p': p, 'q': q}, F(r), f'\\sqrt{{{poly([p, q])}}} = x', sol
    # log_x (bx + c) = 2 → x² − bx − c = 0, корень > 0 и ≠ 1
    r = rng.randint(2, 11)
    s = rng.randint(-9, -1)
    b, c = r + s, -r * s
    if b <= 0:
        return None
    sol = (f'По определению логарифма $x^{{2}} = {poly([b, c])}$ при $x > 0$, $x \\ne 1$. '
           f'Корни квадратного уравнения: ${r}$ и ${s}$; основание логарифма должно быть положительным, '
           f'поэтому подходит только $x = {r}$.')
    return {'fam': 'logbase', 'b': b, 'c': c}, F(r), f'\\log_{{x}}({poly([b, c])}) = 2', sol


def ans_ok(x):
    try:
        ans(x)
        return True
    except ValueError:
        return False


def main():
    rng = random.Random(SEED)
    out, seen = [], set()
    for k, (level, fam) in enumerate(PLAN, 1):
        while True:
            r = make(rng, fam)
            if r is None:
                continue
            spec, x, eq, sol = r
            if eq in seen or not ans_ok(x):
                continue
            seen.add(eq)
            break
        spec['eq'] = eq
        extra = ''
        if fam == 'quad':
            text = f'Решите уравнение $${eq}$$. Если уравнение имеет более одного корня, в ответе запишите {spec["which"]} из корней.'
        elif fam == 'irrx':
            text = f'Решите уравнение $${eq}$$. Если уравнение имеет более одного корня, укажите меньший из них.'
        else:
            text = f'{ASK} $${eq}$$.'
        text = text.replace('$$', '$')
        sol = sol.replace('$$', '$')
        title = {'lin': 'Линейное', 'exp': 'Показательное', 'expfrac': 'Показательное, основание-дробь', 'log': 'Логарифмическое',
                 'sqrt': 'Иррациональное', 'rat': 'Дробно-рациональное', 'quad': 'Квадратное: ' + spec.get('which', ''),
                 'irrx': 'Корень равен x', 'logbase': 'Переменное основание'}[fam] + ': ' + tex_plain(eq)
        out.append(item(7, k, level, TOPIC, title[:90], text, sol, ans(x), spec, extra))
    emit(out)


if __name__ == '__main__':
    main()
