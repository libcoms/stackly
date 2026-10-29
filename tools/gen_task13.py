#!/usr/bin/env python3
"""Генератор задач ЕГЭ №13 (анализ хода исполнения алгоритма, формат 2027 года) для банка stackly.

    python3 tools/gen_task13.py > /tmp/task13.json      # 50 задач: 20 базовых, 20 средних, 10 сложных

Исполнитель с двумя-тремя командами преобразует число; нужно найти количество программ из A в B, в том числе
с обязательными и запретными числами в траектории, с уменьшающими командами, с командой «Поменяй местами» из
демоверсии 2027 (меняет две младшие цифры, если цифра десятков меньше цифры единиц), а также количество различных
результатов программ заданной длины. Решение на Python запускается и должно вывести ответ. Описание задачи хранится
комментарием <!--spec:…--> — тест tests/test_bank_task13.py пересчитывает ответ динамикой вперёд.
Генерация детерминирована (seed).
"""
import json, os, random, subprocess, sys
from functools import lru_cache

SEED = 20271013
# команда: (вид, параметр). add — прибавить, mul — умножить, sub — вычесть, div — разделить нацело, swap — поменять
CMD_TEXT = {'add': 'Прибавь {}', 'mul': 'Умножь на {}', 'sub': 'Вычти {}', 'div': 'Раздели нацело на {}',
            'swap': 'Поменяй местами'}
PLAN = ([('Б', 'basic')] * 8 + [('Б', 'through')] * 6 + [('Б', 'avoid')] * 6
        + [('П', 'through_avoid')] * 6 + [('П', 'three')] * 6 + [('П', 'swap')] * 8
        + [('В', 'swap_through')] * 3 + [('В', 'decrease')] * 4 + [('В', 'results')] * 3)


def apply(c, x):
    k, a = c
    if k == 'add':
        return x + a
    if k == 'mul':
        return x * a
    if k == 'sub':
        return x - a
    if k == 'div':
        return x // a
    t, u = x // 10 % 10, x % 10
    return x - 10 * t - u + 10 * u + t if t < u else None


def count(cmds, a, b, need=(), ban=()):
    up = cmds[0][0] in ('add', 'mul', 'swap')

    @lru_cache(None)
    def f(x, y):
        if x in ban or ((x > y) if up else (x < y)):
            return 0
        if x == y:
            return 1
        s = 0
        for c in cmds:
            z = apply(c, x)
            if z is not None and z != x:
                s += f(z, y)
        return s
    pts = [a, *need, b]
    r = 1
    for u, v in zip(pts, pts[1:]):
        r *= f(u, v)
    return r


def results(cmds, a, n):
    cur = {a}
    for _ in range(n):
        cur = {y for x in cur for c in cmds for y in [apply(c, x)] if y is not None}
    return len(cur)


def make(rng, fam):
    if fam in ('basic', 'through', 'avoid', 'through_avoid', 'three'):
        cmds = [('add', 1), ('mul', 2)] if fam != 'three' else [('add', 1), ('add', rng.choice([2, 3])), ('mul', 2)]
        if rng.random() < 0.4 and fam != 'three':
            cmds = [('add', rng.choice([1, 2])), ('mul', rng.choice([2, 3]))]
        a = rng.randint(1, 6)
        b = rng.randint(24, 40) if fam != 'three' else rng.randint(18, 30)
        need, ban = (), ()
        if fam in ('through', 'through_avoid'):
            need = (rng.randint(a + 4, b - 6),)
        if fam in ('avoid', 'through_avoid'):
            lo = need[0] + 2 if need else a + 3
            ban = (rng.randint(lo, b - 2),)
        return {'fam': fam, 'cmds': cmds, 'a': a, 'b': b, 'need': list(need), 'ban': list(ban)}
    if fam in ('swap', 'swap_through'):
        cmds = [('add', 1), ('swap', 0)]
        a = rng.choice([100, 110, 120, 200, 210, 300, 1000, 1200]) + rng.randint(0, 4)
        b = a + rng.randint(25, 48)
        need = (rng.randint(a + 8, b - 10),) if fam == 'swap_through' else ()
        return {'fam': fam, 'cmds': cmds, 'a': a, 'b': b, 'need': list(need), 'ban': []}
    if fam == 'decrease':
        cmds = [('sub', rng.choice([1, 2])), ('div', rng.choice([2, 3]))]
        a = rng.randint(60, 120)
        b = rng.randint(2, 6)
        ban = (rng.randint(b + 3, 20),) if rng.random() < 0.5 else ()
        return {'fam': fam, 'cmds': cmds, 'a': a, 'b': b, 'need': [], 'ban': list(ban)}
    cmds = rng.choice([[('add', 1), ('mul', 2)], [('add', 2), ('mul', 3)], [('add', 1), ('add', 3), ('mul', 2)],
                       [('sub', 1), ('mul', 2)]])
    return {'fam': fam, 'cmds': cmds, 'a': rng.randint(1, 5), 'n': rng.randint(8, 12) if len(cmds) == 2 else rng.randint(6, 8)}


