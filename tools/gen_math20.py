#!/usr/bin/env python3
"""Генератор задач ЕГЭ-2027 по профильной математике, №20 (числа и их свойства, часть 2, 4 балла).

    python3 tools/gen_math20.py > /tmp/m20.json      # 12 задач высокого уровня

Задача из трёх пунктов (а — «может ли», б — «может ли», в — «наибольшее»), как в демоверсии. Сюжеты выбраны так,
чтобы эталонное решение было строгим для любых чисел условия:
• N различных нечётных натуральных чисел с суммой S: возможно тогда и только тогда, когда N² ≤ S и N той же
  чётности, что S (пример: 1, 3, …, 2N − 3 и S − (N − 1)²);
• k различных чисел из 1, 2, …, n с суммой S: возможно, когда сумма k наименьших ≤ S ≤ сумма k наибольших
  (суммы k-элементных наборов заполняют весь этот отрезок).
В описании <!--spec:…--> — условие и ответы; tests/test_bank_math.py проверяет все три пункта перебором.
"""
import random, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathkit import item2, emit

SEED = 20270120
TOPIC = 'Числа и их свойства'
PLAN = [('В', 'odd')] * 6 + [('В', 'subset')] * 6


def odd_ok(N, S):
    return N * N <= S and (S - N) % 2 == 0


def odd_example(N, S):
    xs = [2 * i + 1 for i in range(N - 1)] + [S - (N - 1) ** 2]
    return xs


def sub_ok(k, n, S):
    return k * (k + 1) // 2 <= S <= k * (2 * n - k + 1) // 2 and 1 <= k <= n


def sub_example(k, n, S):
    """k различных чисел из 1..n с суммой S: от наименьших сдвигаем наибольшее, пока можно, затем следующее."""
    xs = list(range(1, k + 1))
    need = S - sum(xs)
    for i in range(k - 1, -1, -1):
        cap = n - (k - 1 - i) - xs[i]
        step = min(cap, need)
        xs[i] += step
        need -= step
    assert need == 0 and sum(xs) == S and len(set(xs)) == k
    return sorted(xs)


