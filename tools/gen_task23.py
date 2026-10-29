#!/usr/bin/env python3
"""Генератор задач ЕГЭ №23 (анализ графов, новое задание 2027 года) для банка stackly.

    python3 tools/gen_task23.py > /tmp/task23.json      # 50 задач: 18 базовых, 18 средних, 14 сложных

Как в демоверсии 2027: у каждой задачи свой файл 23.txt с ациклическим ориентированным взвешенным графом —
в строке «L M W»: ребро из L в M веса W; вершины пронумерованы не подряд (до 1000), рёбер не больше 200, числа
разделены пробелами и табуляциями вперемешку. Вопросы: целая часть длины кратчайшего (или самого длинного) пути,
наименьшее число рёбер в пути, количество различных путей — всего, через вершину, в обход вершины, кратчайший путь
через вершину. Веса кратны 0,25 — такие числа float хранит точно, поэтому целая часть не зависит от погрешности.
Решение на Python запускается на своём файле и должно вывести ответ. Описание задачи хранится комментарием
<!--spec:…--> — тест tests/test_bank_task23.py пересчитывает ответ топологической сортировкой в точных дробях.
Генерация детерминирована (seed).
"""
import json, os, random, subprocess, sys, tempfile
from functools import lru_cache

SEED = 20271023
PLAN = ([('Б', 'short')] * 12 + [('Б', 'edges')] * 6 + [('П', 'count')] * 10 + [('П', 'long')] * 8
        + [('В', 'count_through')] * 5 + [('В', 'count_avoid')] * 5 + [('В', 'short_through')] * 4)
ENDS = [(1, 100), (1, 100), (1, 100), (1, 500), (10, 1000), (2, 999), (5, 300)]


def wfmt(w):
    s = f'{w:.2f}'.rstrip('0')
    return s + '0' if s.endswith('.') else s


def make_graph(rng, frac):
    s, t = rng.choice(ENDS)
    nv = rng.randint(40, 70)
    labels = rng.sample([x for x in range(1, 1001) if x not in (s, t)], nv - 2)
    # топологический порядок: s ближе к началу, t ближе к концу; вершины до s и после t — тупики и «лишние» входы
    k1, k2 = rng.randint(0, 3), rng.randint(0, 3)
    order = labels[:k1] + [s] + labels[k1:nv - 2 - k2] + [t] + labels[nv - 2 - k2:]
    pos = {v: i for i, v in enumerate(order)}
    ne = rng.randint(130, 200)
    edges = {}
    i = pos[s]
    while i < pos[t]:                                   # гарантированный путь s → t
        j = min(pos[t], i + rng.randint(1, 4))
        edges[(order[i], order[j])] = None
        i = j
    while len(edges) < ne:
        i = rng.randrange(nv - 1)
        j = min(nv - 1, i + rng.choice([1, 1, 2, 2, 3, 4, 6, 9]))
        edges.setdefault((order[i], order[j]), None)
    for e in edges:
        w = rng.randint(100, 9000) if not frac else rng.randint(4, 3600) / 4
        edges[e] = float(w)
    return s, t, [(u, v, w) for (u, v), w in edges.items()]


def tools(edges):
    g = {}
    for u, v, w in edges:
        g.setdefault(u, []).append((v, w))

    @lru_cache(None)
    def short(v, t):
        return 0.0 if v == t else min((w + short(u, t) for u, w in g.get(v, [])), default=float('inf'))

    @lru_cache(None)
    def long(v, t):
        return 0.0 if v == t else max((w + long(u, t) for u, w in g.get(v, [])), default=float('-inf'))

    @lru_cache(None)
    def paths(v, t, ban=None):
        if v == ban:
            return 0
        return 1 if v == t else sum(paths(u, t, ban) for u, _ in g.get(v, []))

    @lru_cache(None)
    def nedges(v, t):
        return 0 if v == t else min((1 + nedges(u, t) for u, _ in g.get(v, [])), default=10 ** 9)
    return g, short, long, paths, nedges


