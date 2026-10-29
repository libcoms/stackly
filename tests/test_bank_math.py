"""Банк профильной математики (встроенные задачи с subject = 'Математика', номера ЕГЭ-2027).

Общие проверки: поля задачи, ответ — целое или конечная десятичная дробь с запятой, уровни и названия, формулы
разбираются public/tex.js (tests/tex_check.js в node). Для каждого номера ответ проверяется по скрытому описанию
(<!--spec:…-->) своим способом — подстановкой корня, перебором исходов, построением по координатам и т. п.,
а не той формулой, которой пользовался генератор."""
import json, math, os, re, shutil, subprocess, unittest
from fractions import Fraction as F
from itertools import product, permutations, combinations

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANS = re.compile(r'^-?\d+(,\d+)?$')


def bank():
    s = open(os.path.join(ROOT, 'content', 'ege.js'), encoding='utf-8').read()
    a = s.index('window.BANK = ') + len('window.BANK = ')
    return json.loads(s[a:s.index(';\n', a)])


def math_items():
    return [p for p in bank() if p.get('subject') == 'Математика']


def spec(p):
    """Описание задачи; числа (и дроби, записанные строкой «19/4») — как Fraction."""
    def conv(v):
        if isinstance(v, dict):
            return {k: conv(x) for k, x in v.items()}
        if isinstance(v, list):
            return [conv(x) for x in v]
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return F(str(v))
        if isinstance(v, str) and re.fullmatch(r'-?\d+(/\d+)?', v):
            return F(v)
        return v
    return conv(json.loads(re.search(r'<!--spec:(.*?)-->', p['extra']).group(1)))


def val(a):
    return F(a.replace(',', '.'))


def fr(x):
    return F(x)


# ------------------------------------------------------------------ №7: корень подстановкой
def v7(sp, x):
    f = sp['fam']
    if f == 'lin':
        assert sp['a'] * x + sp['b'] == sp['c'] * x + sp['d']
        assert sp['a'] != sp['c']
    elif f == 'exp':
        e = sp['k'] * x + sp['b']
        assert e.denominator == 1 and F(sp['p']) ** int(e) == fr(sp['rhs'])
    elif f == 'expfrac':
        e = x + sp['b']
        assert e.denominator == 1 and F(1, sp['p']) ** int(e) == fr(sp['rhs'])
    elif f == 'log':
        arg = sp['k'] * x + sp['b']
        assert arg > 0 and arg == F(sp['a']) ** sp['c']
    elif f == 'sqrt':
        assert sp['k'] * x + sp['b'] == sp['c'] ** 2 and sp['c'] >= 0
    elif f == 'rat':
        d = fr(sp['d'])
        assert x + sp['b'] != 0 and (x + sp['a']) == d * (x + sp['b'])
    elif f == 'quad':
        a, b, c = (int(v) for v in sp['cs'])
        D = b * b - 4 * a * c
        assert math.isqrt(D) ** 2 == D
        roots = sorted({F(-b + s * math.isqrt(D), 2 * a) for s in (1, -1)})
        assert all(a * r * r + b * r + c == 0 for r in roots) and len(roots) == 2
        assert x == (roots[0] if sp['which'] == 'меньший' else roots[1])
    elif f == 'irrx':
        assert x >= 0 and x * x == sp['p'] * x + sp['q']
        others = [r for r in range(-50, 51) if r * r == sp['p'] * r + sp['q'] and r != x]
        assert all(r < 0 for r in others)            # второй корень квадратного уравнения — посторонний
    elif f == 'logbase':
        assert x > 0 and x != 1 and x * x == sp['b'] * x + sp['c']
    else:
        raise AssertionError(f)


# ------------------------------------------------------------------ №8: прямое вычисление того же выражения
def v8(sp, x):
    v = eval(sp['py'], {'math': math, '__builtins__': {}})
    assert abs(v - float(x)) < 1e-9, (v, x)


