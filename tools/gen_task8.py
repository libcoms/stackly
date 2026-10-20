#!/usr/bin/env python3
"""Генератор задач ЕГЭ №8 (комбинаторика: слова, перестановки, числа, номер в алфавитном списке) для банка stackly.

    python3 tools/gen_task8.py > /tmp/task8.json      # 100 задач: 55 базовых, 30 средних, 15 сложных

Задача описывается spec: какие объекты перебираются (слова из букв, перестановки букв слова, числа в системе
счисления, алфавитный список слов), набор условий и вопрос. По spec строятся текст условия, решение на Python
и ответ (полным перебором). Решение запускается и должно вывести ответ. Для простых задач к пояснению добавляется
решение «руками» по формуле — генератор проверяет, что формула даёт тот же ответ. Spec хранится в задаче
HTML-комментарием <!--spec:…--> — по нему tests/test_bank_task8.py пересчитывает ответ своим перебором.
Генерация детерминирована (seed).
"""
import json, math, random, subprocess, sys
from itertools import permutations, product

SEED = 20261020
VOW = 'АЕИОУЫЭЮЯ'
DIG = '0123456789ABCDEF'
NUM = {1: 'один', 2: 'два', 3: 'три', 4: 'четыре'}
BASE_ADJ = {3: 'троичной', 4: 'четверичной', 5: 'пятеричной', 6: 'шестеричной', 7: 'семеричной', 8: 'восьмеричной',
            9: 'девятеричной', 10: 'десятичной', 12: 'двенадцатеричной', 16: 'шестнадцатеричной'}
BASE_SHORT = {3: 'Троичные', 4: 'Четверичные', 5: 'Пятеричные', 6: 'Шестеричные', 7: 'Семеричные', 8: 'Восьмеричные',
              9: 'Девятеричные', 10: 'Десятичные', 12: 'Двенадцатеричные', 16: 'Шестнадцатеричные'}
LEN_ADJ = {3: 'трёхзначных', 4: 'четырёхзначных', 5: 'пятизначных', 6: 'шестизначных', 7: 'семизначных'}
LEN_NOM = {3: 'трёхзначные', 4: 'четырёхзначные', 5: 'пятизначные', 6: 'шестизначные', 7: 'семизначные'}
# слова с разными буквами — из них берутся алфавиты; с Й — для условий «Й не стоит после гласной»
ALPHS = ['ЛИМОН', 'ПАРУС', 'ГРОЗА', 'ВЕКТОР', 'МАРС', 'ШАРФ', 'ДЕКОР', 'ФЛОТ', 'ПИРОГ', 'ВОЛНА', 'КАРТЕЖ',
         'МУЗЫКА', 'СТОЛ', 'КЛАД', 'ЗЕБРА', 'ПЛОВ', 'ГЕНИЙ', 'СУХАРЬ']
ALPHS_Y = ['ТАЙМЕР', 'ЙОГУРТ', 'КЛЕЙ', 'СОЙКА', 'ЛАЙНЕР', 'ЧАЙКО']
PERM_UNIQ = ['ЗЕБРА', 'ЛИСТОК', 'ФОНАРИК', 'ПЕСКАРЬ', 'КОМПАС', 'ГРУЗИК', 'МОРЯК', 'ПРИЧАЛ']
PERM_REP = ['ПАРАБОЛА', 'КОЛОКОЛ', 'ТРАКТОР', 'БАРАБАН', 'МОЛОКО', 'ТРАССА', 'КАРКАС', 'ВОРОНА', 'СОСИСКА',
            'АНАНАС', 'КАРТОШКА', 'ЛОПАТА', 'ТЕЛЕФОН', 'ПАПАХА', 'АВОКАДО', 'КАРАВАН']
NAMES = [('Петя', 'составляет', 'может составить'), ('Маша', 'составляет', 'может составить'),
         ('Вася', 'составляет', 'может составить'), ('Аня', 'составляет', 'может составить'),
         ('Миша', 'составляет', 'может составить'), ('Оля', 'составляет', 'может составить')]


# ------------------------------------------------------------------ объекты перебора
def objects(sp):
    """Все объекты задачи — в порядке, в котором их нумерует алфавитный список (для подсчёта порядок не важен)."""
    k = sp['kind']
    if k == 'words':
        return [''.join(w) for w in product(sp['alph'], repeat=sp['k'])]
    if k == 'nums':
        return [''.join(w) for w in product(DIG[:sp['b']], repeat=sp['k']) if w[0] != '0']
    if k == 'perm':
        return sorted(set(''.join(w) for w in permutations(sp['src'])))
    raise ValueError(k)


def dval(c):
    return int(c, 16)


def ok(c, s):
    t = c['c']
    if t == 'cnt':
        return cmp(s.count(c['x']), c['op'], c['v'])
    if t == 'cntset':
        return cmp(sum(ch in c['set'] for ch in s), c['op'], c['v'])
    if t == 'first':
        return (s[0] in c['set']) != c['neg']
    if t == 'last':
        return (s[-1] in c['set']) != c['neg']
    if t == 'noadj':
        return not any(s[i] in c['set'] and s[i + 1] in c['set'] for i in range(len(s) - 1))
    if t == 'noafter':
        return not any(s[i] in c['set'] and s[i + 1] == c['x'] for i in range(len(s) - 1))
    if t == 'nonext':
        return not any((s[i] == c['x'] and s[i + 1] in c['set']) or (s[i] in c['set'] and s[i + 1] == c['x'])
                       for i in range(len(s) - 1))
    if t == 'nosame':
        return all(s[i] != s[i + 1] for i in range(len(s) - 1))
    if t == 'distinct':
        return len(set(s)) == len(s)
    if t == 'sub':
        return (c['s'] in s) != c['neg']
    if t == 'altpar':
        return all(dval(s[i]) % 2 != dval(s[i + 1]) % 2 for i in range(len(s) - 1))
    if t == 'nondec':
        return all(dval(s[i]) <= dval(s[i + 1]) for i in range(len(s) - 1))
    if t == 'sumdiv':
        return sum(dval(ch) for ch in s) % c['m'] == 0
    raise ValueError(t)


