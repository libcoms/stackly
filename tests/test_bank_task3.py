"""Задачи №3 банка: справочники «Магазин» и «Товар» читаются из HTML-таблиц условия, движение — из файла задачи,
вопрос — из скрытого описания (<!--spec:…-->). Ответ пересчитывается своим способом: строки движения соединяются со
справочниками в одну таблицу (как ВПР), затем фильтр и агрегат. Проверяется и сама база: номера операций идут
подряд, даты внутри периода, остаток товара в магазине никогда не уходит в минус, превью совпадает с началом
файла. Решение на Python из каждой задачи запускается на её файле и должно вывести ответ."""
import json, os, re, subprocess, sys, tempfile, unittest
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bank():
    s = open(os.path.join(ROOT, 'content', 'ege.js'), encoding='utf-8').read()
    a = s.index('window.BANK = ') + len('window.BANK = ')
    return json.loads(s[a:s.index(';\n', a)])


def tables(html):
    """Все таблицы из HTML: список таблиц, таблица — список строк (первая — заголовок)."""
    out = []
    for t in re.findall(r'<table[^>]*>(.*?)</table>', html):
        out.append([re.findall(r'<t[hd]>(.*?)</t[hd]>', r) for r in re.findall(r'<tr>(.*?)</tr>', t)])
    return out


def joined(p):
    """Движение товаров, где к каждой строке подтянуты район магазина, отдел и фасовка товара."""
    shops, goods, preview = tables(p['extra'])
    district = {r[0]: r[1] for r in shops[1:]}
    info = {int(r[0]): (r[1], Fraction(r[4].replace(',', '.'))) for r in goods[1:]}
    lines = p['data'].split('\n')
    rows = []
    for line in lines[1:]:
        oid, date, shop, art, typ, q, price = line.split('\t')
        dept, per = info[int(art)]
        rows.append({'id': int(oid), 'day': int(date[:2]), 'date': date, 'shop': shop, 'art': int(art), 'typ': typ,
                     'q': int(q), 'price': int(price), 'district': district[shop], 'dept': dept, 'per': per})
    return rows, preview, lines


def solve(sp, rows):
    f = sp['f']
    lo, hi = sp.get('d1', 1), sp.get('d2', 99)
    if f == 'stock':
        lo = 1
    sel = [r for r in rows if lo <= r['day'] <= hi
           and ('R' not in sp or f == 'compare' or r['district'] == sp['R'])
           and ('D' not in sp or r['dept'] == sp['D'])
           and ('X' not in sp or r['art'] == sp['X'])]
    sold = [r for r in sel if r['typ'] == 'Продажа']
    came = [r for r in sel if r['typ'] == 'Поступление']

    def top(key, val):
        acc = {}
        for r in sold:
            acc[key(r)] = acc.get(key(r), 0) + val(r)
        best = sorted(acc.items(), key=lambda kv: -kv[1])
        assert len(best) == 1 or best[0][1] > best[1][1], 'наибольшее значение должно быть одно'
        return best[0][0]

    if f in ('qty', 'weight'):
        return sum(r['q'] * r['per'] for r in sold)
    if f in ('packsIn',):
        return sum(r['q'] for r in came)
    if f == 'dates':
        return sum(r['q'] for r in sold)
    if f == 'revenue':
        return sum(r['q'] * r['price'] for r in sold)
    if f == 'change':
        return sum(r['q'] for r in came) - sum(r['q'] for r in sold)
    if f == 'profit':
        return sum(r['q'] * r['price'] for r in sold) - sum(r['q'] * r['price'] for r in came)
    if f == 'stock':
        return sum(r['q'] * r['per'] for r in came) - sum(r['q'] * r['per'] for r in sold)
    if f == 'maxShop':
        return top(lambda r: r['shop'], lambda r: r['q'])
    if f == 'topProduct':
        return top(lambda r: r['art'], lambda r: r['q'] * r['price'])
    if f == 'bestDay':
        return top(lambda r: r['day'], lambda r: r['q'] * r['price'])
    if f == 'compare':
        a = sum(r['q'] * r['price'] for r in sold if r['district'] == sp['R'])
        b = sum(r['q'] * r['price'] for r in sold if r['district'] == sp['R2'])
        return a - b
    raise ValueError(f)


