"""Задачи №23 банка (анализ графов, новое задание 2027 года): ответ пересчитывается по файлу задачи своим способом —
вершины упорядочиваются сортировкой Кана, длины путей считаются динамикой в точных дробях (Fraction), а не рекурсией
с float, как в решении. Файл проверяется на ограничения из условия: граф ациклический, рёбер не больше 200, номера
вершин до 1000, вес до 10 000, нет повторных рёбер. Решение на Python из каждой задачи запускается на своём файле
и должно вывести ответ."""
import json, os, re, subprocess, sys, tempfile, unittest
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bank():
    s = open(os.path.join(ROOT, 'content', 'ege.js'), encoding='utf-8').read()
    a = s.index('window.BANK = ') + len('window.BANK = ')
    return json.loads(s[a:s.index(';\n', a)])


def probs():
    return [p for p in bank() if p['task'] == 23 and '<!--spec:' in p['extra']]


def spec(p):
    return json.loads(re.search(r'<!--spec:(.*?)-->', p['extra']).group(1))


def read(data):
    return [(int(a), int(b), Fraction(w)) for a, b, w in (l.split() for l in data.split('\n') if l.strip())]


def topo(edges):
    nodes = {u for u, _, _ in edges} | {v for _, v, _ in edges}
    indeg = {v: 0 for v in nodes}
    for _, v, _ in edges:
        indeg[v] += 1
    order, ready = [], sorted(v for v in nodes if indeg[v] == 0)
    while ready:
        u = ready.pop()
        order.append(u)
        for a, b, _ in edges:
            if a == u:
                indeg[b] -= 1
                if indeg[b] == 0:
                    ready.append(b)
    assert len(order) == len(nodes), 'в графе есть цикл'
    return order


def dp(edges, s, kind, ban=None):
    """Значение для каждой вершины по путям из s: min/max длины, min число рёбер или количество путей."""
    order = topo(edges)
    val = {s: 1 if kind == 'count' else 0}
    for u in order:
        if u not in val or u == ban:
            continue
        for a, b, w in edges:
            if a != u or b == ban:
                continue
            x = {'min': val[u] + w, 'max': val[u] + w, 'steps': val[u] + 1, 'count': val[u]}[kind]
            if b not in val:
                val[b] = x
            elif kind == 'count':
                val[b] += x
            else:
                val[b] = max(val[b], x) if kind == 'max' else min(val[b], x)
    return val


def solve(sp, edges):
    f, s, t, c = sp['fam'], sp['s'], sp['t'], sp.get('c')
    if f == 'short':
        return int(dp(edges, s, 'min')[t])
    if f == 'long':
        return int(dp(edges, s, 'max')[t])
    if f == 'edges':
        return dp(edges, s, 'steps')[t]
    if f == 'count':
        return dp(edges, s, 'count')[t]
    if f == 'count_through':
        return dp(edges, s, 'count')[c] * dp(edges, c, 'count')[t]
    if f == 'count_avoid':
        return dp(edges, s, 'count', ban=c).get(t, 0)
    return int(dp(edges, s, 'min')[c] + dp(edges, c, 'min')[t])


class Task23BankTest(unittest.TestCase):
    def test_each_solution_prints_its_answer(self):
        with tempfile.TemporaryDirectory() as d:
            for p in [p for p in bank() if p['task'] == 23 and p['data']]:
                with self.subTest(p['id']):
                    open(os.path.join(d, p['dname']), 'w').write(p['data'] + '\n')
                    r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=60, cwd=d)
                    self.assertEqual(r.stdout.strip(), p['answer'])

    def test_answers_recomputed_from_file(self):
        ps = probs()
        self.assertGreaterEqual(len(ps), 50)
        for p in ps:
            with self.subTest(p['id']):
                self.assertEqual(str(solve(spec(p), read(p['data']))), p['answer'])

    def test_file_follows_the_statement(self):
        for p in probs():
            sp, edges = spec(p), read(p['data'])
            with self.subTest(p['id']):
                self.assertLessEqual(len(edges), 200)
                self.assertEqual(len({(a, b) for a, b, _ in edges}), len(edges))
                for a, b, w in edges:
                    self.assertTrue(1 <= a <= 1000 and 1 <= b <= 1000 and a != b)
                    self.assertTrue(0 < w <= 10000)
                    self.assertEqual((w * 4).denominator, 1)          # кратно 0,25 — float считает точно
                topo(edges)
                self.assertIn(f'номером {sp["s"]} в вершину с номером {sp["t"]}', p['text'])
                if 'c' in sp:
                    self.assertIn(f'вершину с номером {sp["c"]}', p['text'])
                self.assertTrue(re.search(r'\d[ \t]*\t|\d {2,}', p['data']), 'разделители должны быть разными')

    def test_levels_and_titles(self):
        ps = probs()
        levels = {}
        for p in ps:
            levels[p['level']] = levels.get(p['level'], 0) + 1
        self.assertEqual(levels, {'Б': 18, 'П': 18, 'В': 14})
        titles = [p['title'] for p in ps]
        self.assertEqual(len(titles), len(set(titles)))

    def test_rules(self):
        # граф из «типового примера» генератора: кратчайший 1 → 12 → 7 → 100 (1 + 3 + 2 = 6), а не прямое ребро 1 → 7;
        # путей 1 → 100 четыре: напрямую, через 7, через 12 и 7, через 30
        ex = read('100 4 2.0\n12 7 3.0\n1 12 1.0\n1 7 5.5\n7 100 2.0\n30 100 8.0\n1 100 12.0\n1 30 2.5')
        self.assertEqual(solve({'fam': 'short', 's': 1, 't': 100}, ex), 6)
        self.assertEqual(solve({'fam': 'count', 's': 1, 't': 100}, ex), 4)
        self.assertEqual(solve({'fam': 'count_avoid', 's': 1, 't': 100, 'c': 7}, ex), 2)
        self.assertEqual(solve({'fam': 'long', 's': 1, 't': 100}, ex), 12)
        self.assertEqual(solve({'fam': 'edges', 's': 1, 't': 100}, ex), 1)


if __name__ == '__main__':
    unittest.main()
