#!/usr/bin/env python3
"""Генератор задач ЕГЭ-2027 по профильной математике, №13 (текстовые и финансовые задачи с кратким ответом —
новая позиция 2027 года), для банка stackly.

    python3 tools/gen_math13.py > /tmp/m13.json      # 32 задачи: 24 повышенных, 8 высоких

Как в демоверсии 2027: экономическая задача бывшего №16 в упрощённом виде, ответ — одно число. Кредит равными
(аннуитетными) платежами — общая сумма выплат или размер платежа; кредит с долгом, уменьшающимся на одну и ту же
величину, — общая сумма выплат или первый платёж; вклад с ежегодным пополнением; кредит, погашенный двумя
заданными платежами, — сумма кредита. Числа подбираются так, чтобы все суммы были целыми. Описание <!--spec:…-->
— график платежей; tests/test_bank_math.py проводит кредит (вклад) по годам и проверяет ответ.
"""
import random, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathkit import F, ans, n, item, emit, plural

SEED = 20270113
TOPIC = 'Финансовые задачи'
PLAN = ([('П', 'annuity_total')] * 6 + [('П', 'annuity_pay')] * 5 + [('П', 'diff_total')] * 6 + [('П', 'diff_first')] * 3
        + [('П', 'deposit')] * 4 + [('В', 'two_pay')] * 4 + [('В', 'diff_find_S')] * 4)
YEARS = {2: 'два года', 3: 'три года', 4: 'четыре года', 5: 'пять лет', 6: 'шесть лет', 8: 'восемь лет', 10: 'десять лет'}
RULE = ('Условия его возврата таковы:<br>— каждый январь долг увеличивается на {r}% по сравнению с концом предыдущего года;'
        '<br>— с февраля по июнь каждого года необходимо выплатить одним платежом часть долга.')


def rub(x):
    return f'{int(x):,}'.replace(',', ' ') + ' рублей'


