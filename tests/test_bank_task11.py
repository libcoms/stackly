"""Задачи №11 банка: ответ пересчитывается заново по скрытому описанию (<!--spec:…-->) — своим способом: мощность
алфавита складывается из частей, бит на символ подбирается циклом, «наибольшее» ищется перебором вверх, байты
считаются через остаток от деления. Мощность алфавита сверяется с текстом условия. Решение на Python из каждой
задачи запускается и должно вывести ответ."""
import json, os, subprocess, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BYTES = {'байт': 1, 'Кбайт': 1024, 'Мбайт': 1024 * 1024}
SIZE = {'LAT': 26, 'lat': 26, 'RUS': 33, 'RUS32': 32, 'DIG': 10}
WORDS = {'LAT': 'заглавные латинские буквы', 'lat': 'строчные латинские буквы', 'RUS': 'заглавные буквы русского алфавита',
         'RUS32': 'кроме Ё', 'DIG': 'десятичные цифры'}


def bank():
    s = open(os.path.join(ROOT, 'content', 'ege.js'), encoding='utf-8').read()
    a = s.index('window.BANK = ') + len('window.BANK = ')
    return json.loads(s[a:s.index(';\n', a)])


def power(al):
    n = 0
    for a in al:
        if isinstance(a, str):
            n += SIZE[a]
        elif a[0] == 'set':
            assert len(set(a[1])) == len(a[1]), 'символы набора не повторяются'
            n += len(a[1])
        else:
            n += a[1]
    return n


def bits_per(n):
    i = 0
    while 2 ** i < n:
        i += 1
    return i


def to_bytes(b):
    """Целое число байт, в которое помещаются b бит."""
    return b // 8 + (1 if b % 8 else 0)


def record(sp, L=None):
    L = sp['L'] if L is None else L
    b = L * bits_per(power(sp['al']))
    if sp.get('L2'):
        b += sp['L2'] * bits_per(power(sp['al2']))
    if sp.get('M') is not None:
        b += bits_per(sp['M'] + 1)
    return to_bytes(b) + sp.get('E', 0)


def largest(fits):
    k = 0
    while fits(k + 1):
        k += 1
    return k


def solve(sp):
    f = sp['f']
    if f in ('pw', 'multi', 'two'):
        total = sp['K'] * record(sp)
        assert total % BYTES[sp['u']] == 0
        return total // BYTES[sp['u']]
    if f == 'extra':
        assert sp['V'] % sp['K'] == 0
        return sp['V'] // sp['K'] - record(sp)
    lim = sp.get('X', 0) * BYTES.get(sp.get('u'), 1)
    if f in ('maxN', 'maxNbig'):
        i = largest(lambda d: sp['K'] * (to_bytes(sp['L'] * d) + sp.get('E', 0)) <= lim)
        return 2 ** i
    if f == 'maxL':
        return largest(lambda L: sp['K'] * record(sp, L) <= lim)
    if f == 'maxK':
        return largest(lambda n: n * record(sp) <= lim)
    if f == 'minL':
        L = 0
        while power(sp['al']) ** L < sp['need']:
            L += 1
        return sp['K'] * record(sp, L)
    raise ValueError(f)


def probs():
    return [p for p in bank() if p['task'] == 11 and p['extra'].startswith('<!--spec:')]


def spec(p):
    return json.loads(p['extra'][len('<!--spec:'):-len('-->')])


class Task11BankTest(unittest.TestCase):
    def test_each_solution_prints_its_answer(self):
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        for p in [p for p in bank() if p['task'] == 11]:
            with self.subTest(p['id']):
                r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=60,
                                   encoding='utf-8', env=env)
                self.assertEqual(r.stdout.strip(), p['answer'])

    def test_answers_recomputed_from_spec(self):
        ps = probs()
        self.assertGreaterEqual(len(ps), 100)
        for p in ps:
            with self.subTest(p['id']):
                a = solve(spec(p))
                self.assertEqual(str(a), p['answer'])
                self.assertGreater(a, 1)

    def test_alphabet_is_described_in_text(self):
        for p in probs():
            sp = spec(p)
            with self.subTest(p['id']):
                for al in (sp.get('al'), sp.get('al2')):
                    for a in al or []:
                        if isinstance(a, str):
                            if sp['f'] != 'two':
                                self.assertIn(WORDS[a], p['text'])
                        elif a[0] == 'set':
                            self.assertIn(', '.join(a[1]), p['text'])
                        else:
                            self.assertIn(f'{a[1]}-символьного', p['text'])
                for key in ('K', 'X', 'V', 'E', 'M', 'L', 'L2'):
                    if sp.get(key):
                        self.assertIn(str(sp[key]), p['text'])

    def test_levels_and_titles(self):
        ps = probs()
        levels = {}
        for p in ps:
            levels[p['level']] = levels.get(p['level'], 0) + 1
        self.assertEqual(levels, {'Б': 55, 'П': 30, 'В': 15})
        titles = [p['title'] for p in ps]
        self.assertEqual(len(titles), len(set(titles)))

    def test_rules(self):
        # 26 + 10 + 6 = 42 символа → 6 бит; пароль из 11 символов — 66 бит → 9 байт; +25 байт, 120 человек
        sp = {'f': 'pw', 'al': ['LAT', 'DIG', ['set', '!@#$%^']], 'L': 11, 'E': 25, 'K': 120, 'u': 'байт'}
        self.assertEqual(solve(sp), 4080)
        # округление до байта — для каждой записи отдельно: 3 символа по 3 бита = 9 бит → 2 байта, а не 9·K/8
        self.assertEqual(solve({'f': 'pw', 'al': [['n', 8]], 'L': 3, 'K': 8, 'u': 'байт'}), 16)
        # демоверсия: 64 идентификатора по 250 символов в 16 Кбайт → 8 бит, 256 символов
        self.assertEqual(solve({'f': 'maxN', 'L': 250, 'K': 64, 'X': 16, 'u': 'Кбайт'}), 256)


if __name__ == '__main__':
    unittest.main()
