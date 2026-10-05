#!/usr/bin/env python3
"""Генератор задач ЕГЭ №2 (фрагмент таблицы истинности) для банка stackly.

    python3 tools/gen_task2.py > /tmp/task2.json      # 50 задач: 35 базовых, 10 средних, 5 сложных

Каждая задача проверяется полным перебором: все заполнения пустых клеток и все соответствия
«столбец → переменная», при которых строки фрагмента различны и значения F совпадают с таблицей.
Задача остаётся, только если подходит ровно одно соответствие. Затем запускается решение на Python
из самой задачи — его вывод должен совпасть с ответом. Генерация детерминирована (seed).
"""
import itertools, json, random, subprocess, sys

SEED = 20261005

# ------------------------------------------------------------------ формулы
# узел: ('v', 'x') | ('not', A) | (op, A, B), op ∈ and / or / imp / eq
SYM = {'and': '∧', 'or': '∨', 'imp': '→', 'eq': '≡'}
PY = {'and': 'and', 'or': 'or', 'imp': '<=', 'eq': '=='}


def ev(e, env):
    k = e[0]
    if k == 'v':
        return env[e[1]]
    if k == 'not':
        return 1 - ev(e[1], env)
    a, b = ev(e[1], env), ev(e[2], env)
    return {'and': a & b, 'or': a | b, 'imp': (1 - a) | b, 'eq': int(a == b)}[k]


def show(e, top=True):
    """Текст для условия: каждая двухместная операция в скобках, кроме цепочек ∧/∨ одного уровня."""
    k = e[0]
    if k == 'v':
        return e[1]
    if k == 'not':
        inner = show(e[1], False)
        return '¬' + inner
    parts = []
    for c in e[1:]:
        if k in ('and', 'or') and c[0] == k:
            parts.append(show(c, True))          # x ∧ y ∧ z — без лишних скобок
        else:
            parts.append(show(c, False))
    s = f' {SYM[k]} '.join(parts)
    return s if top else f'({s})'


def py(e):
    """Выражение на Python с явными скобками вокруг каждой операции (сравнения и not не путаются)."""
    k = e[0]
    if k == 'v':
        return e[1]
    if k == 'not':
        return f'(not {py(e[1])})'
    return f'({py(e[1])} {PY[k]} {py(e[2])})'


def vars_of(e):
    return {e[1]} if e[0] == 'v' else set().union(*(vars_of(c) for c in e[1:]))


def size(e):
    return 0 if e[0] == 'v' else 1 + sum(size(c) for c in e[1:])


def lit(rng, v, neg=.3):
    return ('not', ('v', v)) if rng.random() < neg else ('v', v)


def clause(rng, vs, deep=False):
    """Кусок формулы в духе ЕГЭ: импликация, эквиваленция, конъюнкция с отрицанием и т.п."""
    a, b = rng.sample(vs, 2)
    kind = rng.choice(['imp', 'eq', 'neq', 'and', 'or', 'imp', 'eq'] + (['deep_eq', 'deep_imp', 'deep_and'] * 2 if deep else []))
    if kind == 'neq':
        return ('not', ('eq', ('v', a), ('v', b)))
    if kind in ('imp', 'eq', 'and', 'or'):
        return (kind, lit(rng, a), lit(rng, b))
    c = rng.choice([v for v in vs if v not in (a, b)] or [a])
    if kind == 'deep_eq':                       # (x → y) ≡ z,  (x ∧ ¬y) ≡ (z ∨ w)
        return ('eq', (rng.choice(['imp', 'and', 'or']), lit(rng, a), lit(rng, b)), lit(rng, c, .2))
    if kind == 'deep_imp':                      # (x ∨ y) → (z ≡ w)
        return ('imp', (rng.choice(['and', 'or']), lit(rng, a), lit(rng, b)), (rng.choice(['eq', 'imp']), ('v', c), lit(rng, rng.choice(vs))))
    return ('not', (rng.choice(['imp', 'eq']), ('v', a), ('v', b)))


def formula(rng, vs, n_clauses, deep):
    top = rng.choice(['and', 'or', 'or'])
    cl = [clause(rng, vs, deep) for _ in range(n_clauses)]
    if rng.random() < .35:                      # одинокая переменная: «… ∨ ¬w», «… ∧ x»
        cl[-1] = lit(rng, rng.choice(vs), .5)
    if deep and rng.random() < .5:              # верхний уровень — эквиваленция или импликация двух частей
        top = rng.choice(['eq', 'imp'])
        left = cl[0] if len(cl) < 3 else (rng.choice(['and', 'or']), cl[0], cl[1])
        return (top, left, cl[-1])
    e = cl[0]
    for c in cl[1:]:
        e = (top, e, c)
    return e


