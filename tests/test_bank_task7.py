"""Задачи №7 банка: ответ пересчитывается заново по скрытому описанию (<!--spec:…-->) — своими формулами, без
log2 и bit_length: глубина цвета подбирается циклом, «наибольшее» ищется перебором вверх до первого непомещения.
Числа из описания сверяются с текстом условия. Решение на Python из каждой задачи запускается и должно вывести ответ."""
import json, os, subprocess, sys, unittest
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BYTES = {'байт': 1, 'Кбайт': 1024, 'Мбайт': 1024 * 1024, 'Гбайт': 1024 * 1024 * 1024}


def bank():
    s = open(os.path.join(ROOT, 'content', 'ege.js'), encoding='utf-8').read()
    a = s.index('window.BANK = ') + len('window.BANK = ')
    return json.loads(s[a:s.index(';\n', a)])


def depth(n):
    """Сколько бит нужно, чтобы различить n цветов (значений)."""
    i = 0
    while 2 ** i < n:
        i += 1
    return i


def bits_of(x, unit):
    return x * BYTES[unit] * 8


def largest(fits):
    """Наибольшее k ≥ 1, для которого fits(k) ещё верно (fits монотонно: сначала да, потом нет)."""
    k = 0
    while fits(k + 1):
        k += 1
    return k


