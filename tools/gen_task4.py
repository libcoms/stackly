#!/usr/bin/env python3
"""Генератор задач ЕГЭ №4 (неравномерный код, условие Фано) для банка stackly.

    python3 tools/gen_task4.py > /tmp/task4.json      # 100 задач: 55 базовых, 30 средних, 15 сложных

Задача описывается spec: семейство (кратчайшее слово для буквы, наименьшая сумма длин, сколько букв ещё
поместится, длина сообщения по Хаффману, троичный код, сообщение при части известных кодов) и данные — известные
кодовые слова, число новых букв, частоты. Ответ ищется перебором наборов длин с жадной раскладкой слов по
свободным веткам (короткие — первыми). Решение на Python из задачи запускается и должно вывести ответ. Spec
хранится HTML-комментарием <!--spec:…--> — tests/test_bank_task4.py пересчитывает ответ своим способом (обходом
дерева кодов). Генерация детерминирована (seed).
"""
import heapq, json, os, random, subprocess, sys
from collections import Counter
from fractions import Fraction as Fr
from itertools import combinations_with_replacement, product

SEED = 20261023
LET = 'АБВГДЕЖЗИКЛМНОПРСТ'
WORDS = ['КАРАКАТИЦА', 'АБРАКАДАБРА', 'ПАРАЛЛЕЛЕПИПЕД', 'ИНФОРМАТИКА', 'КОЛОКОЛЬЧИК', 'ВОДОВОРОТ',
         'ПЕРЕПЕЛКА', 'МОЛОКОВОЗ', 'ОБОРОНОСПОСОБНОСТЬ', 'ПРОГРАММИРОВАНИЕ', 'ПЕРЕВОЗЧИК', 'КОЛОКОЛА',
         'ДЕРЕВООБРАБОТКА', 'ТЕЛЕПЕРЕДАЧА', 'САМОСОВЕРШЕНСТВОВАНИЕ', 'КОНСТАНТИНОПОЛЬ', 'ЭЛЕКТРОСТАНЦИЯ',
         'КАНЦЕЛЯРИЯ', 'ПАРАШЮТИСТ', 'ВЕЛОСИПЕДИСТ']
NUMW = {2: 'двух', 3: 'трёх', 4: 'четырёх', 5: 'пяти', 6: 'шести', 7: 'семи', 8: 'восьми'}


def plural(n, one, few, many):
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def listing(xs):
    xs = list(xs)
    return xs[0] if len(xs) == 1 else ', '.join(xs[:-1]) + ' и ' + xs[-1]


# ------------------------------------------------------------------ дерево кодов
def fits(w, codes):
    """Слово w можно добавить: оно не начало другого слова и другое слово не его начало."""
    return all(not w.startswith(c) and not c.startswith(w) for c in codes)


def free_roots(codes, b):
    """Свободные ветки: самые верхние узлы, под которыми нет занятых слов и которые сами не под занятым."""
    out, stack = [], [str(d) for d in range(b)]
    while stack:
        v = stack.pop()
        if v in codes:
            continue
        if any(c.startswith(v) for c in codes):
            stack += [v + str(d) for d in range(b)]
        else:
            out.append(v)
    return sorted(out, key=lambda w: (len(w), w))


def place(lengths, fixed, b):
    """Жадная раскладка: короткие слова первыми, каждое — в первую подходящую ветку. None — не помещаются."""
    codes, new = list(fixed), []
    for L in sorted(lengths):
        for p in product('0123'[:b], repeat=L):
            w = ''.join(p)
            if fits(w, codes):
                codes.append(w)
                new.append(w)
                break
        else:
            return None
    return new


def best(weights, fixed, b):
    """Наименьшая Σ вес·длина для новых букв. Возвращает (стоимость, длины по убыванию весов, слова)."""
    ws = sorted(weights, reverse=True)
    roots = free_roots(fixed, b)
    cap = sum(Fr(1, b ** len(r)) for r in roots)
    top = max(len(r) for r in roots) + len(ws)
    res = None
    for ls in combinations_with_replacement(range(1, top + 1), len(ws)):
        if sum(Fr(1, b ** L) for L in ls) > cap:
            continue
        cost = sum(w * L for w, L in zip(ws, ls))
        if res and cost >= res[0]:
            continue
        words = place(ls, fixed, b)
        if words:
            res = (cost, ls, words)
    return res