# ------------------------------------------------------------------ фрагмент таблицы
def solutions(e, vs, rows, fvals, limit=2):
    """Все соответствия «столбцы → переменные», при которых фрагмент можно дополнить: строки различны, F как в таблице."""
    holes = [(i, j) for i, r in enumerate(rows) for j, c in enumerate(r) if c is None]
    found = set()
    for fill in itertools.product([0, 1], repeat=len(holes)):
        t = [list(r) for r in rows]
        for (i, j), v in zip(holes, fill):
            t[i][j] = v
        if len({tuple(r) for r in t}) < len(t):
            continue
        for names in itertools.permutations(vs):
            if names in found:
                continue
            if all(ev(e, dict(zip(names, r))) == f for r, f in zip(t, fvals)):
                found.add(names)
                if len(found) >= limit:
                    return found
    return found


def build(rng, pid, level, n_vars, n_rows, f_mode, holes, n_clauses, deep):
    vs = ['w', 'x', 'y', 'z'][:n_vars] if n_vars == 4 else ['x', 'y', 'z']
    for _ in range(20000):
        e = formula(rng, vs, n_clauses, deep)
        if vars_of(e) != set(vs) or size(e) > (9 if deep else 7):
            continue
        all_rows = list(itertools.product([0, 1], repeat=n_vars))
        ones = [r for r in all_rows if ev(e, dict(zip(vs, r)))]
        if not 2 <= len(ones) <= 2 ** n_vars - 2:
            continue
        # значения F во фрагменте
        if f_mode == 1:
            fv = [1] * n_rows
        elif f_mode == 0:
            fv = [0] * n_rows
        else:
            fv = [rng.randint(0, 1) for _ in range(n_rows)]
            if len(set(fv)) < 2:
                continue
        pool = {1: ones, 0: [r for r in all_rows if r not in ones]}
        if any(len(pool[f]) < fv.count(f) for f in (0, 1)):
            continue
        # строки: перебираем случайные наборы, пока полный фрагмент не задаёт соответствие однозначно
        order = list(vs); rng.shuffle(order)
        if order == sorted(order):
            continue
        for _ in range(300):
            rows = []
            for f in fv:
                rows.append(rng.choice([x for x in pool[f] if x not in rows]))
            cols = [[r[vs.index(v)] for v in order] for r in rows]
            frag = [list(r) for r in cols]
            if solutions(e, vs, frag, fv) == {tuple(order)}:
                break
        else:
            continue
        # пустые клетки: стираем по одной, пока ответ единственный (так составляют задачи и на экзамене);
        # в каждом столбце остаётся хотя бы одна заполненная клетка
        cells = [(i, j) for i in range(n_rows) for j in range(n_vars)]
        rng.shuffle(cells)
        k = 0
        for i, j in cells:
            if k == holes:
                break
            if sum(frag[t][j] is None for t in range(n_rows)) + 1 >= n_rows:
                continue
            keep, frag[i][j] = frag[i][j], None
            if solutions(e, vs, frag, fv) == {tuple(order)}:
                k += 1
            else:
                frag[i][j] = keep
        if k < holes:
            continue
        return e, vs, frag, fv, ''.join(order)
    raise RuntimeError(f'не удалось собрать {pid}')


INTROS = [
    ('Миша заполнял таблицу истинности логической функции <span class="f">F = {f}</span>, но успел заполнить лишь '
     'фрагмент из {ng} различных её строк, даже не указав, какому столбцу таблицы соответствует каждая из переменных {vs}.'),
    ('Логическая функция F задаётся выражением <span class="f">{f}</span>. Дан частично заполненный фрагмент, '
     'содержащий неповторяющиеся строки таблицы истинности функции F.'),
    ('Логическая функция F задаётся выражением <span class="f">{f}</span>. На рисунке приведён частично заполненный '
     'фрагмент таблицы истинности функции F, содержащий {nn} неповторяющиеся строки.'),
]
ASK = ('Определите, какому столбцу таблицы истинности соответствует каждая из переменных {vs}. '
       'В ответе напишите буквы {vs} в том порядке, в котором идут соответствующие им столбцы '
       '(сначала буква, соответствующая первому столбцу; затем — второму и т. д.). '
       'Буквы в ответе пишите подряд, никаких разделителей ставить не нужно.')
NUM = {3: 'трёх', 4: 'четырёх'}
NUM_NOM = {3: 'три', 4: 'четыре'}


def table_html(frag, fv):
    n = len(frag[0])
    head = '<tr>' + '<th>?</th>' * n + '<th>F</th></tr>'
    rows = ''.join('<tr>' + ''.join(f'<td>{"" if c is None else c}</td>' for c in r) + f'<td>{f}</td></tr>' for r, f in zip(frag, fv))
    return f'<div class="tblwrap"><table class="tt">{head}{rows}</table></div>'


