#!/usr/bin/env python3
"""Генератор задач ЕГЭ №1 (граф + таблица) для банка stackly.

    python3 tools/gen_task1.py > /tmp/task1.json      # 50 задач: 35 базовых, 10 средних, 5 сложных

Каждая задача проверяется:
  * перебираются ВСЕ сопоставления букв графа и номеров таблицы, совместимые со структурой;
    ответ должен быть одинаковым при любом из них (иначе задача отбрасывается);
  * решение на Python, которое кладётся в задачу, запускается, и его вывод сверяется с ответом.
Генерация детерминирована (seed), повторный запуск даёт те же задачи.
"""
import heapq, itertools, json, math, random, subprocess, sys

SEED = 20261004
MIN_GAP = 58          # минимальное расстояние между центрами пунктов на схеме: кружки и стрелки не слипаются


def spaced(pts):
    return all(math.dist(a, b) >= MIN_GAP for a, b in itertools.combinations(pts, 2))
LET = 'АБВГДЕЖЗИК'
INTRO = ('На рисунке схема дорог N-ского района изображена в виде графа, в таблице содержатся сведения о длинах '
         'этих дорог (в километрах). Так как таблицу и схему рисовали независимо друг от друга, нумерация населённых '
         'пунктов в таблице никак не связана с буквенными обозначениями на графе.')
INTRO_STAR = ('На рисунке схема дорог N-ского района изображена в виде графа, в таблице звёздочкой обозначено наличие '
              'дороги из одного населённого пункта в другой. Отсутствие звёздочки означает, что такой дороги нет. '
              'Так как таблицу и схему рисовали независимо друг от друга, нумерация населённых пунктов в таблице '
              'никак не связана с буквенными обозначениями на графе.')
INTRO_DIR = ('На рисунке схема дорог N-ского района изображена в виде графа. Стрелки показывают направление движения: '
             'по дороге со стрелкой на одном конце можно ехать только в эту сторону, со стрелками на обоих концах — в обе. '
             'В таблице на пересечении строки П<i>i</i> и столбца П<i>j</i> указана длина дороги (в километрах) '
             'из пункта П<i>i</i> в пункт П<i>j</i>. Нумерация пунктов в таблице никак не связана с буквенными '
             'обозначениями на графе.')


# ------------------------------------------------------------------ граф и рисунок
def seg_cross(p1, p2, p3, p4):
    def o(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if {p1, p2} & {p3, p4}:
        return False
    return o(p1, p2, p3) * o(p1, p2, p4) < 0 and o(p3, p4, p1) * o(p3, p4, p2) < 0


def seg_point_dist(a, b, p):
    (x1, y1), (x2, y2), (x, y) = a, b, p
    dx, dy = x2 - x1, y2 - y1
    t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x1 + t * dx - x, y1 + t * dy - y)


