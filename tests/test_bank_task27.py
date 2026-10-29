"""Задачи №27 банка (кластеризация частиц, формат 2027 года): по файлу задачи энергии считаются в точных дробях
(Fraction), разбиение на K кластеров с разбросом не больше R проверяется на единственность — динамикой считается,
сколькими способами отсортированные энергии режутся на K отрезков. Ещё проверяется, что промежутки между кластерами
меньше R (иначе задача решается «по разрыву» и теряет смысл), а центры единственны. Ответ пересчитывается заново;
решение на Python из каждой задачи запускается на своём файле и должно вывести ответ."""
import json, math, os, re, subprocess, sys, tempfile, unittest
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bank():
    s = open(os.path.join(ROOT, 'content', 'ege.js'), encoding='utf-8').read()
    a = s.index('window.BANK = ') + len('window.BANK = ')
    return json.loads(s[a:s.index(';\n', a)])


def probs():
    return [p for p in bank() if p['task'] == 27 and '<!--spec:' in p['extra']]


def spec(p):
    return json.loads(re.search(r'<!--spec:(.*?)-->', p['extra']).group(1))


def read(data):
    ps = []
    for line in data.split('\n'):
        a = line.split()
        if a:
            x, y, vx, vy, m = (Fraction(v.replace(',', '.')) for v in a[:5])
            ps.append({'E': m * (vx * vx + vy * vy) / 2, 'x': x, 'y': y, 'm': m, 'f': a[5]})
    return sorted(ps, key=lambda p: p['E'])


def cuts(es, K, R):
    """Сколькими способами отсортированные энергии делятся на K подряд идущих групп с разбросом ≤ R."""
    n = len(es)
    ways = [[0] * (K + 1) for _ in range(n + 1)]
    ways[0][0] = 1
    for i in range(1, n + 1):
        for j in range(i, 0, -1):                       # группа es[j-1 .. i-1]
            if es[i - 1] - es[j - 1] > R:
                break
            for k in range(1, K + 1):
                ways[i][k] += ways[j - 1][k - 1]
    return ways[n][K]


def clusters(ps, R):
    out = []
    for p in ps:
        if out and p['E'] - out[-1][0]['E'] <= R:
            out[-1].append(p)
        else:
            out.append([p])
    return out


def dist(a, b):
    return math.hypot(float(a['x'] - b['x']), float(a['y'] - b['y']))


def solve(sp, cls):
    cens = []
    for c in cls:
        cost = {id(p): sum(abs(p['E'] - q['E']) for q in c) for p in c}
        best = min(cost.values())
        assert list(cost.values()).count(best) == 1, 'центр не единственный'
        cens.append(next(p for p in c if cost[id(p)] == best))
    if sp['q1'] in ('dmax', 'dmin'):
        ds = [dist(a, b) for c in cls for i, a in enumerate(c) for b in c[i + 1:] if a['f'] == b['f'] == sp['f']]
        q1 = max(ds) if sp['q1'] == 'dmax' else min(ds)
    else:
        q1 = max(dist(cen, p) for cen, c in zip(cens, cls) for p in c)
    es = [c['E'] for c in cens]
    q2 = {'emax': max(es), 'emin': min(es), 'esum': sum(es), 'mavg': sum(c['m'] for c in cens) / len(cens)}[sp['q2']]
    return f'{math.floor(q1 * 10000)} {math.floor(q2 * 10000)}'


class Task27BankTest(unittest.TestCase):
    def test_each_solution_prints_its_answer(self):
        with tempfile.TemporaryDirectory() as d:
            for p in [p for p in bank() if p['task'] == 27 and p['data']]:
                with self.subTest(p['id']):
                    open(os.path.join(d, p['dname']), 'w').write(p['data'] + '\n')
                    r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=300, cwd=d)
                    self.assertEqual(r.stdout.strip(), p['answer'])

    def test_partition_is_unique_and_tricky(self):
        ps_all = probs()
        self.assertGreaterEqual(len(ps_all), 12)
        for p in ps_all:
            sp, ps = spec(p), read(p['data'])
            R = Fraction(str(sp['R']))
            with self.subTest(p['id']):
                es = [q['E'] for q in ps]
                self.assertEqual(len(set(es)), len(es))
                self.assertEqual(cuts(es, sp['K'], R), 1)
                cls = clusters(ps, R)
                self.assertEqual(len(cls), sp['K'])
                self.assertTrue(all(len(c) % 2 for c in cls))
                gaps = [b[0]['E'] - a[-1]['E'] for a, b in zip(cls, cls[1:])]
                self.assertTrue(all(g < R for g in gaps), 'промежутки должны быть меньше R, как в демоверсии')

    def test_answers_recomputed_from_file(self):
        for p in probs():
            sp = spec(p)
            with self.subTest(p['id']):
                self.assertEqual(solve(sp, clusters(read(p['data']), Fraction(str(sp['R'])))), p['answer'])

    def test_statement(self):
        for p in probs():
            sp = spec(p)
            with self.subTest(p['id']):
                self.assertIn(f'(K = {sp["K"]})', p['text'])
                self.assertIn(f'R = {str(sp["R"]).replace(".", ",")}', p['text'])
                if sp['q1'] in ('dmax', 'dmin'):
                    self.assertIn(f'признак {sp["f"]},', p['text'])
                self.assertRegex(p['answer'], r'^\d+ \d+$')     # формат 2027: одна строка из двух чисел

    def test_rules(self):
        # кластеры по энергии: 1; 1,5; 2,1 | 2,8; 3,4 — промежуток 0,7 меньше R = 1,2, но разбиение одно:
        # ширина 1,1 + промежуток 0,7 > R и промежуток 0,7 + ширина 0,6 > R
        es = [Fraction(x) for x in ('1', '1.5', '2.1', '2.8', '3.4')]
        self.assertEqual(cuts(es, 2, Fraction('1.2')), 1)
        # а при 1; 1,5; 2,2 | 2,9; 3,3 подходит и {1; 1,5} {2,2; 2,9; 3,3} — разбиение не единственно
        self.assertEqual(cuts([Fraction(x) for x in ('1', '1.5', '2.2', '2.9', '3.3')], 2, Fraction('1.2')), 2)
        # деление «по разрыву больше R» здесь дало бы один кластер — поэтому так делать нельзя
        self.assertTrue(all(b - a <= Fraction('1.2') for a, b in zip(es, es[1:])))


if __name__ == '__main__':
    unittest.main()