def cmp(a, op, v):
    return a == v if op == '==' else a <= v if op == '<=' else a >= v


def answer(sp):
    objs = objects(sp)
    good = [(i, s) for i, s in enumerate(objs, 1) if all(ok(c, s) for c in sp['conds'])]
    q = sp['q']
    t = q['t']
    if t == 'count':
        return len(good)
    if t == 'first':
        return good[0][0] if good else None
    if t == 'last':
        return good[-1][0] if good else None
    if t == 'num_of':
        return objs.index(q['w']) + 1
    if t == 'word_at':
        return objs[q['N'] - 1]
    if t == 'max_odd':
        return max((i for i, _ in good if i % 2), default=None)
    if t == 'cnt_even':
        return sum(i % 2 == 0 for i, _ in good)
    raise ValueError(t)


# ------------------------------------------------------------------ текст условий
NOUN = {  # им. ед., им. мн. (2–4), род. мн., род. ед., твор. ед.
    'vow': ('гласная', 'гласные', 'гласных', 'гласной', 'гласной'),
    'cons': ('согласная', 'согласные', 'согласных', 'согласной', 'согласной'),
    'odd': ('нечётная цифра', 'нечётные цифры', 'нечётных цифр', 'нечётной цифры', 'нечётной цифрой'),
    'even': ('чётная цифра', 'чётные цифры', 'чётных цифр', 'чётной цифры', 'чётной цифрой'),
}


def unit(sp):
    return 'цифра' if sp['kind'] == 'nums' else 'буква'


def where(sp):
    return 'в записи числа' if sp['kind'] == 'nums' else 'в слове'


def who(sp):
    return 'запись числа' if sp['kind'] == 'nums' else 'слово'


def times(op, v):
    if op == '==':
        return {1: 'ровно один раз', 2: 'ровно два раза', 3: 'ровно три раза', 4: 'ровно четыре раза'}[v]
    if op == '<=':
        return {1: 'не более одного раза', 2: 'не более двух раз', 3: 'не более трёх раз'}[v]
    return {1: 'хотя бы один раз', 2: 'не менее двух раз', 3: 'не менее трёх раз'}[v]


def how_many(nm, op, v):
    one, few, many, gen1, _ = NOUN[nm]
    if op == '==':
        if v == 1:
            return 'ровно одна ' + one
        return f'ровно {["", "", "две", "три", "четыре"][v]} {few}'
    if op == '<=':
        return 'не более одной ' + gen1 if v == 1 else f'не более {["", "", "двух", "трёх", "четырёх"][v]} {many}'
    return 'хотя бы одна ' + one if v == 1 else f'не менее {["", "", "двух", "трёх", "четырёх"][v]} {many}'


def set_word(sp, c, case):
    """«гласной» / «буквы К или Л» / «цифры 3» — для «начинается с …», «рядом с …»."""
    if c.get('nm'):
        return NOUN[c['nm']][4] if case == 'ins' else NOUN[c['nm']][3]
    xs = list(c['set'])
    u = unit(sp)
    if case == 'ins':
        return f'{"цифрой" if u == "цифра" else "буквой"} ' + ' или '.join(xs)
    return f'{"цифры" if u == "цифра" else "буквы"} ' + ' или '.join(xs)


def phrase(sp, c):
    t, u = c['c'], unit(sp)
    if t == 'cnt':
        return f'{u} {c["x"]} встречается {where(sp)} {times(c["op"], c["v"])}'
    if t == 'cntset':
        return f'{where(sp)} {how_many(c["nm"], c["op"], c["v"])}'
    if t == 'first':
        if sp['kind'] == 'nums':
            return f'запись числа {"не " if c["neg"] else ""}начинается с {set_word(sp, c, "gen")}'
        return f'слово {"не " if c["neg"] else ""}начинается с {set_word(sp, c, "gen")}'
    if t == 'last':
        if sp['kind'] == 'nums':
            return f'запись числа {"не " if c["neg"] else ""}оканчивается {set_word(sp, c, "ins")}'
        return f'слово {"не " if c["neg"] else ""}заканчивается {set_word(sp, c, "ins")}'
    if t == 'noadj':
        if c.get('nm'):
            return f'никакие две {NOUN[c["nm"]][1]} не стоят рядом'
        return f'никакие две {"цифры" if u == "цифра" else "буквы"} {c["set"]} не стоят рядом'
    if t == 'noafter':
        return f'{u} {c["x"]} не стоит сразу после {set_word(sp, c, "gen")}'
    if t == 'nonext':
        return f'{u} {c["x"]} не стоит рядом с {set_word(sp, c, "ins")}'
    if t == 'nosame':
        return f'никакие две одинаковые {"цифры" if u == "цифра" else "буквы"} не стоят рядом'
    if t == 'distinct':
        return 'все цифры числа различны' if u == 'цифра' else 'каждая буква встречается в слове не более одного раза'
    if t == 'sub':
        return f'{where(sp)} {"нет" if c["neg"] else "есть"} {"сочетания" if c["neg"] else "сочетание"} «{c["s"]}»'
    if t == 'altpar':
        return 'любые две соседние цифры имеют разную чётность'
    if t == 'nondec':
        return 'цифры числа не убывают слева направо (каждая следующая не меньше предыдущей)'
    if t == 'sumdiv':
        return f'сумма цифр числа делится на {c["m"]}'
    raise ValueError(t)


