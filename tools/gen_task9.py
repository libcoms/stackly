#!/usr/bin/env python3
"""Генератор задач ЕГЭ №9 (обработка строк электронной таблицы) для банка stackly.

    python3 tools/gen_task9.py > /tmp/task9.json      # 50 задач: 35 базовых, 10 средних, 5 сложных

У каждой задачи свой файл данных (300 строк чисел через табуляцию). Условия собираются из набора
проверок в духе ФИПИ; данные подбираются так, чтобы подходящих строк было заметное, но не подавляющее
число. Решение на Python из задачи запускается на её данных и должно вывести ответ. Описание условий
хранится в задаче комментарием <!--spec:…--> — тест tests/test_bank_task9.py проверяет ответы своей,
независимой реализацией условий. Генерация детерминирована (seed).
"""
import json, os, random, subprocess, sys, tempfile
from collections import Counter

SEED = 20261011
ROWS = 300
NUM = {4: 'четыре', 5: 'пять', 6: 'шесть', 7: 'семь'}

# ------------------------------------------------------------------ условия: проверка, текст, код
def rep_info(a):
    c = Counter(a)
    reps = [v for v, k in c.items() if k > 1]
    return c, reps


def cond_ok(name, a):
    c, reps = rep_info(a)
    s = sorted(a)
    uniq = [x for x in a if c[x] == 1]
    if name == 'pair1':
        return len(reps) == 1 and c[reps[0]] == 2
    if name == 'triple1':
        return len(reps) == 1 and c[reps[0]] == 3
    if name == 'two_pairs':
        return len(reps) == 2 and all(c[v] == 2 for v in reps)
    if name == 'distinct':
        return not reps
    if name == 'has_rep':
        return bool(reps)
    if name in ('mean_u_le_r', 'mean_u_gt_r'):
        if len(reps) != 1 or not uniq:
            return False
        m = sum(uniq) / len(uniq)
        return m <= reps[0] if name == 'mean_u_le_r' else m > reps[0]
    if name == 'max_lt_rest':
        return s[-1] < sum(s[:-1])
    if name == 'maxmin2_le_rest':
        return 2 * (s[0] + s[-1]) <= sum(s[1:-1])
    if name == 'sq':
        return (s[0] + s[-1]) ** 2 > sum(x * x for x in s[1:-1])
    if name == 'even_more':
        ev = sum(x % 2 == 0 for x in a)
        return ev > len(a) - ev
    if name == 'max_once':
        return c[s[-1]] == 1
    if name == 'max_rep':
        return c[s[-1]] > 1
    if name == 'mean_gt_med':
        n = len(s)
        med = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
        return sum(s) / n > med
    raise ValueError(name)


TXT = {
    'pair1': 'в строке есть <b>ровно одно</b> число, которое повторяется дважды, остальные числа различны',
    'triple1': 'в строке есть <b>ровно одно</b> число, которое повторяется трижды, остальные числа различны',
    'two_pairs': 'в строке есть <b>ровно два</b> различных числа, каждое из которых повторяется дважды, остальные числа различны',
    'distinct': 'все числа в строке <b>различны</b>',
    'has_rep': 'в строке есть хотя бы одно число, которое <b>повторяется</b>',
    'mean_u_le_r': 'среднее арифметическое неповторяющихся чисел строки <b>не больше</b> повторяющегося числа',
    'mean_u_gt_r': 'среднее арифметическое неповторяющихся чисел строки <b>больше</b> повторяющегося числа',
    'max_lt_rest': 'наибольшее число строки <b>меньше</b> суммы остальных её чисел',
    'maxmin2_le_rest': 'удвоенная сумма наибольшего и наименьшего чисел строки <b>не больше</b> суммы оставшихся чисел',
    'sq': 'квадрат суммы наибольшего и наименьшего чисел строки <b>больше</b> суммы квадратов оставшихся её чисел',
    'even_more': 'чётных чисел в строке <b>больше</b>, чем нечётных',
    'max_once': 'наибольшее число строки встречается в ней <b>ровно один раз</b>',
    'max_rep': 'наибольшее число строки <b>повторяется</b>',
    'mean_gt_med': 'среднее арифметическое чисел строки <b>больше</b> её медианы (для чётного количества чисел — среднего двух центральных)',
}

PY = {
    'pair1': "len(rep) == 1 and a.count(rep[0]) == 2",
    'triple1': "len(rep) == 1 and a.count(rep[0]) == 3",
    'two_pairs': "len(rep) == 2 and all(a.count(v) == 2 for v in rep)",
    'distinct': "len(set(a)) == len(a)",
    'has_rep': "len(set(a)) < len(a)",
    'mean_u_le_r': "len(rep) == 1 and len(uniq) > 0 and sum(uniq) / len(uniq) <= rep[0]",
    'mean_u_gt_r': "len(rep) == 1 and len(uniq) > 0 and sum(uniq) / len(uniq) > rep[0]",
    'max_lt_rest': "s[-1] < sum(s[:-1])",
    'maxmin2_le_rest': "2 * (s[0] + s[-1]) <= sum(s[1:-1])",
    'sq': "(s[0] + s[-1]) ** 2 > sum(x * x for x in s[1:-1])",
    'even_more': "sum(x % 2 == 0 for x in a) > sum(x % 2 == 1 for x in a)",
    'max_once': "a.count(s[-1]) == 1",
    'max_rep': "a.count(s[-1]) > 1",
    'mean_gt_med': "sum(s) / len(s) > (s[len(s) // 2] if len(s) % 2 else (s[len(s) // 2 - 1] + s[len(s) // 2]) / 2)",
}

