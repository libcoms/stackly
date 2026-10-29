#!/usr/bin/env python3
"""Генератор задач ЕГЭ-2027 по профильной математике, №1 (планиметрия), для банка stackly.

    python3 tools/gen_math1.py > /tmp/m1.json      # 52 задачи базового уровня

Как в банке ФИПИ и рубриках тренировочных сборников: центральные и вписанные углы, вписанный четырёхугольник,
синус и косинус острого угла прямоугольного треугольника, площадь треугольника по двум сторонам и углу,
площади параллелограмма, ромба и трапеции, углы равнобедренного треугольника, угол между биссектрисой и высотой,
описанный четырёхугольник, радиус описанной окружности, средняя линия. К большинству задач — чертёж с буквами
(без чисел). Описание <!--spec:…--> — данные фигуры; tests/test_bank_math.py строит фигуру по координатам и
измеряет ответ численно.
"""
import random, sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathkit import F, ans, n, item, emit, is_dec, svg, pl, seg, circ, dot, lab, out_label, fit

SEED = 20270101
TOPIC = 'Планиметрия'
KINDS = ['central', 'inquad', 'cosA', 'sideA', 'area_sin', 'paral', 'rhomb', 'trap', 'iso', 'bis_alt', 'tangq', 'circR']
PLAN = [('Б', k) for k in KINDS for _ in range(4)] + [('Б', 'midline')] * 4 + [('Б', 'central')] * 0


def draw(points, edges, labels, circle=None, extra=''):
    """Точки в своих координатах (y вверх) → SVG; labels — {имя: точка}, подписи снаружи от центра фигуры."""
    allp = list(points.values()) + ([(circle[0][0] + circle[1], circle[0][1]), (circle[0][0] - circle[1], circle[0][1]),
                                     (circle[0][0], circle[0][1] + circle[1]), (circle[0][0], circle[0][1] - circle[1])] if circle else [])
    T = fit(allp, 300, 220, 30)
    cx = sum(p[0] for p in points.values()) / len(points)
    cy = sum(p[1] for p in points.values()) / len(points)
    center = T(circle[0]) if circle else T((cx, cy))
    b = []
    if circle:
        r = math.dist(T(circle[0]), T((circle[0][0] + circle[1], circle[0][1])))
        b.append(circ(T(circle[0]), r))
    for a, c in edges:
        b.append(seg(T(points[a]), T(points[c])))
    for name in labels:
        p = T(points[name])
        b.append(dot(p))
        b.append(out_label(p, center, name, 15) if name != 'O' else lab((p[0] + 10, p[1] - 8), 'O'))
    return svg(300, 220, ''.join(b) + extra, 'Чертёж к задаче')


def on_circle(deg, r=1.0):
    return (r * math.cos(math.radians(deg)), r * math.sin(math.radians(deg)))


