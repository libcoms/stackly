"""Общие функции генераторов банка по профильной математике (tools/gen_math*.py).

Задача банка математики — обычная встроенная задача stackly с предметом: task = 0, subject = 'Математика',
snum — номер задания ЕГЭ-2027 (tools/fipi_math.py, EGE2027), topic — тема номера. Формулы в условии (text),
чертеже (extra) и решении (sol) пишутся как $…$ в подмножестве TeX, которое понимает public/tex.js; code —
то же решение простым текстом (его видит учитель в редакторе). Ответ — целое число или конечная десятичная
дробь с запятой, как в бланке ЕГЭ. Описание задачи хранится в extra комментарием <!--spec:…--> — по нему
tests/test_bank_math.py пересчитывает ответ своим способом.
"""
import json, math
from fractions import Fraction as F

SUBJECT = 'Математика'


# ------------------------------------------------------------------ числа
def ans(x):
    """Ответ ЕГЭ: целое или конечная десятичная дробь с запятой; иначе — ошибка генератора."""
    x = F(x)
    d = x.denominator
    while d % 2 == 0:
        d //= 2
    while d % 5 == 0:
        d //= 5
    if d != 1:
        raise ValueError(f'ответ {x} не записывается конечной десятичной дробью')
    if x.denominator == 1:
        return str(x.numerator)
    k = 0
    while (x * 10 ** k).denominator != 1:
        k += 1
    s = f'{abs(x.numerator) * 10 ** k // x.denominator:0{k + 1}d}'
    return ('-' if x < 0 else '') + s[:-k] + ',' + s[-k:]


def plural(k, one, few, many):
    """1 день, 2 дня, 5 дней."""
    k = abs(int(k))
    if k % 10 == 1 and k % 100 != 11:
        return one
    if 2 <= k % 10 <= 4 and not 12 <= k % 100 <= 14:
        return few
    return many


def rnd(x, k=2):
    """Округление «до сотых» (k знаков) по школьному правилу: половина — вверх по модулю."""
    x = F(x)
    q = abs(x) * 10 ** k
    r = int(q) + (1 if q - int(q) >= F(1, 2) else 0)
    return F(r if x >= 0 else -r, 10 ** k)


def is_dec(x):
    try:
        ans(x)
        return True
    except ValueError:
        return False


def n(x):
    """Число для формулы: 0,25; −3; дробь, если она не конечная десятичная."""
    x = F(x)
    return ans(x) if is_dec(x) else fr(x)


def fr(x):
    x = F(x)
    if x.denominator == 1:
        return str(x.numerator)
    sign = '-' if x < 0 else ''
    return f'{sign}\\frac{{{abs(x.numerator)}}}{{{x.denominator}}}'


def signed(x, first=False):
    """Слагаемое со знаком: + 3, - 5 (для записи многочленов)."""
    x = F(x)
    if first:
        return n(x)
    return f'+ {n(x)}' if x >= 0 else f'- {n(-x)}'


def poly(cs, var='x'):
    """Многочлен по коэффициентам от старшей степени: [1, -3, 2] → x^{2} - 3x + 2."""
    deg = len(cs) - 1
    out = []
    for i, c in enumerate(cs):
        c = F(c)
        p = deg - i
        if c == 0:
            continue
        mag = abs(c)
        coef = '' if (mag == 1 and p > 0) else n(mag)
        term = coef + (var if p >= 1 else '') + (f'^{{{p}}}' if p > 1 else '')
        if not out:
            out.append(('-' if c < 0 else '') + term)
        else:
            out.append(('- ' if c < 0 else '+ ') + term)
    return ' '.join(out) or '0'


# ------------------------------------------------------------------ SVG
def svg(w, h, body, label='Чертёж'):
    return f'<svg class="msvg" viewBox="0 0 {w} {h}" role="img" aria-label="{label}">{body}</svg>'


def pl(pts, cls='ln', close=True):
    d = ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts)
    return f'<{"polygon" if close else "polyline"} class="{cls}" points="{d}"/>'


def seg(a, b, cls='ln'):
    return f'<line class="{cls}" x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}"/>'


def circ(c, r, cls='ln'):
    return f'<circle class="{cls}" cx="{c[0]:.1f}" cy="{c[1]:.1f}" r="{r:.1f}"/>'


def dot(p, r=2.6):
    return f'<circle class="dt" cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="{r}"/>'


def lab(p, t, cls='lb', dx=0, dy=0):
    return f'<text class="{cls}" x="{p[0] + dx:.1f}" y="{p[1] + dy:.1f}">{t}</text>'


def out_label(p, center, t, d=14):
    """Подпись вершины снаружи фигуры: от центра через вершину."""
    vx, vy = p[0] - center[0], p[1] - center[1]
    L = math.hypot(vx, vy) or 1
    return lab((p[0] + vx / L * d, p[1] + vy / L * d), t)