def make_layout(rng, n):
    """n точек на поле 320×220 без наложений: сетка 5×3 с небольшим сдвигом."""
    slots = [(40 + 60 * c, 40 + 70 * r) for r in range(3) for c in range(5)]
    while True:
        pts = rng.sample(slots, n)
        pts = [(x + rng.randint(-12, 12), y + rng.randint(-10, 10)) for x, y in pts]
        xs = sorted({x // 60 for x, _ in pts})
        if len(xs) >= 4 and spaced(pts):      # растянуто по ширине и без слипшихся пунктов
            break
    pts.sort(key=lambda p: (p[0], p[1]))     # буквы идут слева направо, как на экзамене
    return pts


def make_graph(rng, n, m_lo, m_hi, min_deg=2):
    """Плоский связный граф: рёбра не пересекаются и не проходят вплотную к чужим вершинам."""
    for _ in range(2000):
        pts = make_layout(rng, n)
        pairs = sorted(((math.dist(pts[i], pts[j]), i, j) for i in range(n) for j in range(i + 1, n)))
        pairs = [(d, i, j) for d, i, j in pairs if d < 175]
        rng.shuffle(pairs)
        pairs.sort(key=lambda x: x[0] + rng.uniform(0, 60))
        edges = []
        target = rng.randint(m_lo, m_hi)
        for _, i, j in pairs:
            if len(edges) >= target:
                break
            if any(seg_cross(pts[i], pts[j], pts[a], pts[b]) for a, b in edges):
                continue
            if any(seg_point_dist(pts[i], pts[j], pts[k]) < 24 for k in range(n) if k not in (i, j)):
                continue
            edges.append((i, j))
        if len(edges) < m_lo:
            continue
        adj = {i: set() for i in range(n)}
        for a, b in edges:
            adj[a].add(b); adj[b].add(a)
        if min(len(v) for v in adj.values()) < min_deg:
            continue
        seen, st = {0}, [0]
        while st:
            for w in adj[st.pop()]:
                if w not in seen:
                    seen.add(w); st.append(w)
        if len(seen) == n:
            return pts, sorted(edges)
    raise RuntimeError('не удалось построить граф')


def make_sym_graph(rng, n):
    """Зеркальная схема: ось x = 160, на оси 2 пункта, остальные — пары-отражения. Возвращает и отражение."""
    k_axis = 2 if n % 2 == 0 else 1
    pairs = (n - k_axis) // 2
    for _ in range(4000):
        left = []
        cols = rng.sample([35, 75, 115], min(3, pairs)) if pairs <= 3 else [35, 75, 115]
        ys = [40, 110, 180]
        for c in range(pairs):
            left.append((cols[c % len(cols)] + rng.randint(-6, 6), rng.choice(ys) + rng.randint(-8, 8)))
        axis = [(160, y) for y in rng.sample([30, 110, 190], k_axis)]
        pts = left + [(320 - x, y) for x, y in left] + axis
        if not spaced(pts):
            continue
        mir = {i: i + pairs for i in range(pairs)} | {i + pairs: i for i in range(pairs)} | {2 * pairs + j: 2 * pairs + j for j in range(k_axis)}
        cand = [(i, j) for i in range(n) for j in range(i + 1, n) if math.dist(pts[i], pts[j]) < 175]
        rng.shuffle(cand)
        edges = set()
        target = rng.randint(11, 13)
        for i, j in cand:
            e2 = tuple(sorted((mir[i], mir[j])))
            new = {(i, j), e2} - edges
            if len(edges) + len(new) > target:
                continue
            ok = True
            for a, b in new:
                if any(seg_cross(pts[a], pts[b], pts[c], pts[d]) for c, d in edges | (new - {(a, b)})):
                    ok = False
                if any(seg_point_dist(pts[a], pts[b], pts[k]) < 24 for k in range(n) if k not in (a, b)):
                    ok = False
            if ok:
                edges |= new
        adj = {i: set() for i in range(n)}
        for a, b in edges:
            adj[a].add(b); adj[b].add(a)
        if len(edges) < 10 or min(len(v) for v in adj.values()) < 2:
            continue
        seen, st = {0}, [0]
        while st:
            for w in adj[st.pop()]:
                if w not in seen:
                    seen.add(w); st.append(w)
        if len(seen) < n:
            continue
        # буквы слева направо: переставляем вершины по координатам
        order = sorted(range(n), key=lambda v: (pts[v][0], pts[v][1]))
        re = {v: k for k, v in enumerate(order)}
        return [pts[v] for v in order], sorted(tuple(sorted((re[a], re[b]))) for a, b in edges), {re[a]: re[b] for a, b in mir.items()}
    raise RuntimeError('нет симметричной схемы')


def svg(pid, pts, edges, directed=None):
    """directed: {(a, b): 'ab' | 'ba' | 'both'} для схем с односторонним движением."""
    out = [f'<svg class="gsvg" viewBox="0 0 320 220" role="img" aria-label="Граф дорог">']
    if directed:
        mid = f'ar-{pid}'
        out.append(f'<defs><marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                   f'orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="ga"/></marker></defs>')
    for a, b in edges:
        (x1, y1), (x2, y2) = pts[a], pts[b]
        attrs = ''
        if directed:
            d = math.dist(pts[a], pts[b]); k = 17 / d
            x1, y1, x2, y2 = x1 + (x2 - x1) * k, y1 + (y2 - y1) * k, x2 - (x2 - x1) * k, y2 - (y2 - y1) * k
            way = directed[(a, b)]
            if way in ('ab', 'both'):
                attrs += f' marker-end="url(#{mid})"'
            if way in ('ba', 'both'):
                attrs += f' marker-start="url(#{mid})"'
        out.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" class="ge"{attrs}/>')
    for i, (x, y) in enumerate(pts):
        out.append(f'<circle cx="{x}" cy="{y}" r="15" class="gn"/><text x="{x}" y="{y + 5}" class="gt">{LET[i]}</text>')
    out.append('</svg>')
    return ''.join(out)


def table_html(n, cell):
    """cell(i, j) → строка для пересечения строки Пi и столбца Pj (нумерация с 1)."""
    head = '<tr><th></th>' + ''.join(f'<th>П{j}</th>' for j in range(1, n + 1)) + '</tr>'
    rows = ''.join('<tr><th>П{0}</th>{1}</tr>'.format(i, ''.join(f'<td>{cell(i, j)}</td>' for j in range(1, n + 1)))
                   for i in range(1, n + 1))
    return f'<div class="tblwrap"><table class="mtx">{head}{rows}</table></div>'


# ------------------------------------------------------------------ сопоставления
def mappings(n, gadj, tadj, gdeg, tdeg):
    """Все биекции вершина графа → номер таблицы, сохраняющие смежность (с учётом направления)."""
    res, m, used = [], {}, set()
    order = sorted(range(n), key=lambda v: gdeg.count(gdeg[v]))   # сначала вершины с редкой степенью — меньше перебора

    def rec(k):
        if k == n:
            res.append(dict(m)); return
        v = order[k]
        for t in range(n):
            if t in used or gdeg[v] != tdeg[t]:
                continue
            if all(((u, v) in gadj['e']) == ((m[u], t) in tadj['e']) and ((v, u) in gadj['e']) == ((t, m[u]) in tadj['e'])
                   for u in m):
                m[v] = t; used.add(t)
                rec(k + 1)
                del m[v]; used.discard(t)
    rec(0)
    return res


def ident_level(n, adj, v):
    """0 — вершина узнаётся по степени, 1 — по степени и степеням соседей, 2 — сложнее."""
    deg = [len(adj[i]) for i in range(n)]
    if sum(d == deg[v] for d in deg) == 1:
        return 0
    sig = [(deg[i], tuple(sorted(deg[j] for j in adj[i]))) for i in range(n)]
    if sum(s == sig[v] for s in sig) == 1:
        return 1
    return 2


def dijkstra(n, w, s):
    dist = [math.inf] * n; dist[s] = 0; q = [(0, s)]
    while q:
        d, v = heapq.heappop(q)
        if d > dist[v]:
            continue
        for (a, b), c in w.items():
            if a == v and d + c < dist[b]:
                dist[b] = d + c; heapq.heappush(q, (dist[b], b))
    return dist


# ------------------------------------------------------------------ код решения для ученика
def code_for(kind, n, gedges, tw, q, directed=False, stars=False):
    letters = LET[:n]
    if directed:
        g = [LET[a] + LET[b] for a, b in gedges]          # ребро «XY» — дорога из X в Y
        t = {(a + 1, b + 1): c for (a, b), c in sorted(tw.items())}
        head = ('from itertools import permutations\n'
                '# дороги по рисунку: «XY» — из X в Y (двусторонняя дорога записана дважды)\n'
                f'g = {g}\n'
                '# таблица: (из пункта, в пункт): длина\n'
                f't = {t}\n'
                f"letters = '{letters}'\n"
                'ans = set()\n'
                f'for p in permutations(range(1, {n + 1})):\n'
                '    m = dict(zip(letters, p))\n'
                '    if all((a + b in g) == ((m[a], m[b]) in t) for a in letters for b in letters if a != b):\n')
        road = lambda x, y: f"t[(m['{x}'], m['{y}'])]"
    else:
        g = sorted({''.join(sorted(LET[a] + LET[b], key=LET.index)) for a, b in gedges})
        if stars:
            t = sorted({tuple(sorted((a + 1, b + 1))) for (a, b) in tw})
            head = ('from itertools import permutations\n'
                    '# рёбра графа (рисунок)\n'
                    f'g = {g}\n'
                    '# звёздочки таблицы: пары пунктов, между которыми есть дорога\n'
                    f't = {t}\n')
            has = '(min(m[a], m[b]), max(m[a], m[b])) in t'
        else:
            t = {(a + 1, b + 1): c for (a, b), c in sorted(tw.items()) if a < b}
            head = ('from itertools import permutations\n'
                    '# рёбра графа (рисунок)\n'
                    f'g = {g}\n'
                    '# веса из таблицы: (пункт, пункт): длина\n'
                    f't = {t}\n')
            has = '(min(m[a], m[b]), max(m[a], m[b])) in t'
        head += (f"letters = '{letters}'\n"
                 'ans = set()\n'
                 f'for p in permutations(range(1, {n + 1})):\n'
                 '    m = dict(zip(letters, p))\n'
                 f'    if all((a + b in g or b + a in g) == ({has})\n'
                 '           for i, a in enumerate(letters) for b in letters[i + 1:]):\n')
        road = lambda x, y: f"t[tuple(sorted((m['{x}'], m['{y}'])))]"
    if kind == 'road':
        body = f'        ans.add({road(*q)})\n'
    elif kind == 'sum':
        body = f'        ans.add({road(q[0], q[1])} + {road(q[2], q[3])})\n'
    elif kind == 'diff':
        body = f'        ans.add({road(q[0], q[1])} - {road(q[2], q[3])})\n'
    elif kind == 'route':
        body = '        ans.add(' + ' + '.join(road(q[i], q[i + 1]) for i in range(len(q) - 1)) + ')\n'
    elif kind == 'star':
        body = f"        ans.add(''.join(map(str, sorted((m['{q[0]}'], m['{q[1]}'])))))\n"
    elif kind == 'from':
        body = (f"        x = m['{q[0]}']\n"
                '        ans.add(sum(c for (a, b), c in t.items() if x in (a, b)))\n')
    elif kind == 'short':
        if directed:
            nb = '[(b, c) for (a, b), c in t.items() if a == v]'
        else:
            nb = '[(b if a == v else a, c) for (a, b), c in t.items() if v in (a, b)]'
        body = (f"        s, f = m['{q[0]}'], m['{q[1]}']\n"
                '        dist = {s: 0}\n'
                '        todo = [s]\n'
                '        while todo:                      # Дейкстра в простейшей форме\n'
                '            v = min(todo, key=dist.get); todo.remove(v)\n'
                f'            for u, c in {nb}:\n'
                '                if dist[v] + c < dist.get(u, 10 ** 9):\n'
                '                    dist[u] = dist[v] + c; todo.append(u)\n'
                '        ans.add(dist[f])\n')
    return head + body + 'print(*ans)'


# ------------------------------------------------------------------ сборка одной задачи
def build(rng, pid, level, kind, n, directed=False, stars=False, need=None, sym=False):
    """need — дополнительные требования к сложности (функция от контекста); перебираем, пока не подойдёт."""
    for attempt in range(4000):
        m_lo, m_hi = {6: (7, 9), 7: (9, 11), 8: (11, 13)}[n]
        if sym:
            pts, edges, mir = make_sym_graph(rng, n)
        else:
            pts, edges = make_graph(rng, n, m_lo, m_hi)
        adj = {i: set() for i in range(n)}
        for a, b in edges:
            adj[a].add(b); adj[b].add(a)
        perm = list(range(n)); rng.shuffle(perm)            # вершина графа v ↔ номер таблицы perm[v]
        ws = rng.sample(range(5, 61), len(edges) * 2)
        if directed:
            way = {}
            for k, (a, b) in enumerate(edges):
                way[(a, b)] = rng.choice(['ab', 'ba', 'both', 'ab', 'ba'])
            ge = set()
            for (a, b), wv in way.items():
                if wv in ('ab', 'both'): ge.add((a, b))
                if wv in ('ba', 'both'): ge.add((b, a))
            tw = {}
            for k, (a, b) in enumerate(sorted(ge)):
                tw[(perm[a], perm[b])] = ws[k]
            # двусторонняя дорога в обе стороны одной длины
            for (a, b) in ge:
                if (b, a) in ge:
                    tw[(perm[b], perm[a])] = tw[(perm[a], perm[b])]
            gdeg = [(sum((v, u) in ge for u in range(n)), sum((u, v) in ge for u in range(n))) for v in range(n)]
            te = set(tw)
            tdeg = [(sum((t, u) in te for u in range(n)), sum((u, t) in te for u in range(n))) for t in range(n)]
            maps = mappings(n, {'e': ge}, {'e': te}, gdeg, tdeg)
            gedges = sorted(ge)
        else:
            ge = set(edges) | {(b, a) for a, b in edges}
            tw = {}
            for k, (a, b) in enumerate(edges):
                tw[(perm[a], perm[b])] = tw[(perm[b], perm[a])] = ws[k]
            te = set(tw)
            gdeg = [len(adj[v]) for v in range(n)]
            tdeg = [sum((t, u) in te for u in range(n)) for t in range(n)]
            maps = mappings(n, {'e': ge}, {'e': te}, gdeg, tdeg)
            gedges = edges
        assert maps and any(all(mp[v] == perm[v] for v in range(n)) for mp in maps)

        # вопрос
        V = list(range(n))
        road = lambda mp, x, y: tw.get((mp[x], mp[y]))
        if sym and kind == 'sum':
            # пара дорог-отражений: каждую по отдельности не опознать, сумма — однозначна
            cand = [e for e in edges if tuple(sorted((mir[e[0]], mir[e[1]]))) != e]
            if not cand:
                continue
            e1 = rng.choice(cand); e2 = (mir[e1[0]], mir[e1[1]])
            q = (*e1, *e2)
            f = lambda mp: road(mp, *e1) + road(mp, *e2)
        elif sym and kind == 'road':
            # дорога между пунктами-отражениями: концы не опознать, длина — однозначна
            cand = [e for e in edges if mir[e[0]] == e[1]]
            if not cand:
                continue
            q = rng.choice(cand)
            f = lambda mp: road(mp, *q)
        elif kind == 'road':
            a, b = rng.choice(gedges if directed else edges)
            if not directed and rng.random() < .5:
                a, b = b, a
            q = (a, b)
            f = lambda mp: road(mp, a, b)
        elif kind in ('sum', 'diff'):
            e1, e2 = rng.sample(gedges if directed else edges, 2)
            if kind == 'diff' and tw[(perm[e1[0]], perm[e1[1]])] <= tw[(perm[e2[0]], perm[e2[1]])]:
                e1, e2 = e2, e1
            if kind == 'diff' and tw[(perm[e1[0]], perm[e1[1]])] == tw[(perm[e2[0]], perm[e2[1]])]:
                continue
            q = (*e1, *e2)
            f = (lambda mp: road(mp, *e1) + road(mp, *e2)) if kind == 'sum' else (lambda mp: road(mp, *e1) - road(mp, *e2))
        elif kind == 'route':
            # маршрут из 3–4 пунктов по дорогам, без повторов
            path = [rng.choice(V)]
            while len(path) < rng.choice([3, 4]):
                nxt = [u for u in V if u not in path and (path[-1], u) in ge]
                if not nxt:
                    break
                path.append(rng.choice(nxt))
            if len(path) < 3:
                continue
            q = tuple(path)
            f = lambda mp: sum(road(mp, q[i], q[i + 1]) for i in range(len(q) - 1))
        elif kind == 'star':
            a, b = rng.sample(V, 2)
            q = (a, b)
            f = lambda mp: ''.join(map(str, sorted((mp[a] + 1, mp[b] + 1))))
        elif kind == 'from':
            a = rng.choice(V)
            q = (a,)
            f = lambda mp: sum(c for (x, y), c in tw.items() if x == mp[a])
        elif kind == 'short':
            a, b = rng.sample(V, 2)
            q = (a, b)
            tw_dir = tw if directed else tw
            def f(mp):
                d = dijkstra(n, tw_dir, mp[a])
                return d[mp[b]]
        answers = {f(mp) for mp in maps}
        if len(answers) != 1 or None in answers:
            continue
        ans = answers.pop()
        if ans == math.inf:
            continue
        ctx = dict(n=n, adj=adj, edges=edges, maps=maps, q=q, perm=perm, tw=tw, ge=ge, directed=directed, ans=ans)
        if need and not need(ctx):
            continue
        break
    else:
        raise RuntimeError(f'не удалось собрать {pid} ({kind})')

    L = lambda v: LET[v]
    # условие
    if kind == 'road':
        ask = f'Определите длину дороги из пункта <b>{L(q[0])}</b> в пункт <b>{L(q[1])}</b>.'
        title = f'Длина дороги {L(q[0])}{L(q[1])}'
    elif kind == 'sum':
        ask = (f'Определите сумму длин дорог <b>{L(q[0])}{L(q[1])}</b> и <b>{L(q[2])}{L(q[3])}</b>.' if not directed else
               f'Определите сумму длин дорог из <b>{L(q[0])}</b> в <b>{L(q[1])}</b> и из <b>{L(q[2])}</b> в <b>{L(q[3])}</b>.')
        title = f'Сумма дорог {L(q[0])}{L(q[1])} и {L(q[2])}{L(q[3])}'
    elif kind == 'diff':
        ask = (f'На сколько километров дорога <b>{L(q[0])}{L(q[1])}</b> длиннее дороги <b>{L(q[2])}{L(q[3])}</b>? '
               'В ответе запишите целое число.')
        title = f'Разность дорог {L(q[0])}{L(q[1])} и {L(q[2])}{L(q[3])}'
    elif kind == 'route':
        r = ' → '.join(f'<b>{L(v)}</b>' for v in q)
        ask = f'Определите длину маршрута {r}, проходящего по дорогам схемы. В ответе запишите целое число — длину в километрах.'
        title = 'Маршрут ' + '→'.join(L(v) for v in q)
    elif kind == 'star':
        ask = (f'Определите, какие номера в таблице соответствуют пунктам <b>{L(q[0])}</b> и <b>{L(q[1])}</b>. '
               'В ответе запишите эти два номера в порядке возрастания без пробелов и знаков препинания.')
        title = f'Номера пунктов {L(q[0])} и {L(q[1])}'
    elif kind == 'from':
        ask = f'Определите суммарную длину всех дорог, ведущих из пункта <b>{L(q[0])}</b>.'
        title = f'Все дороги из пункта {L(q[0])}'
    elif kind == 'short':
        ask = (f'Определите длину кратчайшего пути из пункта <b>{L(q[0])}</b> в пункт <b>{L(q[1])}</b>. '
               'Передвигаться можно только по дорогам, указанным в таблице.')
        title = f'Кратчайший путь {L(q[0])}→{L(q[1])}'
    if directed:
        title = 'Одностороннее движение: ' + title[0].lower() + title[1:]

    intro = INTRO_DIR if directed else INTRO_STAR if stars else INTRO
    if directed:
        way = {}
        for a, b in edges:
            way[(a, b)] = 'both' if ((a, b) in ge and (b, a) in ge) else 'ab' if (a, b) in ge else 'ba'
        pic = svg(pid, pts, edges, way)
        tbl = table_html(n, lambda i, j: tw.get((i - 1, j - 1), ''))
    else:
        pic = svg(pid, pts, edges)
        tbl = table_html(n, (lambda i, j: '*' if (i - 1, j - 1) in tw else '') if stars else (lambda i, j: tw.get((i - 1, j - 1), '')))

    # подсказка-разбор: как опознать нужные вершины
    tnum = lambda v: perm[v] + 1
    asked = list(dict.fromkeys(q))
    if directed:
        deg = lambda v: f'выходит {sum((v, u) in ge for u in range(n))}, входит {sum((u, v) in ge for u in range(n))}'
        hints = [f'{L(v)}: {deg(v)} → П{tnum(v)}' for v in asked]
        note = 'Считайте для каждого пункта выходящие и входящие дороги (в таблице — заполненные клетки строки и столбца). ' + '; '.join(hints) + '.'
    else:
        parts = []
        for v in asked:
            lv = ident_level(n, adj, v)
            d = len(adj[v])
            how = (f'единственная вершина степени {d}' if lv == 0 else
                   f'степень {d}, отличается от других вершин той же степени соседями' if lv == 1 else
                   f'степень {d}, узнаётся только по положению среди соседей')
            parts.append(f'{L(v)} — {how} → П{tnum(v)}')
        note = 'Степени вершин графа сравниваем с числом заполненных клеток в строках таблицы. ' + '; '.join(parts) + '.'
        if len(maps) > 1:
            note += (' Схема симметрична: сопоставление пунктов определяется не единственным образом, '
                     'но ответ при любом допустимом сопоставлении одинаковый.')
    if kind == 'short':
        note += ' После опознания пунктов ищем кратчайший путь по таблице — прямая дорога не всегда самая короткая.'
    code = code_for(kind, n, gedges, tw, tuple(L(v) for v in q), directed=directed, stars=stars)
    return {'id': pid, 'task': 1, 'level': level, 'title': title,
            'text': f'{intro} {ask}',
            'extra': f'<div class="duo">{pic}{tbl}</div>',
            'code': code, 'answer': str(ans), 'data': '', 'dname': '', 'note': note,
            '_meta': {'kind': kind, 'n': n, 'directed': directed, 'stars': stars, 'maps': len(maps)}}


# ------------------------------------------------------------------ требования к сложности
def easy_ident(ctx):
    """Базовый: каждый нужный пункт опознаётся по степени или по степени соседей; сопоставление однозначно."""
    return len(ctx['maps']) == 1 and all(ident_level(ctx['n'], ctx['adj'], v) <= 1 for v in ctx['q'])


def medium_ident(ctx):
    """Средний: хотя бы один пункт не узнаётся по степени — нужно смотреть на соседей."""
    return len(ctx['maps']) == 1 and any(ident_level(ctx['n'], ctx['adj'], v) >= 1 for v in ctx['q'])


def hard_short(ctx):
    """Сложный: кратчайший путь строго короче любого пути из одной или двух дорог."""
    n, tw, perm, q = ctx['n'], ctx['tw'], ctx['perm'], ctx['q']
    s, f = perm[q[0]], perm[q[1]]
    short = [tw[(s, f)]] if (s, f) in tw else []
    short += [tw[(s, k)] + tw[(k, f)] for k in range(n) if (s, k) in tw and (k, f) in tw]
    return len(ctx['maps']) == 1 and ctx['ans'] < min(short, default=math.inf)


def hard_sym(ctx):
    """Сложный: схема симметрична, нужные пункты нельзя опознать однозначно, но ответ единственный."""
    maps, q = ctx['maps'], ctx['q']
    return len(maps) > 1 and any(len({mp[v] for mp in maps}) > 1 for v in q)


# ------------------------------------------------------------------ план: 35 + 10 + 5
PLAN = (
    [('Б', 'road', 6)] * 4 + [('Б', 'road', 7)] * 6 +
    [('Б', 'sum', 6)] * 3 + [('Б', 'sum', 7)] * 4 +
    [('Б', 'diff', 7)] * 4 +
    [('Б', 'star', 6)] * 3 + [('Б', 'star', 7)] * 4 +
    [('Б', 'from', 6)] * 2 + [('Б', 'from', 7)] * 3 +
    [('Б', 'route', 7)] * 2 +
    [('П', 'road', 8)] * 2 + [('П', 'sum', 8)] * 2 + [('П', 'route', 8)] * 2 +
    [('П', 'road', 7, 'dir')] * 2 + [('П', 'route', 7, 'dir')] * 2 +
    [('В', 'short', 8)] * 2 + [('В', 'short', 7, 'dir')] * 1 + [('В', 'sum', 8, 'sym')] * 1 + [('В', 'road', 8, 'sym')] * 1
)


def main():
    rng = random.Random(SEED)
    out = []
    for k, spec in enumerate(PLAN, 1):
        level, kind, n = spec[:3]
        flag = spec[3] if len(spec) > 3 else ''
        pid = f'1-g{k:02d}'
        need = (hard_sym if flag == 'sym' else hard_short if kind == 'short' else
                easy_ident if level == 'Б' and flag != 'dir' else
                (lambda c: len(c['maps']) == 1) if flag == 'dir' else medium_ident)
        if level == 'П' and not flag:
            need = medium_ident
        while True:                         # заголовки не должны повторяться — иначе собираем заново
            p = build(rng, pid, level, kind, n, directed=flag == 'dir', stars=kind == 'star', need=need, sym=flag == 'sym')
            if p['title'] not in {x['title'] for x in out} | {'Длина дороги ГЕ', 'Длина дороги ДЖ'}:
                break
        out.append(p)

    # проверка: решение из задачи выдаёт её ответ
    for p in out:
        r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=120)
        got = r.stdout.strip()
        if got != p['answer']:
            raise SystemExit(f"{p['id']}: решение даёт «{got}», ответ «{p['answer']}»\n{r.stderr}")
    # заголовки не повторяются
    titles = [p['title'] for p in out]
    assert len(set(titles)) == len(titles), 'повтор заголовков'
    stat = {}
    for p in out:
        stat[p['level']] = stat.get(p['level'], 0) + 1
    print(json.dumps(stat, ensure_ascii=False), file=sys.stderr)
    for p in out:
        p.pop('_meta')
    json.dump(out, sys.stdout, ensure_ascii=False)


if __name__ == '__main__':
    main()
