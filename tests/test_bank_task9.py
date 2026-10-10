"""Задачи №9 банка: условия из скрытого описания (<!--spec:…-->) проверяются здесь своей реализацией —
через подсчёт частот словарём, без a.count() и Counter, как в генераторе, — по данным из самой задачи.
Решение на Python из каждой задачи запускается на её файле и должно вывести ответ; превью таблицы
в условии совпадает с началом файла."""
import json, os, re, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bank():
    s = open(os.path.join(ROOT, 'content', 'ege.js'), encoding='utf-8').read()
    a = s.index('window.BANK = ') + len('window.BANK = ')
    return json.loads(s[a:s.index(';\n', a)])


def freq(a):
    f = {}
    for x in a:
        f[x] = f.get(x, 0) + 1
    return f


def check(name, a):
    f = freq(a)
    hi, lo = max(a), min(a)
    rest = list(a)
    rest.remove(hi); rest.remove(lo)               # «оставшиеся» — без одного наибольшего и одного наименьшего
    multi = [v for v in f if f[v] >= 2]
    singles = [x for x in a if f[x] == 1]
    return {
        'pair1': len(multi) == 1 and f[multi[0]] == 2,
        'triple1': len(multi) == 1 and f[multi[0]] == 3,
        'two_pairs': len(multi) == 2 and f[multi[0]] == 2 and f[multi[1]] == 2,
        'distinct': len(f) == len(a),
        'has_rep': len(f) < len(a),
        'mean_u_le_r': len(multi) == 1 and len(singles) > 0 and sum(singles) <= multi[0] * len(singles),
        'mean_u_gt_r': len(multi) == 1 and len(singles) > 0 and sum(singles) > multi[0] * len(singles),
        'max_lt_rest': hi < sum(a) - hi,
        'maxmin2_le_rest': 2 * (hi + lo) <= sum(rest),
        'sq': (hi + lo) ** 2 > sum(x * x for x in rest),
        'even_more': 2 * len([x for x in a if x % 2 == 0]) > len(a),
        'max_once': f[hi] == 1,
        'max_rep': f[hi] >= 2,
        'mean_gt_med': (lambda s: 2 * sum(s) * (1 if len(s) % 2 else 1) > len(s) * (2 * s[len(s) // 2] if len(s) % 2 else s[len(s) // 2 - 1] + s[len(s) // 2]))(sorted(a)),
    }[name]


def expected(spec, data):
    rows = [list(map(int, l.split())) for l in data.split('\n') if l.strip()]
    hit = [(i, r) for i, r in enumerate(rows, 1) if all(check(c, r) for c in spec['conds'])]
    q = spec['q']
    if q == 'count':
        return len(hit)
    if q == 'first':
        return hit[0][0]
    if q == 'last':
        return hit[-1][0]
    return (max if q == 'maxsum' else min)(sum(r) for _, r in hit)


class Task9BankTest(unittest.TestCase):
    def test_each_solution_prints_its_answer(self):
        with tempfile.TemporaryDirectory() as d:
            for p in [p for p in bank() if p['task'] == 9 and p['data']]:
                with self.subTest(p['id']):
                    open(os.path.join(d, p['dname'] or '9.txt'), 'w').write(p['data'] + '\n')
                    r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=120, cwd=d)
                    self.assertEqual(r.stdout.strip(), p['answer'])

    def test_answers_recomputed_from_conditions(self):
        probs = [p for p in bank() if p['task'] == 9 and p['extra'].startswith('<!--spec:')]
        self.assertGreaterEqual(len(probs), 50)
        for p in probs:
            with self.subTest(p['id']):
                spec = json.loads(p['extra'][len('<!--spec:'):p['extra'].index('-->')])
                self.assertEqual(str(expected(spec, p['data'])), p['answer'])
                shown = [[int(x) for x in re.findall(r'<td>(\d+)</td>', r)] for r in re.findall(r'<tr>(<td>.*?)</tr>', p['extra'])]
                first = [list(map(int, l.split())) for l in p['data'].split('\n')[:len(shown)]]
                self.assertEqual(shown, first, 'превью совпадает с началом файла')
                self.assertEqual(len(p['text'].split('<li>')) - 1, len(spec['conds']))


if __name__ == '__main__':
    unittest.main()