def fit(points, w, h, pad=24):
    """Масштаб и сдвиг, чтобы точки (в своих координатах, y вверх) поместились в w×h."""
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    sx = (w - 2 * pad) / ((max(xs) - min(xs)) or 1)
    sy = (h - 2 * pad) / ((max(ys) - min(ys)) or 1)
    s = min(sx, sy)
    ox = pad + ((w - 2 * pad) - s * (max(xs) - min(xs))) / 2 - s * min(xs)
    oy = pad + ((h - 2 * pad) - s * (max(ys) - min(ys))) / 2 + s * max(ys)
    return lambda p: (ox + s * p[0], oy - s * p[1])


_clip = [0]


def grid_plot(xr, yr, curves, marks=(), cell=26, labels=(), arrows=True):
    """Клетчатая координатная плоскость: xr, yr — диапазоны целых; curves — [(f, cls, (x0, x1))];
    marks — точки [(x, y)] (жирные), labels — [(x, y, текст)]."""
    x0, x1 = xr
    y0, y1 = yr
    W, H = (x1 - x0) * cell, (y1 - y0) * cell
    X = lambda x: (x - x0) * cell
    Y = lambda y: (y1 - y) * cell
    b = []
    for x in range(x0, x1 + 1):
        b.append(seg((X(x), 0), (X(x), H), 'gr'))
    for y in range(y0, y1 + 1):
        b.append(seg((0, Y(y)), (W, Y(y)), 'gr'))
    b.append(seg((0, Y(0)), (W, Y(0)), 'ax'))
    b.append(seg((X(0), 0), (X(0), H), 'ax'))
    if arrows:
        b.append(pl([(W, Y(0)), (W - 8, Y(0) - 4), (W - 8, Y(0) + 4)], 'dt'))
        b.append(pl([(X(0), 0), (X(0) - 4, 8), (X(0) + 4, 8)], 'dt'))
    b.append(lab((W - 8, Y(0) + 13), 'x'))
    b.append(lab((X(0) + 11, 10), 'y'))
    b.append(lab((X(0) - 8, Y(0) + 11), '0', 'nb'))
    b.append(lab((X(1), Y(0) + 11), '1', 'nb'))
    b.append(lab((X(0) - 8, Y(1)), '1', 'nb'))
    _clip[0] += 1
    cid = f'mclip{_clip[0]}'                         # несколько чертежей на странице — разные id
    clip = f'<clipPath id="{cid}"><rect x="0" y="0" width="{W}" height="{H}"/></clipPath>'
    paths = []
    for f, cls, (a, c) in curves:
        pts, seg_ = [], []
        steps = int((c - a) * 24) + 1
        for k in range(steps + 1):
            x = a + (c - a) * k / steps
            try:
                y = f(x)
            except (ValueError, ZeroDivisionError, OverflowError):
                y = None
            if y is None or not math.isfinite(y) or y > y1 + 3 or y < y0 - 3:
                if len(seg_) > 1:
                    pts.append(seg_)
                seg_ = []
                continue
            seg_.append((X(x), Y(y)))
        if len(seg_) > 1:
            pts.append(seg_)
        for s_ in pts:
            paths.append(pl(s_, cls, close=False))
    b.append(clip)
    b.append(f'<g clip-path="url(#{cid})">' + ''.join(paths) + '</g>')
    for x, y in marks:
        b.append(dot((X(x), Y(y)), 3.4))
    for x, y, t in labels:
        b.append(lab((X(x), Y(y)), t))
    return svg(W, H, ''.join(b), 'Координатная плоскость с графиком'), (W, H)


# ------------------------------------------------------------------ задача
def item(num, k, level, topic, title, text, sol, answer, spec, extra='', code=''):
    meta = json.dumps(spec, ensure_ascii=False, separators=(',', ':'), default=str)
    return {'id': f'm{num}-g{k:03d}', 'task': 0, 'subject': SUBJECT, 'snum': num, 'topic': topic, 'level': level,
            'title': title, 'text': text, 'extra': f'<!--spec:{meta}-->' + extra, 'code': code or plain(sol),
            'sol': sol, 'answer': answer, 'data': '', 'dname': '', 'note': ''}


def tex_plain(t):
    r"""Формула для названия задачи (в списках это обычный текст): \frac{1}{2} → 1/2, \sqrt{x} → √(x), x^{2} → x^2."""
    import re
    simple = lambda g: g if re.fullmatch(r'\d+(,\d+)?|[A-Za-zα-ω]', g) else f'({g})'
    s = t.replace(r'\left', '').replace(r'\right', '').replace(r'^\circ', '°')
    for k, v in {'cdot': '·', 'pi': 'π', 'angle': '∠', 'le': '≤', 'ge': '≥', 'ne': '≠', 'alpha': 'α', 'beta': 'β',
                 'gamma': 'γ', 'triangle': '△', 'vec': '', 'in': '∈'}.items():
        s = re.sub(r'\\' + k + r'(?![A-Za-z])', v, s)
    for _ in range(4):
        s = re.sub(r'\\frac\{([^{}]*)\}\{([^{}]*)\}', lambda m: simple(m.group(1)) + '/' + simple(m.group(2)), s)
        s = re.sub(r'\\sqrt\[3\]\{([^{}]*)\}', r'∛(\1)', s)
        s = re.sub(r'\\sqrt\[(\d+)\]\{([^{}]*)\}', r'\1√(\2)', s)
        s = re.sub(r'\\sqrt\{([^{}]*)\}', r'√(\1)', s)
        s = re.sub(r'\^\{([^{}]*)\}', lambda m: '^' + simple(m.group(1)), s)
        s = re.sub(r'_\{([^{}]*)\}', r'_\1', s)
    s = re.sub(r'\\([A-Za-z]+)', r'\1', s).replace('{', '').replace('}', '')
    return re.sub(r'\s+', ' ', s).strip()


