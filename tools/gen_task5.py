#!/usr/bin/env python3
"""Генератор задач ЕГЭ №5 (анализ алгоритма, строящего число R по числу N) для банка stackly.

    python3 tools/gen_task5.py > /tmp/task5.json      # 100 задач: 70 базовых, 20 средних, 10 сложных

Каждая задача описывается правилом (spec). По нему строятся текст условия, пример «N → R» и решение на Python.
Ответ ищется перебором N; поиск повторяется на вчетверо большем диапазоне, и задача остаётся,
только если ответ не изменился (значит, диапазона хватает). Решение из задачи запускается и должно
вывести ответ. Spec сохраняется в задаче как HTML-комментарий — по нему тест tests/test_bank_task5.py
независимо пересчитывает ответ и пример. Генерация детерминирована (seed).
"""
import json, random, subprocess, sys

SEED = 20261006
SUB = str.maketrans('0123456789', '₀₁₂₃₄₅₆₇₈₉')


def to_base(n, b):
    s = ''
    while n:
        s = '0123456789'[n % b] + s
        n //= b
    return s or '0'


# ------------------------------------------------------------------ правила: R(n) по spec
def R(sp, n):
    f = sp['f']
    if f in ('par', 'ones'):
        s = to_base(n, 2)
        key = n % 2 if f == 'par' else s.count('1') % 2
        l, r = sp['rules'][key]
        return int(l + s + r, 2)
    if f == 'sumbit':
        s = to_base(n, 2)
        for _ in range(sp['k']):
            s += str(s.count('1') % 2)
        return int(s, 2)
    if f == 'mod':
        b, m, k, c = sp['b'], sp['m'], sp['k'], sp['c']
        s = to_base(n, b)
        s = s + s[-k:] if n % m == 0 else s + to_base((n % m) * c, b)
        return int(s, b)
    if f == 'inv':
        s = to_base(n, 2)
        cond = {'even': n % 2 == 0, 'odd': n % 2 == 1, 'ones_odd': s.count('1') % 2 == 1, 'always': True}[sp['when']]
        if cond:
            s = ''.join('1' if c == '0' else '0' for c in s).lstrip('0') or '0'
        l, r = sp['add']
        return int(l + s + r, 2)
    if f == 'digits':
        d = [int(c) for c in str(n)]
        op = (lambda a, b: a + b) if sp['op'] == 'sum' else (lambda a, b: a * b)
        pairs = [(0, 1), (1, 2)] if sp['len'] == 3 else [(0, 1), (2, 3)]
        v = sorted(op(d[i], d[j]) for i, j in pairs)
        if sp['order'] == 'desc':
            v = v[::-1]
        return int(''.join(map(str, v)))
    raise ValueError(f)


def digits_clean(sp, K):
    """Результат однозначно читается: ни у одного подходящего N записанные числа не начинаются с нуля
    (иначе «0» и «12» превращаются в 12 и путаются с «1» и «2»)."""
    op = (lambda a, b: a + b) if sp['op'] == 'sum' else (lambda a, b: a * b)
    pairs = [(0, 1), (1, 2)] if sp['len'] == 3 else [(0, 1), (2, 3)]
    for n in domain(sp, 0):
        if R(sp, n) != K:
            continue
        d = [int(c) for c in str(n)]
        v = sorted(op(d[i], d[j]) for i, j in pairs)
        if 0 in v:
            return False
    return True


def domain(sp, hi):
    if sp['f'] == 'digits':
        lo = 10 ** (sp['len'] - 1)
        return range(lo, 10 ** sp['len'])
    return range(1, hi)


