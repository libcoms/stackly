"""Задачи №13 банка (количество программ, формат 2027 года): ответ пересчитывается по скрытому описанию
(<!--spec:…-->) своим способом — динамикой вперёд по числам (сколько программ приводит в каждое число), а не
рекурсией, как в решении. Команды и числа из описания сверяются с текстом условия. Решение на Python из каждой
задачи запускается и должно вывести ответ."""
import json, os, re, subprocess, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bank():
    s = open(os.path.join(ROOT, 'content', 'ege.js'), encoding='utf-8').read()
    a = s.index('window.BANK = ') + len('window.BANK = ')
    return json.loads(s[a:s.index(';\n', a)])


def probs():
    return [p for p in bank() if p['task'] == 13 and '<!--spec:' in p['extra']]


def spec(p):
    return json.loads(re.search(r'<!--spec:(.*?)-->', p['extra']).group(1))


def step(c, x):
    k, a = c
    if k == 'swap':
        d = str(x)
        return int(d[:-2] + d[-1] + d[-2]) if len(d) >= 2 and d[-2] < d[-1] else None
    return {'add': x + a, 'mul': x * a, 'sub': x - a, 'div': x // a}[k]


def ways(cmds, a, b, ban):
    """Динамика вперёд: cnt[x] — сколько программ приводят из a в x, не заходя в запретные числа и за b."""
    up = cmds[0][0] in ('add', 'mul', 'swap')
    order = range(a, b + 1) if up else range(a, b - 1, -1)
    cnt = {a: 0 if a in ban else 1}
    for x in order:
        c = cnt.get(x, 0)
        if not c or x == b:
            continue
        for cmd in cmds:
            y = step(cmd, x)
            if y is None or y == x or y in ban or ((y > b) if up else (y < b)):
                continue
            cnt[y] = cnt.get(y, 0) + c
    return cnt.get(b, 0)


def solve(sp):
    cmds = [tuple(c) for c in sp['cmds']]
    if sp['fam'] == 'results':
        cur = {sp['a']}
        for _ in range(sp['n']):
            cur = {step(c, x) for x in cur for c in cmds} - {None}
        return len(cur)
    pts = [sp['a'], *sp['need'], sp['b']]
    r = 1
    for u, v in zip(pts, pts[1:]):
        r *= ways(cmds, u, v, set(sp['ban']))
    return r


class Task13BankTest(unittest.TestCase):
    def test_each_solution_prints_its_answer(self):
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        for p in [p for p in bank() if p['task'] == 13]:
            with self.subTest(p['id']):
                r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=60,
                                   encoding='utf-8', env=env)
                self.assertEqual(r.stdout.strip(), p['answer'])

    def test_answers_recomputed_from_spec(self):
        ps = probs()
        self.assertGreaterEqual(len(ps), 50)
        for p in ps:
            with self.subTest(p['id']):
                self.assertEqual(str(solve(spec(p))), p['answer'])

    def test_numbers_and_commands_are_in_text(self):
        names = {'add': 'Прибавь {}', 'mul': 'Умножь на {}', 'sub': 'Вычти {}', 'div': 'Раздели нацело на {}', 'swap': 'Поменяй местами'}
        for p in probs():
            sp = spec(p)
            with self.subTest(p['id']):
                for k, a in sp['cmds']:
                    self.assertIn(names[k].format(a), p['text'])
                self.assertRegex(p['text'], f'(исходном числе|исходного числа) {sp["a"]} ')
                for key in ('b', 'n'):
                    if key in sp:
                        self.assertIn(str(sp[key]), p['text'])
                for x in sp.get('need', []):
                    self.assertIn(f'содержит число {x}', p['text'])
                for x in sp.get('ban', []):
                    self.assertIn(f'не содержит числа {x}', p['text'])

    def test_levels_and_titles(self):
        ps = probs()
        levels = {}
        for p in ps:
            levels[p['level']] = levels.get(p['level'], 0) + 1
        self.assertEqual(levels, {'Б': 20, 'П': 20, 'В': 10})
        titles = [p['title'] for p in ps]
        self.assertEqual(len(titles), len(set(titles)))

    def test_rules(self):
        swap = [['add', 1], ['swap', 0]]
        # демоверсия 2027: команды «Прибавь 1» и «Поменяй местами», из 100 в 141 — 16 программ
        self.assertEqual(solve({'fam': 'swap', 'cmds': swap, 'a': 100, 'b': 141, 'need': [], 'ban': []}), 16)
        # пример из условия демоверсии: программа ABA из 13 даёт траекторию 14, 41, 42
        self.assertEqual([step(('add', 1), 13), step(('swap', 0), 14), step(('add', 1), 41)], [14, 41, 42])
        self.assertIsNone(step(('swap', 0), 41))
        # классика: +1, ×2 из 1 в 10 — 14 программ
        self.assertEqual(solve({'fam': 'basic', 'cmds': [['add', 1], ['mul', 2]], 'a': 1, 'b': 10, 'need': [], 'ban': []}), 14)


if __name__ == '__main__':
    unittest.main()