# ------------------------------------------------------------------ №4–6: перебор исходов
def rounded(p, sp):
    if sp.get('round'):
        k = int(sp['round'])
        q = p * 10 ** k
        return F(int(q) + (1 if q - int(q) >= F(1, 2) else 0), 10 ** k)
    return p


def v4(sp, x):
    f = sp['fam']
    if f == 'defect':
        items = ['брак'] * int(sp['k']) + ['годный'] * int(sp['N'] - sp['k'])
        p = F(sum(1 for i in items if (i == 'годный') == sp['good']), len(items))
    elif f == 'order':
        people = [i for i, c in enumerate(sp['cnt']) for _ in range(int(c))]
        p = F(people.count(int(sp['i'])), len(people))         # на любом месте — любой с равными шансами
    elif f == 'lot':
        N, k = int(sp['N']), int(sp['k'])
        p = F(math.comb(N - 1, k - 1), math.comb(N, k))       # наборы из k человек, в которые попал А.
    elif f == 'coins':
        m, k = int(sp['m']), int(sp['k'])
        outs = list(product('ОР', repeat=m))
        good = [o for o in outs if (o.count('О') == k if sp['what'] == 'exact' else o.count('О') >= k)]
        p = F(len(good), len(outs))
    elif f in ('dice', 'dice_no6'):
        outs = [o for o in product(range(1, 7), repeat=2) if f == 'dice' or 6 not in o]
        op = {'=': lambda s: s == sp['s'], '≥': lambda s: s >= sp['s'], '≤': lambda s: s <= sp['s']}[sp['op']]
        p = F(sum(1 for o in outs if op(sum(o))), len(outs))
    elif f == 'conf':
        N, k, d = int(sp['N']), int(sp['k']), int(sp['d'])
        days = [1] * k + [day for day in range(2, d + 1) for _ in range((N - k) // (d - 1))]
        assert len(days) == N
        p = F(days.count(int(sp['j'])), N)
    else:
        raise AssertionError(f)
    assert rounded(p, sp) == x, (p, x)


def prob_of(outcomes):
    """Сумма вероятностей исходов: исход — список вероятностей независимых элементарных событий."""
    total = F(0)
    for o in outcomes:
        pr = F(1)
        for q in o:
            pr *= q
        total += pr
    return total


def v5(sp, x):
    f = sp['fam']
    if f == 'shooter':
        p, pat = sp['p'], [int(v) for v in sp['pat']]
        # все 2^m исходов, отбираем один нужный шаблон попаданий
        ps = prob_of([[p if h else 1 - p for h in o] for o in product((1, 0), repeat=len(pat)) if list(o) == pat])
    elif f == 'lamps':
        q, m = sp['q'], int(sp['m'])
        ps = prob_of([[q if b else 1 - q for b in o] for o in product((1, 0), repeat=m) if not all(o)])
    elif f == 'coffee':
        a, c = sp['a'], sp['c']
        cells = {(1, 1): c, (1, 0): a - c, (0, 1): a - c, (0, 0): 1 - 2 * a + c}   # таблица совместных исходов
        assert all(v >= 0 for v in cells.values())
        ps = cells[(0, 0)] if sp['ask'] == 'both_stay' else cells[(1, 0)] + cells[(0, 1)]
    elif f == 'bread':
        ps = sp['a'] - (1 - sp['b'])                          # P(m < hi) − P(m ≤ lo)
    elif f == 'until':
        p, k = sp['p'], int(sp['k'])
        ps = sum(((1 - p) ** (j - 1) * p for j in range(1, k + 1)), F(0))   # первое попадание на 1-м, …, k-м выстреле
    elif f in ('control', 'bayes'):
        q, r1, r2 = sp['q'], sp['r1'], sp['r2']
        tree = {('неиспр', 'брак'): q * r1, ('неиспр', 'ок'): q * (1 - r1), ('испр', 'брак'): (1 - q) * r2, ('испр', 'ок'): (1 - q) * (1 - r2)}
        rej = sum(v for (s, c), v in tree.items() if c == 'брак')
        ps = rej if f == 'control' else tree[('неиспр', 'брак')] / rej
    else:
        raise AssertionError(f)
    assert rounded(ps, sp) == x, (ps, x)


def v6(sp, x):
    f = sp['fam']
    if 'xs' in sp:
        xs, ps = sp['xs'], sp['ps']
        assert sum(ps) == 1 and all(p > 0 for p in ps)
        E = sum(a * p for a, p in zip(xs, ps))
        D = sum((a - E) ** 2 * p for a, p in zip(xs, ps))       # по определению, а не через E(X²)
        r = {'E': E, 'D': D}.get(sp['q'])
        if sp['q'] == 'S':
            assert math.isqrt(D.numerator) ** 2 == D.numerator and D.denominator == 1
            r = F(math.isqrt(D.numerator))
    elif f in ('binE', 'binD'):
        m, p = int(sp['m']), sp['p']
        dist = {}
        for o in product((1, 0), repeat=m) if m <= 12 else []:
            pr = prob_of([[p if b else 1 - p for b in o]])
            dist[sum(o)] = dist.get(sum(o), 0) + pr
        if not dist:                                          # длинная серия: распределение по формуле Бернулли
            dist = {k: math.comb(m, k) * p ** k * (1 - p) ** (m - k) for k in range(m + 1)}
        E = sum(k * v for k, v in dist.items())
        r = E if f == 'binE' else sum((k - E) ** 2 * v for k, v in dist.items())
    elif f == 'linear':
        # E и D для X, принимающей E ± √D с вероятностями 1/2, — любая подходящая величина даёт тот же ответ
        a, b = sp['a'], sp['b']
        r = a * sp['E'] + b if sp['q'] == 'E' else a * a * sp['D']
    elif f == 'uniform':
        a, b = sp['a'], sp['b']
        if sp['q'] == 'P':
            r = (sp['d'] - sp['c']) / (b - a)
        else:
            # дискретное приближение: середины N равных частей отрезка; E точное, D сходится к (b − a)²/12
            N = 2000
            pts = [a + (b - a) * (2 * i + 1) / (2 * N) for i in range(N)]
            E = sum(pts) / N
            r = E if sp['q'] == 'E' else None
            if r is None:
                Dn = sum((t - E) ** 2 for t in pts) / N
                assert abs(float(Dn) - float(x)) < 1e-4, (Dn, x)
                return
    elif f == 'normal':
        p = sp['p']
        r = p if sp['q'] == 'mirror' else 1 - 2 * p
    else:
        raise AssertionError(f)
    assert r == x, (r, x)


# ------------------------------------------------------------------ №2: векторы покоординатно
def v2(sp, x):
    f = sp['fam']
    if 'a' in sp and isinstance(sp['a'], list):
        a, b = sp['a'], sp['b']
    if f in ('len', 'coord'):
        c = [sp['k1'] * a[i] + sp['k2'] * b[i] for i in (0, 1)]
        if f == 'len':
            assert x >= 0 and x * x == c[0] ** 2 + c[1] ** 2
        else:
            assert x == {'абсциссу': c[0], 'ординату': c[1], 'сумму координат': c[0] + c[1]}[sp['which']]
    elif f == 'dot':
        assert x == a[0] * b[0] + a[1] * b[1]
    elif f == 'cos':
        d = a[0] * b[0] + a[1] * b[1]
        assert abs(float(x) - float(d) / math.hypot(*a) / math.hypot(*b)) < 1e-12
    else:
        la, lb, ang = sp['la'], sp['lb'], float(sp['ang'])
        # вектор a вдоль оси x, b — под углом ang: считаем по координатам
        bx, by = float(lb) * math.cos(math.radians(ang)), float(lb) * math.sin(math.radians(ang))
        r = float(la) * bx if f == 'dotang' else math.hypot(float(la) + bx, by)
        assert abs(r - float(x)) < 1e-9, (r, x)


# ------------------------------------------------------------------ №10, №11: подстановка ответа в уравнение задачи
def v_check(sp, x):
    assert eval(sp['check'], {'math': math, 'x': x, '__builtins__': {'abs': abs}}), sp['check']


# ------------------------------------------------------------------ №13: кредит и вклад по годам
def v13(sp, x):
    k = sp['kind']
    if k == 'deposit':
        bal = sp['S']
        for y in range(int(sp['N'])):
            bal = bal * (100 + sp['r']) / 100
            if y < sp['N'] - 1:
                bal += sp['add']
        assert bal == x
        return
    S, r, pays = sp['S'], sp['r'], sp['pays']
    debt = S
    for i, p in enumerate(pays, 1):
        debt = debt * (100 + r) / 100 - p
        assert debt >= 0
        if k.startswith('diff'):
            assert debt == S - S * i / len(pays)             # долг уменьшается на одну и ту же величину
    assert debt == 0
    if k.startswith('annuity'):
        assert len(set(pays)) == 1
    want = {'total': sum(pays), 'pay': pays[0], 'first': pays[0], 'S': S}[sp['ask']]
    assert want == x, (want, x)


# ------------------------------------------------------------------ №12: функция восстанавливается по отмеченным узлам
def lagrange(pts):
    """Многочлен через точки (x, y) — как функция."""
    pts = [(F(x), F(y)) for x, y in pts]
    def f(t):
        t = F(t)
        s = F(0)
        for i, (xi, yi) in enumerate(pts):
            term = yi
            for j, (xj, _) in enumerate(pts):
                if j != i:
                    term *= (t - xj) / (xi - xj)
            s += term
        return s
    return f


def rat_root(y, m):
    """Положительное рациональное a с a^m = y (основания из небольших дробей)."""
    for p in range(1, 11):
        for q in range(1, 11):
            if F(p, q) ** m == y:
                return F(p, q)
    raise AssertionError(f'нет основания для {y}, {m}')


def v12(sp, x):
    k = sp['kind']
    if k == 'lin':
        assert lagrange(sp['marks'])(sp['x0']) == x
    elif k == 'hyp':
        (x1, y1), = sp['marks']
        assert x1 * y1 / sp['x0'] == x
    elif k == 'hypa':
        (x1, y1), (x2, y2) = sp['marks']
        kk = (y1 - y2) / (1 / x1 - 1 / x2)
        a = y1 - kk / x1
        assert kk / sp['x0'] + a == x
    elif k == 'quad':
        assert len(sp['marks']) == 3 and lagrange(sp['marks'])(sp['x0']) == x
    elif k == 'sqrt':
        (x1, y1), = sp['marks']
        a = y1 / math.isqrt(int(x1))
        x0 = sp['x0']
        r = F(math.isqrt(x0.numerator), math.isqrt(x0.denominator))
        assert r * r == x0 and a * r == x
    elif k == 'exp':
        (m, y), = sp['marks']
        a = rat_root(y, int(m)) if m > 0 else 1 / rat_root(y, -int(m))
        assert a ** int(sp['x0']) == x
    elif k == 'log':
        (x1, y1), = sp['marks']
        a = rat_root(x1, int(y1)) if y1 > 0 else 1 / rat_root(x1, -int(y1))
        assert a ** int(x) == sp['x0'] and x.denominator == 1
    elif k == 'lines':
        f1, f2 = lagrange(sp['m1']), lagrange(sp['m2'])
        k1, b1 = f1(1) - f1(0), f1(0)
        k2, b2 = f2(1) - f2(0), f2(0)
        xi = (b2 - b1) / (k1 - k2)
        assert (xi if sp['ask'] == 'x' else f1(xi)) == x
    elif k == 'quadline':
        f, g = lagrange(sp['mf']), lagrange(sp['mg'])
        h = lambda t: f(t) - g(t)                             # квадратный трёхчлен
        C = h(0)
        A = (h(1) + h(-1)) / 2 - C
        B = (h(1) - h(-1)) / 2
        assert h(sp['xa']) == 0 and A != 0
        assert -B / A - sp['xa'] == x and h(x) == 0
    else:
        raise AssertionError(k)


# ------------------------------------------------------------------ №9: численно — знаки, перебор по сетке, Симпсон
def peval(cs, t):
    return sum(c * t ** (len(cs) - 1 - i) for i, c in enumerate(cs))


def v9(sp, x):
    k = sp['kind']
    if k == 'tangent':
        (x1, y1), (x2, y2) = sp['pts']
        assert (y2 - y1) / (x2 - x1) == x
    elif k in ('dcount', 'dpoint', 'dmaxon'):
        rs, lead = [int(r) for r in sp['roots']], int(sp['lead'])
        sign = lambda t: lead * (-1) ** sum(1 for r in rs if r > t)   # правее последнего нуля — знак lead
        maxs = [r for r in rs if sign(r - 0.5) > 0 > sign(r + 0.5)]
        mins = [r for r in rs if sign(r - 0.5) < 0 < sign(r + 0.5)]
        if k == 'dcount':
            lo, hi = sp['seg']
            pool = maxs if sp['what'] == 'максимума' else mins
            assert sum(1 for r in pool if lo <= r <= hi) == x
        elif k == 'dpoint':
            assert len(rs) == 1 and x == rs[0] and (rs[0] in maxs) == (sp['what'] == 'максимума')
        else:
            lo, hi = sp['seg']
            # f растёт, где f′ > 0: идём по отрезку с мелким шагом и копим приращения
            f, best, bt = 0.0, 0.0, lo
            steps = 400
            for i in range(1, steps + 1):
                t = float(lo) + (float(hi) - float(lo)) * i / steps
                f += sign(t - 1e-9)
                if f > best:
                    best, bt = f, t
            assert abs(bt - float(x)) < 1e-9 or (best == 0 and x == lo)
    elif k == 'fsign':
        knots = [(float(a), float(b)) for a, b in sp['knots']]
        f = lambda t: next(ya + (yb - ya) * (1 - math.cos(math.pi * (t - xa) / (xb - xa))) / 2
                           for (xa, ya), (xb, yb) in zip(knots, knots[1:]) if xa <= t <= xb)
        h = 1e-4
        cnt = sum(1 for p in sp['pts'] if ((f(float(p) + h) - f(float(p) - h)) < 0) == sp['neg'])
        assert cnt == x
    elif k in ('ext3', 'segval'):
        cs = sp['f']
        if k == 'ext3':
            d = lambda t: (peval(cs, t + F(1, 1000)) - peval(cs, t - F(1, 1000)))
            assert abs(peval([c * (len(cs) - 1 - i) for i, c in enumerate(cs[:-1])], x)) == 0
            left, right = d(x - F(1, 10)), d(x + F(1, 10))
            assert (left > 0 > right) == (sp['what'] == 'максимума') and left * right < 0
        else:
            lo, hi = sp['seg']
            grid = [lo + F(i, 1000) for i in range(int(hi - lo) * 1000 + 1)]   # шаг 0,001 — целые точки входят в сетку
            vals = [peval(cs, t) for t in grid]
            assert (max(vals) if sp['what'] == 'наибольшее' else min(vals)) == x
    elif k == 'extlog':
        kk, a, c = float(sp['k']), float(sp['a']), float(sp['c'])
        y = lambda t: kk * t - math.log(t + a) + c
        t = float(x)
        assert t + a > 0 and y(t) < y(t - 1e-3) and y(t) < y(t + 1e-3)
    elif k == 'motion':
        cs, t0 = sp['f'], sp['t0']
        h = F(1, 10 ** 6)
        v = (peval(cs, t0 + h) - peval(cs, t0 - h)) / (2 * h)       # для кубики симметричная разность почти точна
        assert abs(v - x) < F(1, 10 ** 6)
    elif k == 'area':
        cs, (a, b) = sp['f'], sp['seg']
        N = 200                                               # Симпсон точен для многочленов до 3-й степени
        hh = (b - a) / N
        s = peval(cs, a) + peval(cs, b) + sum((4 if i % 2 else 2) * peval(cs, a + i * hh) for i in range(1, N))
        assert s * hh / 3 == x
    else:
        raise AssertionError(k)


# ------------------------------------------------------------------ №1: фигура по координатам, измерения численно
def P(deg, r=1.0):
    return (r * math.cos(math.radians(deg)), r * math.sin(math.radians(deg)))


def angle(a, v, b):
    """Угол avb в градусах."""
    x1, y1, x2, y2 = a[0] - v[0], a[1] - v[1], b[0] - v[0], b[1] - v[1]
    return math.degrees(math.acos((x1 * x2 + y1 * y2) / math.hypot(x1, y1) / math.hypot(x2, y2)))


def area(*pts):
    return abs(sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts)))) / 2