def answer(sp, q, hi):
    xs = [(n, R(sp, n)) for n in domain(sp, hi)]
    t, K = q['t'], q.get('K')
    sel = {
        'minR>': lambda: min((r for n, r in xs if r > K), default=None),
        'minR>=': lambda: min((r for n, r in xs if r >= K), default=None),
        'maxR<': lambda: max((r for n, r in xs if r < K), default=None),
        'minN:R>': lambda: min((n for n, r in xs if r > K), default=None),
        'minN:R>=': lambda: min((n for n, r in xs if r >= K), default=None),
        'maxN:R<': lambda: max((n for n, r in xs if r < K), default=None),
        'maxN:R<=': lambda: max((n for n, r in xs if r <= K), default=None),
        'countR': lambda: len({r for n, r in xs if q['a'] <= r <= q['b']}),
        'countN': lambda: sum(q['a'] <= r <= q['b'] for n, r in xs),
        'maxN:R=': lambda: max((n for n, r in xs if r == K), default=None),
        'minN:R=': lambda: min((n for n, r in xs if r == K), default=None),
        'countN:R=': lambda: sum(r == K for n, r in xs),
    }[t]
    return sel()


# ------------------------------------------------------------------ текст
def side(l, r):
    """«слева дописывается 1, а справа — 0»"""
    p = []
    if l:
        p.append(f'слева дописывается <code>{l}</code>')
    if r:
        p.append(f'справа дописывается <code>{r}</code>' if not l else f'справа — <code>{r}</code>')
    return ', а '.join(p) if len(p) == 2 else p[0]


def steps(sp):
    f = sp['f']
    if f in ('par', 'ones'):
        cond = ('Если число N чётное' if f == 'par' else 'Если в двоичной записи числа N чётное количество единиц', 'если нечётное')
        (l0, r0), (l1, r1) = sp['rules'][0], sp['rules'][1]
        return ['Строится двоичная запись числа N.',
                f'{cond[0]}, то к этой записи {side(l0, r0)}; {cond[1]} — {side(l1, r1)}.',
                'Полученная таким образом запись является двоичной записью искомого числа R.']
    if f == 'sumbit':
        st = ['Строится двоичная запись числа N.',
              'К этой записи дописывается справа ещё один разряд: складываются все цифры двоичной записи, '
              'и остаток от деления суммы на 2 дописывается в конец записи.']
        if sp['k'] == 2:
            st.append('Над полученной записью производятся те же действия — справа дописывается остаток от деления суммы её цифр на 2.')
        elif sp['k'] == 3:
            st.append('Над полученной записью те же действия выполняются ещё два раза.')
        st.append('Полученная таким образом запись является двоичной записью искомого числа R.')
        return st
    if f == 'mod':
        b, m, k, c = sp['b'], sp['m'], sp['k'], sp['c']
        name = {2: 'двоичная', 3: 'троичная', 4: 'четверичная', 5: 'пятеричная', 6: 'шестеричная', 8: 'восьмеричная'}[b]
        gen = {2: 'двоичную', 3: 'троичную', 4: 'четверичную', 5: 'пятеричную', 6: 'шестеричную', 8: 'восьмеричную'}[b]
        last = {1: 'её последняя цифра', 2: 'две её последние цифры', 3: 'три её последние цифры'}[k]
        return [f'Строится {name} запись числа N.',
                f'Если число N делится на {m}, то к этой записи справа {"дописывается" if k == 1 else "дописываются"} {last}; '
                f'иначе остаток от деления N на {m} умножается на {c}, переводится в {gen} запись и дописывается в конец.',
                f'Полученная таким образом запись является {name.replace("ая", "ой")} записью искомого числа R.']
    if f == 'inv':
        when = {'even': 'Если число N чётное, то', 'odd': 'Если число N нечётное, то',
                'ones_odd': 'Если в двоичной записи числа N нечётное количество единиц, то', 'always': ''}[sp['when']]
        inv = 'все цифры двоичной записи заменяются на противоположные (0 на 1, 1 на 0), незначащие нули отбрасываются'
        st = ['Строится двоичная запись числа N.', (f'{when} {inv}.' if when else inv[0].upper() + inv[1:] + '.').strip()]
        l, r = sp['add']
        if l or r:
            st.append(f'К полученной записи {side(l, r)}.')
        st.append('Полученная таким образом запись является двоичной записью искомого числа R.')
        return st
    if f == 'digits':
        nm = 'трёхзначное' if sp['len'] == 3 else 'четырёхзначное'
        op = 'Складываются' if sp['op'] == 'sum' else 'Перемножаются'
        pairs = 'первая и вторая, а также вторая и третья цифры' if sp['len'] == 3 else 'первая и вторая, а также третья и четвёртая цифры'
        what = 'суммы' if sp['op'] == 'sum' else 'произведения'
        order = 'неубывания' if sp['order'] == 'asc' else 'невозрастания'
        return [f'{op} {pairs} числа.', f'Полученные два числа ({what}) записываются друг за другом в порядке {order} без разделителей.']