def answer(sp):
    cmds = [tuple(c) for c in sp['cmds']]
    if sp['fam'] == 'results':
        return results(cmds, sp['a'], sp['n'])
    return count(cmds, sp['a'], sp['b'], tuple(sp['need']), tuple(sp['ban']))


def letters(sp):
    return 'AB' if sp['fam'].startswith('swap') else None


def build(sp):
    cmds = [tuple(c) for c in sp['cmds']]
    names = letters(sp) or '123'
    lst = '<br>'.join(f'{names[i]}. {CMD_TEXT[k].format(a)}' for i, (k, a) in enumerate(cmds))
    head = (f'Исполнитель преобразует число на экране. У исполнителя есть {"две команды" if len(cmds) == 2 else "три команды"}, '
            f'которые обозначены {"латинскими буквами" if letters(sp) else "номерами"}:<br>{lst}<br>')
    desc = []
    for i, (k, a) in enumerate(cmds):
        if k == 'swap':
            desc.append(f'Команда {names[i]} применяется только к числу, у которого цифра в разряде десятков по значению '
                        'меньше цифры, стоящей в разряде единиц, и заменяет число на экране числом, в котором цифры двух '
                        'младших разрядов поменялись местами.')
        elif k == 'div':
            desc.append(f'Команда {names[i]} делит число на {a} нацело (остаток отбрасывается).')
    head += ' '.join(desc) + (' ' if desc else '') + 'Программа для исполнителя — это последовательность команд. '
    ex_start = sp['a'] if sp['fam'] != 'swap' else 13
    if sp['fam'].startswith('swap'):
        ex_start = 13
        prog = 'ABA'
    elif sp['fam'] == 'decrease':
        ex_start = 40
        prog = '121' if len(cmds) == 2 else '1231'
    else:
        ex_start = 3
        prog = '121' if len(cmds) == 2 else '1312'
    traj, x = [], ex_start
    for ch in prog:
        x = apply(cmds[names.index(ch)], x)
        traj.append(x)
    traj_txt = (f'Траектория вычислений программы — это последовательность результатов выполнения всех команд программы. '
                f'Например, для программы {prog} при исходном числе {ex_start} траектория состоит из чисел {", ".join(map(str, traj))}.')
    if sp['fam'] == 'results':
        q = (f'Сколько различных результатов можно получить из исходного числа {sp["a"]} в результате выполнения программ, '
             f'содержащих ровно {sp["n"]} команд?')
        text = head + q
        ttl = f'Различные результаты: {sp["a"]}, {sp["n"]} команд, ' + ', '.join(CMD_TEXT[k].format(a).lower() for k, a in cmds)
    else:
        cond = []
        if sp['need']:
            cond.append(f'траектория вычислений содержит число {sp["need"][0]}')
        if sp['ban']:
            cond.append(f'траектория вычислений не содержит числа {sp["ban"][0]}')
        q = (f'Сколько существует программ, для которых при исходном числе {sp["a"]} результатом является число {sp["b"]}'
             + (', и при этом ' + ' и '.join(cond) if cond else '') + '? ')
        text = head + q + traj_txt
        ttl = f'{sp["a"]} → {sp["b"]}: ' + ', '.join(CMD_TEXT[k].format(a).lower() for k, a in cmds)
        if sp['need']:
            ttl += f', через {sp["need"][0]}'
        if sp['ban']:
            ttl += f', без {sp["ban"][0]}'
    return text, code_for(sp, cmds), note_for(sp), ttl