def shortest(fixed, b, rest):
    """Кратчайшее (а среди них наименьшее) слово, после которого для rest букв ещё есть место."""
    for L in range(1, 12):
        for p in product('0123'[:b], repeat=L):
            w = ''.join(p)
            if fits(w, fixed) and (rest == 0 or free_roots(fixed + [w], b)):
                return w
    raise ValueError


def huffman(counts, b=2):
    h = list(counts)
    while (len(h) - 1) % (b - 1):
        h.append(0)
    heapq.heapify(h)
    total, merges = 0, []
    while len(h) > 1:
        part = [heapq.heappop(h) for _ in range(b)]
        total += sum(part)
        merges.append(part)
        heapq.heappush(h, sum(part))
    return total, merges


# ------------------------------------------------------------------ ответ по spec
def answer(sp):
    f, b = sp['f'], sp.get('b', 2)
    fixed = list(sp['fix'].values()) if 'fix' in sp else []
    if f == 'short':
        return shortest(fixed, b, 0)
    if f == 'short2':
        return shortest(fixed, b, len(sp['rest']))
    if f == 'count':
        return sum(b ** (sp['L'] - len(r)) for r in free_roots(fixed, b) if len(r) <= sp['L'])
    if f == 'msg':
        return huffman(Counter(sp['word']).values())[0]
    if f in ('sumAll', 'sumRest', 'sumBig', 'tern', 'ternFix'):
        cost = best([1] * sp['k'], fixed, b)[0]
        return cost + (sum(map(len, fixed)) if sp['q'] == 'all' else 0)
    if f in ('msgFix', 'ternMsg'):
        cnt = sp['cnt']
        rest = [c for ch, c in cnt.items() if ch not in sp['fix']]
        return best(rest, fixed, b)[0] + sum(cnt[ch] * len(w) for ch, w in sp['fix'].items())
    raise ValueError(f)


# ------------------------------------------------------------------ случайные данные
def rand_code(rng, b, nleaves, maxd):
    leaves = [str(d) for d in range(b)]
    while len(leaves) < nleaves:
        cand = [w for w in leaves if len(w) < maxd]
        if not cand:
            return None
        w = rng.choice(cand)
        leaves.remove(w)
        leaves += [w + str(d) for d in range(b)]
    return leaves


def rand_fixed(rng, b, nfix, nfree, maxd):
    leaves = rand_code(rng, b, nfix + nfree, maxd)
    if not leaves:
        return None
    rng.shuffle(leaves)
    return leaves[:nfix]


def fix_dict(fixed):
    return {LET[i]: w for i, w in enumerate(fixed)}


def rand_spec(rng, fam):
    if fam in ('short', 'short2'):
        nfix = rng.randint(3, 6)
        rest = rng.randint(1, 3) if fam == 'short2' else 0
        fixed = rand_fixed(rng, 2, nfix, rng.randint(1, 3), rng.randint(3, 5))
        if not fixed:
            return None
        sp = {'f': fam, 'fix': fix_dict(fixed), 'x': LET[nfix]}
        if fam == 'short2':
            sp['rest'] = list(LET[nfix + 1:nfix + 1 + rest])
            if shortest(fixed, 2, 0) == shortest(fixed, 2, rest):
                return None                       # интересно, только если первое свободное слово не годится
        elif len(shortest(fixed, 2, 0)) < 2:
            return None
        return sp
    if fam == 'count':
        fixed = rand_fixed(rng, 2, rng.randint(2, 5), rng.randint(1, 3), rng.randint(3, 4))
        if not fixed:
            return None
        L = max(map(len, fixed)) + rng.choice([0, 1, 1, 2])
        return {'f': fam, 'fix': fix_dict(fixed), 'L': L}
    if fam in ('sumAll', 'sumRest', 'sumBig', 'tern', 'ternFix'):
        b = 3 if fam.startswith('tern') else 2
        nfix, k = {'sumAll': (rng.randint(2, 4), rng.randint(2, 4)), 'sumRest': (rng.randint(2, 4), rng.randint(2, 4)),
                   'sumBig': (rng.randint(3, 5), rng.randint(4, 7)), 'tern': (rng.randint(2, 4), rng.randint(2, 5)),
                   'ternFix': (rng.randint(3, 6), rng.randint(5, 8))}[fam]
        fixed = rand_fixed(rng, b, nfix, rng.randint(1, 3), rng.randint(3, 4) if b == 2 else 3)
        if not fixed:
            return None
        q = 'rest' if fam == 'sumRest' or (fam != 'sumAll' and rng.random() < .4) else 'all'
        return {'f': fam, 'b': b, 'fix': fix_dict(fixed), 'k': k, 'q': q}
    if fam == 'msg':
        return {'f': fam, 'word': rng.choice(WORDS)}
    if fam in ('msgFix', 'ternMsg'):
        b = 3 if fam == 'ternMsg' else 2
        n = rng.randint(6, 9)
        cnt = {LET[i]: rng.randint(1, 30) for i in range(n)}
        nfix = rng.randint(2, 3)
        fixed = rand_fixed(rng, b, nfix, rng.randint(1, 3), 4 if b == 2 else 3)
        if not fixed:
            return None
        letters = rng.sample(LET[:n], nfix)
        return {'f': fam, 'b': b, 'cnt': cnt, 'fix': {ch: w for ch, w in zip(sorted(letters), fixed)}}
    raise ValueError(fam)