def label(sp, c):
    t = c['c']
    if t == 'cnt':
        return f'{c["x"]} {({"==": "ровно", "<=": "не более", ">=": "не менее"})[c["op"]]} {c["v"]}'
    if t == 'cntset':
        nm = {'vow': 'гласных', 'cons': 'согласных', 'odd': 'нечётных', 'even': 'чётных'}[c['nm']]
        return f'{nm} {({"==": "ровно", "<=": "не более", ">=": "не менее"})[c["op"]]} {c["v"]}'
    if t in ('first', 'last'):
        what = NOUN[c['nm']][0] if c.get('nm') else '/'.join(c['set'])
        if c['neg']:
            return ('не с ' if t == 'first' else 'не на ') + what
        return ('в начале ' if t == 'first' else 'в конце ') + what
    if t == 'noadj':
        return (NOUN[c['nm']][1] if c.get('nm') else c['set']) + ' не рядом'
    if t == 'noafter':
        return f'{c["x"]} не после {NOUN[c["nm"]][3] if c.get("nm") else c["set"]}'
    if t == 'nonext':
        return f'{c["x"]} не рядом с {NOUN[c["nm"]][4] if c.get("nm") else c["set"]}'
    return {'nosame': 'без одинаковых соседей', 'distinct': 'без повторов', 'altpar': 'чётность чередуется',
            'nondec': 'цифры не убывают'}.get(t) or (f'без «{c["s"]}»' if t == 'sub' and c['neg'] else
                                                     f'есть «{c["s"]}»' if t == 'sub' else f'сумма цифр кратна {c["m"]}')


def join_and(xs):
    # «слово начинается с К и слово заканчивается…» → «слово начинается с К и заканчивается…»
    xs = [x if i == 0 or not (x.startswith(('слово ', 'запись числа ')) and xs[i - 1].split(' ')[0] == x.split(' ')[0])
          else x.split(' ', 2 if x.startswith('запись') else 1)[-1] for i, x in enumerate(xs)]
    return xs[0] if len(xs) == 1 else ', '.join(xs[:-1]) + ' и ' + xs[-1]


def letters(s):
    return ', '.join(f'{ch}' for ch in s)


def text(sp, rng):
    k, conds, q = sp['kind'], sp['conds'], sp['q']
    cl = [phrase(sp, c) for c in conds]
    if k == 'words' and q['t'] == 'count':
        name, verb, can = rng.choice(NAMES)
        if sp.get('ctx') == 'code':
            intro = (f'Для передачи сообщений используются кодовые слова длиной {sp["k"]} из букв '
                     f'<b>{letters(sp["shown"])}</b>. Каждая буква может встречаться в кодовом слове любое число раз '
                     'или не встречаться совсем.')
            ask = f' Сколько существует кодовых слов, для которых верно, что {join_and(cl)}?' if cl else ' Сколько существует таких кодовых слов?'
            return intro + ask
        intro = (f'{name} {verb} {sp["k"]}-буквенные слова из букв <b>{letters(sp["shown"])}</b>. '
                 'Каждая буква может встречаться в слове любое количество раз или не встречаться совсем. '
                 'Словом считается любая последовательность букв, не обязательно осмысленная.')
        return intro + (f' Сколько различных слов {can} {name}, если {join_and(cl)}?' if cl else f' Сколько различных слов {can} {name}?')
    if k == 'perm' and q['t'] == 'count':
        name, verb, can = rng.choice(NAMES)
        intro = (f'{name} {verb} слова, переставляя буквы слова <b>{sp["src"]}</b>: в каждом слове используются '
                 'все буквы исходного слова, каждая — столько раз, сколько она встречается в исходном слове. '
                 'Словом считается любая последовательность букв, не обязательно осмысленная.')
        return intro + (f' Сколько различных слов {can} {name}, если {join_and(cl)}?' if cl else f' Сколько различных слов {can} {name}?')
    if k == 'nums' and q['t'] == 'count':
        return (f'Определите количество {LEN_ADJ[sp["k"]]} чисел, записанных в {BASE_ADJ[sp["b"]]} системе счисления, '
                f'для которых {join_and(cl)}.')
    # алфавитный список
    objs = objects(sp)
    head = '<br>'.join(f'{i}. {w}' for i, w in enumerate(objs[:5], 1))
    if k == 'words':
        intro = (f'Все {sp["k"]}-буквенные слова, составленные из букв <b>{letters(sp["shown"])}</b>, записаны '
                 'в алфавитном порядке и пронумерованы, начиная с 1. Ниже приведено начало списка.')
    elif k == 'perm':
        intro = (f'Все слова, которые можно получить перестановкой букв слова <b>{sp["src"]}</b> (каждое слово записано '
                 'один раз), записаны в алфавитном порядке и пронумерованы, начиная с 1. Начало списка:')
    else:
        intro = (f'Все {LEN_NOM[sp["k"]]} числа в {BASE_ADJ[sp["b"]]} системе счисления записаны в порядке возрастания '
                 'и пронумерованы, начиная с 1. Начало списка:')
    intro += f'<br>{head}<br>…'
    nm = 'число' if k == 'nums' else 'слово'
    cond = f', для которого верно, что {join_and(cl)}' if cl else ''
    t = q['t']
    ask = {
        'first': f'Под каким номером в списке стоит первое {nm}{cond}?',
        'last': f'Под каким номером в списке стоит последнее {nm}{cond}?',
        'num_of': f'Под каким номером в списке стоит {nm} <b>{q.get("w")}</b>?',
        'word_at': f'Какое {nm} стоит в списке под номером <b>{q.get("N")}</b>?',
        'max_odd': f'Укажите наибольший <b>нечётный</b> номер {"числа" if k == "nums" else "слова"}{cond}.'.replace(', для которого', ', для которого'),
        'cnt_even': (f'Сколько {"чисел" if k == "nums" else "слов"}{", для которых верно, что " + join_and(cl) if cl else ""}, '
                     'стоят в списке под <b>чётными</b> номерами?'),
    }[t]
    return f'{intro} {ask}'


