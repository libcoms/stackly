"""Задачи №2 банка: формулу разбираем прямо из текста условия (свой разбор, независимый от генератора),
таблицу — из HTML, и полным перебором проверяем, что подходит ровно одно соответствие столбцов — записанное в ответе."""
import itertools, json, os, re, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bank():
    s = open(os.path.join(ROOT, 'content', 'ege.js'), encoding='utf-8').read()
    a = s.index('window.BANK = ') + len('window.BANK = ')
    return json.loads(s[a:s.index(';\n', a)])


def parse(src):
    """Старшинство: ¬, затем ∧, ∨, →, ≡ (как принято в ЕГЭ). → правоассоциативна."""
    toks = re.findall(r'[wxyz]|[¬∧∨→≡()]', src.replace('F =', ''))
    pos = [0]
    peek = lambda: toks[pos[0]] if pos[0] < len(toks) else None
    def take(t=None):
        tok = toks[pos[0]]; assert t is None or tok == t, (src, tok, t); pos[0] += 1; return tok
    def atom():
        t = take()
        if t == '¬':
            a = atom(); return lambda e: 1 - a(e)
        if t == '(':
            a = eqv(); take(')'); return a
        return lambda e, v=t: e[v]
    def chain(sub, op, f):
        a = sub()
        while peek() == op:
            take(); b = sub(); a = (lambda x, y: lambda e: f(x(e), y(e)))(a, b)
        return a
    conj = lambda: chain(atom, '∧', lambda a, b: a & b)
    disj = lambda: chain(conj, '∨', lambda a, b: a | b)
    def imp():
        a = disj()
        if peek() == '→':
            take(); b = imp(); return lambda e: (1 - a(e)) | b(e)
        return a
    eqv = lambda: chain(imp, '≡', lambda a, b: int(a == b))
    f = eqv()
    assert pos[0] == len(toks), ('лишние символы', src)
    return f


def solve(p):
    src = re.search(r'<span class="f">(.*?)</span>', p['text']).group(1)
    f = parse(src)
    vs = sorted(set(re.findall(r'[wxyz]', src)))
    rows = [re.findall(r'<td>(.*?)</td>', r) for r in re.findall(r'<tr>(<td>.*?)</tr>', p['extra'])]
    frag, fv = [[None if c == '' else int(c) for c in r[:-1]] for r in rows], [int(r[-1]) for r in rows]
    holes = [(i, j) for i, r in enumerate(frag) for j, c in enumerate(r) if c is None]
    found = set()
    for fill in itertools.product([0, 1], repeat=len(holes)):
        t = [list(r) for r in frag]
        for (i, j), v in zip(holes, fill):
            t[i][j] = v
        if len({tuple(r) for r in t}) < len(t):
            continue
        for names in itertools.permutations(vs):
            if all(f(dict(zip(names, r))) == x for r, x in zip(t, fv)):
                found.add(''.join(names))
    return found


class Task2BankTest(unittest.TestCase):
    def test_parser_precedence(self):
        # ¬x ∨ y → z ≡ w  читается как  ((¬x ∨ y) → z) ≡ w
        f = parse('¬x ∨ y → z ≡ w')
        for x, y, z, w in itertools.product([0, 1], repeat=4):
            self.assertEqual(f(dict(x=x, y=y, z=z, w=w)), int((((1 - x) | y) <= z) == w))

    def test_every_task2_problem_has_unique_correct_answer(self):
        probs = [p for p in bank() if p['task'] == 2 and 'class="f"' in p['text'] and 'class="tt"' in p['extra']]
        self.assertGreaterEqual(len(probs), 50)
        for p in probs:
            with self.subTest(p['id']):
                self.assertEqual(solve(p), {p['answer']})


if __name__ == '__main__':
    unittest.main()