def example(sp, rng):
    if sp['f'] == 'digits':
        n = rng.randrange(10 ** (sp['len'] - 1), 10 ** sp['len'])
        return n, f'Например, для числа N = {n} результат будет R = {R(sp, n)}.'
    n = rng.randint(4, 13)
    r = R(sp, n)
    b = sp.get('b', 2)
    if b == 10:
        return n, f'Например, для N = {n} получаем R = {r}.'
    return n, (f'Например, для исходного числа N = {n} = {to_base(n, b)}{str(b).translate(SUB)} '
               f'результатом является число {to_base(r, b)}{str(b).translate(SUB)}, то есть R = {r}.')


def question(q, sp):
    t, K, A, B = q['t'], q.get('K'), q.get('a'), q.get('b')
    if sp['f'] == 'digits':
        return {'maxN:R=': f'Укажите <b>наибольшее</b> число N, в результате обработки которого автомат выдаст число <b>{K}</b>.',
                'minN:R=': f'Укажите <b>наименьшее</b> число N, в результате обработки которого автомат выдаст число <b>{K}</b>.',
                'countN:R=': f'Сколько существует чисел N, в результате обработки которых автомат выдаст число <b>{K}</b>?'}[t]
    dec = ' В ответе запишите это число в десятичной системе счисления.'
    return {
        'minR>': f'Укажите <b>минимальное число R</b>, большее {K}, которое может быть получено с помощью описанного алгоритма.' + dec,
        'minR>=': f'Укажите <b>минимальное число R</b>, не меньшее {K}, которое может быть получено с помощью описанного алгоритма.' + dec,
        'maxR<': f'Укажите <b>максимальное число R</b>, меньшее {K}, которое может быть получено с помощью описанного алгоритма.' + dec,
        'minN:R>': f'Укажите <b>минимальное число N</b>, после обработки которого с помощью этого алгоритма получается число R, большее {K}.',
        'minN:R>=': f'Укажите <b>минимальное число N</b>, после обработки которого с помощью этого алгоритма получается число R, не меньшее {K}.',
        'maxN:R<': f'Укажите <b>максимальное число N</b>, после обработки которого с помощью этого алгоритма получается число R, меньшее {K}.',
        'maxN:R<=': f'Укажите <b>максимальное число N</b>, после обработки которого с помощью этого алгоритма получается число R, не большее {K}.',
        'countR': f'Сколько различных чисел R, принадлежащих отрезку [{A}; {B}], могут быть получены с помощью этого алгоритма?',
        'countN': f'Для скольких чисел N результат работы алгоритма R принадлежит отрезку [{A}; {B}]?',
    }[t]