# ------------------------------------------------------------------ текст, код, пояснение
INTRO = [
    'По каналу связи передаются сообщения, содержащие только буквы {L}. Для передачи используется {code}, '
    'удовлетворяющий условию Фано: никакое кодовое слово не является началом другого кодового слова.',
    'Для кодирования некоторой последовательности, состоящей из букв {L}, используется {code}, удовлетворяющий '
    'условию Фано (никакое кодовое слово не является началом другого кодового слова).',
    'Сообщения из букв {L} кодируются: каждой букве сопоставляется кодовое слово, и используется {code} с условием '
    'Фано — никакое кодовое слово не совпадает с началом другого.',
]
CODE = {2: 'неравномерный двоичный код', 3: 'неравномерный троичный код (кодовые слова состоят из цифр 0, 1 и 2)'}


def known(fix):
    keys = list(fix)
    words = listing(f'<code>{fix[k]}</code>' for k in keys)
    if len(keys) == 1:
        return f'Для буквы {keys[0]} использовали кодовое слово {words}.'
    return f'Для букв {listing(keys)} использовали кодовые слова {words} соответственно.'


def roots_text(fixed, b):
    rs = free_roots(fixed, b)
    return ', '.join(f'{r} (длина {len(r)})' for r in rs)


def py_list(xs):
    return '[' + ', '.join(f"'{x}'" for x in xs) + ']'


HEAD = '''from itertools import product{extra}

digits = '{digits}'
fixed = {fixed}{comment}


def fits(w, codes):
    """w не начало ни одного слова из codes, и ни одно из них не начало w."""
    return all(not w.startswith(c) and not c.startswith(w) for c in codes)
'''

PLACE = '''

def place(lengths):
    """Раздать слова таких длин: короткие — первыми, каждое — в первую свободную ветку."""
    codes = fixed[:]
    for L in sorted(lengths):
        for p in product(digits, repeat=L):
            if fits(''.join(p), codes):
                codes.append(''.join(p))
                break
        else:
            return False
    return True
'''


def head(sp, extra=''):
    b = sp.get('b', 2)
    fix = sp['fix']
    return HEAD.format(extra=extra, digits='012'[:b], fixed=py_list(fix.values()),
                       comment=f'{" " * max(1, 34 - len(py_list(fix.values())))}# {", ".join(fix)}')