def make(rng, fam):
    while True:
        frac = rng.random() < 0.5
        s, t, edges = make_graph(rng, frac)
        g, short, long, paths, nedges = tools(edges)
        mids = [v for v in g if v not in (s, t) and paths(s, v) and paths(v, t)]
        sp = {'fam': fam, 's': s, 't': t, 'ne': len(edges)}
        if fam == 'short':
            ans = int(short(s, t))
        elif fam == 'long':
            ans = int(long(s, t))
        elif fam == 'edges':
            ans = nedges(s, t)
        elif fam == 'count':
            ans = paths(s, t)
        elif fam in ('count_through', 'short_through'):
            c = rng.choice(mids)
            sp['c'] = c
            ans = paths(s, c) * paths(c, t) if fam == 'count_through' else int(short(s, c) + short(c, t))
            if fam == 'short_through' and int(short(s, t)) == ans:
                continue                                 # иначе «через вершину» ничего не меняет
        else:
            c = rng.choice(mids)
            sp['c'] = c
            ans = paths(s, t, c)
            if ans in (0, paths(s, t)):
                continue
        if ans >= 2:
            rng.shuffle(edges)
            return sp, ans, edges


def data_text(rng, edges):
    lines = []
    for u, v, w in edges:
        gap = lambda: rng.choice([' ', '  ', '   ', '\t', '\t\t', ' \t', '        '])
        lines.append(f'{u}{gap()}{v}{gap()}{wfmt(w)}')
    return '\n'.join(lines)


Q = {'short': 'Найдите и запишите в ответе целую часть длины кратчайшего пути из вершины с номером {s} в вершину с номером {t}.',
     'long': 'Найдите и запишите в ответе целую часть длины самого длинного пути из вершины с номером {s} в вершину с номером {t}. '
             'Под длиной пути понимается сумма весов рёбер, составляющих путь.',
     'edges': 'Найдите наименьшее количество рёбер в пути из вершины с номером {s} в вершину с номером {t}.',
     'count': 'Найдите количество различных путей из вершины с номером {s} в вершину с номером {t}.',
     'count_through': 'Найдите количество различных путей из вершины с номером {s} в вершину с номером {t}, '
                      'проходящих через вершину с номером {c}.',
     'count_avoid': 'Найдите количество различных путей из вершины с номером {s} в вершину с номером {t}, '
                    'не проходящих через вершину с номером {c}.',
     'short_through': 'Найдите и запишите в ответе целую часть длины кратчайшего пути из вершины с номером {s} '
                      'в вершину с номером {t}, проходящего через вершину с номером {c}.'}
TITLE = {'short': 'Кратчайший путь {s} → {t}', 'long': 'Самый длинный путь {s} → {t}', 'edges': 'Меньше всего рёбер {s} → {t}',
         'count': 'Количество путей {s} → {t}', 'count_through': 'Пути {s} → {t} через {c}',
         'count_avoid': 'Пути {s} → {t} в обход {c}', 'short_through': 'Кратчайший путь {s} → {t} через {c}'}


def example(sp):
    """Маленький граф для «типового примера» с теми же концами и ответом на тот же вопрос."""
    s, t = sp['s'], sp['t']
    a, b, c = 7, 12, 30
    if sp.get('c') is not None:
        a = 7
    ex = [(t, 4, 2.0), (b, a, 3.0), (s, b, 1.0), (s, a, 5.5), (a, t, 2.0), (c, t, 8.0), (s, t, 12.0), (s, c, 2.5)]
    _, short, long, paths, nedges = tools(ex)
    f = sp['fam']
    if f == 'short':
        ans = int(short(s, t))
    elif f == 'long':
        ans = int(long(s, t))
    elif f == 'edges':
        ans = nedges(s, t)
    elif f == 'count':
        ans = paths(s, t)
    elif f == 'count_through':
        ans = paths(s, a) * paths(a, t)
    elif f == 'count_avoid':
        ans = paths(s, t, a)
    else:
        ans = int(short(s, a) + short(a, t))
    rows = '\n'.join(f'{u}  {v}  {wfmt(w)}' for u, v, w in ex)
    who = f' (вершина {a} — та, о которой спрашивается в вопросе)' if sp.get('c') is not None else ''
    return rows, ans, who