# ------------------------------------------------------------------ решение на Python
def code_R(sp):
    f = sp['f']
    if f in ('par', 'ones'):
        (l0, r0), (l1, r1) = sp['rules'][0], sp['rules'][1]
        cond = 'n % 2 == 0' if f == 'par' else "s.count('1') % 2 == 0"
        return ("def R(n):\n    s = bin(n)[2:]\n"
                f"    if {cond}:\n        s = '{l0}' + s + '{r0}'\n    else:\n        s = '{l1}' + s + '{r1}'\n"
                "    return int(s, 2)\n").replace("'' + ", '').replace(" + ''", '')
    if f == 'sumbit':
        return ("def R(n):\n    s = bin(n)[2:]\n"
                f"    for _ in range({sp['k']}):\n        s += str(s.count('1') % 2)\n    return int(s, 2)\n")
    if f == 'mod':
        b, m, k, c = sp['b'], sp['m'], sp['k'], sp['c']
        conv = "def to_base(n, b):\n    s = ''\n    while n > 0:\n        s = str(n % b) + s\n        n //= b\n    return s\n\n" if b != 2 else ''
        tb = (lambda x: f'bin({x})[2:]') if b == 2 else (lambda x: f'to_base({x}, {b})')
        return (conv + f"def R(n):\n    s = {tb('n')}\n"
                f"    if n % {m} == 0:\n        s = s + s[-{k}:]\n    else:\n        s = s + {tb(f'(n % {m}) * {c}')}\n"
                f"    return int(s, {b})\n")
    if f == 'inv':
        cond = {'even': 'n % 2 == 0', 'odd': 'n % 2 == 1', 'ones_odd': "s.count('1') % 2 == 1", 'always': 'True'}[sp['when']]
        l, r = sp['add']
        body = "    s = s.replace('0', '*').replace('1', '0').replace('*', '1').lstrip('0') or '0'\n"
        core = ("def R(n):\n    s = bin(n)[2:]\n" +
                (f"    if {cond}:\n    " + body if sp['when'] != 'always' else body) +
                (f"    s = '{l}' + s + '{r}'\n".replace("'' + ", '').replace(" + ''", '') if (l or r) else '') +
                "    return int(s, 2)\n")
        return core
    if f == 'digits':
        op = '+' if sp['op'] == 'sum' else '*'
        pairs = '[d[0] {0} d[1], d[1] {0} d[2]]' if sp['len'] == 3 else '[d[0] {0} d[1], d[2] {0} d[3]]'
        return ("def R(n):\n    d = [int(c) for c in str(n)]\n"
                f"    v = sorted({pairs.format(op)}{', reverse=True' if sp['order'] == 'desc' else ''})\n"
                "    return int(''.join(map(str, v)))\n")


def code_q(sp, q, hi):
    rng = f"range({10 ** (sp['len'] - 1)}, {10 ** sp['len']})" if sp['f'] == 'digits' else f'range(1, {hi})'
    t, K, A, B = q['t'], q.get('K'), q.get('a'), q.get('b')
    return {
        'minR>': f'print(min(R(n) for n in {rng} if R(n) > {K}))',
        'minR>=': f'print(min(R(n) for n in {rng} if R(n) >= {K}))',
        'maxR<': f'print(max(R(n) for n in {rng} if R(n) < {K}))',
        'minN:R>': f'print(min(n for n in {rng} if R(n) > {K}))',
        'minN:R>=': f'print(min(n for n in {rng} if R(n) >= {K}))',
        'maxN:R<': f'print(max(n for n in {rng} if R(n) < {K}))',
        'maxN:R<=': f'print(max(n for n in {rng} if R(n) <= {K}))',
        'countR': f'print(len({{R(n) for n in {rng} if {A} <= R(n) <= {B}}}))',
        'countN': f'print(sum({A} <= R(n) <= {B} for n in {rng}))',
        'maxN:R=': f'print(max(n for n in {rng} if R(n) == {K}))',
        'minN:R=': f'print(min(n for n in {rng} if R(n) == {K}))',
        'countN:R=': f'print(sum(R(n) == {K} for n in {rng}))',
    }[t]


# ------------------------------------------------------------------ случайные правила и вопросы
BITS = ['0', '1', '00', '01', '10', '11']


def rand_rules(rng):
    while True:
        a = (rng.choice(['', '', '1', '11', '10']), rng.choice(BITS + ['']))
        b = (rng.choice(['', '', '1', '11', '10']), rng.choice(BITS + ['']))
        if a != b and (a[0] or a[1]) and (b[0] or b[1]):
            return [a, b]