# ------------------------------------------------------------------ решение на Python
def lit(s):
    return "'" + s + "'"


def code_cond(c, sp):
    t = c['c']
    if t == 'cnt':
        return f"s.count({lit(c['x'])}) {c['op']} {c['v']}"
    if t == 'cntset':
        if len(c['set']) == 1:
            return f"s.count({lit(c['set'])}) {c['op']} {c['v']}"
        return f"sum(ch in {lit(c['set'])} for ch in s) {c['op']} {c['v']}"
    if t in ('first', 'last'):
        i = '0' if t == 'first' else '-1'
        if len(c['set']) == 1:
            return f"s[{i}] {'!=' if c['neg'] else '=='} {lit(c['set'])}"
        return f"s[{i}] {'not in' if c['neg'] else 'in'} {lit(c['set'])}"
    n1 = 'len(s) - 1'
    if t == 'noadj':
        if len(c['set']) == 1:
            return f"{lit(c['set'] * 2)} not in s"
        return f"not any(s[i] in {lit(c['set'])} and s[i + 1] in {lit(c['set'])} for i in range({n1}))"
    if t == 'noafter':
        return f"not any(s[i] in {lit(c['set'])} and s[i + 1] == {lit(c['x'])} for i in range({n1}))"
    if t == 'nonext':
        x, st = lit(c['x']), lit(c['set'])
        return f"not any(s[i] == {x} and s[i + 1] in {st} or s[i] in {st} and s[i + 1] == {x} for i in range({n1}))"
    if t == 'nosame':
        return f"all(s[i] != s[i + 1] for i in range({n1}))"
    if t == 'distinct':
        return "len(set(s)) == len(s)"
    if t == 'sub':
        return f"{lit(c['s'])} {'not in' if c['neg'] else 'in'} s"
    conv = 'int(ch, 16)' if sp.get('b', 10) > 10 else 'int(ch)'
    convi = (lambda j: f'int(s[{j}], 16)') if sp.get('b', 10) > 10 else (lambda j: f'int(s[{j}])')
    if t == 'altpar':
        return f"all({convi('i')} % 2 != {convi('i + 1')} % 2 for i in range({n1}))"
    if t == 'nondec':
        return f"all(s[i] <= s[i + 1] for i in range({n1}))"
    if t == 'sumdiv':
        return f"sum({conv} for ch in s) % {c['m']} == 0"
    raise ValueError(t)


def code(sp):
    k, q, conds = sp['kind'], sp['q'], sp['conds']
    if k == 'words':
        imp, loop = 'from itertools import product', f"product({lit(sp['alph'])}, repeat={sp['k']})"
    elif k == 'nums':
        imp, loop = 'from itertools import product', f"product({lit(DIG[:sp['b']])}, repeat={sp['k']})"
    else:
        imp = 'from itertools import permutations'
        loop = (f"sorted(set(permutations({lit(sp['src'])})))" if q['t'] != 'count' else
                f"set(permutations({lit(sp['src'])}))" if len(set(sp['src'])) < len(sp['src']) else f"permutations({lit(sp['src'])})")
    cs = [code_cond(c, sp) for c in conds]
    if not cs:
        test = ''
    elif len(cs) == 1:
        test = cs[0]
    else:
        test = '(' + ('\n            and '.join(cs)) + ')'
    lead = "    if s[0] == '0':  # запись числа не начинается с нуля\n        continue\n" if k == 'nums' else ''
    t = q['t']
    if t in ('num_of', 'word_at'):
        body = f"{imp}\n\nwords = [''.join(w) for w in {loop}]\n"
        if k == 'nums':
            body = f"{imp}\n\nnums = [''.join(w) for w in {loop} if w[0] != '0']\n"
            return body + (f"print(nums.index({lit(q['w'])}) + 1)" if t == 'num_of' else f"print(nums[{q['N']} - 1])")
        return body + (f"print(words.index({lit(q['w'])}) + 1)" if t == 'num_of' else f"print(words[{q['N']} - 1])")
    if t == 'count':
        out = f"{imp}\n\ncnt = 0\nfor w in {loop}:\n    s = ''.join(w)\n{lead}"
        out += f"    if {test}:\n        cnt += 1\n" if test else '    cnt += 1\n'
        return out + 'print(cnt)'
    if k == 'nums':
        # номера идут только по числам без ведущего нуля — нумеруем их сами
        out = f"{imp}\n\nnum = 0\n"
        head = f"for w in {loop}:\n    s = ''.join(w)\n{lead}    num += 1\n"
    else:
        out = f"{imp}\n\n"
        head = f"for num, w in enumerate({loop}, 1):  # алфавитный порядок: буквы в строке отсортированы\n    s = ''.join(w)\n"
    if t == 'first':
        return out + head + f"    if {test}:\n        print(num)\n        break"
    if t == 'last':
        return out + 'last = 0\n' + head + f"    if {test}:\n        last = num\nprint(last)"
    if t == 'max_odd':
        return out + 'best = 0\n' + head + f"    if num % 2 == 1 and {test}:\n        best = num\nprint(best)"
    if t == 'cnt_even':
        return out + 'cnt = 0\n' + head + f"    if num % 2 == 0 and {test}:\n        cnt += 1\nprint(cnt)"
    raise ValueError(t)


