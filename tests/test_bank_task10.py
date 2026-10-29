"""Задачи №10 банка (маски, формат 2027 года): ответ пересчитывается по скрытому описанию (<!--spec:…-->) своим
способом — адреса переводятся в 32-битные числа, маска строится сдвигом, без модуля ipaddress. Адреса из описания
сверяются с текстом условия. Решение на Python из каждой задачи запускается и должно вывести ответ."""
import json, os, re, subprocess, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bank():
    s = open(os.path.join(ROOT, 'content', 'ege.js'), encoding='utf-8').read()
    a = s.index('window.BANK = ') + len('window.BANK = ')
    return json.loads(s[a:s.index(';\n', a)])


def probs():
    return [p for p in bank() if p['task'] == 10 and '<!--spec:' in p['extra']]


def spec(p):
    return json.loads(re.search(r'<!--spec:(.*?)-->', p['extra']).group(1))


def num(ip):
    a, b, c, d = map(int, ip.split('.'))
    return ((a * 256 + b) * 256 + c) * 256 + d


def octets(x):
    return [(x >> s) & 255 for s in (24, 16, 8, 0)]


def mask(p):
    return (0xFFFFFFFF << (32 - p)) & 0xFFFFFFFF


def ones(x):
    return bin(x).count('1')


def solve(sp):
    f = sp['fam']
    if f in ('net', 'top', 'bcast', 'hosts'):
        m = mask(sp['p'])
        net = num(sp['ip']) & m
        last = net | (~m & 0xFFFFFFFF)
        return {'net': sum(octets(net)), 'top': sum(octets(last - 1)), 'bcast': sum(octets(last)),
                'hosts': last - net - 1}[f]
    if f in ('mask_byte', 'mask_sum_max', 'masks_count'):
        ok = [p for p in range(33) if num(sp['ip']) & mask(p) == num(sp['net'])]
        if f == 'mask_byte':
            assert len(ok) == 1, ok
            return octets(mask(ok[0]))[sp['byte'] - 1]
        if f == 'mask_sum_max':
            return sum(octets(mask(min(ok))))
        return len(ok)
    m = mask(sp['p'])
    net = num(sp['net'])
    assert net & m == net
    size = 1 << (32 - sp['p'])
    if f == 'ones':
        want = sp['mode'] == 'mod0'
        return sum(1 for x in range(net, net + size) if (ones(x) % sp['k'] == 0) == want)
    cmp_ = {'gt': lambda l, r: l > r, 'lt': lambda l, r: l < r, 'eq': lambda l, r: l == r}[sp['cmp']]
    return sum(1 for x in range(net + 1, net + size - 1) if cmp_(ones(x >> 16), ones(x & 0xFFFF)))


class Task10BankTest(unittest.TestCase):
    def test_each_solution_prints_its_answer(self):
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        for p in [p for p in bank() if p['task'] == 10]:
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

    def test_addresses_are_in_text(self):
        for p in probs():
            sp = spec(p)
            with self.subTest(p['id']):
                for key in ('ip', 'net'):
                    if key in sp:
                        self.assertIn(f'<b>{sp[key]}</b>', p['text'])
                if 'p' in sp:
                    self.assertIn('.'.join(map(str, octets(mask(sp['p'])))), p['text'])

    def test_levels_and_titles(self):
        ps = probs()
        levels = {}
        for p in ps:
            levels[p['level']] = levels.get(p['level'], 0) + 1
        self.assertEqual(levels, {'Б': 26, 'П': 16, 'В': 8})
        titles = [p['title'] for p in ps]
        self.assertEqual(len(titles), len(set(titles)))

    def test_rules(self):
        # демоверсия 2027: узел 192.168.159.86, маска 255.255.252.0 → сеть 192.168.156.0, сумма октетов 516
        self.assertEqual(solve({'fam': 'net', 'ip': '192.168.159.86', 'p': 22}), 516)
        # пример из условия ФИПИ: 231.32.255.131 и 255.255.240.0 дают сеть 231.32.240.0
        self.assertEqual(octets(num('231.32.255.131') & mask(20)), [231, 32, 240, 0])
        # /30: четыре адреса, узлам — два
        self.assertEqual(solve({'fam': 'hosts', 'ip': '10.0.0.5', 'p': 30}), 2)


if __name__ == '__main__':
    unittest.main()
