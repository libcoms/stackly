"""Задачи №5 банка: правило из скрытого описания (<!--spec:…-->) реализовано здесь заново — арифметикой,
без строк, как в генераторе, — и по нему пересчитываются ответ (на вдвое большем диапазоне N) и пример из
текста условия. Решение на Python из каждой задачи запускается и должно вывести ответ."""
import json, os, re, subprocess, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bank():
    s = open(os.path.join(ROOT, 'content', 'ege.js'), encoding='utf-8').read()
    a = s.index('window.BANK = ') + len('window.BANK = ')
    return json.loads(s[a:s.index(';\n', a)])


def ndig(x, b):
    """Число цифр записи x в системе b (у нуля — одна)."""
    k = 1
    while x >= b:
        x //= b; k += 1
    return k


def ones(x):
    c = 0
    while x:
        c += x & 1; x >>= 1
    return c


def attach(left, core, core_len, right):
    """Двоичная склейка строк битов: left + core + right, где left/right — строки из 0/1 как в условии."""
    v = int(left, 2) if left else 0
    v = (v << core_len) | core
    return (v << len(right)) | (int(right, 2) if right else 0)


def R(sp, n):
    f = sp['f']
    if f in ('par', 'ones'):
        key = n % 2 if f == 'par' else ones(n) % 2
        l, r = sp['rules'][key]
        return attach(l, n, n.bit_length(), r)
    if f == 'sumbit':
        v = n
        for _ in range(sp['k']):
            v = (v << 1) | (ones(v) % 2)
        return v
    if f == 'mod':
        b, m, k, c = sp['b'], sp['m'], sp['k'], sp['c']
        if n % m == 0:
            kk = min(k, ndig(n, b))                       # последние k цифр (или вся запись, если она короче)
            return n * b ** kk + n % b ** kk
        v = (n % m) * c
        return n * b ** ndig(v, b) + v
    if f == 'inv':
        L = n.bit_length()
        cond = {'even': n % 2 == 0, 'odd': n % 2 == 1, 'ones_odd': ones(n) % 2 == 1, 'always': True}[sp['when']]
        core = (1 << L) - 1 - n if cond else n             # инверсия; ведущие нули исчезают сами
        l, r = sp['add']
        return attach(l, core, max(1, core.bit_length()), r)
    if f == 'digits':
        d, x = [], n
        while x:
            d.append(x % 10); x //= 10
        d = d[::-1]
        op = (lambda a, b: a + b) if sp['op'] == 'sum' else (lambda a, b: a * b)
        pairs = [(0, 1), (1, 2)] if sp['len'] == 3 else [(0, 1), (2, 3)]
        v = sorted(op(d[i], d[j]) for i, j in pairs)
        if sp['order'] == 'desc':
            v.reverse()
        return v[0] * 10 ** ndig(v[1], 10) + v[1]
    raise ValueError(f)


def solve(sp, q, hi=40000):
    ns = range(10 ** (sp['len'] - 1), 10 ** sp['len']) if sp['f'] == 'digits' else range(1, hi)
    t, K, A, B = q['t'], q.get('K'), q.get('a'), q.get('b')
    rs = [(n, R(sp, n)) for n in ns]
    if t == 'countR':
        return len({r for _, r in rs if A <= r <= B})
    if t == 'countN':
        return sum(A <= r <= B for _, r in rs)
    if t == 'countN:R=':
        return sum(r == K for _, r in rs)
    test = {'>': lambda r: r > K, '>=': lambda r: r >= K, '<': lambda r: r < K, '<=': lambda r: r <= K, '=': lambda r: r == K}
    m = re.match(r'(min|max)(R|N:R)(>=|<=|>|<|=)$', t)
    agg, what, cmp = m.groups()
    vals = [r if what == 'R' else n for n, r in rs if test[cmp](r)]
    return (min if agg == 'min' else max)(vals)


class Task5BankTest(unittest.TestCase):
    def test_each_solution_prints_its_answer(self):
        for p in [p for p in bank() if p['task'] == 5]:
            with self.subTest(p['id']):
                r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=300)
                self.assertEqual(r.stdout.strip(), p['answer'])

    def test_answers_and_examples_recomputed_from_rule(self):
        probs = [p for p in bank() if p['task'] == 5 and p['extra'].startswith('<!--spec:')]
        self.assertGreaterEqual(len(probs), 100)
        for p in probs:
            with self.subTest(p['id']):
                d = json.loads(p['extra'][len('<!--spec:'):-len('-->')])
                sp, q = d['spec'], d['q']
                self.assertEqual(str(solve(sp, q)), p['answer'])
                n = int(re.search(r'N = (\d+)', p['text']).group(1))
                r = int(re.search(r'R = (\d+)', p['text']).group(1))
                self.assertEqual(n, d['ex'])
                self.assertEqual(R(sp, n), r, 'пример в условии')

    def test_mod_rule_reads_last_digits(self):
        # 12 = 1100₂, делится на 3 → дописываем две последние цифры «00»: 110000₂ = 48
        self.assertEqual(R({'f': 'mod', 'b': 2, 'm': 3, 'k': 2, 'c': 5}, 12), 48)
        # 7 = 111₂, инверсия даёт 0 → «0», слева 1, справа 1: 101₂ = 5
        self.assertEqual(R({'f': 'inv', 'when': 'always', 'add': ['1', '1']}, 7), 5)


if __name__ == '__main__':
    unittest.main()