def rand_spec(rng, fam):
    if fam in ('par', 'ones'):
        return {'f': fam, 'rules': rand_rules(rng)}
    if fam == 'sumbit':
        return {'f': 'sumbit', 'k': rng.choice([2, 2, 1, 3])}
    if fam == 'mod2':
        return {'f': 'mod', 'b': 2, 'm': rng.choice([3, 4, 5]), 'k': rng.choice([2, 3]), 'c': rng.choice([2, 3, 5, 7])}
    if fam == 'modb':
        b = rng.choice([3, 3, 4, 5, 6])
        return {'f': 'mod', 'b': b, 'm': rng.choice([b, b, 4 if b != 4 else 3]), 'k': rng.choice([1, 2]), 'c': rng.choice([2, 3, 4, 5])}
    if fam == 'inv':
        return {'f': 'inv', 'when': rng.choice(['even', 'odd', 'ones_odd', 'always']),
                'add': (rng.choice(['', '1', '10', '11']), rng.choice(['0', '1', '01', '10', '']))}
    if fam == 'digits':
        return {'f': 'digits', 'len': rng.choice([3, 3, 4]), 'op': rng.choice(['sum', 'sum', 'mul']), 'order': rng.choice(['asc', 'desc'])}


def rand_q(rng, t, sp):
    if t in ('countR', 'countN'):
        a = rng.randint(50, 400) * rng.choice([1, 2, 5])
        return {'t': t, 'a': a, 'b': a + rng.randint(80, 900)}
    if t.endswith('R='):
        n = rng.randrange(10 ** (sp['len'] - 1), 10 ** sp['len'])
        return {'t': t, 'K': R(sp, n)}
    return {'t': t, 'K': rng.randint(40, 2000) if rng.random() < .6 else rng.randint(100, 30000)}


HI = 20000


def make(rng, level, fam, qtypes, need=None):
    for _ in range(5000):
        sp = rand_spec(rng, fam)
        q = rand_q(rng, rng.choice(qtypes), sp)
        a1 = answer(sp, q, HI)
        if a1 is None or (isinstance(a1, int) and a1 == 0 and not q['t'].startswith('count')):
            continue
        if sp['f'] != 'digits' and answer(sp, q, HI * 4) != a1:      # диапазона N не хватает
            continue
        if q['t'] in ('minR>', 'minR>=') and a1 in (q['K'] + 1, q['K']):  # слишком просто: подходит K+1
            continue
        if q['t'].startswith('count') and not 3 <= a1 <= 400:
            continue
        if q['t'] == 'countN:R=' and a1 < 2:
            continue
        if sp['f'] == 'digits' and q['t'].endswith('R=') and not digits_clean(sp, q['K']):
            continue
        if need and not need(sp, q, a1):
            continue
        return sp, q, a1
    raise RuntimeError(f'не удалось собрать {fam} {qtypes}')


FAM_TITLE = {'par': 'Чётность N', 'ones': 'Чётность числа единиц', 'sumbit': 'Бит чётности', 'mod': 'Остаток от деления',
             'inv': 'Инверсия разрядов', 'digits': 'Цифры числа'}
Q_TITLE = {'minR>': 'наименьшее R > {K}', 'minR>=': 'наименьшее R ≥ {K}', 'maxR<': 'наибольшее R < {K}',
           'minN:R>': 'наименьшее N при R > {K}', 'minN:R>=': 'наименьшее N при R ≥ {K}', 'maxN:R<': 'наибольшее N при R < {K}',
           'maxN:R<=': 'наибольшее N при R ≤ {K}', 'countR': 'сколько R в [{a}; {b}]', 'countN': 'сколько N дают R в [{a}; {b}]',
           'maxN:R=': 'наибольшее N, дающее {K}', 'minN:R=': 'наименьшее N, дающее {K}', 'countN:R=': 'сколько N дают {K}'}