def code_for(e, vs, frag, fv):
    holes = sum(c is None for r in frag for c in r)
    k = iter(range(holes))
    rows = ', '.join('(' + ', '.join(f'p[{next(k)}]' if c is None else str(c) for c in r) + ')' for r in frag)
    if len(frag) == 1:
        rows += ','
    fcheck = f'F(**dict(zip(names, row))) == {fv[0]} for row in t' if len(set(fv)) == 1 else \
        f'F(**dict(zip(names, row))) == f for row, f in zip(t, {fv})'
    return ('from itertools import product, permutations\n\n'
            f'def F({", ".join(vs)}):\n'
            f'    return {py(e)}\n\n'
            'ans = set()\n'
            f'for p in product([0, 1], repeat={holes}):\n'
            f'    t = [{rows}]\n'
            '    if len(set(t)) < len(t):      # строки фрагмента должны быть различны\n'
            '        continue\n'
            f"    for names in permutations('{''.join(vs)}'):\n"
            f'        if all({fcheck}):\n'
            "            ans.add(''.join(names))\n"
            'print(*ans)')


def hint(e, fv):
    """Короткая подсказка: с чего начать рассуждение."""
    k = e[0]
    parts = []
    def flat(x, op):
        return flat(x[1], op) + flat(x[2], op) if x[0] == op else [x]
    if len(set(fv)) == 1 and fv[0] == 0 and k == 'or':
        parts = flat(e, 'or')
        return 'F = 0 только если ложны все части дизъюнкции: ' + ', '.join(show(p) + ' = 0' for p in parts) + '. Начните с части, которая сильнее всего ограничивает значения.'
    if len(set(fv)) == 1 and fv[0] == 1 and k == 'and':
        parts = flat(e, 'and')
        return 'F = 1 только если истинны все части конъюнкции: ' + ', '.join(show(p) + ' = 1' for p in parts) + '. Начните с части, которая сильнее всего ограничивает значения.'
    if k == 'imp' and len(set(fv)) == 1 and fv[0] == 0:
        return f'Импликация ложна только при истинной посылке и ложном следствии: {show(e[1])} = 1 и {show(e[2])} = 0.'
    return ('Здесь значения F в строках разные или функция не распадается на простые условия — надёжнее перебрать '
            'заполнения пустых клеток и перестановки переменных (см. решение на Python).')


PLAN = (
    # базовый: 3 строки, F постоянна, немного пропусков; часть — от трёх переменных
    [('Б', 3, 3, 1, 2, 2, False)] * 4 + [('Б', 3, 3, 0, 2, 2, False)] * 4 +
    [('Б', 4, 3, 1, 3, 2, False)] * 7 + [('Б', 4, 3, 0, 3, 2, False)] * 7 +
    [('Б', 4, 3, 1, 4, 3, False)] * 6 + [('Б', 4, 3, 0, 4, 3, False)] * 7 +
    # средний: столбец F со значениями 0 и 1, больше пропусков, вложенные эквиваленции
    [('П', 4, 3, 'mix', 5, 3, True)] * 5 + [('П', 4, 4, 'mix', 6, 3, True)] * 3 + [('П', 4, 3, 0, 5, 3, True)] * 2 +
    # сложный: почти пустой фрагмент, глубокие формулы
    [('В', 4, 3, 'mix', 6, 3, True)] * 3 + [('В', 4, 3, 1, 6, 3, True)] * 1 + [('В', 4, 3, 0, 6, 3, True)] * 1
)


def main():
    rng = random.Random(SEED)
    out, seen = [], set()
    for k, (level, nv, nr, fm, holes, ncl, deep) in enumerate(PLAN, 1):
        pid = f'2-g{k:02d}'
        while True:
            e, vs, frag, fv, ans = build(rng, pid, level, nv, nr, fm, holes, ncl, deep)
            f = show(e)
            if f not in seen:
                seen.add(f); break
        vlist = ', '.join(vs)
        intro = rng.choice(INTROS).format(f=f, ng=NUM[nr], nn=NUM_NOM[nr], vs=vlist)
        fvals = 'F = 1' if set(fv) == {1} else 'F = 0' if set(fv) == {0} else 'F = 0 и 1'
        out.append({'id': pid, 'task': 2, 'level': level,
                    'title': f'{fvals}: {f}' if len(f) <= 46 else f'{fvals}: {f[:44]}…',
                    'text': intro + ' ' + ASK.format(vs=vlist),
                    'extra': table_html(frag, fv), 'code': code_for(e, vs, frag, fv), 'answer': ans,
                    'data': '', 'dname': '', 'note': hint(e, fv)})
    for p in out:
        r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=120)
        if r.stdout.strip() != p['answer']:
            raise SystemExit(f"{p['id']}: решение даёт «{r.stdout.strip()}», ответ «{p['answer']}»\n{r.stderr}")
    titles = [p['title'] for p in out]
    assert len(set(titles)) == len(titles), 'повтор заголовков'
    stat = {}
    for p in out:
        stat[p['level']] = stat.get(p['level'], 0) + 1
    print(json.dumps(stat, ensure_ascii=False), file=sys.stderr)
    json.dump(out, sys.stdout, ensure_ascii=False)


if __name__ == '__main__':
    main()
