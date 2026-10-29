#!/usr/bin/env python3
"""Генератор задач ЕГЭ-2027 по профильной математике, №17 (моделирование — новая позиция части 2, 2 балла).

    python3 tools/gen_math17.py > /tmp/m17.json      # 20 задач повышенного уровня

Как в демоверсии 2027: по формулам из условия составить функцию одной переменной и найти её наибольшее
(наименьшее) значение или точку, где оно достигается, с помощью производной. Мощность в нагрузке генератора,
коробка наибольшего объёма из листа, цена с наибольшей прибылью, участок у стены, экономичная скорость.
Ответ — одно число (его можно сверить автоматически). В описании <!--spec:…--> — функция на Python, отрезок
и вопрос; tests/test_bank_math.py находит экстремум перебором по сетке.
"""
import random, sys, os, math
from fractions import Fraction as F
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathkit import n, ans, item2, emit, is_dec

SEED = 20270117
TOPIC = 'Моделирование: оптимизация'
KINDS = ['power', 'box', 'profit', 'fence', 'speed']
PLAN = [('П', k) for k in KINDS for _ in range(4)]


def make(rng, kind):
    if kind == 'power':
        eps, r = rng.choice([12, 20, 24, 30, 36, 40, 48, 50, 60]), rng.choice([1, 2, 3, 4, 5, 6])
        ask = rng.choice(['P', 'R'])
        Pm = F(eps * eps, 4 * r)
        if not is_dec(Pm):
            return None
        text = (f'На заводе имеется генератор с ЭДС $\\varepsilon = {eps}$ В и внутренним сопротивлением $r = {r}$ Ом. К генератору '
                f'подключают нагрузку с сопротивлением $R$ (в омах). Сила тока в цепи (в амперах) $I = \\frac{{\\varepsilon}}{{R + r}}$, '
                f'тепловая мощность, выделяемая в нагрузке (в ваттах), $P = I^{{2}}R$. '
                + ('Какова наибольшая мощность, которую может выделить нагрузка? Ответ дайте в ваттах.' if ask == 'P'
                   else 'При каком сопротивлении нагрузки выделяемая в ней мощность будет наибольшей? Ответ дайте в омах.'))
        sol = (f'$P(R) = \\frac{{{eps * eps}R}}{{(R + {r})^{{2}}}}$, $R > 0$. $P\'(R) = {eps * eps} \\cdot \\frac{{(R + {r})^{{2}} - 2R(R + {r})}}{{(R + {r})^{{4}}}} '
               f'= {eps * eps} \\cdot \\frac{{{r} - R}}{{(R + {r})^{{3}}}}$. Производная положительна при $R < {r}$ и отрицательна при $R > {r}$, '
               f'поэтому максимум при $R = {r}$ Ом' + (f': $P_{{\\max}} = \\frac{{{eps * eps} \\cdot {r}}}{{{(2 * r) ** 2}}} = {n(Pm)}$ Вт.' if ask == 'P' else '.'))
        f = f'{eps * eps}*x/(x + {r})**2'
        return {'kind': kind, 'f': f, 'lo': 0.001, 'hi': 1000, 'ask': 'max' if ask == 'P' else 'argmax'}, (Pm if ask == 'P' else F(r)), text, sol, f'Мощность нагрузки: ε = {eps}, r = {r}, {"P max" if ask == "P" else "R"}'
    if kind == 'box':
        a = rng.choice([6, 12, 18, 24, 30, 36, 42, 48, 60])
        ask = rng.choice(['V', 'x'])
        x0 = F(a, 6)
        V = x0 * (a - 2 * x0) ** 2
        text = (f'Из квадратного листа жести со стороной ${a}$ см нужно сделать открытую сверху коробку: в углах вырезают одинаковые '
                f'квадраты со стороной $x$ см и загибают края. ' + ('Найдите наибольший возможный объём коробки (в см³).' if ask == 'V'
                                                                  else 'При какой стороне вырезаемого квадрата объём коробки будет наибольшим? Ответ дайте в сантиметрах.'))
        sol = (f'$V(x) = x({a} - 2x)^{{2}}$, $0 < x < {n(F(a, 2))}$. $V\'(x) = ({a} - 2x)^{{2}} - 4x({a} - 2x) = ({a} - 2x)({a} - 6x)$. '
               f'На интервале производная меняет знак с «+» на «−» в точке $x = {n(x0)}$ — это максимум' + (f': $V = {n(x0)} \\cdot {n(a - 2 * x0)}^{{2}} = {n(V)}$ см³.' if ask == 'V' else '.'))
        return {'kind': kind, 'f': f'x*({a} - 2*x)**2', 'lo': 0, 'hi': a / 2, 'ask': 'max' if ask == 'V' else 'argmax'}, (V if ask == 'V' else x0), text, sol, f'Коробка из листа {a} см, {"объём" if ask == "V" else "вырез"}'
    if kind == 'profit':
        A, B = rng.choice([(1200, 10), (900, 5), (2000, 20), (1500, 10), (800, 4), (3000, 25), (600, 2)])
        c = rng.choice([20, 30, 40, 50, 60, 80])
        pmax = F(A, B)
        if c >= pmax:
            return None
        p0 = (pmax + c) / 2
        P = (p0 - c) * (A - B * p0)
        ask = rng.choice(['p', 'P'])
        if not is_dec(p0) or not is_dec(P):
            return None
        text = (f'Себестоимость одного изделия ${c}$ руб. При цене $p$ рублей за изделие в месяц продают $q = {A} - {B}p$ изделий '
                f'($c < p < {n(pmax)}$). Прибыль равна $(p - {c})q$. ' + ('При какой цене прибыль будет наибольшей? Ответ дайте в рублях.' if ask == 'p'
                                                                        else 'Найдите наибольшую возможную месячную прибыль (в рублях).'))
        text = text.replace('$c < p', f'${c} < p')
        sol = (f'$П(p) = (p - {c})({A} - {B}p) = -{B}p^{{2}} + {A + B * c}p - {A * c}$ — парабола ветвями вниз, $П\'(p) = -{2 * B}p + {A + B * c}$. '
               f'$П\'(p) = 0$ при $p = {n(p0)}$' + (f', $П_{{\\max}} = ({n(p0)} - {c})({A} - {B} \\cdot {n(p0)}) = {n(P)}$ руб.' if ask == 'P' else ' руб.'))
        return {'kind': kind, 'f': f'(x - {c})*({A} - {B}*x)', 'lo': c, 'hi': float(pmax), 'ask': 'max' if ask == 'P' else 'argmax'}, (P if ask == 'P' else p0), text, sol, f'Прибыль: q = {A} − {B}p, себестоимость {c}, {"цена" if ask == "p" else "прибыль"}'
    if kind == 'fence':
        L = rng.choice([40, 60, 80, 100, 120, 160, 200, 240])
        x0 = F(L, 4)
        S = x0 * (L - 2 * x0)
        text = (f'Прямоугольный участок одной стороной примыкает к стене дома, а с трёх других сторон огорожен забором длиной ${L}$ м. '
                f'Какую наибольшую площадь (в м²) может иметь участок?')
        sol = (f'Пусть стороны, перпендикулярные стене, равны $x$, тогда третья сторона ${L} - 2x$, $S(x) = x({L} - 2x)$, $0 < x < {L // 2}$. '
               f'$S\'(x) = {L} - 4x = 0$ при $x = {n(x0)}$; это максимум: $S = {n(x0)} \\cdot {n(L - 2 * x0)} = {n(S)}$ м².')
        return {'kind': kind, 'f': f'x*({L} - 2*x)', 'lo': 0, 'hi': L / 2, 'ask': 'max'}, S, text, sol, f'Участок у стены: забор {L} м'
    # speed: расход денег на рейс длиной S при скорости v: S(av + b/v); минимум при v = √(b/a)
    v0 = rng.choice([40, 50, 60, 70, 80, 90, 100])
    a = F(rng.choice([1, 2, 4, 5]), 100)
    b = a * v0 * v0
    S = rng.choice([100, 200, 300, 400, 500])
    ask = rng.choice(['v', 'C'])
    C = S * (a * v0 + b / v0)
    if not is_dec(C) or not is_dec(b):
        return None
    text = (f'Стоимость часа движения грузовика (топливо и оплата водителя) при скорости $v$ км/ч равна ${n(a)}v^{{2}} + {n(b)}$ рублей. '
            f'Рейс имеет длину ${S}$ км. ' + ('При какой скорости стоимость рейса будет наименьшей? Ответ дайте в км/ч.' if ask == 'v'
                                             else 'Найдите наименьшую возможную стоимость рейса (в рублях).'))
    sol = (f'Время рейса $\\frac{{{S}}}{{v}}$ ч, стоимость $C(v) = \\frac{{{S}}}{{v}}({n(a)}v^{{2}} + {n(b)}) = {S}\\left({n(a)}v + \\frac{{{n(b)}}}{{v}}\\right)$. '
           f'$C\'(v) = {S}\\left({n(a)} - \\frac{{{n(b)}}}{{v^{{2}}}}\\right) = 0$ при $v^{{2}} = {n(b / a)}$, $v = {v0}$; производная меняет знак с «−» на «+» — минимум'
           + (f': $C = {n(C)}$ руб.' if ask == 'C' else '.'))
    return {'kind': kind, 'f': f'{S}*({float(a)}*x + {float(b)}/x)', 'lo': 1, 'hi': 300, 'ask': 'min' if ask == 'C' else 'argmin'}, (C if ask == 'C' else F(v0)), text, sol, f'Экономичная скорость: {n(a)}v² + {n(b)}, {S} км, {"скорость" if ask == "v" else "стоимость"}'


def main():
    rng = random.Random(SEED)
    out, titles = [], set()
    for k, (level, kind) in enumerate(PLAN, 1):
        for _ in range(20000):
            r = make(rng, kind)
            if r is None:
                continue
            sp, x, text, sol, title = r
            if title in titles or not is_dec(x):
                continue
            titles.add(title)
            break
        else:
            raise SystemExit(f'№17, {kind}: не удалось подобрать задачу')
        out.append(item2(17, k, level, TOPIC, title, text, f'<p>{sol}</p><p>Ответ: ${n(x)}$.</p>', ans(x), sp, auto=True))
    emit(out)


if __name__ == '__main__':
    main()