# Критерии оценивания части 2 по демоверсии ФИПИ 2027 (пересказ): номер → [(балл, когда ставится)]
_NONE = (0, 'Решение не соответствует ни одному из критериев, перечисленных выше.')
_PROOF = [(3, 'Имеется верное доказательство утверждения пункта а и обоснованно получен верный ответ в пункте б.'),
          (2, 'Получен обоснованный ответ в пункте б, ИЛИ имеется верное доказательство пункта а, но в обоснованном '
              'решении пункта б получен неверный ответ из-за арифметической ошибки.'),
          (1, 'Имеется верное доказательство утверждения пункта а, ИЛИ в обоснованном решении пункта б получен неверный '
              'ответ из-за арифметической ошибки, ИЛИ обоснованно получен верный ответ в пункте б с использованием '
              'утверждения пункта а, при этом пункт а не выполнен.'), _NONE]
CRITERIA = {
    14: [(2, 'Обоснованно получены верные ответы в обоих пунктах.'),
         (1, 'Обоснованно получен верный ответ в пункте а, ИЛИ получены неверные ответы из-за вычислительной ошибки, '
             'но при этом имеется верная последовательность всех шагов решения обоих пунктов.'), _NONE],
    15: _PROOF,
    16: [(2, 'Обоснованно получен верный ответ.'),
         (1, 'Обоснованно получен ответ, отличающийся от верного исключением или включением граничных точек, ИЛИ получен '
             'неверный ответ из-за вычислительной ошибки, но при этом имеется верная последовательность всех шагов решения.'), _NONE],
    17: [(2, 'Обоснованно получен верный ответ.'),
         (1, 'Получен неверный ответ из-за вычислительной ошибки, но при этом имеется верная последовательность всех шагов решения.'), _NONE],
    18: _PROOF,
    19: [(4, 'Обоснованно получен верный ответ.'),
         (3, 'С помощью верного рассуждения получено множество значений a, отличающееся от искомого только включением '
             'или исключением граничных точек.'),
         (2, 'С помощью верного рассуждения получена часть искомого множества (один из промежутков), ИЛИ получен неверный '
             'ответ из-за вычислительной ошибки, но при этом верно выполнены все шаги решения.'),
         (1, 'Задача верно сведена к исследованию взаимного расположения графиков (аналитически или графически) или '
             'к исследованию совокупности уравнений.'), _NONE],
    20: [(4, 'Обоснованно получены верные ответы в пунктах а, б и в.'),
         (3, 'Обоснованно получен верный ответ в пункте в и обоснованно получен верный ответ в пункте а или б.'),
         (2, 'Обоснованно получены верные ответы в пунктах а и б, ИЛИ обоснованно получен верный ответ в пункте в.'),
         (1, 'Обоснованно получен верный ответ в пункте а или б.'), _NONE],
}
POINTS = {14: 2, 15: 3, 16: 2, 17: 2, 18: 3, 19: 4, 20: 4}


def item2(num, k, level, topic, title, text, sol, answer, spec, extra='', auto=False):
    """Задача части 2: развёрнутый ответ, самопроверка по критериям. answer — итоговый ответ простым текстом
    (если auto — одно число, его можно сверить автоматически)."""
    p = item(num, k, level, topic, title, text, sol, answer, spec, extra)
    p.update({'pts': POINTS[num], 'crit': [list(c) for c in CRITERIA[num]], 'auto': bool(auto)})
    return p


def plain(html):
    """Решение простым текстом для редактора учителя: без тегов, формулы остаются в $…$."""
    import re
    s = re.sub(r'<br\s*/?>|</p>|</li>', '\n', html)
    s = re.sub(r'<li>', '- ', s)
    s = re.sub(r'<[^>]+>', '', s)
    return re.sub(r'\n{3,}', '\n\n', s).strip()


def emit(items):
    import sys
    stat = {}
    for p in items:
        stat[p['level']] = stat.get(p['level'], 0) + 1
    titles = [p['title'] for p in items]
    dup = {t for t in titles if titles.count(t) > 1}
    if dup:
        raise SystemExit(f'повторяются названия: {sorted(dup)[:5]}')
    print(json.dumps(stat, ensure_ascii=False), file=sys.stderr)
    sys.stdout.reconfigure(encoding='utf-8')
    json.dump(items, sys.stdout, ensure_ascii=False)


def uniq_loop(make, n_tries=500):
    """Повторять make(), пока не вернёт не None."""
    for _ in range(n_tries):
        r = make()
        if r is not None:
            return r
    raise RuntimeError('не удалось подобрать задачу')
