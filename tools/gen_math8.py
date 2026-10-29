#!/usr/bin/env python3
"""Генератор задач ЕГЭ-2027 по профильной математике, №8 (вычисления и преобразования), для банка stackly.

    python3 tools/gen_math8.py > /tmp/m8.json      # 40 задач: 30 базовых, 10 повышенных

Как в банке ФИПИ и демоверсии: степени с дробными показателями, корни, свойства логарифмов, тригонометрия
(формулы двойного угла и приведения, значение функции по другой функции и четверти), выражение при значении
переменной. Ответ генератор получает через тождества; в описании <!--spec:…--> лежит то же выражение на Python
(«py») — tests/test_bank_math.py вычисляет его напрямую и сравнивает с ответом.
"""
import random, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathkit import F, ans, n, fr, item, emit, tex_plain, is_dec

SEED = 20270108
TOPIC = 'Вычисления и преобразования'
PLAN = ([('Б', 'pow')] * 6 + [('Б', 'powbase')] * 4 + [('Б', 'root')] * 5 + [('Б', 'logsum')] * 5 + [('Б', 'logdiv')] * 4
        + [('Б', 'logpow')] * 3 + [('Б', 'trig2')] * 3 + [('П', 'trigsq')] * 4 + [('П', 'tgq')] * 4 + [('П', 'alg')] * 2)


def dec(x):
    """Показатель-десятичная дробь для формулы: 1,5 → «1,5», для Python — «1.5»."""
    return n(x), str(float(x))