def make(rng, kind):
    if kind == 'central':
        given = rng.choice(['central', 'inscribed'])
        insc = rng.randint(12, 85)
        cen = 2 * insc
        A, B = on_circle(-90 - cen / 2 + 180), on_circle(-90 + cen / 2 + 180)
        A, B = on_circle(90 + cen / 2), on_circle(90 - cen / 2)
        C = on_circle(-90 + rng.uniform(-40, 40))
        pic = draw({'A': A, 'B': B, 'C': C, 'O': (0, 0)}, [('A', 'C'), ('B', 'C'), ('A', 'O'), ('B', 'O')], ['A', 'B', 'C', 'O'], ((0, 0), 1))
        if given == 'central':
            text = f'Центральный угол $AOB$ равен ${cen}^\\circ$. Найдите вписанный угол $ACB$, опирающийся на ту же дугу $AB$. Ответ дайте в градусах.'
            sol = f'Вписанный угол равен половине центрального, опирающегося на ту же дугу: $\\frac{{{cen}^\\circ}}{{2}} = {insc}^\\circ$.'
            res = insc
        else:
            text = f'Вписанный угол $ACB$ равен ${insc}^\\circ$. Найдите центральный угол $AOB$, опирающийся на ту же дугу $AB$. Ответ дайте в градусах.'
            sol = f'Центральный угол вдвое больше вписанного, опирающегося на ту же дугу: $2 \\cdot {insc}^\\circ = {cen}^\\circ$.'
            res = cen
        return {'kind': kind, 'given': given, 'cen': cen}, F(res), text, sol, pic, f'{"Центральный → вписанный" if given == "central" else "Вписанный → центральный"}: {cen if given == "central" else insc}°'
    if kind == 'inquad':
        a, b = rng.randint(10, 70), rng.randint(10, 70)          # ∠ABD = a, ∠CAD = b → ∠ABC = a + b
        if a + b >= 170:
            return None
        A = on_circle(200)
        D = on_circle(200 + 2 * a)
        C = on_circle(200 + 2 * a + 2 * b)
        B = on_circle(200 + 2 * a + 2 * b + (360 - 2 * a - 2 * b) / 2)
        pic = draw({'A': A, 'B': B, 'C': C, 'D': D}, [('A', 'B'), ('B', 'C'), ('C', 'D'), ('D', 'A'), ('B', 'D'), ('A', 'C')],
                   ['A', 'B', 'C', 'D'], ((0, 0), 1))
        text = (f'Четырёхугольник $ABCD$ вписан в окружность. Угол $ABD$ равен ${a}^\\circ$, угол $CAD$ равен ${b}^\\circ$. '
                f'Найдите угол $ABC$. Ответ дайте в градусах.')
        sol = (f'Углы $CAD$ и $CBD$ опираются на одну дугу $CD$, поэтому $\\angle CBD = {b}^\\circ$. '
               f'$\\angle ABC = \\angle ABD + \\angle DBC = {a}^\\circ + {b}^\\circ = {a + b}^\\circ$.')
        return {'kind': kind, 'a': a, 'b': b}, F(a + b), text, sol, pic, f'Вписанный четырёхугольник: {a}° и {b}°'
    if kind in ('cosA', 'sideA'):
        c = rng.randint(4, 30)
        ac = F(rng.randint(1, c * 10 - 1), 10)
        if kind == 'cosA':
            ac = F(rng.randint(1, c - 1))
            bc2 = c * c - ac * ac
            res = ac / c
            if not is_dec(res):
                return None
            bc_txt = n(math.isqrt(int(bc2))) if math.isqrt(int(bc2)) ** 2 == bc2 else f'\\sqrt{{{bc2}}}'
            text = f'В треугольнике $ABC$ угол $C$ равен $90^\\circ$, $AB = {c}$, $BC = {bc_txt}$. Найдите $\\cos A$.'
            sol = (f'$AC = \\sqrt{{AB^{{2}} - BC^{{2}}}} = \\sqrt{{{c * c} - {bc2}}} = {n(ac)}$. '
                   f'$\\cos A = \\frac{{AC}}{{AB}} = \\frac{{{n(ac)}}}{{{c}}} = {n(res)}$.')
            sp = {'kind': kind, 'c': c, 'bc2': bc2}
            title = f'cos A: AB = {c}, BC² = {bc2}'
        else:
            s = F(rng.randint(1, 19), 20)
            res = c * s
            if not is_dec(res):
                return None
            text = f'В треугольнике $ABC$ угол $C$ равен $90^\\circ$, $AB = {c}$, $\\sin A = {n(s)}$. Найдите $BC$.'
            sol = f'$\\sin A = \\frac{{BC}}{{AB}}$, поэтому $BC = AB \\cdot \\sin A = {c} \\cdot {n(s)} = {n(res)}$.'
            sp = {'kind': kind, 'c': c, 's': str(s)}
            bc2 = res * res
            title = f'Катет BC: AB = {c}, sin A = {n(s)}'
        bcv = math.sqrt(float(bc2))
        acv = math.sqrt(c * c - bcv * bcv)
        big = max(acv, bcv)                                 # чертёж схематичный: слишком узкий треугольник не читается
        acv, bcv = max(acv, 0.45 * big), max(bcv, 0.45 * big)
        pic = draw({'A': (acv, 0), 'B': (0, bcv), 'C': (0, 0)}, [('A', 'B'), ('B', 'C'), ('C', 'A')], ['A', 'B', 'C'],
                   extra='')
        return sp, res, text, sol, pic, title
    if kind == 'area_sin':
        a, b = rng.randint(2, 30), rng.randint(2, 30)
        ang = rng.choice([30, 150])
        S = F(a * b, 4)
        if not is_dec(S):
            return None
        text = (f'Две стороны треугольника равны ${a}$ и ${b}$, а угол между ними равен ${ang}^\\circ$. Найдите площадь треугольника.')
        sol = f'$S = \\frac{{1}}{{2}}ab \\sin {ang}^\\circ = \\frac{{1}}{{2}} \\cdot {a} \\cdot {b} \\cdot \\frac{{1}}{{2}} = {n(S)}$.'
        return {'kind': kind, 'a': a, 'b': b, 'ang': ang}, S, text, sol, '', f'Площадь треугольника: {a}, {b}, {ang}°'
    if kind == 'paral':
        a, b = rng.randint(2, 25), rng.randint(2, 25)
        ang = rng.choice([30, 150])
        S = F(a * b, 2)
        pic = draw({'A': (0, 0), 'B': (b * math.cos(math.radians(30)), b * 0.5), 'C': (a + b * math.cos(math.radians(30)), b * 0.5), 'D': (a, 0)},
                   [('A', 'B'), ('B', 'C'), ('C', 'D'), ('D', 'A')], ['A', 'B', 'C', 'D'])
        text = f'Стороны параллелограмма $ABCD$ равны ${a}$ и ${b}$, а один из его углов равен ${ang}^\\circ$. Найдите площадь параллелограмма.'
        sol = f'$S = ab \\sin \\alpha = {a} \\cdot {b} \\cdot \\sin {ang}^\\circ = {a * b} \\cdot \\frac{{1}}{{2}} = {n(S)}$.'
        return {'kind': kind, 'a': a, 'b': b, 'ang': ang}, S, text, sol, pic, f'Параллелограмм: {a}, {b}, {ang}°'
    if kind == 'rhomb':
        d1, d2 = rng.randint(2, 30), rng.randint(2, 30)
        S = F(d1 * d2, 2)
        pic = draw({'A': (-d1 / 2, 0), 'B': (0, d2 / 2), 'C': (d1 / 2, 0), 'D': (0, -d2 / 2)},
                   [('A', 'B'), ('B', 'C'), ('C', 'D'), ('D', 'A'), ('A', 'C'), ('B', 'D')], ['A', 'B', 'C', 'D'])
        text = f'Диагонали ромба $ABCD$ равны ${d1}$ и ${d2}$. Найдите площадь ромба.'
        sol = f'Площадь ромба — половина произведения диагоналей: $\\frac{{{d1} \\cdot {d2}}}{{2}} = {n(S)}$.'
        return {'kind': kind, 'd1': d1, 'd2': d2}, S, text, sol, pic, f'Ромб: диагонали {d1} и {d2}'
    if kind == 'trap':
        a, b = sorted(rng.sample(range(2, 30), 2))
        h = rng.randint(2, 20)
        ask = rng.choice(['S', 'mid'])
        res = F((a + b) * h, 2) if ask == 'S' else F(a + b, 2)
        sh = rng.uniform(0, b - a)
        pic = draw({'A': (0, 0), 'B': (sh, h), 'C': (sh + a, h), 'D': (b, 0)}, [('A', 'B'), ('B', 'C'), ('C', 'D'), ('D', 'A')], ['A', 'B', 'C', 'D'])
        if ask == 'S':
            text = f'Основания трапеции $ABCD$ равны ${a}$ и ${b}$, а высота равна ${h}$. Найдите площадь трапеции.'
            sol = f'$S = \\frac{{a + b}}{{2}} \\cdot h = \\frac{{{a} + {b}}}{{2}} \\cdot {h} = {n(res)}$.'
        else:
            text = f'Основания трапеции $ABCD$ равны ${a}$ и ${b}$. Найдите длину средней линии трапеции.'
            sol = f'Средняя линия равна полусумме оснований: $\\frac{{{a} + {b}}}{{2}} = {n(res)}$.'
        return {'kind': kind, 'a': a, 'b': b, 'h': h, 'ask': ask}, res, text, sol, pic, f'Трапеция: {a}, {b}' + (f', h = {h}' if ask == 'S' else ', средняя линия')
    if kind == 'iso':
        beta = rng.randint(10, 160)
        if beta % 2:
            return None
        ask = rng.choice(['base', 'ext'])
        base = (180 - beta) // 2
        res = base if ask == 'base' else 180 - base
        H = math.cos(math.radians(beta / 2))
        W = math.sin(math.radians(beta / 2))
        pic = draw({'A': (-W, 0), 'B': (0, H), 'C': (W, 0)}, [('A', 'B'), ('B', 'C'), ('C', 'A')], ['A', 'B', 'C'])
        if ask == 'base':
            text = f'В треугольнике $ABC$ стороны $AB$ и $BC$ равны, угол $B$ равен ${beta}^\\circ$. Найдите угол $A$. Ответ дайте в градусах.'
            sol = f'Углы при основании равнобедренного треугольника равны: $\\angle A = \\frac{{180^\\circ - {beta}^\\circ}}{{2}} = {base}^\\circ$.'
        else:
            text = (f'В треугольнике $ABC$ стороны $AB$ и $BC$ равны, угол $B$ равен ${beta}^\\circ$. Найдите внешний угол при вершине $C$. '
                    f'Ответ дайте в градусах.')
            sol = f'$\\angle C = \\frac{{180^\\circ - {beta}^\\circ}}{{2}} = {base}^\\circ$, внешний угол $180^\\circ - {base}^\\circ = {res}^\\circ$.'
        return {'kind': kind, 'beta': beta, 'ask': ask}, F(res), text, sol, pic, f'Равнобедренный: B = {beta}°, {"угол A" if ask == "base" else "внешний при C"}'
    if kind == 'bis_alt':
        a, b = rng.sample(range(20, 80), 2)
        if (a - b) % 2 or a + b >= 170:
            return None
        res = abs(a - b) // 2
        text = (f'В треугольнике $ABC$ угол $A$ равен ${a}^\\circ$, угол $B$ равен ${b}^\\circ$. $CD$ — биссектриса, $CH$ — высота. '
                f'Найдите угол $DCH$. Ответ дайте в градусах.')
        sol = (f'$\\angle C = 180^\\circ - {a}^\\circ - {b}^\\circ = {180 - a - b}^\\circ$, $\\angle ACD = {n(F(180 - a - b, 2))}^\\circ$. '
               f'В прямоугольном треугольнике $ACH$: $\\angle ACH = 90^\\circ - {a}^\\circ = {90 - a}^\\circ$. '
               f'$\\angle DCH = |{n(F(180 - a - b, 2))}^\\circ - {90 - a}^\\circ| = {res}^\\circ$.')
        return {'kind': kind, 'a': a, 'b': b}, F(res), text, sol, '', f'Биссектриса и высота: A = {a}°, B = {b}°'
    if kind == 'tangq':
        t = [rng.randint(1, 12) for _ in range(4)]
        AB, BC, CD, DA = t[0] + t[1], t[1] + t[2], t[2] + t[3], t[3] + t[0]
        ask = rng.choice(['P', 'side'])
        if ask == 'P':
            res = 2 * (AB + CD)
            text = f'В четырёхугольник $ABCD$ вписана окружность, $AB = {AB}$, $CD = {CD}$. Найдите периметр четырёхугольника $ABCD$.'
            sol = f'У описанного четырёхугольника суммы противоположных сторон равны: $AD + BC = AB + CD = {AB + CD}$. Периметр $2 \\cdot {AB + CD} = {res}$.'
        else:
            res = AB + CD - BC
            text = f'В четырёхугольник $ABCD$ вписана окружность, $AB = {AB}$, $BC = {BC}$, $CD = {CD}$. Найдите $AD$.'
            sol = f'$AB + CD = BC + AD$, откуда $AD = {AB} + {CD} - {BC} = {res}$.'
        return {'kind': kind, 't': t, 'ask': ask}, F(res), text, sol, '', f'Описанный четырёхугольник: {AB}, {BC if ask == "side" else "…"}, {CD}'
    if kind == 'circR':
        a = rng.randint(2, 40)
        ang = rng.choice([30, 150, 90])
        if ang == 90:
            res = F(a, 2)
            text = f'Гипотенуза прямоугольного треугольника равна ${a}$. Найдите радиус окружности, описанной около этого треугольника.'
            sol = f'Центр описанной окружности прямоугольного треугольника — середина гипотенузы: $R = \\frac{{{a}}}{{2}} = {n(res)}$.'
        else:
            res = F(a)
            text = (f'В треугольнике $ABC$ сторона $AB$ равна ${a}$, а угол $C$ равен ${ang}^\\circ$. Найдите радиус окружности, '
                    f'описанной около этого треугольника.')
            sol = f'По теореме синусов $\\frac{{AB}}{{\\sin C}} = 2R$, $\\sin {ang}^\\circ = \\frac{{1}}{{2}}$, поэтому $R = {a}$.'
        return {'kind': kind, 'a': a, 'ang': ang}, res, text, sol, '', f'Радиус описанной: {a}, {ang}°'
    # midline: в треугольнике площадью S проведена средняя линия; площадь отсечённого треугольника или трапеции
    S = rng.randint(4, 200)
    ask = rng.choice(['small', 'trap'])
    res = F(S, 4) if ask == 'small' else F(3 * S, 4)
    if not is_dec(res):
        return None
    pic = draw({'A': (0, 0), 'B': (1.3, 2.2), 'C': (4, 0), 'M': (0.65, 1.1), 'N': (2.65, 1.1)},
               [('A', 'B'), ('B', 'C'), ('C', 'A'), ('M', 'N')], ['A', 'B', 'C', 'M', 'N'])
    text = (f'Площадь треугольника $ABC$ равна ${S}$. $MN$ — средняя линия, параллельная стороне $AC$. Найдите площадь '
            + ('треугольника $MBN$.' if ask == 'small' else 'трапеции $AMNC$.'))
    sol = (f'Треугольник $MBN$ подобен $ABC$ с коэффициентом $\\frac{{1}}{{2}}$, его площадь в 4 раза меньше: $\\frac{{{S}}}{{4}} = {n(F(S, 4))}$.'
           + ('' if ask == 'small' else f' Площадь трапеции ${S} - {n(F(S, 4))} = {n(res)}$.'))
    return {'kind': kind, 'S': S, 'ask': ask}, res, text, sol, pic, f'Средняя линия: S = {S}, {"треугольник" if ask == "small" else "трапеция"}'


def main():
    rng = random.Random(SEED)
    out, titles = [], set()
    for k, (level, kind) in enumerate(PLAN, 1):
        for _ in range(20000):
            r = make(rng, kind)
            if r is None:
                continue
            sp, x, text, sol, pic, title = r
            if title in titles or not is_dec(x):
                continue
            titles.add(title)
            break
        else:
            raise SystemExit(f'№1, {kind}: не удалось подобрать задачу')
        out.append(item(1, k, level, TOPIC, title, text, sol, ans(x), sp, extra=pic))
    emit(out)


if __name__ == '__main__':
    main()