def make(rng, kind):
    year = rng.randint(2028, 2032)
    if kind in ('annuity_total', 'annuity_pay'):
        r = rng.choice([10, 20, 25, 50])
        N = rng.choice([2, 3]) if r != 10 else 2
        q = F(100 + r, 100)
        base = sum(q ** -k for k in range(1, N + 1))
        x = F(rng.randint(1, 30) * base.denominator * rng.choice([1, 10, 100, 1000]))
        S = x * base
        if S.denominator != 1 or S > 10 ** 8 or S < 10000:
            return None
        text = (f'В июле {year} года планируется взять кредит в банке на {YEARS[N]} в размере {rub(S)}. '
                + RULE.format(r=r) + '<br>Кредит будет полностью погашен '
                + {2: 'двумя', 3: 'тремя'}[N] + ' равными платежами. ')
        if kind == 'annuity_total':
            text += 'Сколько рублей составит общая сумма выплат после полного погашения кредита?'
            res = N * x
        else:
            text += 'Найдите размер одного платежа (в рублях).'
            res = x
        sol = (f'Пусть платёж $x$. Долг через год после начисления процентов: ${n(S)} \\cdot {n(q)}$; после всех платежей '
               f'он равен нулю: ${n(S)} \\cdot {n(q)}^{{{N}}} = x(' + ' + '.join(f'{n(q)}^{{{k}}}' if k > 1 else n(q) if k == 1 else '1' for k in range(N - 1, -1, -1))
               + f')$, откуда $x = {n(x)}$' + (f', а всего выплачено ${N} \\cdot {n(x)} = {n(N * x)}$ руб.' if kind == 'annuity_total' else ' руб.'))
        return ({'kind': kind, 'S': str(S), 'r': r, 'pays': [str(x)] * N, 'ask': 'total' if kind == 'annuity_total' else 'pay'},
                res, text, sol, f'Равные платежи: {n(S)} руб., {r}%, {N} г., {"всего" if kind == "annuity_total" else "платёж"}')
    if kind in ('diff_total', 'diff_first', 'diff_find_S'):
        N = rng.choice([2, 3, 4, 5, 6, 8, 10])
        r = rng.choice([1, 2, 3, 4, 5])                    # в месяц, как в банке ФИПИ
        S = F(rng.randint(2, 40) * N * rng.choice([10000, 100000]))
        d = S / N
        debts = [S - d * k for k in range(N)]                 # долг на начало каждого года (до процентов)
        pays = [D * r / 100 + d for D in debts]
        if any(p.denominator != 1 for p in pays) or S > 10 ** 9:
            return None
        total = sum(pays)
        head = (f'15-го января {year} года планируется взять кредит в банке на {N} {plural(N, "месяц", "месяца", "месяцев")}. '
                f'Условия его возврата таковы:<br>— 1-го числа каждого месяца долг возрастает на {r}% по сравнению с концом '
                f'предыдущего месяца;<br>— со 2-го по 14-е число каждого месяца необходимо выплатить часть долга;<br>— 15-го '
                f'числа каждого месяца долг должен быть на одну и ту же сумму меньше долга на 15-е число предыдущего месяца.')
        if kind == 'diff_total':
            text = f'{head}<br>Сумма кредита — {rub(S)}. Сколько рублей нужно выплатить банку за весь срок кредитования?'
            res = total
        elif kind == 'diff_first':
            text = f'{head}<br>Сумма кредита — {rub(S)}. Найдите размер первого платежа (в рублях).'
            res = pays[0]
        else:
            text = f'{head}<br>Известно, что общая сумма выплат составила {rub(total)}. Какую сумму планируется взять в кредит? Ответ дайте в рублях.'
            res = S
        sol = (f'Долг каждый месяц уменьшается на $\\frac{{S}}{{{N}}}$. Проценты начисляются на долги $S, \\frac{{{N - 1}}}{{{N}}}S, \\ldots, '
               f'\\frac{{1}}{{{N}}}S$, их сумма $\\frac{{{N + 1}}}{{2}}S$. Всего выплат: $S + {n(F(r, 100))} \\cdot \\frac{{{N + 1}}}{{2}}S = '
               f'{n(1 + F(r, 100) * F(N + 1, 2))}S$.')
        sol += {'diff_total': f' При $S = {n(S)}$ это ${n(total)}$ руб.',
                'diff_first': f' Первый платёж — проценты на весь долг плюс его доля: ${n(S)} \\cdot {n(F(r, 100))} + \\frac{{{n(S)}}}{{{N}}} = {n(pays[0])}$ руб.',
                'diff_find_S': f' ${n(1 + F(r, 100) * F(N + 1, 2))}S = {n(total)}$, $S = {n(S)}$ руб.'}[kind]
        if kind == 'diff_first':
            sol = f'В первый месяц проценты начисляются на весь долг, а долг уменьшается на $\\frac{{S}}{{{N}}}$: ' + sol.split('Первый платёж — ')[1]
        return ({'kind': kind, 'S': str(S), 'r': r, 'pays': [str(p) for p in pays], 'ask': {'diff_total': 'total', 'diff_first': 'first', 'diff_find_S': 'S'}[kind]},
                res, text, sol, f'Равномерный долг: {n(S)} руб., {r}%, {N} мес., ' + {'diff_total': 'всего', 'diff_first': 'первый платёж', 'diff_find_S': 'сумма кредита'}[kind])
    if kind == 'deposit':
        r = rng.choice([10, 20, 25, 50])
        S = rng.randint(1, 50) * 10000
        add = rng.randint(1, 20) * 10000
        N = rng.choice([2, 3])
        bal = F(S)
        for k in range(N):
            bal = bal * (100 + r) / 100
            if k < N - 1:
                bal += add
        if bal.denominator != 1:
            return None
        text = (f'Вкладчик положил в банк {rub(S)} под {r}% годовых: в конце каждого года банк увеличивает сумму на счёте на {r}%. '
                f'В начале второго{" и третьего" if N == 3 else ""} года вкладчик пополнял вклад на {rub(add)}. Какая сумма будет на '
                f'счёте через {YEARS[N]}? Ответ дайте в рублях.')
        q = n(F(100 + r, 100))
        sol = (f'Через год: ${S} \\cdot {q} = {n(S * F(100 + r, 100))}$. ' + ('Дальше каждый год: прибавляем пополнение и умножаем на '
               f'${q}$. ') + f'Итого через {YEARS[N]}: ${n(bal)}$ руб.')
        return {'kind': kind, 'S': S, 'r': r, 'add': add, 'N': N}, bal, text, sol, f'Вклад: {S} руб., {r}%, +{add}, {N} г.'
    # two_pay: кредит на 2 года, платежи x1 и x2 заданы → сумма кредита
    r = rng.choice([10, 20, 25, 50])
    q = F(100 + r, 100)
    x1 = rng.randint(2, 60) * 10000
    x2 = rng.randint(2, 60) * 10000
    S = (x1 + x2 / q) / q
    if S.denominator != 1:
        return None
    text = (f'В июле {year} года планируется взять кредит в банке на два года. ' + RULE.format(r=r)
            + f'<br>Известно, что первый платёж составил {rub(x1)}, второй — {rub(x2)}, и после второго платежа кредит был '
              f'полностью погашен. Какую сумму взяли в кредит? Ответ дайте в рублях.')
    sol = (f'После первого года долг $S \\cdot {n(q)} - {x1}$, после второго $(S \\cdot {n(q)} - {x1}) \\cdot {n(q)} - {x2} = 0$. '
           f'Отсюда $S = \\frac{{{x1} + \\frac{{{x2}}}{{{n(q)}}}}}{{{n(q)}}} = {n(S)}$ руб.')
    return {'kind': kind, 'S': str(S), 'r': r, 'pays': [x1, x2], 'ask': 'S'}, S, text, sol, f'Два платежа: {x1} и {x2}, {r}%'


def main():
    rng = random.Random(SEED)
    out, titles = [], set()
    for k, (level, kind) in enumerate(PLAN, 1):
        for _ in range(50000):
            r = make(rng, kind)
            if r is None:
                continue
            sp, x, text, sol, title = r
            if title in titles or F(x).denominator != 1 or x <= 0:
                continue
            titles.add(title)
            break
        else:
            raise SystemExit(f'№13, {kind}: не удалось подобрать задачу')
        out.append(item(13, k, level, TOPIC, title, text, sol, ans(x), sp))
    emit(out)


if __name__ == '__main__':
    main()