def up(x):
    x = Fraction(x)
    return -(-x.numerator // x.denominator)


def solve(sp):
    f = sp['f']
    i = sp['i'] if 'i' in sp else depth(sp['N']) if 'N' in sp else None
    if f == 'img':
        return Fraction(sp['W'] * sp['H'] * i * sp['n'], 8 * BYTES[sp['u']])
    if f in ('imgN', 'compress'):
        keep = Fraction(100 - sp.get('p', 0), 100)
        return 2 ** largest(lambda d: sp['W'] * sp['H'] * d * keep <= bits_of(sp['V'], sp['vu']))
    if f == 'snd':
        return up(Fraction(sp['fr'] * sp['i'] * sp['k'] * sp['t'], 8 * BYTES[sp['u']]))
    if f == 'sndT':
        sec = Fraction(bits_of(sp['X'], sp['u']), sp['fr'] * sp['i'] * sp['k'])
        return sec / 60 if sp['tu'] == 'мин' else sec
    if f == 'send':
        if sp['q'] == 'time':
            return Fraction(bits_of(sp['X'], sp['u']), sp['v'])
        return Fraction(sp['v'] * sp['t'], 8 * BYTES[sp['u']])
    if f == 'send2':
        t = Fraction(bits_of(sp['X'], 'Кбайт'), sp['v1'])
        return t * sp['v2'] / bits_of(1, 'Кбайт')
    if f == 'imgK':
        photo = sp['W'] * sp['H'] * i + 8 * sp.get('svc', 0)
        return largest(lambda n: n * photo <= bits_of(sp['X'], sp['u']))
    if f == 'imgSvc':
        return 2 ** largest(lambda d: sp['K'] * (sp['W'] * sp['H'] * d + 8 * sp['svc']) <= bits_of(sp['X'], sp['u']))
    if f == 'recode':
        i1, i2 = depth(sp['N1']), depth(sp['N2'])
        pixels = Fraction(bits_of(sp['D'], 'Кбайт'), i1 - i2)
        assert pixels.denominator == 1
        return pixels * (i1 if sp['q'] == 'old' else i2) / bits_of(1, 'Кбайт')
    if f in ('redig', 'redig2'):
        k = Fraction(sp['k2'], sp['k1']) * Fraction(sp['rf']) * Fraction(sp['ff'])
        return sp['X'] * k if f == 'redig' else sp['T1'] * k / Fraction(sp['c'])
    if f == 'sendSnd':
        return up(Fraction(sp['fr'] * sp['i'] * sp['k'] * sp['t'], sp['v']))
    if f == 'video':
        sec = sp['F'] * sp['W'] * sp['H'] * i + (sp['fr'] * sp['si'] * sp['k'] if 'fr' in sp else 0)
        if sp['q'] == 'size':
            return up(Fraction(sec * sp['t'], bits_of(1, 'Мбайт')))
        return largest(lambda t: t * sec <= bits_of(sp['X'], sp['u']))
    if f == 'stream':
        keep = Fraction(100 - sp['p'], 100)
        return 2 ** largest(lambda d: sp['W'] * sp['H'] * d * keep <= sp['v'] * sp['T'])
    if f == 'sndMax':
        room = bits_of(sp['X'], sp['u']) - 8 * sp['hdr']
        return room // (sp['i'] * sp['k'] * sp['t'])
    raise ValueError(f)


def probs():
    return [p for p in bank() if p['task'] == 7 and p['extra'].startswith('<!--spec:')]


def spec(p):
    return json.loads(p['extra'][len('<!--spec:'):-len('-->')])


class Task7BankTest(unittest.TestCase):
    def test_each_solution_prints_its_answer(self):
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        for p in [p for p in bank() if p['task'] == 7]:
            with self.subTest(p['id']):
                r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=60,
                                   encoding='utf-8', env=env)
                self.assertEqual(r.stdout.strip(), p['answer'])

    def test_answers_recomputed_from_spec(self):
        ps = probs()
        self.assertGreaterEqual(len(ps), 100)
        levels = {}
        for p in ps:
            levels[p['level']] = levels.get(p['level'], 0) + 1
            with self.subTest(p['id']):
                sp = spec(p)
                a = Fraction(solve(sp))
                self.assertEqual(a.denominator, 1, 'ответ должен быть целым')
                self.assertEqual(str(a.numerator), p['answer'])
                self.assertGreater(a, 1)

    def test_numbers_from_spec_are_in_text(self):
        for p in probs():
            sp = spec(p)
            with self.subTest(p['id']):
                if 'W' in sp:
                    self.assertIn(f"{sp['W']} × {sp['H']}", p['text'])
                for key in ('N', 'X', 'V', 'D', 'K', 'svc', 'hdr'):
                    if sp.get(key):
                        self.assertIn(str(sp[key]), p['text'])
                if 'u' in sp:
                    self.assertIn(sp['u'], p['text'])
                if sp['f'] in ('snd', 'sendSnd', 'video') and sp.get('fr'):
                    self.assertIn('кГц', p['text'])

    def test_rounding_is_asked_where_needed(self):
        # где ответ округлён вверх, условие обязано сказать «не меньшее»
        for p in probs():
            sp = spec(p)
            if sp['f'] not in ('snd', 'sendSnd', 'video') or sp.get('q') == 'time':
                continue
            exact = {'snd': lambda: Fraction(sp['fr'] * sp['i'] * sp['k'] * sp['t'], bits_of(1, 'Мбайт')),
                     'sendSnd': lambda: Fraction(sp['fr'] * sp['i'] * sp['k'] * sp['t'], sp['v']),
                     'video': lambda: Fraction(1, 3)}[sp['f']]()
            with self.subTest(p['id']):
                if exact.denominator != 1:
                    self.assertIn('не меньшее', p['text'])

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
        # 4096 цветов — 12 бит, 4097 — уже 13; 1024 × 768 × 12 бит = 1152 Кбайт
        self.assertEqual(depth(4096), 12)
        self.assertEqual(depth(4097), 13)
        self.assertEqual(solve({'f': 'img', 'W': 1024, 'H': 768, 'N': 4096, 'n': 1, 'u': 'Кбайт'}), 1152)
        # стерео, 48 кГц, 24 бит, 2 минуты — 33 Мбайт с округлением вверх
        self.assertEqual(solve({'f': 'snd', 'fr': 48000, 'i': 24, 'k': 2, 't': 120, 'u': 'Мбайт'}), 33)
        # сжатие на 25%: до сжатия места больше, а не меньше
        base = {'f': 'compress', 'W': 1024, 'H': 1024, 'V': 768, 'vu': 'Кбайт'}
        self.assertEqual(solve({**base, 'p': 0}), 2 ** 6)
        self.assertEqual(solve({**base, 'p': 25}), 2 ** 8)


if __name__ == '__main__':
    unittest.main()