def probs():
    return [p for p in bank() if p['task'] == 3 and p['extra'].startswith('<!--spec:')]


def spec(p):
    e = p['extra']
    return json.loads(e[len('<!--spec:'):e.index('-->')])


class Task3BankTest(unittest.TestCase):
    def test_each_solution_prints_its_answer(self):
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        with tempfile.TemporaryDirectory() as d:
            for p in [p for p in bank() if p['task'] == 3]:
                with self.subTest(p['id']):
                    open(os.path.join(d, p['dname']), 'w', encoding='utf-8').write(p['data'] + '\n')
                    r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=60,
                                       cwd=d, encoding='utf-8', env=env)
                    self.assertEqual(r.stdout.strip(), p['answer'])

    def test_answers_recomputed_from_tables(self):
        ps = probs()
        self.assertGreaterEqual(len(ps), 100)
        for p in ps:
            with self.subTest(p['id']):
                a = solve(spec(p), joined(p)[0])
                if not isinstance(a, str):                  # ID магазина — строка, остальное — числа
                    a = Fraction(a)
                    self.assertEqual(a.denominator, 1, 'ответ должен быть целым')
                    a = a.numerator
                    self.assertNotEqual(a, 0)
                self.assertEqual(str(a), p['answer'])

    def test_database_is_consistent(self):
        for p in probs():
            with self.subTest(p['id']):
                rows, preview, lines = joined(p)
                self.assertEqual([r['id'] for r in rows], list(range(1, len(rows) + 1)))
                self.assertEqual(preview[0], lines[0].split('\t'))
                for row, line in zip(preview[1:], lines[1:]):
                    self.assertEqual(row, line.split('\t'))
                m = re.search(r'с 1 по (\d+) (\w+) 2026', p['text'])
                last = int(m.group(1))
                stock = {}
                for r in rows:
                    self.assertTrue(1 <= r['day'] <= last)
                    k = (r['shop'], r['art'])
                    stock[k] = stock.get(k, 0) + (r['q'] if r['typ'] == 'Поступление' else -r['q'])
                    self.assertGreaterEqual(stock[k], 0, f'продано больше, чем было: {k}')
                self.assertEqual(sorted(rows, key=lambda r: r['day']), rows, 'строки идут по датам')

    def test_question_mentions_its_filters(self):
        for p in probs():
            sp = spec(p)
            with self.subTest(p['id']):
                if 'R' in sp:
                    self.assertIn(sp['R'][:-2] + 'ого района', p['text'])
                if 'D' in sp:
                    self.assertIn(f'отдела «{sp["D"]}»', p['text'])
                if 'X' in sp:
                    name = [r for r in tables(p['extra'])[1] if r[0] == str(sp['X'])][0][2]
                    self.assertIn(f'«{name}»', p['text'])
                if 'd1' in sp:
                    self.assertIn(f'с {sp["d1"]} по {sp["d2"]} ', p['text'])

    def test_levels_and_titles(self):
        ps = probs()
        levels = {}
        for p in ps:
            levels[p['level']] = levels.get(p['level'], 0) + 1
        self.assertEqual(levels, {'Б': 55, 'П': 30, 'В': 15})
        titles = [p['title'] for p in ps]
        self.assertEqual(len(titles), len(set(titles)))

    def test_rules(self):
        # задача 3-1 банка: яйца Заречного района считаются штуками — упаковки × 10
        p = [p for p in bank() if p['id'] == '3-1'][0]
        lines = p['data'].split('\n')[1:]
        shops = {'M1', 'M3'}
        eggs = {2, 5}
        total = sum(int(q) * 10 for _, _, shop, art, q, typ in (l.split('\t') for l in lines)
                    if shop in shops and int(art) in eggs and typ.strip() == 'Продажа')
        self.assertEqual(str(total), p['answer'])


if __name__ == '__main__':
    unittest.main()
