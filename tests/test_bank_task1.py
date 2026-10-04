"""Задачи №1 банка: решаем каждую только по тому, что видит ученик (SVG-схема, таблица, текст условия)
и сверяем с записанным ответом. Заодно проверяем, что линии схемы не задевают чужие пункты."""
import heapq, itertools, json, math, os, re, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bank():
    s = open(os.path.join(ROOT, 'content', 'ege.js'), encoding='utf-8').read()        # закрытые материалы
    a = s.index('window.BANK = ') + len('window.BANK = ')
    return json.loads(s[a:s.index(';\n', a)])


def solve(p):
    ex, text = p['extra'], p['text']
    circles = [(float(x), float(y)) for x, y in re.findall(r'<circle cx="([\d.]+)" cy="([\d.]+)"', ex)]
    letters = re.findall(r'class="gt">(\w)</text>', ex)
    pos = dict(zip(letters, circles))
    near = lambda x, y: min(pos, key=lambda k: math.dist(pos[k], (x, y)))
    g = set()
    for m in re.finditer(r'<line x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="([\d.]+)" class="ge"([^/]*)/>', ex):
        x1, y1, x2, y2 = map(float, m.groups()[:4]); a, b = near(x1, y1), near(x2, y2)
        assert a != b and math.dist(pos[a], (x1, y1)) < 20 and math.dist(pos[b], (x2, y2)) < 20, p['id']
        # линия не должна проходить через чужой кружок
        for k, c in pos.items():
            if k in (a, b): continue
            (X1, Y1), (X2, Y2) = pos[a], pos[b]; dx, dy = X2 - X1, Y2 - Y1
            t = max(0, min(1, ((c[0]-X1)*dx + (c[1]-Y1)*dy) / (dx*dx+dy*dy)))
            assert math.dist((X1+t*dx, Y1+t*dy), c) > 18, (p['id'], 'линия задевает', k)
        attrs = m.group(5); directed = 'marker' in ex
        if not directed: g |= {(a, b), (b, a)}
        else:
            if 'marker-end' in attrs: g.add((a, b))
            if 'marker-start' in attrs: g.add((b, a))
    rows = re.findall(r'<tr><th>П(\d+)</th>(.*?)</tr>', ex)
    n = len(rows)
    t = {}
    for i, cells in rows:
        for j, c in enumerate(re.findall(r'<td>(.*?)</td>', cells), 1):
            if c: t[(int(i), j)] = c
    assert n == len(letters)
    stars = all(v == '*' for v in t.values())
    if not directed: assert all(t.get((j, i)) == v for (i, j), v in t.items()), (p['id'], 'таблица несимметрична')
    asked = list(''.join(re.findall(r'<b>(\w+)</b>', text)))
    title = p['title'].lower()
    sols = set()
    for perm in itertools.permutations(range(1, n + 1)):
        m = dict(zip(letters, perm))
        if not all(((a, b) in g) == ((m[a], m[b]) in t) for a in letters for b in letters if a != b): continue
        w = lambda a, b: int(t[(m[a], m[b])])
        if 'номера' in title: r = ''.join(map(str, sorted((m[asked[0]], m[asked[1]]))))
        elif 'кратчайший' in title:
            s0, f0 = m[asked[0]], m[asked[1]]; dist = {s0: 0}; q = [(0, s0)]
            while q:
                d, v = heapq.heappop(q)
                for (x, y), c in t.items():
                    if x == v and d + int(c) < dist.get(y, 1e9): dist[y] = d + int(c); heapq.heappush(q, (dist[y], y))
            r = dist[f0]
        elif 'все дороги' in title: r = sum(int(c) for (x, y), c in t.items() if x == m[asked[0]])
        elif 'Маршрут' in title or 'маршрут' in title: r = sum(w(asked[i], asked[i+1]) for i in range(len(asked)-1))
        elif 'разность' in title: r = w(asked[0], asked[1]) - w(asked[2], asked[3])
        elif 'Сумма' in title or 'сумма' in title: r = w(asked[0], asked[1]) + w(asked[2], asked[3])
        else: r = w(asked[0], asked[1])
        sols.add(str(r))
    return sols


class Task1BankTest(unittest.TestCase):
    def test_every_task1_problem_has_unique_correct_answer(self):
        probs = [p for p in bank() if p['task'] == 1 and '<svg' in p['extra'] and '<table class="mtx">' in p['extra']]
        self.assertGreaterEqual(len(probs), 50)
        for p in probs:
            with self.subTest(p['id']):
                self.assertEqual(solve(p), {p['answer']})

    def test_problem_ids_unique(self):
        ids = [p['id'] for p in bank()]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == '__main__':
    unittest.main()