def build(sp, ans):
    f, b = sp['f'], sp.get('b', 2)
    fix = sp.get('fix', {})
    fixed = list(fix.values())
    rng = random.Random(json.dumps(sp, sort_keys=True))
    intro = rng.choice(INTRO)
    if f in ('short', 'short2'):
        letters = list(fix) + [sp['x']] + sp.get('rest', [])
        text = intro.format(L=listing(letters), code=CODE[b]) + ' ' + known(fix) + ' '
        if f == 'short':
            text += (f'Укажите <b>кратчайшее</b> кодовое слово для буквы {sp["x"]}, при котором код будет удовлетворять '
                     'условию Фано. Если таких кодов несколько, укажите код с <b>наименьшим числовым значением</b>.')
        else:
            r = sp['rest']
            text += (f'Укажите <b>кратчайшее</b> кодовое слово для буквы {sp["x"]}, при котором код будет удовлетворять '
                     f'условию Фано и для {"буквы" if len(r) == 1 else "букв"} {listing(r)} тоже можно будет подобрать '
                     f'{"кодовое слово" if len(r) == 1 else "кодовые слова"}. Если таких кодов несколько, укажите код с <b>наименьшим числовым значением</b>.')
        code = head(sp)
        if f == 'short':
            code += '''

for L in range(1, 10):                      # сначала короткие слова
    good = [''.join(p) for p in product(digits, repeat=L) if fits(''.join(p), fixed)]
    if good:                                # product перебирает слова по возрастанию значения
        print(good[0])
        break
'''
        else:
            code += f'''

def room(codes):
    """Осталась ли хоть одна свободная ветка: тогда в неё поместится сколько угодно букв."""
    return any(fits(''.join(p), codes) for L in range(1, 10) for p in product(digits, repeat=L))


for L in range(1, 10):
    good = [''.join(p) for p in product(digits, repeat=L)
            if fits(''.join(p), fixed) and room(fixed + [''.join(p)])]
    if good:
        print(good[0])                      # для {listing(sp['rest'])} место остаётся
        break
'''
        note = f'Занятые слова: {", ".join(fixed)}. Свободные ветки дерева: {roots_text(fixed, b)}. '
        if f == 'short':
            note += f'Берём самую короткую, а среди равных — с наименьшим значением: {ans}.'
        else:
            naive = shortest(fixed, b, 0)
            left = ', '.join(free_roots(fixed + [ans], b))
            note += (f'Слово {naive} подошло бы для {sp["x"]}, но после него свободных веток не останется и '
                     f'{listing(sp["rest"])} закодировать будет нельзя. Кратчайшее слово, после которого место '
                     f'остаётся, — {ans}: свободными остаются {left}, туда и пойдут {listing(sp["rest"])}.')
        ttl = (f'Кратчайший код для {sp["x"]}: ' if f == 'short' else f'Код для {sp["x"]} с запасом: ') + ', '.join(fixed)
        return text, code, note, ttl

    if f == 'count':
        text = (f'Для кодирования букв используется {CODE[b]}, удовлетворяющий условию Фано (никакое кодовое слово '
                f'не является началом другого). Уже выбраны кодовые слова: '
                + ', '.join(f'{k} — <code>{w}</code>' for k, w in fix.items())
                + f'. Какое <b>наибольшее</b> количество букв можно ещё закодировать, если длина каждого нового '
                  f'кодового слова должна быть <b>не больше {sp["L"]}</b>?')
        code = head(sp) + f'''

L = {sp['L']}
# больше всего слов — если все новые слова длины ровно L: слово короче занимает место нескольких
print(sum(fits(''.join(p), fixed) for p in product(digits, repeat=L)))
'''
        parts = [(r, b ** (sp['L'] - len(r))) for r in free_roots(fixed, b) if len(r) <= sp['L']]
        note = (f'Свободные ветки дерева: {roots_text(fixed, b)}. Ветка длины d вмещает {b}<sup>{sp["L"]}−d</sup> '
                f'слов длины {sp["L"]}: ' + ' + '.join(str(c) for _, c in parts) + f' = {ans}. Слова короче брать '
                f'невыгодно: одно слово длины {sp["L"] - 1} занимает место {b} слов длины {sp["L"]}.')
        return text, code, note, f'Сколько ещё букв (до {sp["L"]} знаков): ' + ', '.join(fixed)

    if f in ('sumAll', 'sumRest', 'sumBig', 'tern', 'ternFix'):
        k = sp['k']
        new = list(LET[len(fix):len(fix) + k])
        text = intro.format(L=listing(list(fix) + new), code=CODE[b]) + ' ' + known(fix) + ' '
        if sp['q'] == 'all':
            text += 'Какова <b>наименьшая возможная суммарная длина</b> всех кодовых слов?'
        else:
            text += f'Укажите <b>наименьшую возможную сумму длин</b> кодовых слов для букв {listing(new)}.'
        cost, ls, words = best([1] * k, fixed, b)
        top = max(ls) + 1
        code = head(sp, ', combinations_with_replacement') + PLACE + f'''

k = {k}                                       # {", ".join(new)} — кодов пока нет
M = {top}                                       # длиннее слова не понадобятся
# неравенство Крафта сразу отсекает наборы длин, которым точно не хватит места
best = min(sum(ls) for ls in combinations_with_replacement(range(1, M + 1), k)
           if sum({b} ** (M - L) for L in ls) <= {b} ** M and place(ls))
print(best{" + sum(len(c) for c in fixed)" if sp['q'] == 'all' else ''})
'''
        roots = free_roots(fixed, b)
        note = (f'Занятые слова: {", ".join(fixed)}. Свободные ветки: {roots_text(fixed, b)}. Нужно {k} '
                f'{plural(k, "новое слово", "новых слова", "новых слов")}'
                + ('' if k <= len(roots) else
                   f', а свободных веток {len(roots)} — значит, часть веток придётся делить') +
                '. Лучший вариант: ' + ', '.join(f'{c} — {w}' for c, w in zip(new, words))
                + f'; сумма длин новых слов {" + ".join(map(str, sorted(ls)))} = {cost}')
        note += (f', вместе с известными ({" + ".join(str(len(w)) for w in fixed)}) — {ans}.' if sp['q'] == 'all' else '.')
        kind = 'Троичный код' if b == 3 else 'Сумма длин'
        ttl = f'{kind}: +{k} {plural(k, "буква", "буквы", "букв")} к ' + ', '.join(fixed) + \
            ('' if sp['q'] == 'all' else ' (только новые)')
        return text, code, note, ttl

    if f == 'msg':
        w = sp['word']
        cnt = Counter(w)
        text = (f'Слово <b>{w}</b> нужно закодировать неравномерным двоичным кодом, удовлетворяющим условию Фано '
                '(каждой букве — своё кодовое слово, никакое слово не является началом другого). Какое '
                '<b>наименьшее</b> количество двоичных знаков потребуется для кодирования этого слова?')
        code = f'''import heapq
from collections import Counter

word = '{w}'
h = list(Counter(word).values())          # сколько раз встречается каждая буква
heapq.heapify(h)
total = 0
while len(h) > 1:                         # алгоритм Хаффмана: сливаем две самые редкие группы
    a, b = heapq.heappop(h), heapq.heappop(h)
    total += a + b                        # каждая буква этих групп получает ещё один знак кода
    heapq.heappush(h, a + b)
print(total)
'''
        _, merges = huffman(cnt.values())
        order = sorted(cnt.items(), key=lambda x: (-x[1], x[0]))
        note = ('Частоты букв: ' + ', '.join(f'{c} — {n}' for c, n in order) + '. Алгоритм Хаффмана: объединяем две '
                'самые редкие группы, пока не останется одна: ' + ', '.join(f'{x}+{y}={x + y}' for x, y in merges)
                + '. Длина кода равна сумме всех полученных сумм: '
                + ' + '.join(str(x + y) for x, y in merges) + f' = {ans}.')
        return text, code, note, f'Хаффман: слово {w}'

    if f in ('msgFix', 'ternMsg'):
        cnt = sp['cnt']
        total = sum(cnt.values())
        text = (f'Сообщение длиной {total} {plural(total, "символ", "символа", "символов")} содержит только буквы '
                + ', '.join(f'{ch} ({n} {plural(n, "раз", "раза", "раз")})' for ch, n in cnt.items())
                + f'. Его кодируют, используя {CODE[b]}, удовлетворяющий условию Фано (никакое кодовое слово не '
                  'является началом другого). ' + known(fix)
                + ' Кодовые слова остальных букв нужно подобрать так, чтобы закодированное сообщение было как можно '
                  'короче. Какова <b>наименьшая возможная длина</b> закодированного сообщения (в знаках)?')
        rest = sorted(((n, ch) for ch, n in cnt.items() if ch not in fix), key=lambda x: (-x[0], x[1]))
        cost, ls, words = best([n for n, _ in rest], fixed, b)
        top = max(ls) + 1
        code = head(sp, ', combinations_with_replacement') + PLACE + f'''

cnt = {{{', '.join(f"'{ch}': {n}" for ch, n in cnt.items())}}}
code = {{{', '.join(f"'{ch}': '{w}'" for ch, w in fix.items())}}}
rest = sorted((n for ch, n in cnt.items() if ch not in code), reverse=True)
# частым буквам — короткие слова: длины перебираем по возрастанию, частоты — по убыванию
M = {top}                                   # длиннее слова не понадобятся
best = min(sum(n * L for n, L in zip(rest, ls))
           for ls in combinations_with_replacement(range(1, M + 1), len(rest))
           if sum({b} ** (M - L) for L in ls) <= {b} ** M and place(ls))
print(best + sum(cnt[ch] * len(w) for ch, w in code.items()))
'''
        fixed_part = sum(cnt[ch] * len(w) for ch, w in fix.items())
        note = (f'Известные буквы дают {" + ".join(f"{cnt[ch]}·{len(w)}" for ch, w in fix.items())} = {fixed_part} '
                f'{plural(fixed_part, "знак", "знака", "знаков")}. Свободные ветки: {roots_text(fixed, b)}. '
                'Остальные буквы по убыванию частоты: ' + ', '.join(f'{ch} ({n})' for n, ch in rest)
                + '; частым — короткие слова. Лучший набор: '
                + ', '.join(f'{ch} — {w}' for (n, ch), w in zip(rest, words))
                + f', это {" + ".join(f"{n}·{L}" for (n, _), L in zip(rest, ls))} = {cost}. Итого {fixed_part} + {cost} = {ans}.')
        kind = 'Троичный код' if b == 3 else 'Длина сообщения'
        ttl = f'{kind}: {len(cnt)} букв, известны ' + ', '.join(f'{ch}={w}' for ch, w in fix.items())
        return text, code, note, ttl
    raise ValueError(f)


