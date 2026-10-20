"""Задачи №8 банка: условия из скрытого описания (<!--spec:…-->) проверены здесь заново — своим рекурсивным
перебором без itertools и без строковых методов count/in, — и по ним пересчитывается ответ. Начало алфавитного
списка в тексте условия сверяется с перебором. Решение на Python из каждой задачи запускается и должно вывести ответ."""
import json, os, re, subprocess, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIG = '0123456789ABCDEF'


def bank():
    s = open(os.path.join(ROOT, 'content', 'ege.js'), encoding='utf-8').read()
    a = s.index('window.BANK = ') + len('window.BANK = ')
    return json.loads(s[a:s.index(';\n', a)])


def words(alph, k):
    """Все слова длины k по алфавиту — в порядке, в котором их пишет словарь (alph отсортирован)."""
    if k == 0:
        return [[]]
    return [[ch] + rest for ch in alph for rest in words(alph, k - 1)]


def perms(letters):
    """Различные перестановки мультимножества букв в алфавитном порядке."""
    if not letters:
        return [[]]
    out, used = [], []
    for i, ch in enumerate(sorted(letters)):
        if ch in used:
            continue
        used.append(ch)
        rest = sorted(letters)
        del rest[i]
        out += [[ch] + p for p in perms(rest)]
    return out


def objects(sp):
    if sp['kind'] == 'words':
        return words(sorted(sp['alph']), sp['k'])
    if sp['kind'] == 'nums':
        return [w for w in words(list(DIG[:sp['b']]), sp['k']) if w[0] != '0']
    return perms(list(sp['src']))


def count(w, test):
    n = 0
    for ch in w:
        if test(ch):
            n += 1
    return n


def holds(c, w):
    t = c['c']
    pairs = list(zip(w, w[1:]))
    if t in ('cnt', 'cntset'):
        n = count(w, (lambda ch: ch == c['x']) if t == 'cnt' else (lambda ch: ch in set(c['set'])))
        return {'==': n == c['v'], '<=': n <= c['v'], '>=': n >= c['v']}[c['op']]
    if t in ('first', 'last'):
        ch = w[0] if t == 'first' else w[-1]
        return (ch in set(c['set'])) != c['neg']
    if t == 'noadj':
        return all(not (a in c['set'] and b in c['set']) for a, b in pairs)
    if t == 'noafter':
        return all(not (a in c['set'] and b == c['x']) for a, b in pairs)
    if t == 'nonext':
        return all(not ({a, b} & {c['x']} and ((a == c['x'] and b in c['set']) or (b == c['x'] and a in c['set'])))
                   for a, b in pairs)
    if t == 'nosame':
        return all(a != b for a, b in pairs)
    if t == 'distinct':
        return all(w[i] not in w[:i] for i in range(len(w)))
    if t == 'sub':
        m = len(c['s'])
        found = any(w[i:i + m] == list(c['s']) for i in range(len(w) - m + 1))
        return found != c['neg']
    v = [DIG.index(ch) for ch in w]
    if t == 'altpar':
        return all((a + b) % 2 == 1 for a, b in zip(v, v[1:]))
    if t == 'nondec':
        return all(a <= b for a, b in zip(v, v[1:]))
    if t == 'sumdiv':
        return sum(v) % c['m'] == 0
    raise ValueError(t)


def solve(sp):
    objs = objects(sp)
    good = [i for i, w in enumerate(objs, 1) if all(holds(c, w) for c in sp['conds'])]
    q = sp['q']
    t = q['t']
    if t == 'count':
        return len(good)
    if t == 'first':
        return good[0]
    if t == 'last':
        return good[-1]
    if t == 'num_of':
        return [''.join(w) for w in objs].index(q['w']) + 1
    if t == 'word_at':
        return ''.join(objs[q['N'] - 1])
    if t == 'max_odd':
        return max(i for i in good if i % 2)
    if t == 'cnt_even':
        return len([i for i in good if i % 2 == 0])
    raise ValueError(t)


def probs():
    return [p for p in bank() if p['task'] == 8 and p['extra'].startswith('<!--spec:')]


class Task8BankTest(unittest.TestCase):
    def test_each_solution_prints_its_answer(self):
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        for p in [p for p in bank() if p['task'] == 8]:
            with self.subTest(p['id']):
                r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=300,
                                   encoding='utf-8', env=env)
                self.assertEqual(r.stdout.strip(), p['answer'])

    def test_answers_recomputed_from_spec(self):
        ps = probs()
        self.assertGreaterEqual(len(ps), 100)
        levels = {}
        for p in ps:
            levels[p['level']] = levels.get(p['level'], 0) + 1
            with self.subTest(p['id']):
                sp = json.loads(p['extra'][len('<!--spec:'):-len('-->')])
                self.assertEqual(str(solve(sp)), p['answer'])
                # буквы в условии — те же, что в алфавите решения
                if sp['kind'] == 'words':
                    self.assertEqual(sorted(sp['shown']), sorted(sp['alph']))
                    self.assertIn(', '.join(sp['shown']), p['text'])
                    self.assertIn(repr(sp['alph']), p['code'])
                # начало алфавитного списка в тексте совпадает с перебором
                head = re.findall(r'<br>(\d+)\. ([^<]+)', p['text'])
                if head:
                    objs = objects(sp)
                    self.assertEqual([(int(i), w) for i, w in head], [(i, ''.join(objs[i - 1])) for i in range(1, len(head) + 1)])
        self.assertEqual(levels, {'Б': 55, 'П': 30, 'В': 15})

    def test_titles_unique(self):
        titles = [p['title'] for p in probs()]
        self.assertEqual(len(titles), len(set(titles)))

    def test_guide_examples_print_what_they_say(self):
        # примеры кода в разборе задания 8: каждый запускается, и если в print стоит комментарий «# 346», вывод — 346
        s = open(os.path.join(ROOT, 'content', 'ege.js'), encoding='utf-8').read()
        a = s.index('\nE({\n  n: 8,')
        block = s[a:s.index('\nE({', a + 5)]
        codes = re.findall(r"c: R`([^`]*)`", block)
        self.assertGreaterEqual(len(codes), 20)
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        for c in codes:
            with self.subTest(c.split('\n')[0]):
                r = subprocess.run([sys.executable, '-c', c], capture_output=True, text=True, timeout=60, encoding='utf-8', env=env)
                self.assertEqual(r.stderr, '')
                said = re.findall(r'print\(.*\)\s*#\s*(?:.*= )?(\S+?)(?::|$)', c, re.M)
                if said:
                    self.assertEqual(r.stdout.split()[-1], said[-1])

    def test_rules(self):
        # КОЛОКОЛ: 7! / (3! · 2! · 2!) = 210 различных перестановок
        self.assertEqual(len(perms(list('КОЛОКОЛ'))), 210)
        # «Й не после гласной»: ОЙ — нельзя, ЙО — можно
        c = {'c': 'noafter', 'x': 'Й', 'set': 'АО'}
        self.assertFalse(holds(c, list('КОЙ')))
        self.assertTrue(holds(c, list('ЙОК')))
        # пятизначные восьмеричные: 7 · 8⁴
        self.assertEqual(len(objects({'kind': 'nums', 'b': 8, 'k': 5})), 7 * 8 ** 4)


if __name__ == '__main__':
    unittest.main()