# сочетания условий; первое — про повторы, дальше — числовые
COMBOS_B = [
    ('pair1', 'mean_u_le_r'), ('pair1', 'mean_u_gt_r'), ('triple1', 'mean_u_le_r'), ('distinct', 'max_lt_rest'),
    ('distinct', 'maxmin2_le_rest'), ('distinct', 'sq'), ('pair1', 'max_once'), ('has_rep', 'max_lt_rest'),
    ('distinct', 'even_more'), ('pair1', 'even_more'), ('has_rep', 'maxmin2_le_rest'), ('distinct', 'mean_gt_med'),
]
COMBOS_P = [
    ('pair1', 'mean_u_le_r', 'even_more'), ('distinct', 'sq', 'even_more'), ('two_pairs', 'max_lt_rest'),
    ('triple1', 'mean_u_gt_r', 'max_once'), ('pair1', 'max_rep', 'mean_gt_med'), ('distinct', 'maxmin2_le_rest', 'mean_gt_med'),
]


def row(rng, n, lo, hi, mix):
    kind = rng.choices(['pair', 'triple', 'two', 'free'], weights=mix)[0]
    if kind == 'pair' and n >= 3:
        base = rng.sample(range(lo, hi + 1), n - 1); base.append(base[0])
    elif kind == 'triple' and n >= 4:
        base = rng.sample(range(lo, hi + 1), n - 2); base += [base[0], base[0]]
    elif kind == 'two' and n >= 5:
        base = rng.sample(range(lo, hi + 1), n - 2); base += [base[0], base[1]]
    else:
        base = [rng.randint(lo, hi) for _ in range(n)]
    rng.shuffle(base)
    return base


def matches(conds, a):
    return all(cond_ok(c, a) for c in conds)


def answer(q, conds, data):
    hits = [(i, a) for i, a in enumerate(data, 1) if matches(conds, a)]
    if not hits:
        return None
    if q == 'count':
        return len(hits)
    if q == 'first':
        return hits[0][0]
    if q == 'last':
        return hits[-1][0]
    if q == 'maxsum':
        return max(sum(a) for _, a in hits)
    if q == 'minsum':
        return min(sum(a) for _, a in hits)


QTXT = {
    'count': 'Определите количество строк таблицы, содержащих числа, для которых выполнены {all} условия:',
    'first': 'Определите номер первой строки таблицы, для чисел которой выполнены {all} условия:',
    'last': 'Определите номер последней строки таблицы, для чисел которой выполнены {all} условия:',
    'maxsum': 'Среди строк, для чисел которых выполнены {all} условия, найдите наибольшую сумму чисел строки:',
    'minsum': 'Среди строк, для чисел которых выполнены {all} условия, найдите наименьшую сумму чисел строки:',
}
QPY = {
    'count': ('cnt = 0', '        cnt += 1', 'print(cnt)'),
    'first': ('ans = None', '        ans = i\n        break', 'print(ans)'),
    'last': ('ans = None', '        ans = i', 'print(ans)'),
    'maxsum': ('best = 0', '        best = max(best, sum(a))', 'print(best)'),
    'minsum': ('best = 10 ** 9', '        best = min(best, sum(a))', 'print(best)'),
}


def code_for(q, conds):
    init, hit, fin = QPY[q]
    need = set()
    for c in conds:
        need |= {'rep'} if any(w in PY[c] for w in ('rep',)) else set()
        need |= {'uniq'} if 'uniq' in PY[c] else set()
        need |= {'s'} if 's[' in PY[c] or 'sum(s)' in PY[c] or 'len(s)' in PY[c] else set()
    lines = [init, "for i, line in enumerate(open('9.txt'), 1):", '    a = list(map(int, line.split()))']
    if 's' in need:
        lines.append('    s = sorted(a)')
    if 'rep' in need or 'uniq' in need:
        lines.append('    rep = [x for x in set(a) if a.count(x) > 1]       # повторяющиеся значения')
    if 'uniq' in need:
        lines.append('    uniq = [x for x in a if a.count(x) == 1]          # неповторяющиеся числа')
    cond = ' and\n            '.join(f'({PY[c]})' for c in conds)
    lines.append(f'    if ({cond}):')
    lines.append(hit)
    lines.append(fin)
    return '\n'.join(lines)


def preview(data):
    n = len(data[0])
    cols = 'ABCDEFG'[:n]
    head = '<tr>' + ''.join(f'<th>{c}</th>' for c in cols) + '</tr>'
    rows = ''.join('<tr>' + ''.join(f'<td>{x}</td>' for x in r) + '</tr>' for r in data[:5])
    return f'<div class="tblwrap"><table class="db small">{head}{rows}</table></div><p class="muted" style="font-size:13px">Первые 5 строк из {len(data)}. Весь файл — кнопками «Показать» и «Скопировать».</p>'