def code_for(sp):
    head = ("g = {}\nfor line in open('23.txt'):\n    a = line.split()                 # пробелы и табуляции — любые\n"
            "    if a:\n        u, v, w = int(a[0]), int(a[1]), float(a[2])\n        g.setdefault(u, []).append((v, w))\n\n")
    f, s, t, c = sp['fam'], sp['s'], sp['t'], sp.get('c')
    if f in ('short', 'long', 'short_through'):
        op, inf = ('min', "float('inf')") if f != 'long' else ('max', "float('-inf')")
        body = (f"@lru_cache(None)\ndef best(v, t):                     # {'кратчайший' if op == 'min' else 'самый длинный'} путь из v в t\n"
                f"    if v == t:\n        return 0\n    return {op}((w + best(u, t) for u, w in g.get(v, [])), default={inf})\n\n\n")
        out = f'print(int(best({s}, {c}) + best({c}, {t})))' if f == 'short_through' else f'print(int(best({s}, {t})))'
    elif f == 'edges':
        body = ("@lru_cache(None)\ndef steps(v, t):\n    if v == t:\n        return 0\n"
                "    return min((1 + steps(u, t) for u, _ in g.get(v, [])), default=10 ** 9)\n\n\n")
        out = f'print(steps({s}, {t}))'
    else:
        body = ("@lru_cache(None)\ndef paths(v, t, ban=None):\n    if v == ban:\n        return 0\n    if v == t:\n        return 1\n"
                "    return sum(paths(u, t, ban) for u, _ in g.get(v, []))\n\n\n")
        out = {'count': f'print(paths({s}, {t}))', 'count_through': f'print(paths({s}, {c}) * paths({c}, {t}))',
               'count_avoid': f'print(paths({s}, {t}, ban={c}))'}[f]
    return 'from functools import lru_cache\n\n' + head + body + out


NOTE = {'short': 'В ациклическом графе кратчайший путь из v — минимум по рёбрам v → u величины «вес + кратчайший путь из u». '
                 'Кеш (lru_cache) делает перебор быстрым; Дейкстра тоже подойдёт.',
        'long': 'Самый длинный путь ищется так же, как кратчайший, только max вместо min — это возможно, потому что в графе нет циклов.',
        'edges': 'Наименьшее число рёбер — тот же кратчайший путь, если вес каждого ребра считать равным 1 (или обход в ширину).',
        'count': 'Число путей из v — сумма чисел путей из всех вершин, в которые ведут рёбра из v. Путей бывают миллиарды: '
                 'перебирать их по одному нельзя, нужен кеш.',
        'count_through': 'Через обязательную вершину C: пути до C и пути от C независимы, их количества перемножаются.',
        'count_avoid': 'Запретная вершина: если путь попал в неё, функция возвращает 0.',
        'short_through': 'Кратчайший путь через C складывается из кратчайшего пути до C и кратчайшего пути от C.'}


def build(sp, rng_note=None):
    rows, ex_ans, who = example(sp)
    q = Q[sp['fam']].format(**sp)
    weights = 'одно положительное вещественное число (W)'
    text = ('В текстовом файле содержится описание ациклического ориентированного взвешенного графа. В каждой строке файла '
            f'записаны два натуральных числа (L, M) и {weights}. L и M — номера вершин графа, W — вес ребра, ведущего из '
            'вершины L в вершину M. Таким образом, количество строк в файле равно количеству рёбер в графе. Две вершины '
            f'графа не могут быть соединены более чем одним ребром.<br>{q} Существование хотя бы одного такого пути '
            'гарантируется.<br>Для выполнения этого задания следует написать программу. Вершины графа могут быть '
            'пронумерованы не подряд. L ≤ 1000, M ≤ 1000; W ≤ 10 000. Количество строк в файле не превосходит 200. '
            'Числа в строках разделены произвольным ненулевым количеством пробелов и/или табуляций.'
            f'<br>Типовой пример организации данных во входном файле:<pre>{rows}</pre>'
            f'Для приведённого примера{who} верным ответом будет {ex_ans}. Типовой пример имеет иллюстративный характер — '
            'для выполнения задания используйте данные из прилагаемого файла.')
    n = sp['ne']
    word = 'ребро' if n % 10 == 1 and n % 100 != 11 else 'ребра' if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else 'рёбер'
    return text, code_for(sp), NOTE[sp['fam']], TITLE[sp['fam']].format(**sp) + f' ({n} {word})'


def main():
    rng = random.Random(SEED)
    out, titles = [], set()
    for k, (level, fam) in enumerate(PLAN, 1):
        while True:
            sp, ans, edges = make(rng, fam)
            text, code, note, ttl = build(sp)
            if ttl not in titles:
                titles.add(ttl)
                break
        meta = json.dumps(sp, ensure_ascii=False, separators=(',', ':'))
        out.append({'id': f'23-g{k:03d}', 'task': 23, 'level': level, 'title': ttl, 'text': text,
                    'extra': f'<!--spec:{meta}-->', 'code': code, 'answer': str(ans), 'data': data_text(rng, edges),
                    'dname': '23.txt', 'note': note})
    with tempfile.TemporaryDirectory() as d:
        for p in out:
            open(os.path.join(d, '23.txt'), 'w').write(p['data'] + '\n')
            r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=120, cwd=d)
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