# ------------------------------------------------------------------ решение руками для простых случаев
def places(n):
    return f'{n} ' + ('место' if n % 10 == 1 and n % 100 != 11 else 'места' if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else 'мест')


def hand(sp, ans):
    """Короткое решение по формуле или None. Каждая формула проверяется: её значение должно совпасть с ответом."""
    k, q, conds = sp['kind'], sp['q'], sp['conds']
    t = q['t']
    if k == 'words' and t in ('num_of', 'word_at'):
        n, a = len(sp['alph']), sp['alph']
        key = ', '.join(f'{ch} → {i}' for i, ch in enumerate(a))
        if t == 'num_of':
            digs = [a.index(ch) for ch in q['w']]
            val = 0
            for d in digs:
                val = val * n + d
            assert val + 1 == ans
            return (f'Вручную: список совпадает с записью чисел в системе с основанием {n} ({key}). '
                    f'Слово {q["w"]} — это {"".join(map(str, digs))}<sub>{n}</sub> = {val}, номер на единицу больше: {val + 1}.')
        x, digs = q['N'] - 1, []
        for _ in range(sp['k']):
            digs.append(x % n); x //= n
        digs = digs[::-1]
        assert ''.join(a[d] for d in digs) == ans
        return (f'Вручную: список совпадает с записью чисел в системе с основанием {n} ({key}). '
                f'Слову под номером {q["N"]} соответствует число {q["N"]} − 1 = {q["N"] - 1} = '
                f'{"".join(map(str, digs))}<sub>{n}</sub>, заменяем цифры буквами: {ans}.')
    if k == 'words' and t == 'count':
        n, L = len(sp['alph']), sp['k']
        if not conds:
            assert n ** L == ans
            return f'Вручную: на каждое из {places(L)} — любая из {n} букв, всего {n}<sup>{L}</sup> = {ans}.'
        if len(conds) == 1:
            c = conds[0]
            if c['c'] in ('cnt', 'cntset') and c['op'] == '==':
                v = c['v']
                m = 1 if c['c'] == 'cnt' else len(c['set'])
                what = (f'букв {c["x"]}' if v > 1 else f'буквы {c["x"]}') if c['c'] == 'cnt' else NOUN[c['nm']][2 if v > 1 else 3]
                f = math.comb(L, v) * m ** v * (n - m) ** (L - v)
                assert f == ans
                pick = (f'{"место" if v == 1 else "места"} для {what} {"выбирается" if v == 1 else "выбираются"} '
                        f'C({L}, {v}) = {math.comb(L, v)} способами')
                fill = '' if m == 1 else f', на каждое из них — любая из {m} ({", ".join(c["set"])})'
                expr = f'{math.comb(L, v)}' + (f' · {m}<sup>{v}</sup>' if m > 1 else '') + f' · {n - m}<sup>{L - v}</sup>'
                return f'Вручную: {pick}{fill}, на остальные {places(L - v)} — любая из {n - m} других букв: {expr} = {ans}.'
            if c['c'] == 'cnt' and c['op'] == '>=' and c['v'] == 1:
                f = n ** L - (n - 1) ** L
                assert f == ans
                return (f'Вручную: из всех слов {n}<sup>{L}</sup> вычитаем слова совсем без буквы {c["x"]} — '
                        f'{n - 1}<sup>{L}</sup>: {n ** L} − {(n - 1) ** L} = {ans}.')
            if c['c'] in ('first', 'last'):
                m = len(c['set']) if not c['neg'] else n - len(c['set'])
                f = m * n ** (L - 1)
                assert f == ans
                pos = 'первое' if c['c'] == 'first' else 'последнее'
                opts = ''.join(ch for ch in sp['alph'] if (ch in c['set']) != c['neg'])
                return (f'Вручную: на {pos} место {"подходит" if m == 1 else "подходят"} {m} из {n} букв ({", ".join(opts)}), '
                        f'на остальные {places(L - 1)} — любая из {n}: {m} · {n}<sup>{L - 1}</sup> = {ans}.')
            if c['c'] == 'distinct':
                f = math.perm(n, L)
                assert f == ans
                return f'Вручную: на первое место {n} букв, на второе {n - 1}, … — размещения: {" · ".join(str(n - i) for i in range(L))} = {ans}.'
    if k == 'perm' and t == 'count' and not conds:
        cnt = {ch: sp['src'].count(ch) for ch in sp['src']}
        rep = [f'{v}!' for v in cnt.values() if v > 1]
        f = math.factorial(len(sp['src']))
        for v in cnt.values():
            f //= math.factorial(v)
        assert f == ans
        if rep:
            return (f'Вручную: перестановки с повторениями — {len(sp["src"])}! / ({" · ".join(rep)}) = {ans}: '
                    'перестановки одинаковых букв между собой новых слов не дают.')
        return f'Вручную: все буквы разные, это {len(sp["src"])}! = {ans} перестановок.'
    if k == 'nums' and t == 'count' and len(conds) == 1 and conds[0]['c'] == 'distinct':
        b, L = sp['b'], sp['k']
        f = (b - 1) * math.perm(b - 1, L - 1)
        assert f == ans
        return (f'Вручную: первая цифра — любая, кроме 0 ({b - 1} вариантов), дальше — любые ещё не использованные: '
                f'{b - 1} · {" · ".join(str(b - 1 - i) for i in range(L - 1))} = {ans}.')
    return None