def close(a, b):
    assert abs(float(a) - float(b)) < 1e-6, (a, b)


def v1(sp, x):
    k = sp['kind']
    if k == 'central':
        cen = float(sp['cen'])
        A, B, C = P(90 + cen / 2), P(90 - cen / 2), P(-90 + 17)      # C — на большой дуге
        close(angle(A, C, B) if sp['given'] == 'central' else angle(A, (0, 0), B), x)
    elif k == 'inquad':
        a, b = float(sp['a']), float(sp['b'])
        A, D, C = P(0), P(2 * a), P(2 * a + 2 * b)
        B = P(2 * a + 2 * b + 37)                               # любая точка дуги AC, не содержащей D
        close(angle(A, B, D), a)
        close(angle(C, A, D), b)
        close(angle(A, B, C), x)
    elif k == 'cosA':
        c, bc = float(sp['c']), math.sqrt(float(sp['bc2']))
        Cc, B = (0, 0), (0, bc)
        A = (math.sqrt(c * c - bc * bc), 0)
        close(math.cos(math.radians(angle(B, A, Cc))), x)
    elif k == 'sideA':
        c, s = float(sp['c']), float(sp['s'])
        A, Cc = (0, 0), (c * math.cos(math.asin(s)), 0)
        B = (Cc[0], c * s)                                     # угол C прямой, AB = c, угол A с синусом s
        close(math.dist(A, B), c)
        close(math.dist(B, Cc), x)
    elif k in ('area_sin', 'paral'):
        a, b, ang = float(sp['a']), float(sp['b']), float(sp['ang'])
        A, B, D = (0, 0), P(ang, b), (a, 0)
        close(area(A, B, D) * (1 if k == 'area_sin' else 2), x)
    elif k == 'rhomb':
        d1, d2 = float(sp['d1']), float(sp['d2'])
        close(area((-d1 / 2, 0), (0, d2 / 2), (d1 / 2, 0), (0, -d2 / 2)), x)
    elif k == 'trap':
        a, b, h = float(sp['a']), float(sp['b']), float(sp['h'])
        A, B, C, D = (0, 0), (1.3, h), (1.3 + a, h), (b, 0)
        if sp['ask'] == 'S':
            close(area(A, B, C, D), x)
        else:
            M, N = ((A[0] + B[0]) / 2, h / 2), ((C[0] + D[0]) / 2, h / 2)
            close(math.dist(M, N), x)
    elif k == 'iso':
        beta = float(sp['beta'])
        B, A, C = (0, 0), P(-90 - beta / 2), P(-90 + beta / 2)
        a_ = angle(B, A, C)
        close(a_ if sp['ask'] == 'base' else 180 - angle(B, C, A), x)
    elif k == 'bis_alt':
        a, b = float(sp['a']), float(sp['b'])
        A, B = (0, 0), (1, 0)
        # C — пересечение лучей из A под углом a и из B под углом b
        ta, tb = math.tan(math.radians(a)), math.tan(math.radians(b))
        cx = tb / (ta + tb)
        C = (cx, ta * cx)
        H = (cx, 0)
        # D — на AB, делит её в отношении AC : CB (свойство биссектрисы проверяем углами)
        lo, hi = 0.0, 1.0
        for _ in range(100):
            mid = (lo + hi) / 2
            if angle(A, C, (mid, 0)) < angle((mid, 0), C, B):
                lo = mid
            else:
                hi = mid
        D = (lo, 0)
        close(angle(D, C, H), x)
    elif k == 'tangq':
        t = [float(v) for v in sp['t']]
        AB, BC, CD, DA = t[0] + t[1], t[1] + t[2], t[2] + t[3], t[3] + t[0]   # отрезки касательных из вершин
        close(AB + BC + CD + DA if sp['ask'] == 'P' else DA, x)
    elif k == 'circR':
        a, ang = float(sp['a']), float(sp['ang'])
        A, B = (0, 0), (a, 0)
        # C на дуге, из которой AB видна под углом ang: строим через окружность радиуса R и проверяем угол
        R = a / 2 / math.sin(math.radians(ang))
        # острый угол — центр по ту же сторону от AB, что и C (сверху), тупой — по другую
        O = (a / 2, math.sqrt(max(R * R - a * a / 4, 0)) * (1 if ang < 90 else -1))
        Cc = (O[0] + R * math.cos(math.radians(70)), O[1] + R * math.sin(math.radians(70)))
        close(angle(A, Cc, B), ang)
        close(math.dist(O, A), x)
    elif k == 'midline':
        S = float(sp['S'])
        A, B, C = (0, 0), (1.7, 2.9), (4.4, 0)
        sc = math.sqrt(S / area(A, B, C))
        A, B, C = [(p[0] * sc, p[1] * sc) for p in (A, B, C)]
        M, N = ((A[0] + B[0]) / 2, (A[1] + B[1]) / 2), ((B[0] + C[0]) / 2, (B[1] + C[1]) / 2)
        close(area(M, B, N) if sp['ask'] == 'small' else area(A, M, N, C), x)
    else:
        raise AssertionError(k)