def make(rng, kind):
    if kind == 'odd':
        S = rng.randint(40, 160)
        best = max(N for N in range(1, 20) if odd_ok(N, S))
        yes = [N for N in range(2, best + 1) if odd_ok(N, S)]
        no_par = [N for N in range(2, best) if not odd_ok(N, S)]        # мешает чётность
        no_big = [best + 2]                                            # мешает размер (та же чётность, что S)
        if len(yes) < 2 or not no_par:
            return None
        a_N = rng.choice(yes[:-1])
        b_N = rng.choice(no_par + no_big)
        ex = odd_example(a_N, S)
        text = (f'На доске написано несколько различных нечётных натуральных чисел, их сумма равна ${S}$.'
                f'<br>а) Может ли на доске быть ровно ${a_N}$ чисел?<br>б) Может ли на доске быть ровно ${b_N}$ чисел?'
                f'<br>в) Какое наибольшее количество чисел может быть на доске?')
        why_b = (f'Сумма ${b_N}$ нечётных чисел имеет ту же чётность, что и ${b_N}$, — {"чётна" if b_N % 2 == 0 else "нечётна"}, '
                 f'а ${S}$ — {"чётное" if S % 2 == 0 else "нечётное"} число.') if b_N in no_par else (
                 f'Сумма ${b_N}$ различных нечётных натуральных чисел не меньше $1 + 3 + \\ldots + {2 * b_N - 1} = {b_N}^{{2}} = {b_N * b_N} > {S}$.')
        sol = (f'<p>Заметим: сумма $N$ различных нечётных натуральных чисел не меньше $1 + 3 + \\ldots + (2N - 1) = N^{{2}}$ и имеет '
               f'ту же чётность, что $N$.</p>'
               f'<p><b>а)</b> Да, например: ${", ".join(map(str, ex))}$ — сумма ${S}$.</p>'
               f'<p><b>б)</b> Нет. {why_b}</p>'
               f'<p><b>в)</b> Нужно $N^{{2}} \\le {S}$ и $N$ одной чётности с ${S}$. Наибольшее такое $N = {best}$: '
               f'${best}^{{2}} = {best * best} \\le {S}$, а у следующего подходящего по чётности ${best + 2}^{{2}} = {(best + 2) ** 2} > {S}$. '
               f'Пример для $N = {best}$: ${", ".join(map(str, odd_example(best, S)))}$.</p>')
        return {'kind': kind, 'S': S, 'a': a_N, 'b': b_N, 'ans': ['да', 'нет', best]}, text, sol, f'Нечётные числа с суммой {S}: {a_N}, {b_N}'
    n = rng.randint(10, 25)
    S = rng.randint(30, n * (n + 1) // 2 - 20)
    best = max(k for k in range(1, n + 1) if sub_ok(k, n, S))
    low = min(k for k in range(1, n + 1) if sub_ok(k, n, S))
    yes = [k for k in range(2, best) if sub_ok(k, n, S)]
    no_small = [k for k in range(1, low) if k >= 2]                     # даже k наибольших не хватает
    if not yes or not no_small:
        return None
    a_k = rng.choice(yes)
    b_k = rng.choice(no_small + [best + 1])
    ex = sub_example(a_k, n, S)
    text = (f'Из чисел $1, 2, \\ldots, {n}$ выбрали несколько различных, сумма выбранных чисел равна ${S}$.'
            f'<br>а) Могли ли выбрать ровно ${a_k}$ чисел?<br>б) Могли ли выбрать ровно ${b_k}$ чисел?'
            f'<br>в) Какое наибольшее количество чисел могли выбрать?')
    if b_k > best:
        why_b = f'Сумма любых ${b_k}$ различных натуральных чисел не меньше $1 + 2 + \\ldots + {b_k} = {b_k * (b_k + 1) // 2} > {S}$.'
    else:
        top = b_k * (2 * n - b_k + 1) // 2
        why_b = f'Сумма любых ${b_k}$ из этих чисел не больше суммы ${b_k}$ наибольших: ${top} < {S}$.'
    sol = (f'<p>Сумма $k$ различных чисел из $1, \\ldots, {n}$ не меньше $\\frac{{k(k + 1)}}{{2}}$ (сумма $k$ наименьших) и не больше суммы '
           f'$k$ наибольших. Любое значение между ними достигается: от набора $1, 2, \\ldots, k$ можно увеличивать числа по одному, '
           f'начиная с наибольшего, — сумма растёт на 1 на каждом шаге.</p>'
           f'<p><b>а)</b> Да, например: ${", ".join(map(str, ex))}$ — сумма ${S}$.</p>'
           f'<p><b>б)</b> Нет. {why_b}</p>'
           f'<p><b>в)</b> Нужно $\\frac{{k(k + 1)}}{{2}} \\le {S}$. При $k = {best}$: ${best * (best + 1) // 2} \\le {S}$, при $k = {best + 1}$: '
           f'${(best + 1) * (best + 2) // 2} > {S}$. Пример для $k = {best}$: ${", ".join(map(str, sub_example(best, n, S)))}$. Ответ: ${best}$.</p>')
    return {'kind': 'subset', 'n': n, 'S': S, 'a': a_k, 'b': b_k, 'ans': ['да', 'нет', best]}, text, sol, f'Числа от 1 до {n} с суммой {S}: {a_k}, {b_k}'


def main():
    rng = random.Random(SEED)
    out, titles = [], set()
    for k, (level, kind) in enumerate(PLAN, 1):
        for _ in range(20000):
            r = make(rng, kind)
            if r is None:
                continue
            sp, text, sol, title = r
            if title in titles:
                continue
            titles.add(title)
            break
        else:
            raise SystemExit(f'№20, {kind}: не удалось подобрать задачу')
        a, b, c = sp['ans']
        out.append(item2(20, k, level, TOPIC, title, text, sol + f'<p>Ответ: а) {a}; б) {b}; в) ${c}$.</p>', f'а) {a}; б) {b}; в) {c}', sp))
    emit(out)


if __name__ == '__main__':
    main()