NOTE = {
    'words': 'Перебираем все слова через product(алфавит, repeat=длина) и проверяем условия у каждого слова-строки.',
    'perm': 'Перестановки — permutations(слово). Если в исходном слове есть одинаковые буквы, одинаковые перестановки '
            'встречаются несколько раз: оберните перебор в set(), иначе ответ получится завышенным.',
    'nums': 'Числа — это строки цифр: product(цифры, repeat=длина). Запись числа не начинается с нуля — такие варианты пропускаем.',
    'lex': 'product выдаёт слова ровно в алфавитном порядке, если буквы алфавита записаны в строке по алфавиту. '
           'Номер слова считаем через enumerate(…, 1).',
}


def note(sp, ans):
    t = sp['q']['t']
    base = NOTE['lex'] if t != 'count' and sp['kind'] != 'nums' else NOTE[sp['kind']]
    if sp['kind'] == 'nums' and t != 'count':
        base = NOTE['nums'] + ' Порядок возрастания чисел совпадает с порядком перебора product, номер считаем сами.'
    if sp['kind'] == 'perm' and t != 'count':
        base = NOTE['perm'] + ' Для номеров множество нужно ещё отсортировать: sorted(set(…)).'
    if sp['kind'] == 'words' and t != 'count' and sp['shown'] != sp['alph']:
        base += f' В условии буквы перечислены не по алфавиту — сначала отсортируйте их: {sp["alph"]}.'
    h = hand(sp, ans)
    return base + (' ' + h if h else '')


# ------------------------------------------------------------------ случайные spec
def alph_of(word, rng, sort=True):
    a = ''.join(sorted(word))
    shown = a if sort else ''.join(rng.sample(word, len(word)))
    return a, shown


def vowels(s):
    return ''.join(ch for ch in s if ch in VOW)


def cons(s):
    return ''.join(ch for ch in s if ch not in VOW and ch not in 'ЬЪЙ')


def digset(b, par):
    return ''.join(DIG[d] for d in range(b) if d % 2 == par)


def letter_cond(rng, a, kinds, L):
    """Одно случайное условие на слово из букв a."""
    t = rng.choice(kinds)
    v, cn = vowels(a), cons(a)
    if t == 'cnt':
        op = rng.choice(['==', '==', '==', '>=', '<='])
        return {'c': 'cnt', 'x': rng.choice(a), 'op': op, 'v': rng.choice([1, 2] if op != '==' else [1, 2, 2, 3][:L - 1])}
    if t == 'cntset':
        nm = rng.choice(['vow', 'vow', 'cons'])
        st = v if nm == 'vow' else cn
        if not st or len(st) == len(a):
            return None
        op = rng.choice(['==', '==', '>=', '<='])
        return {'c': 'cntset', 'set': st, 'nm': nm, 'op': op, 'v': rng.choice([1, 2, 2, 3][:L - 1])}
    if t in ('first', 'last'):
        r = rng.random()
        if r < .35 and v and cn:
            nm = rng.choice(['vow', 'cons'])
            return {'c': t, 'set': v if nm == 'vow' else cn, 'nm': nm, 'neg': False}
        return {'c': t, 'set': ''.join(sorted(rng.sample(a, rng.choice([1, 1, 2])))), 'neg': rng.random() < .5}
    if t == 'noadj':
        if rng.random() < .65 and len(v) >= 2:
            return {'c': 'noadj', 'set': v, 'nm': 'vow'}
        return {'c': 'noadj', 'set': rng.choice(a)}
    if t == 'noafter':
        x = 'Й' if 'Й' in a else 'Ь' if 'Ь' in a else rng.choice(cn or a)
        if not v or x in v:
            return None
        return {'c': 'noafter', 'x': x, 'set': v, 'nm': 'vow'}
    if t == 'nonext':
        x = 'Й' if 'Й' in a else rng.choice(a)
        st = v if x not in v else cn
        if not st:
            return None
        return {'c': 'nonext', 'x': x, 'set': st, 'nm': 'vow' if st == v else 'cons'}
    if t == 'nosame':
        return {'c': 'nosame'}
    if t == 'distinct':
        return {'c': 'distinct'}
    if t == 'sub':
        return {'c': 'sub', 's': ''.join(rng.sample(a, 2)), 'neg': rng.random() < .7}
    raise ValueError(t)


def digit_cond(rng, b, kinds, L):
    t = rng.choice(kinds)
    odd, even = digset(b, 1), digset(b, 0)
    if t == 'cnt':
        op = rng.choice(['==', '==', '<=', '>='])
        return {'c': 'cnt', 'x': DIG[rng.randrange(b)], 'op': op, 'v': rng.choice([1, 1, 2])}
    if t == 'cntset':
        nm = rng.choice(['odd', 'even'])
        return {'c': 'cntset', 'set': odd if nm == 'odd' else even, 'nm': nm, 'op': rng.choice(['==', '==', '<=', '>=']),
                'v': rng.choice([1, 2, 2, 3][:L - 1])}
    if t in ('first', 'last'):
        if rng.random() < .5:
            nm = rng.choice(['odd', 'even'])
            return {'c': t, 'set': odd if nm == 'odd' else even, 'nm': nm, 'neg': False}
        return {'c': t, 'set': DIG[rng.randrange(1, b)], 'neg': rng.random() < .5}
    if t == 'noadj':
        nm = rng.choice(['odd', 'even'])
        return {'c': 'noadj', 'set': odd if nm == 'odd' else even, 'nm': nm}
    if t == 'nonext':
        x = DIG[rng.randrange(1, b)]
        nm = rng.choice(['odd', 'even'])
        return {'c': 'nonext', 'x': x, 'set': odd if nm == 'odd' else even, 'nm': nm}
    if t in ('nosame', 'distinct', 'altpar', 'nondec'):
        return {'c': t}
    if t == 'sumdiv':
        return {'c': 'sumdiv', 'm': rng.choice([3, 4, 5, 7])}
    raise ValueError(t)