PLAN = ([('Б', 'count', COMBOS_B)] * 30 + [('Б', 'first', COMBOS_B)] * 5 +
        [('П', 'count', COMBOS_P)] * 7 + [('П', 'last', COMBOS_P)] * 3 +
        [('В', 'maxsum', COMBOS_P)] * 3 + [('В', 'minsum', COMBOS_P)] * 2)

SHORT = {'pair1': 'одна пара', 'triple1': 'одна тройка', 'two_pairs': 'две пары', 'distinct': 'все различны', 'has_rep': 'есть повтор',
         'mean_u_le_r': 'среднее ≤ повтора', 'mean_u_gt_r': 'среднее > повтора', 'max_lt_rest': 'max < суммы остальных',
         'maxmin2_le_rest': '2(max+min) ≤ остальных', 'sq': '(max+min)² > Σ квадратов', 'even_more': 'чётных больше',
         'max_once': 'max один раз', 'max_rep': 'max повторяется', 'mean_gt_med': 'среднее > медианы'}
QSHORT = {'count': 'сколько строк', 'first': 'первая строка', 'last': 'последняя строка', 'maxsum': 'наибольшая сумма', 'minsum': 'наименьшая сумма'}


def make(rng, level, q, combos):
    for _ in range(4000):
        conds = list(rng.choice(combos))
        n = rng.choice([5, 6, 6, 7] if 'two_pairs' in conds or 'triple1' in conds else [4, 5, 6, 6, 7])
        lo, hi = rng.choice([(1, 100), (1, 99), (10, 99), (1, 150), (2, 80)])
        w_rep = .45 if conds[0] in ('pair1', 'has_rep') else .1
        mix = {'pair': w_rep, 'triple': .25 if 'triple1' in conds else .05, 'two': .3 if 'two_pairs' in conds else .05}
        mix['free'] = 1
        data = [row(rng, n, lo, hi, [mix['pair'], mix['triple'], mix['two'], mix['free']]) for _ in range(ROWS)]
        ans = answer(q, conds, data)
        if ans is None:
            continue
        hits = sum(matches(conds, a) for a in data)
        if q == 'count' and not 8 <= hits <= ROWS * .6:
            continue
        if q in ('first', 'last') and not 2 <= hits <= 60:
            continue
        if q == 'first' and ans < 10 or q == 'last' and ans > ROWS - 10:
            continue
        if q in ('maxsum', 'minsum') and hits < 5:
            continue
        return n, conds, data, ans
    raise RuntimeError((level, q))


def main():
    rng = random.Random(SEED)
    out, titles = [], set()
    for k, (level, q, combos) in enumerate(PLAN, 1):
        pid = f'9-g{k:02d}'
        while True:
            n, conds, data, ans = make(rng, level, q, combos)
            title = f'{QSHORT[q]}: ' + ', '.join(SHORT[c] for c in conds) + f' ({n} чисел)'
            if title not in titles:
                titles.add(title); break
        allw = 'оба' if len(conds) == 2 else 'все'
        text = (f'В каждой строке электронной таблицы записаны {NUM[n]} натуральных {"числа" if n == 4 else "чисел"}. '
                + QTXT[q].format(all=allw) + '<ul>' + ''.join(f'<li>{TXT[c]};</li>' for c in conds[:-1])
                + f'<li>{TXT[conds[-1]]}.</li></ul>' + ('В ответе запишите только число.' if q != 'first' and q != 'last' else 'В ответе запишите только номер строки (строки нумеруются с единицы).'))
        spec = json.dumps({'q': q, 'conds': conds}, ensure_ascii=False, separators=(',', ':'))
        out.append({'id': pid, 'task': 9, 'level': level, 'title': title, 'text': text,
                    'extra': f'<!--spec:{spec}-->' + preview(data), 'code': code_for(q, conds), 'answer': str(ans),
                    'data': '\n'.join('\t'.join(map(str, r)) for r in data), 'dname': '9.txt',
                    'note': 'Повторы удобно считать через a.count(x) или Counter; наибольшее и наименьшее — через sorted(a). '
                            'Проверьте решение на первых строках вручную.'})
    # решения запускаются на своих данных
    with tempfile.TemporaryDirectory() as d:
        for p in out:
            open(os.path.join(d, '9.txt'), 'w').write(p['data'] + '\n')
            r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=120, cwd=d)
            if r.stdout.strip() != p['answer']:
                raise SystemExit(f"{p['id']}: решение даёт «{r.stdout.strip()}», ответ «{p['answer']}»\n{r.stderr}\n{p['code']}")
    stat = {}
    for p in out:
        stat[p['level']] = stat.get(p['level'], 0) + 1
    print(json.dumps(stat, ensure_ascii=False), file=sys.stderr)
    json.dump(out, sys.stdout, ensure_ascii=False)


if __name__ == '__main__':
    main()
