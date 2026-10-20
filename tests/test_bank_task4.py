"""Задачи №4 банка: ответ пересчитывается заново по скрытому описанию (<!--spec:…-->) — своим способом: вместо
перебора длин с жадной раскладкой строятся все возможные деревья кода под свободными ветками (какие наборы длин
листьев там помещаются), длина сообщения — тем же обходом, без алгоритма Хаффмана. Известные кодовые слова
сверяются с текстом условия. Решение на Python из каждой задачи запускается и должно вывести ответ."""
import json, os, subprocess, sys, unittest
from functools import lru_cache
from itertools import product

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bank():
    s = open(os.path.join(ROOT, 'content', 'ege.js'), encoding='utf-8').read()
    a = s.index('window.BANK = ') + len('window.BANK = ')
    return json.loads(s[a:s.index(';\n', a)])


def splits(k, parts):
    """Все способы разложить k по parts корзинам (с нулями)."""
    if parts == 1:
        yield (k,)
        return
    for a in range(k + 1):
        for rest in splits(k - a, parts - 1):
            yield (a,) + rest


def merge(sets):
    out = {()}
    for s in sets:
        out = {tuple(sorted(x + y)) for x in out for y in s}
    return out


@lru_cache(maxsize=None)
def free_tree(k, b):
    """Наборы глубин листьев (от корня поддерева) для k слов в пустом поддереве."""
    if k == 0:
        return frozenset({()})
    if k == 1:
        return frozenset({(0,)})
    out = set()
    for sp in splits(k, b):
        if sum(1 for x in sp if x) < 2:         # всё в одну ветку — то же дерево, только глубже: не нужно
            continue
        for m in merge(free_tree(x, b) for x in sp):
            out.add(tuple(d + 1 for d in m))
    return frozenset(out)


def options(v, k, fixed, b):
    """Наборы длин k новых слов, которые можно разместить под узлом v (fixed — занятые слова)."""
    if v in fixed:
        return {()} if k == 0 else set()
    if any(c.startswith(v) for c in fixed):
        out = set()
        for sp in splits(k, b):
            out |= merge(options(v + str(d), x, fixed, b) for d, x in zip(range(b), sp))
        return out
    return {tuple(d + len(v) for d in m) for m in free_tree(k, b)}


def min_cost(weights, fixed, b):
    ws = sorted(weights, reverse=True)
    return min(sum(w * L for w, L in zip(ws, m)) for m in options('', len(ws), fixed, b))


def solve(sp):
    f, b = sp['f'], sp.get('b', 2)
    fixed = list(sp.get('fix', {}).values())
    if f in ('short', 'short2'):
        need = len(sp.get('rest', []))
        for L in range(1, 12):
            for p in product('012'[:b], repeat=L):
                w = ''.join(p)
                if w in fixed or any(w.startswith(c) or c.startswith(w) for c in fixed):
                    continue
                if need == 0 or options('', need, fixed + [w], b):
                    return w
    if f == 'count':
        return sum(1 for p in product('012'[:b], repeat=sp['L'])
                   if not any(''.join(p).startswith(c) or c.startswith(''.join(p)) for c in fixed))
    if f == 'msg':
        cnt = {}
        for ch in sp['word']:
            cnt[ch] = cnt.get(ch, 0) + 1
        return min_cost(cnt.values(), [], 2)
    if f in ('sumAll', 'sumRest', 'sumBig', 'tern', 'ternFix'):
        return min_cost([1] * sp['k'], fixed, b) + (sum(map(len, fixed)) if sp['q'] == 'all' else 0)
    if f in ('msgFix', 'ternMsg'):
        cnt = sp['cnt']
        rest = [n for ch, n in cnt.items() if ch not in sp['fix']]
        return min_cost(rest, fixed, b) + sum(cnt[ch] * len(w) for ch, w in sp['fix'].items())
    raise ValueError(f)


def probs():
    return [p for p in bank() if p['task'] == 4 and p['extra'].startswith('<!--spec:')]


def spec(p):
    return json.loads(p['extra'][len('<!--spec:'):-len('-->')])


class Task4BankTest(unittest.TestCase):
    def test_each_solution_prints_its_answer(self):
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        for p in [p for p in bank() if p['task'] == 4]:
            with self.subTest(p['id']):
                r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=120,
                                   encoding='utf-8', env=env)
                self.assertEqual(r.stdout.strip(), p['answer'])

    def test_answers_recomputed_from_spec(self):
        ps = probs()
        self.assertGreaterEqual(len(ps), 100)
        for p in ps:
            with self.subTest(p['id']):
                self.assertEqual(str(solve(spec(p))), p['answer'])

    def test_known_codes_are_prefix_free_and_in_text(self):
        for p in probs():
            sp = spec(p)
            with self.subTest(p['id']):
                fixed = list(sp.get('fix', {}).values())
                for a in fixed:
                    self.assertIn(f'<code>{a}</code>', p['text'])
                    for c in fixed:
                        self.assertTrue(a == c or not c.startswith(a), f'{a} — начало {c}')
                    self.assertTrue(set(a) <= set('012'[:sp.get('b', 2)]))
                if 'word' in sp:
                    self.assertIn(sp['word'], p['text'])
                for ch, n in sp.get('cnt', {}).items():
                    self.assertIn(f'{ch} ({n} раз', p['text'])
                if sp.get('b') == 3:
                    self.assertIn('троичный', p['text'])

    def test_levels_and_titles(self):
        ps = probs()
        levels = {}
        for p in ps:
            levels[p['level']] = levels.get(p['level'], 0) + 1
        self.assertEqual(levels, {'Б': 55, 'П': 30, 'В': 15})
        titles = [p['title'] for p in ps]
        self.assertEqual(len(titles), len(set(titles)))
        ids = [p['id'] for p in ps]
        self.assertEqual(len(ids), len(set(ids)))

    def test_rules(self):
        # задачи 4-1 и 4-2 банка, решённые вручную: 18 и 12 (свободны 11, 010, 100 — четвёртой букве ветку 11 делим)
        self.assertEqual(solve({'f': 'sumAll', 'fix': {'А': '1', 'Б': '010', 'В': '011'}, 'k': 3, 'q': 'all'}), 18)
        self.assertEqual(solve({'f': 'sumRest', 'fix': {'А': '00', 'Б': '011', 'В': '101'}, 'k': 4, 'q': 'rest'}), 12)
        p = [p for p in bank() if p['id'] == '4-2'][0]
        self.assertEqual(p['answer'], '12')
        # КАРАКАТИЦА: А 4, К 2, Р Т И Ц по 1 → слияния 2, 2, 4, 6, 10 → 24 знака
        self.assertEqual(solve({'f': 'msg', 'word': 'КАРАКАТИЦА'}), 24)
        # свободна только ветка 10: её нельзя отдать Д целиком, если ещё нужен код для Е
        fix = {'А': '110', 'Б': '01', 'В': '00', 'Г': '111'}
        self.assertEqual(solve({'f': 'short', 'fix': fix}), '10')
        self.assertEqual(solve({'f': 'short2', 'fix': fix, 'rest': ['Е']}), '100')


if __name__ == '__main__':
    unittest.main()