# ------------------------------------------------------------------ №3: объёмы интегрированием площадей сечений
def volume(section, h, steps=2000):
    """∫₀ʰ S(z) dz по формуле Симпсона: S(z) — площадь сечения на высоте z."""
    dz = h / steps
    s = section(0) + section(h) + sum((4 if i % 2 else 2) * section(i * dz) for i in range(1, steps))
    return s * dz / 3


def v3(sp, x):
    k = sp['kind']
    if k == 'diag':
        a, b, c = (float(sp[t]) for t in 'abc')
        A, C1 = (0, 0, 0), (a, b, c)
        close(math.dist(A, C1) if sp['ask'] == 'diag' else c, x)
        if sp['ask'] == 'edge':
            assert float(x) ** 2 + a * a + b * b == math.dist(A, C1) ** 2 or abs(float(x) ** 2 + a * a + b * b - math.dist(A, C1) ** 2) < 1e-9
    elif k == 'cube_k':
        kk = float(sp['k'])
        if sp['what'] == 'объём':
            close(volume(lambda z: kk * kk, kk) / volume(lambda z: 1.0, 1.0), x)
        else:
            close((6 * kk * kk) / 6, x)
    elif k in ('prism_v', 'prism_s'):
        A, B, C = (0.0, 0.0), (5.0, 0.0), (1.7, 3.3)              # любой треугольник основания
        M, N = ((A[0] + B[0]) / 2, (A[1] + B[1]) / 2), ((A[0] + C[0]) / 2, (A[1] + C[1]) / 2)
        if k == 'prism_v':
            ratio = area(A, B, C) / area(A, M, N)
        else:
            per = lambda *p: sum(math.dist(p[i], p[i - 1]) for i in range(len(p)))
            ratio = per(A, B, C) / per(A, M, N)
        val = float(sp['val'])
        close(val * ratio if sp['small'] else val / ratio, x)
    elif k == 'cylcone':
        cyl, cone = volume(lambda z: math.pi, 1.0), volume(lambda z: math.pi * (1 - z) ** 2, 1.0)
        val = float(sp['val'])
        close(val * cone / cyl if sp['given'] == 'cyl' else val * cyl / cone, x)
    elif k == 'spherecyl':
        cyl, sph = volume(lambda z: math.pi, 2.0), volume(lambda z: math.pi * (1 - (z - 1) ** 2), 2.0)
        val = float(sp['val'])
        close(val * cyl / sph if sp['given'] == 'sphere' else val * sph / cyl, x)
    elif k == 'conecut':
        full = volume(lambda z: math.pi * (1 - z) ** 2, 1.0)
        top = volume(lambda z: math.pi * (0.5 - z) ** 2, 0.5)     # малый конус: верхняя половина высоты
        V = float(sp['V'])
        close(V * top / full if sp['ask'] == 'small' else V * (full - top) / full, x)
    elif k == 'vessel':
        h, kk = float(sp['h']), float(sp['k'])
        r2 = kk if sp['dir'] == 'wider' else 1 / kk
        Vliq = math.pi * 1.0 ** 2 * h
        close(Vliq / (math.pi * r2 ** 2), x)
    elif k == 'pyr':
        a, h = float(sp['a']), float(sp['h'])
        close(volume(lambda z: (a * (1 - z / h)) ** 2, h), x)
    elif k == 'tetra':
        a, b, c = (float(sp[t]) for t in 'abc')
        # A(0,0,0), B(a,0,0), D(0,b,0), A1(0,0,c): объём = |det| / 6
        det = a * (b * c - 0) - 0 + 0
        close(abs(det) / 6, x)
    else:
        raise AssertionError(k)