def step_lines(cmds):
    out = []
    for k, a in cmds:
        if k == 'add':
            out.append(f'f(x + {a}, y)')
        elif k == 'mul':
            out.append(f'f(x * {a}, y)')
        elif k == 'sub':
            out.append(f'f(x - {a}, y)')
        elif k == 'div':
            out.append(f'f(x // {a}, y)')
    return out


def code_for(sp, cmds):
    if sp['fam'] == 'results':
        nxt = []
        for k, a in cmds:
            nxt.append({'add': f'x + {a}', 'mul': f'x * {a}', 'sub': f'x - {a}'}[k])
        return (f"cur = {{{sp['a']}}}\nfor _ in range({sp['n']}):\n    cur = {{y for x in cur for y in ({', '.join(nxt)})}}\n"
                f"print(len(cur))")
    up = cmds[0][0] in ('add', 'mul', 'swap')
    over = 'x > y' if up else 'x < y'
    ban = f" or x == {sp['ban'][0]}" if sp['ban'] else ''
    lines = ['from functools import lru_cache', '', '', '@lru_cache(None)', 'def f(x, y):',
             f'    if {over}{ban}:', '        return 0', '    if x == y:', '        return 1']
    if any(k == 'swap' for k, _ in cmds):
        lines += ['    s = f(x + 1, y)', '    t, u = x // 10 % 10, x % 10', '    if t < u:                       # команда B применима',
                  '        s += f(x - 10 * t - u + 10 * u + t, y)', '    return s']
    else:
        lines.append('    return ' + ' + '.join(step_lines(cmds)))
    pts = [sp['a'], *sp['need'], sp['b']]
    lines += ['', '', 'print(' + ' * '.join(f'f({u}, {v})' for u, v in zip(pts, pts[1:])) + ')']
    return '\n'.join(lines)


def note_for(sp):
    if sp['fam'] == 'results':
        return 'Множество текущих чисел после каждого шага: повторы склеиваются сами, поэтому считаются различные результаты.'
    if sp['fam'].startswith('swap'):
        return ('Команда B применяется не всегда: только если цифра десятков меньше цифры единиц. После неё число растёт, '
                'поэтому программы конечны и рекурсия с проверкой x > y работает.')
    if sp['fam'] == 'decrease':
        return 'Команды уменьшают число, поэтому «перелёт» — это x < y. Деление нацело: 7 // 2 = 3.'
    if sp['need']:
        return 'Обязательное число делит путь на два отрезка: количество программ — произведение подсчётов по отрезкам.'
    if sp['ban']:
        return 'Запретное число: если траектория в него попала, такая программа не считается — функция возвращает 0.'
    return 'Количество программ из x — сумма количеств по каждой команде; база: x == y → 1, перелёт → 0.'


def main():
    rng = random.Random(SEED)
    out, titles = [], set()
    for k, (level, fam) in enumerate(PLAN, 1):
        while True:
            sp = make(rng, fam)
            ans = answer(sp)
            if not (2 <= ans <= 10 ** 7):
                continue
            text, code, note, ttl = build(sp)
            if ttl not in titles:
                titles.add(ttl)
                break
        meta = json.dumps(sp, ensure_ascii=False, separators=(',', ':'))
        out.append({'id': f'13-g{k:03d}', 'task': 13, 'level': level, 'title': ttl, 'text': text,
                    'extra': f'<!--spec:{meta}-->', 'code': code, 'answer': str(ans), 'data': '', 'dname': '', 'note': note})
    for p in out:
        r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=120,
                           encoding='utf-8', env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        if r.stdout.strip() != p['answer']:
            raise SystemExit(f"{p['id']}: решение даёт «{r.stdout.strip()}», ответ «{p['answer']}»\n{r.stderr}\n{p['code']}")
    stat = {}
    for p in out:
        stat[p['level']] = stat.get(p['level'], 0) + 1
    print(json.dumps(stat, ensure_ascii=False), file=sys.stderr)
    sys.stdout.reconfigure(encoding='utf-8')
    json.dump(out, sys.stdout, ensure_ascii=False)


if __name__ == '__main__':
    main()