def make(rng, fam):
    if fam == 'pow':
        a = rng.choice([2, 3, 5, 7, 10])
        p, q = F(rng.randint(1, 40), 10), F(rng.randint(1, 40), 10)
        r = p + q - rng.choice([0, 1, 2, 3])
        if r <= 0 or not 1 <= p + q - r <= 3:
            return None
        e = p + q - r
        tx = f'\\frac{{{a}^{{{n(p)}}} \\cdot {a}^{{{n(q)}}}}}{{{a}^{{{n(r)}}}}}'
        py = f'{a}**{float(p)} * {a}**{float(q)} / {a}**{float(r)}'
        sol = f'При умножении показатели складываются, при делении вычитаются: ${a}^{{{n(p)} + {n(q)} - {n(r)}}} = {a}^{{{n(e)}}} = {n(F(a) ** int(e))}$.'
        return tx, py, F(a) ** int(e), sol
    if fam == 'powbase':
        a = rng.choice([2, 3, 5])
        k = rng.choice([2, 3])
        p, q = F(rng.randint(1, 19), 10), F(rng.randint(1, 19), 10)
        e = p + k * q
        if e.denominator != 1 or not 1 <= e <= 4:
            return None
        tx = f'{a}^{{{n(p)}}} \\cdot {a ** k}^{{{n(q)}}}'
        py = f'{a}**{float(p)} * {a ** k}**{float(q)}'
        sol = (f'${a ** k} = {a}^{{{k}}}$, поэтому ${a ** k}^{{{n(q)}}} = {a}^{{{n(k * q)}}}$. Тогда '
               f'${a}^{{{n(p)} + {n(k * q)}}} = {a}^{{{int(e)}}} = {a ** int(e)}$.')
        return tx, py, F(a) ** int(e), sol
    if fam == 'root':
        kind = rng.choice(['sq', 'cube', 'frac'])
        if kind == 'sq':
            m = rng.randint(2, 15)
            b = rng.choice([2, 3, 5, 6, 7, 10])
            if (m * m) % b:
                return None
            a = m * m // b
            if a == b or a < 2:
                return None
            tx, py = f'\\sqrt{{{a}}} \\cdot \\sqrt{{{b}}}', f'({a}**0.5)*({b}**0.5)'
            sol = f'$\\sqrt{{{a}}} \\cdot \\sqrt{{{b}}} = \\sqrt{{{a * b}}} = {m}$.'
            return tx, py, F(m), sol
        if kind == 'cube':
            m = rng.randint(2, 9)
            b = rng.choice([2, 3, 4, 9])
            if m ** 3 % b:
                return None
            a = m ** 3 // b
            if a == b or a < 2:
                return None
            tx, py = f'\\sqrt[3]{{{a}}} \\cdot \\sqrt[3]{{{b}}}', f'({a}**(1/3))*({b}**(1/3))'
            sol = f'$\\sqrt[3]{{{a}}} \\cdot \\sqrt[3]{{{b}}} = \\sqrt[3]{{{a * b}}} = {m}$.'
            return tx, py, F(m), sol
        k = rng.choice([2, 3, 4, 5, 6])
        c = rng.choice([2, 3, 5, 6, 7])
        tx, py = f'\\frac{{({k}\\sqrt{{{c}}})^{{2}}}}{{{c * 2}}}', f'({k}*{c}**0.5)**2/{c * 2}'
        res = F(k * k * c, 2 * c)
        sol = f'$({k}\\sqrt{{{c}}})^{{2}} = {k * k} \\cdot {c} = {k * k * c}$, и ${k * k * c} : {2 * c} = {n(res)}$.'
        return tx, py, res, sol
    if fam == 'logsum':
        a = rng.choice([2, 3, 5, 6, 10])
        k = rng.choice([2, 3, 4]) if a < 5 else rng.choice([1, 2, 3])
        b = rng.choice([x for x in range(2, 60) if (a ** k) % x == 0 and x != a ** k] or [None])
        if b is None:
            return None
        c = F(a ** k, b)
        sign = rng.choice(['+', '-'])
        if sign == '+':
            tx, py = f'\\log_{{{a}}} {n(b)} + \\log_{{{a}}} {n(c)}', f'math.log({b}, {a}) + math.log({float(c)}, {a})'
            sol = f'Сумма логарифмов с одним основанием — логарифм произведения: $\\log_{{{a}}}({n(b)} \\cdot {n(c)}) = \\log_{{{a}}} {a ** k} = {k}$.'
            return (tx, py, F(k), sol) if is_dec(c) else None
        bb = a ** k * rng.randint(2, 9)
        cc = bb // a ** k
        tx, py = f'\\log_{{{a}}} {bb} - \\log_{{{a}}} {cc}', f'math.log({bb}, {a}) - math.log({cc}, {a})'
        sol = f'Разность логарифмов — логарифм частного: $\\log_{{{a}}} \\frac{{{bb}}}{{{cc}}} = \\log_{{{a}}} {a ** k} = {k}$.'
        return tx, py, F(k), sol
    if fam == 'logdiv':
        p = rng.choice([2, 3, 5, 7])
        x, y = rng.sample([2, 3, 4], 2)
        tx, py = f'\\frac{{\\log_{{{p}}} {p ** x}}}{{\\log_{{{p}}} {p ** y}}}', f'math.log({p ** x}, {p}) / math.log({p ** y}, {p})'
        res = F(x, y)
        if not is_dec(res):
            return None
        sol = f'$\\log_{{{p}}} {p ** x} = {x}$, $\\log_{{{p}}} {p ** y} = {y}$, частное $\\frac{{{x}}}{{{y}}} = {n(res)}$.'
        return tx, py, res, sol
    if fam == 'logpow':
        a = rng.choice([2, 3, 5, 7])
        b = rng.randint(2, 15)
        k = rng.choice([2, 3])
        tx, py = f'{a ** k}^{{\\log_{{{a}}} {b}}}', f'{a ** k}**math.log({b}, {a})'
        sol = (f'${a ** k} = {a}^{{{k}}}$, поэтому ${a ** k}^{{\\log_{{{a}}} {b}}} = (\\,{a}^{{\\log_{{{a}}} {b}}})^{{{k}}} '
               f'= {b}^{{{k}}} = {b ** k}$.')
        return tx, py, F(b ** k), sol
    if fam == 'trig2':
        t = rng.choice([x for x in range(4, 44) if x % 15])
        k = rng.randint(2, 30)
        big = 180 - 2 * t if rng.random() < 0.5 else 2 * t
        tx = f'\\frac{{{k} \\sin {big}^\\circ}}{{\\sin {t}^\\circ \\cdot \\sin {90 - t}^\\circ}}'
        py = f'{k}*math.sin(math.radians({big}))/(math.sin(math.radians({t}))*math.sin(math.radians({90 - t})))'
        red = f'$\\sin {big}^\\circ = \\sin {2 * t}^\\circ$, ' if big != 2 * t else ''
        sol = (red + f'$\\sin {90 - t}^\\circ = \\cos {t}^\\circ$ и $\\sin {2 * t}^\\circ = 2 \\sin {t}^\\circ \\cos {t}^\\circ$, '
               f'поэтому дробь равна ${k} \\cdot 2 = {2 * k}$.')
        return tx, py, F(2 * k), sol
    if fam == 'trigsq':
        k = rng.randint(2, 40)
        ang, val_ = rng.choice([('\\frac{\\pi}{8}', 'math.pi/8'), ('\\frac{\\pi}{12}', 'math.pi/12'), ('\\frac{5\\pi}{8}', '5*math.pi/8')])
        if 'pi}{8}' in ang:
            coef, csq = f'{k}\\sqrt{{2}}', 'cos π/4 = √2/2'
            res = F(k) * (1 if ang == '\\frac{\\pi}{8}' else -1)
            pyk = f'{k}*2**0.5'
        else:
            coef, csq = f'{2 * k}', 'cos π/6'
            return None
        tx = f'{coef} \\cos^{{2}} {ang} - {coef} \\sin^{{2}} {ang}'
        py = f'{pyk}*math.cos({val_})**2 - {pyk}*math.sin({val_})**2'
        two = '\\frac{\\pi}{4}' if ang == '\\frac{\\pi}{8}' else '\\frac{5\\pi}{4}'
        sol = (f'Вынесем общий множитель: ${coef}(\\cos^{{2}} {ang} - \\sin^{{2}} {ang}) = {coef} \\cos {two}$. '
               f'$\\cos {two} = {"" if res > 0 else "-"}\\frac{{\\sqrt{{2}}}}{{2}}$, итого ${n(res)}$.')
        return tx, py, res, sol
    if fam == 'tgq':
        a, b, c = rng.choice([(3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25), (20, 21, 29)])
        if rng.random() < 0.5:
            a, b = b, a
        q = rng.choice([2, 3, 4])
        rng_ = {2: '\\left(\\frac{\\pi}{2}; \\pi\\right)', 3: '\\left(\\pi; \\frac{3\\pi}{2}\\right)', 4: '\\left(\\frac{3\\pi}{2}; 2\\pi\\right)'}[q]
        sin_s, cos_s = {2: (1, -1), 3: (-1, -1), 4: (-1, 1)}[q]
        cosv, sinv = F(cos_s * a, c), F(sin_s * b, c)
        k = rng.choice([1, 2, 3, 4, 5]) if a in (3, 4) else rng.choice([1, 2, 5, 10])
        res = k * sinv / cosv
        if not is_dec(res):
            return None
        tx = f'{k if k > 1 else ""}\\tg \\alpha'
        cos_txt = n(cosv)
        sol = (f'В {q}-й четверти синус {"положителен" if sin_s > 0 else "отрицателен"}: $\\sin \\alpha = '
               f'{"" if sin_s > 0 else "-"}\\sqrt{{1 - \\cos^{{2}} \\alpha}} = {n(sinv)}$. Тогда '
               f'${tx} = {k if k > 1 else ""}{"" if k == 1 else " \\cdot "}\\frac{{\\sin \\alpha}}{{\\cos \\alpha}} = {n(res)}$.')
        cond = f'если $\\cos \\alpha = {cos_txt}$ и $\\alpha \\in {rng_}$'
        py = f'{k}*math.tan(math.atan2({float(sinv)}, {float(cosv)}))'
        return (tx, py, res, sol.replace('1\\tg', '\\tg'), cond)
    # alg: значение выражения при a: (a² − b²)/(a − b) − a = b, b подбирается
    b = rng.randint(2, 15)
    a = F(rng.randint(1, 99), rng.choice([1, 10, 4]))
    if a == b:
        return None
    tx = f'\\frac{{a^{{2}} - {b * b}}}{{a - {b}}} - a'
    py = f'({float(a)}**2 - {b * b})/({float(a)} - {b}) - {float(a)}'
    sol = f'$a^{{2}} - {b * b} = (a - {b})(a + {b})$, дробь равна $a + {b}$, и всё выражение равно ${b}$ при любом $a \\ne {b}$.'
    return tx, py, F(b), sol, f'при $a = {n(a)}$'


def main():
    rng = random.Random(SEED)
    out, seen = [], set()
    for k, (level, fam) in enumerate(PLAN, 1):
        while True:
            r = make(rng, fam)
            if r is None:
                continue
            tx, py, res, sol = r[:4]
            cond = r[4] if len(r) > 4 else ''
            if tx in seen or not is_dec(res):
                continue
            seen.add(tx)
            break
        text = f'Найдите значение выражения ${tx}$' + (f' {cond}' if cond else '') + '.'
        title = {'pow': 'Степени', 'powbase': 'Степени, разные основания', 'root': 'Корни', 'logsum': 'Логарифмы',
                 'logdiv': 'Частное логарифмов', 'logpow': 'Степень с логарифмом', 'trig2': 'Синус двойного угла',
                 'trigsq': 'Косинус двойного угла', 'tgq': 'Тангенс по косинусу', 'alg': 'Дробь с переменной'}[fam] + ': ' + tex_plain(tx)
        if cond:
            title += ', ' + tex_plain(cond.replace('$', ''))
        out.append(item(8, k, level, TOPIC, title[:100], text, sol, ans(res), {'fam': fam, 'py': py}))
    emit(out)


if __name__ == '__main__':
    main()