VERIFY = {1: v1, 2: v2, 3: v3, 4: v4, 5: v5, 6: v6, 7: v7, 8: v8, 9: v9, 10: v_check, 11: v_check, 12: v12, 13: v13}


class MathBankTest(unittest.TestCase):
    def test_items_are_well_formed(self):
        items = math_items()
        self.assertGreater(len(items), 0)
        ids = [p['id'] for p in items]
        self.assertEqual(len(ids), len(set(ids)))
        for p in items:
            with self.subTest(p['id']):
                self.assertEqual(p['task'], 0)
                self.assertTrue(1 <= p['snum'] <= 20)
                self.assertTrue(p['topic'] and p['title'] and p['text'] and p['sol'] and p['code'])
                self.assertIn(p['level'], ('Б', 'П', 'В'))
                self.assertRegex(p['answer'], ANS)
                self.assertTrue(p['id'].startswith(f'm{p["snum"]}-'))

    def test_titles_unique_within_number(self):
        by = {}
        for p in math_items():
            by.setdefault(p['snum'], []).append(p['title'])
        for k, ts in by.items():
            with self.subTest(k):
                self.assertEqual(len(ts), len(set(ts)))

    def test_answers_verified_independently(self):
        for p in math_items():
            with self.subTest(p['id']):
                self.assertIn(p['snum'], VERIFY, 'для номера нет независимой проверки')
                VERIFY[p['snum']](spec(p), val(p['answer']))

    @unittest.skipUnless(shutil.which('node'), 'нет node')
    def test_formulas_render(self):
        r = subprocess.run(['node', os.path.join(ROOT, 'tests', 'tex_check.js')], capture_output=True, text=True,
                           encoding='utf-8', timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == '__main__':
    unittest.main()
