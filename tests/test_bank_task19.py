"""Задачи №19–21 банка: игру из скрытого описания (<!--spec:…-->) решаем здесь иначе, чем в генераторе, —
послойной классификацией позиций (W1, L1, W2, L2) без рекурсии — и сверяем ответы всех трёх номеров.
Заодно проверяем, что условие игры (в задаче 19 комплекта) называет те же порог, кучи и диапазон S,
что 20 и 21 ссылаются на игру из 19, и запускаем решения из задач."""
import json, os, re, subprocess, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bank():
    s = open(os.path.join(ROOT, 'content', 'ege.js'), encoding='utf-8').read()
    a = s.index('window.BANK = ') + len('window.BANK = ')
    return json.loads(s[a:s.index(';\n', a)])


def step(kind, k, x):
    return {'add': x + k, 'mul': x * k, 'sub': x - k, 'half': x - x // 2}[kind]   # x - x//2 == ⌈x/2⌉


def layers(sp):
    """Позиции → слой. Перебираем все позиции, где игра ещё идёт, и раскладываем их по слоям."""
    T, ge = sp['T'], sp['end'] == 'ge'
    over = (lambda t: t >= T) if ge else (lambda t: t <= T)
    if sp['heaps'] == 1:
        pos = range(1, T) if ge else range(T + 1, sp['smax'] + 1)
        nxt = lambda p: [step(m, k, p) for m, k in sp['moves']]
        tot = lambda p: p
    else:
        pos = [(a, b) for a in range(1, T) for b in range(1, T) if a + b < T]
        nxt = lambda p: [(step(m, k, p[0]), p[1]) for m, k in sp['moves']] + [(p[0], step(m, k, p[1])) for m, k in sp['moves']]
        tot = lambda p: p[0] + p[1]
    pos = [p for p in pos if not over(tot(p))]
    W1 = {p for p in pos if any(over(tot(q)) for q in nxt(p))}
    L1 = {p for p in pos if p not in W1 and all(q in W1 for q in nxt(p))}
    W2 = {p for p in pos if p not in W1 and any(q in L1 for q in nxt(p))}
    L2 = {p for p in pos if p not in W1 | L1 | W2 and all(q in W1 | W2 for q in nxt(p)) and any(q in W2 for q in nxt(p))}
    return W1, L1, W2, L2, nxt, (lambda p: over(tot(p)))


def expected(sp, task):
    W1, L1, W2, L2, nxt, over = layers(sp)
    st = (lambda s: s) if sp['heaps'] == 1 else (lambda s: (sp['a0'], s))
    S = range(sp['smin'], sp['smax'] + 1)
    far = min if sp['end'] == 'ge' else max
    if task == 19:
        if sp['q19'] == 'unlucky':
            return str(far(s for s in S if any(not over(q) and q in W1 for q in nxt(st(s)))))
        v = [s for s in S if st(s) in L1]
        return str(v[0] if len(v) == 1 else far(v))
    if task == 20:
        v = sorted(s for s in S if st(s) in W2)
        if len(v) > 3:
            v = v[:2] if far is min else v[-2:]
        return ' '.join(map(str, v))
    return str(far(s for s in S if st(s) in L2))


class Task19BankTest(unittest.TestCase):
    def test_each_solution_prints_its_answer(self):
        for p in [p for p in bank() if p['task'] in (19, 20, 21)]:
            with self.subTest(p['id']):
                r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=300)
                self.assertEqual(r.stdout.strip(), p['answer'])

    def test_answers_recomputed_by_layers(self):
        probs = [p for p in bank() if p['task'] in (19, 20, 21) and p['extra'].startswith('<!--spec:')]
        self.assertGreaterEqual(len(probs), 150)
        for p in probs:
            with self.subTest(p['id']):
                sp = json.loads(p['extra'][len('<!--spec:'):-len('-->')])
                self.assertEqual(expected(sp, p['task']), p['answer'])
                if p['task'] != 19:
                    # 20 и 21 — комплект с задачей 19: та же игра, условие только в 19
                    g = next(q for q in probs if q['id'] == '19-' + p['id'][3:])
                    self.assertEqual(g['extra'], p['extra'])
                    self.assertTrue(p['text'].startswith(f'<b>Задание {p["task"]}.</b> Для игры, описанной в задании 19, '))
                    continue
                t = p['text']
                self.assertIn(f'<b>{sp["T"]}</b>', t)
                self.assertIn(f'{sp["smin"]} ≤ S ≤ {sp["smax"]}', t)
                if sp['heaps'] == 2:
                    self.assertIn(f'<b>{sp["a0"]}</b> камней', t)
                self.assertEqual(len(re.findall(r'<b>(добавить|увеличить|убрать|уменьшить)', t)), len(sp['moves']))
                self.assertIn('<b>Задание 19.</b>', t)

    def test_three_tasks_per_game(self):
        B = bank()
        ids = {p['id'] for p in B}
        for p in B:
            m = re.match(r'(19|20|21)-(g?\d+)$', p['id'])
            if m:
                self.assertTrue({f'19-{m[2]}', f'20-{m[2]}', f'21-{m[2]}'} <= ids)
                if p['task'] != 19:   # сайт подставляет игру из задачи 19, поэтому условие её не повторяет
                    self.assertTrue(p['text'].startswith(f'<b>Задание {p["task"]}.</b> Для игры, описанной в задании 19, '), p['id'])
                    self.assertNotIn('Петя и Ваня', p['text'])


if __name__ == '__main__':
    unittest.main()
