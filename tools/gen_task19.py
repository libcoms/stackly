#!/usr/bin/env python3
"""Генератор задач ЕГЭ №19–21 (теория игр, кучи камней) для банка stackly.

    python3 tools/gen_task19.py > /tmp/task19.json   # 50 игр × 3 вопроса (19, 20, 21) = 150 задач

Каждая игра даёт три задачи — как в ЕГЭ, где номера 19, 20 и 21 спрашивают об одной и той же игре.
Ответы считаются функцией game() (число ходов до победы ходящего, со знаком), решение на Python
из каждой задачи запускается и должно вывести ответ. Описание игры сохраняется в задаче комментарием
<!--spec:…--> — тест tests/test_bank_task19.py решает игру другим способом (послойной классификацией
позиций W1, L1, W2, L2) и сверяет ответы. Генерация детерминирована (seed).
"""
import json, math, random, subprocess, sys
from functools import lru_cache

SEED = 20261010


# ------------------------------------------------------------------ правила
def moves(sp, pos):
    """Ходы из позиции: одна куча — число, две кучи — пара."""
    def one(s):
        out = []
        for kind, k in sp['moves']:
            if kind == 'add':
                out.append(s + k)
            elif kind == 'mul':
                out.append(s * k)
            elif kind == 'sub':
                out.append(s - k)
            elif kind == 'half':
                out.append((s + 1) // 2)        # остаётся на 1 больше, чем убрали, если камней нечётно
        return out
    if sp['heaps'] == 1:
        return one(pos)
    a, b = pos
    return [(x, b) for x in one(a)] + [(a, x) for x in one(b)]


def terminal(sp, pos):
    total = pos if sp['heaps'] == 1 else sum(pos)
    return total >= sp['T'] if sp['end'] == 'ge' else total <= sp['T']


def solver(sp):
    @lru_cache(None)
    def game(pos):
        if terminal(sp, pos):
            return 0
        res = [game(m) for m in moves(sp, pos)]
        lose = [r for r in res if r <= 0]
        return -max(lose) + 1 if lose else -max(res)
    return game


def start(sp, s):
    return s if sp['heaps'] == 1 else (sp['a0'], s)


def s_range(sp):
    return range(sp['smin'], sp['smax'] + 1)


# ------------------------------------------------------------------ ответы
def answers(sp):
    g = solver(sp)
    S = list(s_range(sp))
    far = min if sp['end'] == 'ge' else max          # «дальше всего от конца игры»
    unlucky = [s for s in S if any(not terminal(sp, m) and g(m) == 1 for m in moves(sp, start(sp, s)))]
    lose1 = [s for s in S if g(start(sp, s)) == -1]
    win2 = [s for s in S if g(start(sp, s)) == 2]
    lose2 = [s for s in S if g(start(sp, s)) == -2]
    return {'unlucky': unlucky, 'lose1': lose1, 'win2': win2, 'lose2': lose2, 'far': far.__name__}


# ------------------------------------------------------------------ текст
MOVE_TXT = {
    ('add', 1): 'добавить в кучу один камень', ('add', 2): 'добавить в кучу два камня', ('add', 3): 'добавить в кучу три камня',
    ('add', 4): 'добавить в кучу четыре камня', ('add', 5): 'добавить в кучу пять камней', ('add', 6): 'добавить в кучу шесть камней',
    ('mul', 2): 'увеличить количество камней в куче в два раза', ('mul', 3): 'увеличить количество камней в куче в три раза',
    ('mul', 4): 'увеличить количество камней в куче в четыре раза',
    ('sub', 1): 'убрать из кучи один камень', ('sub', 2): 'убрать из кучи два камня', ('sub', 3): 'убрать из кучи три камня',
    ('sub', 4): 'убрать из кучи четыре камня',
    ('sub', 5): 'убрать из кучи пять камней', ('sub', 6): 'убрать из кучи шесть камней',
    ('half', 2): 'уменьшить количество камней в куче в два раза (если камней нечётное число, остаётся на один камень больше, чем было убрано)',
}
MOVE_TXT2 = {k: v.replace('в кучу', 'в одну из куч').replace('в куче', 'в одной из куч').replace('из кучи', 'из одной из куч') for k, v in MOVE_TXT.items()}


def or_list(xs):
    return ', '.join(xs[:-1]) + ' или ' + xs[-1] if len(xs) > 1 else xs[0]


def intro(sp):
    mv = [f'<b>{(MOVE_TXT if sp["heaps"] == 1 else MOVE_TXT2)[m]}</b>' for m in map(tuple, sp['moves'])]
    if sp['heaps'] == 1:
        end = (f'Игра завершается, когда количество камней в куче становится не менее <b>{sp["T"]}</b>.' if sp['end'] == 'ge' else
               f'Игра завершается, когда количество камней в куче становится не более <b>{sp["T"]}</b>.')
        st = f'В начальный момент в куче было S камней, {sp["smin"]} ≤ S ≤ {sp["smax"]}.'
        head = 'Два игрока, Петя и Ваня, играют в следующую игру. Перед игроками лежит куча камней.'
    else:
        end = (f'Игра завершается, когда суммарное количество камней в кучах становится не менее <b>{sp["T"]}</b>.' if sp['end'] == 'ge' else
               f'Игра завершается, когда суммарное количество камней в кучах становится не более <b>{sp["T"]}</b>.')
        st = f'В начальный момент в первой куче было <b>{sp["a0"]}</b> камней, во второй — S камней, {sp["smin"]} ≤ S ≤ {sp["smax"]}.'
        head = 'Два игрока, Петя и Ваня, играют в следующую игру. Перед игроками лежат две кучи камней.'
    return (f'{head} Игроки ходят по очереди, первый ход делает Петя. За один ход игрок может {or_list(mv)}. '
            f'{"Для того чтобы делать ходы, у каждого игрока есть неограниченное количество камней. " if sp["end"] == "ge" else ""}'
            f'{end} Победителем считается игрок, сделавший последний ход, то есть первым получивший такую позицию. {st}')


def num_word(k):
    return {1: 'одно', 2: 'два', 3: 'три', 4: 'четыре'}[k]


def q19(sp, A):
    far = 'минимальное' if A['far'] == 'min' else 'максимальное'
    if sp['q19'] == 'unlucky':
        vals = A['unlucky']
        ans = (min if A['far'] == 'min' else max)(vals)
        return (f'Известно, что Ваня выиграл своим первым ходом после неудачного первого хода Пети. '
                f'Укажите {far} значение S, когда такая ситуация возможна.'), str(ans), 'unlucky'
    vals = A['lose1']
    if len(vals) == 1:
        return ('Укажите такое значение S, при котором Петя не может выиграть за один ход, '
                'но при любом ходе Пети Ваня может выиграть своим первым ходом.'), str(vals[0]), 'lose1'
    ans = (min if A['far'] == 'min' else max)(vals)
    return (f'Укажите {far} значение S, при котором Петя не может выиграть за один ход, '
            'но при любом ходе Пети Ваня может выиграть своим первым ходом.'), str(ans), 'lose1'


def q20(sp, A):
    v = sorted(A['win2'])
    cond = ('у Пети есть выигрышная стратегия, причём одновременно выполняются два условия:'
            '<br>— Петя не может выиграть за один ход;<br>— Петя может выиграть своим вторым ходом независимо от того, как будет ходить Ваня.<br>')
    if len(v) == 1:
        return f'Найдите такое значение S, при котором {cond}', str(v[0])
    if len(v) == 2:
        return f'Найдите два таких значения S, при которых {cond} Найденные значения запишите в ответе в порядке возрастания.', ' '.join(map(str, v))
    if len(v) == 3:
        return f'Найдите три таких значения S, при которых {cond} Найденные значения запишите в ответе в порядке возрастания.', ' '.join(map(str, v))
    pick = v[:2] if A['far'] == 'min' else v[-2:]
    w = 'наименьших' if A['far'] == 'min' else 'наибольших'
    return f'Найдите два {w} значения S, при которых {cond} Найденные значения запишите в ответе в порядке возрастания.', ' '.join(map(str, pick))


def q21(sp, A):
    v = A['lose2']
    far = 'минимальное' if A['far'] == 'min' else 'максимальное'
    ans = (min if A['far'] == 'min' else max)(v)
    txt = (f'Найдите {far} значение S, при котором одновременно выполняются два условия:'
           '<br>— у Вани есть выигрышная стратегия, позволяющая ему выиграть первым или вторым ходом при любой игре Пети;'
           '<br>— у Вани нет стратегии, которая позволит ему гарантированно выиграть первым ходом.')
    if len(v) == 1:
        txt = txt.replace(f'Найдите {far} значение S', 'Найдите значение S')
    return txt, str(ans)


# ------------------------------------------------------------------ код решения
def code(sp, task):
    T = sp['T']
    def mv1(x):
        out = []
        for kind, k in sp['moves']:
            out.append({'add': f'{x} + {k}', 'mul': f'{x} * {k}', 'sub': f'{x} - {k}', 'half': f'({x} + 1) // 2'}[kind])
        return out
    if sp['heaps'] == 1:
        mvs = ', '.join(mv1('s'))
        cond = f's >= {T}' if sp['end'] == 'ge' else f's <= {T}'
        head = ('from functools import lru_cache\n\n'
                'def moves(s):\n'
                f'    return [{mvs}]\n\n'
                '@lru_cache(None)\n'
                'def game(s):\n'
                '    """>0: ходящий выигрывает за столько своих ходов; <0: проигрывает; 0 — игра окончена"""\n'
                f'    if {cond}:\n        return 0\n'
                '    res = [game(m) for m in moves(s)]\n'
                '    lose = [r for r in res if r <= 0]          # ходы в проигрышную для соперника позицию\n'
                '    return -max(lose) + 1 if lose else -max(res)\n\n')
        st, mvs_of, term = 's', 'moves(s)', (f'm >= {T}' if sp['end'] == 'ge' else f'm <= {T}')
    else:
        ma = ', '.join(f'({x}, b)' for x in mv1('a'))
        mb = ', '.join(f'(a, {x})' for x in mv1('b'))
        cond = f'a + b >= {T}' if sp['end'] == 'ge' else f'a + b <= {T}'
        head = ('from functools import lru_cache\n\n'
                'def moves(a, b):\n'
                f'    return [{ma}, {mb}]\n\n'
                '@lru_cache(None)\n'
                'def game(a, b):\n'
                '    """>0: ходящий выигрывает за столько своих ходов; <0: проигрывает; 0 — игра окончена"""\n'
                f'    if {cond}:\n        return 0\n'
                '    res = [game(*m) for m in moves(a, b)]\n'
                '    lose = [r for r in res if r <= 0]          # ходы в проигрышную для соперника позицию\n'
                '    return -max(lose) + 1 if lose else -max(res)\n\n')
        st, mvs_of, term = f'{sp["a0"]}, s', f'moves({sp["a0"]}, s)', (f'sum(m) >= {T}' if sp['end'] == 'ge' else f'sum(m) <= {T}')
    rng = f'range({sp["smin"]}, {sp["smax"] + 1})'
    G = (lambda m: f'game(m)') if sp['heaps'] == 1 else (lambda m: 'game(*m)')
    agg = 'min' if sp['end'] == 'ge' else 'max'
    if task == 19:
        if sp['q19'] == 'unlucky':
            body = (f'# Петя сделал ход m (не закончив игру), и Ваня из m выигрывает одним ходом\n'
                    f'print({agg}(s for s in {rng} if any(not ({term}) and {G("m")} == 1 for m in {mvs_of})))')
        else:
            body = f'print({agg}(s for s in {rng} if game({st}) == -1))'
    elif task == 20:
        body = f'v = [s for s in {rng} if game({st}) == 2]\nprint(*{sp["pick20"]})'
    else:
        body = f'print({agg}(s for s in {rng} if game({st}) == -2))'
    return head + body


# ------------------------------------------------------------------ случайные игры
def rand_spec(rng, kind):
    if kind == 'up1':
        adds = sorted(rng.sample([1, 2, 3, 4, 5, 6], rng.choice([1, 1, 2])))
        mul = rng.choice([2, 2, 3])
        mv = [['add', a] for a in adds] + [['mul', mul]]
        T = rng.randint(20, 140)
        return {'heaps': 1, 'end': 'ge', 'moves': mv, 'T': T, 'smin': 1, 'smax': T - 1}
    if kind == 'up2':
        mv = [['add', rng.choice([1, 1, 2, 3])], ['mul', rng.choice([2, 2, 3])]]
        T = rng.randint(30, 120)
        a0 = rng.randint(3, 15)
        return {'heaps': 2, 'end': 'ge', 'moves': mv, 'T': T, 'a0': a0, 'smin': 1, 'smax': T - a0 - 1}
    if kind == 'down1':
        subs = sorted(rng.sample([1, 2, 3, 4], rng.choice([1, 2])))
        mv = [['sub', a] for a in subs] + ([['half', 2]] if rng.random() < .6 else [])
        if len(mv) < 2:
            mv.append(['sub', 5 if subs[-1] < 5 else 6])
        T = rng.randint(10, 40)
        return {'heaps': 1, 'end': 'le', 'moves': mv, 'T': T, 'smin': T + 1, 'smax': T + rng.randint(60, 160)}
    if kind == 'up1x':          # сложная: три вида добавления и умножение, большой порог
        adds = sorted(rng.sample([1, 2, 3, 4, 5], 2))
        mv = [['add', a] for a in adds] + [['mul', rng.choice([2, 3])]]
        T = rng.randint(150, 400)
        return {'heaps': 1, 'end': 'ge', 'moves': mv, 'T': T, 'smin': 1, 'smax': T - 1}
    if kind == 'up2x':          # сложная: две кучи, два вида добавления и умножение
        adds = sorted(rng.sample([1, 2, 3], 2))
        mv = [['add', a] for a in adds] + [['mul', rng.choice([2, 3])]]
        T = rng.randint(60, 150)
        a0 = rng.randint(4, 20)
        return {'heaps': 2, 'end': 'ge', 'moves': mv, 'T': T, 'a0': a0, 'smin': 1, 'smax': T - a0 - 1}


def make(rng, kind):
    for _ in range(5000):
        sp = rand_spec(rng, kind)
        if sp['smax'] - sp['smin'] < 8:
            continue
        A = answers(sp)
        if not A['unlucky'] or not A['win2'] or not A['lose2']:
            continue
        sp['q19'] = rng.choice(['unlucky', 'unlucky', 'lose1']) if A['lose1'] else 'unlucky'
        # ответ на краю диапазона S выглядит как обрезанный перебор — такие игры не берём
        edge = {sp['smin'], sp['smax']}
        far = min if A['far'] == 'min' else max
        if far(A[sp['q19']]) in edge or far(A['lose2']) in edge or set(A['win2']) & edge:
            continue
        v = sorted(A['win2'])
        if len(v) > 3:
            sp['pick20'] = 'v[:2]' if A['far'] == 'min' else 'v[-2:]'
        else:
            sp['pick20'] = 'v'
        return sp, A
    raise RuntimeError(kind)


PLAN = ['up1'] * 30 + ['down1'] * 5 + ['up2'] * 6 + ['down1'] * 4 + ['up1x'] * 2 + ['up2x'] * 3
LEVEL = ['Б'] * 35 + ['П'] * 10 + ['В'] * 5
# Как на экзамене: 19–21 — комплект, игра описана один раз в задании 19, а 20 и 21 ссылаются на неё.
# Сайт показывает условие игры в карточках 20 и 21 по ссылке на задачу 19 того же комплекта (id 19-gNN).
SET_REF = 'Для игры, описанной в задании 19, '
TITLE = {19: 'выигрыш Вани первым ходом', 20: 'выигрыш Пети вторым ходом', 21: 'стратегия Вани за 1–2 хода'}


def game_name(sp):
    mv = ', '.join({'add': f'+{k}', 'mul': f'×{k}', 'sub': f'−{k}', 'half': '÷2'}[m] for m, k in sp['moves'])
    if sp['heaps'] == 1:
        return f'Куча ({mv}; {"≥" if sp["end"] == "ge" else "≤"} {sp["T"]})'
    return f'Две кучи ({mv}; сумма ≥ {sp["T"]}, первая — {sp["a0"]})'


def main():
    rng = random.Random(SEED)
    out, seen = [], set()
    for k, (kind, level) in enumerate(zip(PLAN, LEVEL), 1):
        while True:
            sp, A = make(rng, kind)
            key = json.dumps(sp, sort_keys=True)
            if key not in seen and game_name(sp) not in {game_name(json.loads(x)) for x in seen}:
                seen.add(key); break
        base = intro(sp)
        t19, a19, _ = q19(sp, A)
        t20, a20 = q20(sp, A)
        t21, a21 = q21(sp, A)
        spec = json.dumps(sp, ensure_ascii=False, separators=(',', ':'))
        for task, qt, ans in ((19, t19, a19), (20, t20, a20), (21, t21, a21)):
            out.append({'id': f'{task}-g{k:02d}', 'task': task, 'level': level,
                        'title': f'{game_name(sp)}: {TITLE[task]}',
                        'text': f'{base}<br><br><b>Задание 19.</b> {qt}' if task == 19 else
                                f'<b>Задание {task}.</b> {SET_REF}{qt[0].lower()}{qt[1:]}',
                        'extra': f'<!--spec:{spec}-->', 'code': code(sp, task), 'answer': ans, 'data': '', 'dname': '',
                        'note': {19: 'Ваня выигрывает первым ходом из позиции m, если game(m) == 1. «Неудачный ход Пети» — '
                                     'хотя бы один ход Пети в такую позицию; «при любом ходе Пети» — game(S) == −1.',
                                 20: 'Петя выигрывает вторым ходом при любой игре Вани ровно тогда, когда game(S) == 2.',
                                 21: 'Ваня выигрывает первым или вторым ходом, но не гарантированно первым — это game(S) == −2.'}[task]})
    for p in out:
        r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=300)
        if r.stdout.strip() != p['answer']:
            raise SystemExit(f"{p['id']}: решение даёт «{r.stdout.strip()}», ответ «{p['answer']}»\n{r.stderr}\n{p['code']}")
    stat = {}
    for p in out:
        stat[(p['task'], p['level'])] = stat.get((p['task'], p['level']), 0) + 1
    print(stat, file=sys.stderr)
    json.dump(out, sys.stdout, ensure_ascii=False)


if __name__ == '__main__':
    main()