def conds_of(rng, n, maker):
    out = []
    for _ in range(50):
        if len(out) == n:
            break
        c = maker()
        if c and c['c'] not in [x['c'] for x in out]:
            out.append(c)
    return out if len(out) == n else None


def rand_spec(rng, fam):
    """fam — семейство задачи из PLAN. Возвращает spec или None (тогда пробуем снова)."""
    if fam in ('w1', 'w2', 'wadj', 'w3', 'wcode'):
        word = rng.choice(ALPHS_Y if fam == 'wadj' and rng.random() < .6 else ALPHS)
        a, shown = alph_of(word, rng, sort=rng.random() < .5)
        L = rng.choice([4, 5, 5, 6]) if len(a) <= 6 else rng.choice([4, 5])
        kinds = {'w1': ['cnt', 'first', 'last', 'cntset', 'distinct'], 'wcode': ['cnt', 'first', 'cntset'],
                 'w2': ['cnt', 'first', 'last', 'cntset', 'sub'],
                 'wadj': ['noadj', 'noafter', 'nonext', 'nosame'], 'w3': ['cnt', 'cntset', 'first', 'last', 'noadj', 'nonext', 'distinct', 'nosame']}[fam]
        n = {'w1': 1, 'wcode': 1, 'w2': 2, 'wadj': 1, 'w3': 3}[fam]
        cs = conds_of(rng, n, lambda: letter_cond(rng, a, kinds, L))
        if fam == 'wadj' and cs and rng.random() < .6:      # к соседству добавим счётное условие
            extra = letter_cond(rng, a, ['cnt', 'first', 'distinct'], L)
            if extra:
                cs.append(extra)
        if not cs:
            return None
        sp = {'kind': 'words', 'alph': a, 'shown': shown, 'k': L, 'conds': cs, 'q': {'t': 'count'}}
        if fam == 'wcode':
            sp['ctx'] = 'code'
        return sp
    if fam in ('lex0', 'lex1', 'lex2', 'lexh'):
        word = rng.choice(ALPHS)
        a, shown = alph_of(word, rng, sort=fam in ('lex0', 'lex1') and rng.random() < .7)
        L = rng.choice([4, 5]) if len(a) <= 5 else 4
        if fam == 'lex0':
            objs = [''.join(w) for w in product(a, repeat=L)]
            if rng.random() < .5:
                return {'kind': 'words', 'alph': a, 'shown': shown, 'k': L, 'conds': [],
                        'q': {'t': 'num_of', 'w': rng.choice(objs[len(objs) // 5:])}}
            return {'kind': 'words', 'alph': a, 'shown': shown, 'k': L, 'conds': [],
                    'q': {'t': 'word_at', 'N': rng.randrange(len(objs) // 5, len(objs))}}
        n = {'lex1': 1, 'lex2': 2, 'lexh': 2}[fam]
        kinds = ['cnt', 'first', 'last', 'cntset', 'noadj', 'distinct', 'nosame', 'sub']
        if fam == 'lex1':
            kinds = ['cnt', 'first', 'last', 'cntset']
        cs = conds_of(rng, n, lambda: letter_cond(rng, a, kinds, L))
        if not cs:
            return None
        qt = rng.choice(['first', 'first', 'last']) if fam != 'lexh' else rng.choice(['max_odd', 'cnt_even', 'last'])
        return {'kind': 'words', 'alph': a, 'shown': shown, 'k': L, 'conds': cs, 'q': {'t': qt}}
    if fam in ('n1', 'n2', 'n3'):
        b = rng.choice({'n1': [5, 6, 7, 8, 8, 9], 'n2': [5, 6, 7, 8, 9, 10], 'n3': [6, 7, 8, 9, 12, 16]}[fam])
        L = rng.choice([4, 5]) if b >= 9 else rng.choice([4, 5, 5, 6])
        if b == 16:
            L = 4
        kinds = {'n1': ['cnt', 'first', 'last', 'distinct', 'cntset'],
                 'n2': ['nosame', 'noadj', 'altpar', 'nonext', 'cnt', 'cntset'],
                 'n3': ['cnt', 'cntset', 'noadj', 'nonext', 'altpar', 'nondec', 'sumdiv', 'nosame', 'last']}[fam]
        n = {'n1': 1, 'n2': 2, 'n3': 3}[fam]
        cs = conds_of(rng, n, lambda: digit_cond(rng, b, kinds, L))
        if not cs:
            return None
        if fam == 'n2' and not any(c['c'] in ('nosame', 'noadj', 'altpar', 'nonext') for c in cs):
            return None
        return {'kind': 'nums', 'b': b, 'k': L, 'conds': cs, 'q': {'t': 'count'}}
    if fam == 'nlex':
        b = rng.choice([4, 5, 6, 7, 8])
        L = rng.choice([4, 5])
        cs = conds_of(rng, rng.choice([1, 2]), lambda: digit_cond(rng, b, ['cnt', 'cntset', 'noadj', 'nosame', 'last'], L))
        if not cs:
            return None
        return {'kind': 'nums', 'b': b, 'k': L, 'conds': cs, 'q': {'t': rng.choice(['first', 'last', 'max_odd'])}}
    if fam in ('p1', 'p2', 'prep', 'plex'):
        if fam == 'p1':
            src = rng.choice(PERM_UNIQ + PERM_REP[:6] if rng.random() < .3 else PERM_UNIQ)
        else:
            src = rng.choice(PERM_REP)
        a = ''.join(sorted(set(src)))
        if fam == 'p1':
            cs = conds_of(rng, rng.choice([0, 1, 1]), lambda: letter_cond(rng, a, ['first', 'last'], len(src)))
        elif fam == 'p2':
            cs = conds_of(rng, 1, lambda: letter_cond(rng, a, ['noadj', 'first', 'last', 'nonext'], len(src)))
        elif fam == 'prep':
            cs = conds_of(rng, 2, lambda: letter_cond(rng, a, ['noadj', 'first', 'last', 'nonext', 'sub', 'nosame'], len(src)))
        else:
            cs = conds_of(rng, rng.choice([0, 1]), lambda: letter_cond(rng, a, ['first', 'last', 'noadj', 'sub'], len(src)))
        if cs is None:
            return None
        if fam == 'plex':
            objs = sorted(set(''.join(w) for w in permutations(src)))
            if not cs:
                return {'kind': 'perm', 'src': src, 'conds': [], 'q': {'t': 'num_of', 'w': rng.choice(objs[len(objs) // 4:])}}
            return {'kind': 'perm', 'src': src, 'conds': cs, 'q': {'t': rng.choice(['first', 'last', 'max_odd'])}}
        return {'kind': 'perm', 'src': src, 'conds': cs, 'q': {'t': 'count'}}
    raise ValueError(fam)


def size(sp):
    if sp['kind'] == 'words':
        return len(sp['alph']) ** sp['k']
    if sp['kind'] == 'nums':
        return sp['b'] ** sp['k']
    return math.factorial(len(sp['src']))


PLAN = (
    # базовый: правило произведения, одно-два простых условия, номер слова без условий
    [('Б', 'w1')] * 12 + [('Б', 'wcode')] * 4 + [('Б', 'lex0')] * 10 + [('Б', 'lex1')] * 9 +
    [('Б', 'n1')] * 10 + [('Б', 'p1')] * 10 +
    # средний: соседство букв и цифр, несколько условий, перестановки с повторяющимися буквами
    [('П', 'wadj')] * 7 + [('П', 'w2')] * 4 + [('П', 'n2')] * 7 + [('П', 'p2')] * 6 + [('П', 'lex2')] * 6 +
    # сложный: три условия, номера с условиями чётности, алфавитный список перестановок и чисел
    [('В', 'w3')] * 3 + [('В', 'n3')] * 4 + [('В', 'lexh')] * 3 + [('В', 'prep')] * 2 + [('В', 'plex')] * 2 + [('В', 'nlex')] * 1
)

KIND_TITLE = {'words': lambda sp: f'{sp["k"]}-буквенные слова из {sp["alph"]}',
              'nums': lambda sp: f'{BASE_SHORT[sp["b"]]} {LEN_ADJ[sp["k"]].replace("ых", "ые")}',
              'perm': lambda sp: f'Перестановки «{sp["src"]}»'}
Q_TITLE = {'count': '', 'first': 'первый номер', 'last': 'последний номер', 'num_of': 'номер слова {w}',
           'word_at': 'слово № {N}', 'max_odd': 'наибольший нечётный номер', 'cnt_even': 'сколько с чётными номерами'}


def title(sp):
    q = sp['q']
    parts = [label(sp, c) for c in sp['conds']]
    qt = Q_TITLE[q['t']].format(**q)
    if q['t'] == 'num_of' and sp['kind'] == 'nums':
        qt = qt.replace('слова', 'числа')
    if qt:
        parts.append(qt)
    head = KIND_TITLE[sp['kind']](sp)
    if sp['kind'] == 'words' and q['t'] != 'count':
        head = f'Список слов из {sp["alph"]}'
    if sp['kind'] == 'perm' and q['t'] != 'count':
        head = f'Список перестановок «{sp["src"]}»'
    return head + (': ' + ', '.join(parts) if parts else '')


def make(rng, fam):
    for _ in range(20000):
        sp = rand_spec(rng, fam)
        if not sp or size(sp) > 1_100_000:
            continue
        a = answer(sp)
        if a is None or a == 0:
            continue
        t = sp['q']['t']
        total = len(objects(sp))
        if t in ('count', 'cnt_even'):
            if a < 3 or (sp['conds'] and a == total // (2 if t == 'cnt_even' else 1)):
                continue
            if sp['conds'] and t == 'count' and a > total * .97:      # условие почти ничего не отсекает
                continue
        if t == 'first' and a < 4:
            continue
        if t in ('last', 'max_odd') and a > total - 2:
            continue
        # каждое условие должно что-то менять: без него ответ другой
        if len(sp['conds']) > 1:
            if any(answer({**sp, 'conds': [c for c in sp['conds'] if c is not x]}) == a for x in sp['conds']):
                continue
        return sp, a
    raise RuntimeError(f'не удалось собрать {fam}')


def main():
    rng = random.Random(SEED)
    out = []
    for k, (level, fam) in enumerate(PLAN, 1):
        while True:
            sp, ans = make(rng, fam)
            ttl = title(sp)
            if ttl not in {p['title'] for p in out}:
                break
        txt = text(sp, rng)
        meta = json.dumps(sp, ensure_ascii=False, separators=(',', ':'))
        out.append({'id': f'8-g{k:03d}', 'task': 8, 'level': level, 'title': ttl, 'text': txt,
                    'extra': f'<!--spec:{meta}-->', 'code': code(sp), 'answer': str(ans), 'data': '', 'dname': '',
                    'note': note(sp, ans)})
    for p in out:
        r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=300,
                           encoding='utf-8', env={**__import__('os').environ, 'PYTHONIOENCODING': 'utf-8'})
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