PLAN = (
    # базовый: кратчайшее слово, сумма длин всех/новых слов, сколько ещё букв поместится
    [('Б', 'short')] * 16 + [('Б', 'sumAll')] * 14 + [('Б', 'sumRest')] * 13 + [('Б', 'count')] * 12 +
    # средний: кратчайшее слово с запасом для других букв, Хаффман для слова, троичный код, много букв
    [('П', 'short2')] * 8 + [('П', 'msg')] * 8 + [('П', 'tern')] * 7 + [('П', 'sumBig')] * 7 +
    # сложный: сообщение при части известных кодов (двоичный и троичный), большой троичный код
    [('В', 'msgFix')] * 6 + [('В', 'ternFix')] * 5 + [('В', 'ternMsg')] * 4
)


def make(rng, fam):
    for _ in range(100000):
        sp = rand_spec(rng, fam)
        if not sp:
            continue
        a = answer(sp)
        if isinstance(a, int) and a < 2:
            continue
        return sp, a
    raise RuntimeError(f'не удалось собрать {fam}')


def main():
    rng = random.Random(SEED)
    out, seen = [], set()
    for k, (level, fam) in enumerate(PLAN, 1):
        while True:
            sp, ans = make(rng, fam)
            text, code, note, ttl = build(sp, ans)
            key = sp.get('word') or json.dumps(sp.get('fix'))
            if ttl not in {p['title'] for p in out} and (fam, key) not in seen:
                seen.add((fam, key))
                break
        meta = json.dumps(sp, ensure_ascii=False, separators=(',', ':'))
        out.append({'id': f'4-g{k:03d}', 'task': 4, 'level': level, 'title': ttl, 'text': text,
                    'extra': f'<!--spec:{meta}-->', 'code': code, 'answer': str(ans), 'data': '', 'dname': '',
                    'note': note})
    for p in out:
        r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=120,
                           encoding='utf-8', env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        if r.stdout.strip() != p['answer']:
            raise SystemExit(f"{p['id']}: решение даёт «{r.stdout.strip()}», ответ «{p['answer']}»\n{r.stderr}\n{p['code']}")
    stat = {}
    for p in out:
        stat[p['level']] = stat.get(p['level'], 0) + 1
    print(json.dumps(stat, ensure_ascii=False), file=sys.stderr)
    sys.stdout.reconfigure(encoding='utf-8')
    json.dump(out, sys.stdout, ensure_ascii=False)


if __name__ == '__main__':
    main()