PLAN = (
    # базовый: двоичная запись, правило по чётности, бит чётности; классические вопросы
    [('Б', 'par', ['minR>', 'minR>=', 'minN:R>', 'minN:R>='])] * 22 +
    [('Б', 'ones', ['minR>', 'minN:R>', 'minN:R>='])] * 14 +
    [('Б', 'sumbit', ['minR>', 'minR>=', 'minN:R>'])] * 12 +
    [('Б', 'mod2', ['minR>', 'minN:R>='])] * 10 +
    [('Б', 'digits', ['maxN:R=', 'minN:R='])] * 12 +
    # средний: другие системы счисления, инверсия, вопросы «наибольшее N»
    [('П', 'modb', ['minR>', 'minN:R>', 'maxN:R<'])] * 7 +
    [('П', 'inv', ['minR>', 'minN:R>', 'maxR<'])] * 5 +
    [('П', 'par', ['maxN:R<', 'maxN:R<=', 'maxR<'])] * 4 +
    [('П', 'digits', ['countN:R='])] * 4 +
    # сложный: подсчёт различных результатов на отрезке, инверсия с «наибольшим N»
    [('В', 'par', ['countR'])] * 2 + [('В', 'ones', ['countR'])] * 2 + [('В', 'modb', ['countR', 'countN'])] * 3 +
    [('В', 'inv', ['maxN:R<', 'countR'])] * 3
)


def note(sp, q):
    if sp['f'] == 'digits':
        return ('Перебираем все числа нужной разрядности, применяем к каждому правило и отбираем те, что дают нужный результат. '
                'Вручную: разложите результат на два числа и подберите цифры — следите за порядком записи.')
    t = q['t']
    tip = 'Напишите функцию R(n), проверьте её на примере из условия и переберите N.'
    if t.startswith('max') and sp['f'] == 'inv':
        tip += ' Инверсия может уменьшать число, поэтому проверьте, что диапазон перебора достаточно велик: увеличьте его и убедитесь, что ответ не изменился.'
    elif t.startswith('count'):
        tip += ' Разные N могут дать одинаковое R — для подсчёта различных R собирайте их во множество.' if t == 'countR' else ''
    else:
        tip += ' Так как R не меньше N, достаточно перебирать N до границы из условия с запасом.'
    return tip


def main():
    rng = random.Random(SEED)
    out, seen = [], set()
    for k, (level, fam, qtypes) in enumerate(PLAN, 1):
        pid = f'5-g{k:03d}'
        while True:
            sp, q, ans = make(rng, level, fam, qtypes)
            key = json.dumps([sp, q], sort_keys=True)
            title = f'{FAM_TITLE[sp["f"]]}: {Q_TITLE[q["t"]].format(**q)}'
            if key not in seen and title not in {p['title'] for p in out}:
                seen.add(key); break
        n0, ex = example(sp, rng)
        if sp['f'] == 'digits':
            intro = (f'Автомат получает на вход {"трёхзначное" if sp["len"] == 3 else "четырёхзначное"} натуральное число N '
                     'и строит по нему новое число R следующим образом.')
        else:
            intro = 'На вход алгоритма подаётся натуральное число N. Алгоритм строит по нему новое число R следующим образом.'
        text = (f'{intro}<ol>' + ''.join(f'<li>{s}</li>' for s in steps(sp)) + f'</ol>{ex} {question(q, sp)}')
        hi = HI if sp['f'] != 'digits' else None
        code = code_R(sp) + '\n' + code_q(sp, q, HI)
        spec = json.dumps({'spec': sp, 'q': q, 'ex': n0}, ensure_ascii=False, separators=(',', ':'))
        out.append({'id': pid, 'task': 5, 'level': level, 'title': title, 'text': text,
                    'extra': f'<!--spec:{spec}-->', 'code': code, 'answer': str(ans), 'data': '', 'dname': '',
                    'note': note(sp, q)})
    for p in out:
        r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=300)
        if r.stdout.strip() != p['answer']:
            raise SystemExit(f"{p['id']}: решение даёт «{r.stdout.strip()}», ответ «{p['answer']}»\n{r.stderr}\n{p['code']}")
    stat = {}
    for p in out:
        stat[p['level']] = stat.get(p['level'], 0) + 1
    print(json.dumps(stat, ensure_ascii=False), file=sys.stderr)
    json.dump(out, sys.stdout, ensure_ascii=False)


if __name__ == '__main__':
    main()
