#!/usr/bin/env python3
"""Генератор задач ЕГЭ-2027 по профильной математике, №3 (стереометрия), для банка stackly.

    python3 tools/gen_math3.py > /tmp/m3.json      # 40 задач базового уровня

Как в банке ФИПИ и рубриках тренировочных сборников: диагональ и объём параллелепипеда, отсечённая призма
(плоскость через среднюю линию основания), цилиндр и конус с общим основанием и высотой, шар в цилиндре,
конус, отсечённый плоскостью через середину высоты, жидкость в сосуде, объём правильной пирамиды,
пирамида из вершин параллелепипеда, боковая поверхность цилиндра. К части задач — схематичный чертёж.
Описание <!--spec:…--> — размеры тел; tests/test_bank_math.py считает объёмы интегрированием площадей сечений
(или координатами), а не формулами-отношениями генератора.
"""
import random, sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathkit import F, ans, n, item, emit, is_dec, svg, seg, lab, plural

SEED = 20270103
TOPIC = 'Стереометрия'
KINDS = ['diag', 'cube_k', 'prism_v', 'prism_s', 'cylcone', 'spherecyl', 'conecut', 'vessel', 'pyr', 'tetra']
PLAN = [('Б', k) for k in KINDS for _ in range(4)]


def box_svg(names=True):
    """Схематичный прямоугольный параллелепипед ABCDA₁B₁C₁D₁ (косоугольная проекция)."""
    A, B, C, D = (40, 170), (200, 170), (250, 130), (90, 130)
    up = lambda p: (p[0], p[1] - 100)
    A1, B1, C1, D1 = map(up, (A, B, C, D))
    b = [seg(A, B), seg(B, C), seg(C, C1), seg(B, B1), seg(A, A1), seg(A1, B1), seg(B1, C1), seg(C1, D1), seg(D1, A1),
         seg(A, D, 'hd'), seg(D, C, 'hd'), seg(D, D1, 'hd')]
    if names:
        for p, t, dx, dy in [(A, 'A', -10, 10), (B, 'B', 0, 14), (C, 'C', 12, 6), (D, 'D', -12, -6), (A1, 'A<tspan font-size="10" dy="3">1</tspan>', -14, -4),
                             (B1, 'B<tspan font-size="10" dy="3">1</tspan>', 4, 14), (C1, 'C<tspan font-size="10" dy="3">1</tspan>', 12, -6),
                             (D1, 'D<tspan font-size="10" dy="3">1</tspan>', -6, -10)]:
            b.append(lab((p[0] + dx, p[1] + dy), t))
    return svg(290, 190, ''.join(b), 'Прямоугольный параллелепипед')


def cyl_cone_svg(cone=True, sphere=False):
    cx, top, bot, rx, ry = 150, 30, 170, 70, 16
    b = [f'<ellipse class="ln" cx="{cx}" cy="{top}" rx="{rx}" ry="{ry}"/>',
         f'<path class="ln" d="M{cx - rx},{bot} A{rx},{ry} 0 0 0 {cx + rx},{bot}"/>',
         f'<path class="hd" d="M{cx - rx},{bot} A{rx},{ry} 0 0 1 {cx + rx},{bot}"/>',
         seg((cx - rx, top), (cx - rx, bot)), seg((cx + rx, top), (cx + rx, bot))]
    if cone:
        b += [seg((cx - rx, bot), (cx, top), 'hd'), seg((cx + rx, bot), (cx, top), 'hd')]
    if sphere:
        b = [f'<ellipse class="ln" cx="{cx}" cy="{top}" rx="{rx}" ry="{ry}"/>', seg((cx - rx, top), (cx - rx, top + 2 * rx)),
             seg((cx + rx, top), (cx + rx, top + 2 * rx)), f'<path class="ln" d="M{cx - rx},{top + 2 * rx} A{rx},{ry} 0 0 0 {cx + rx},{top + 2 * rx}"/>',
             f'<circle class="hd" cx="{cx}" cy="{top + rx}" r="{rx}"/>']
        return svg(300, 2 * rx + 70, ''.join(b), 'Шар, вписанный в цилиндр')
    return svg(300, 200, ''.join(b), 'Цилиндр и конус')


def make(rng, kind):
    if kind == 'diag':
        a, b, c, d = rng.choice([(1, 2, 2, 3), (2, 3, 6, 7), (1, 4, 8, 9), (4, 4, 7, 9), (2, 6, 9, 11), (6, 6, 7, 11), (3, 4, 12, 13),
                                 (2, 10, 11, 15), (1, 12, 12, 17), (8, 9, 12, 17), (6, 10, 15, 19), (4, 5, 20, 21)])
        k = rng.choice([1, 1, 2, 3])
        a, b, c, d = a * k, b * k, c * k, d * k
        ask = rng.choice(['diag', 'edge'])
        if ask == 'diag':
            text = (f'В прямоугольном параллелепипеде $ABCDA_{{1}}B_{{1}}C_{{1}}D_{{1}}$ известно, что $AB = {a}$, $AD = {b}$, '
                    f'$AA_{{1}} = {c}$. Найдите длину диагонали $AC_{{1}}$.')
            sol = f'Квадрат диагонали равен сумме квадратов трёх измерений: $AC_{{1}} = \\sqrt{{{a}^{{2}} + {b}^{{2}} + {c}^{{2}}}} = \\sqrt{{{d * d}}} = {d}$.'
            res = d
        else:
            text = (f'В прямоугольном параллелепипеде $ABCDA_{{1}}B_{{1}}C_{{1}}D_{{1}}$ известно, что $AB = {a}$, $AD = {b}$, '
                    f'$AC_{{1}} = {d}$. Найдите длину ребра $AA_{{1}}$.')
            sol = f'$AA_{{1}} = \\sqrt{{AC_{{1}}^{{2}} - AB^{{2}} - AD^{{2}}}} = \\sqrt{{{d * d} - {a * a} - {b * b}}} = {c}$.'
            res = c
        return {'kind': kind, 'a': a, 'b': b, 'c': c, 'ask': ask}, F(res), text, sol, box_svg(), f'Параллелепипед: {a}, {b}, {c if ask == "diag" else "?"}, {"диагональ" if ask == "diag" else "ребро"}'
    if kind == 'cube_k':
        k = rng.randint(2, 5)
        what = rng.choice(['объём', 'площадь поверхности'])
        res = k ** 3 if what == 'объём' else k ** 2
        text = f'Каждое ребро куба увеличили в {k} раза. Во сколько раз увеличится {"объём" if what == "объём" else "площадь поверхности"} куба?'
        if k >= 5:
            text = text.replace(f'в {k} раза', f'в {k} раз')
        sol = (f'Объём пропорционален кубу ребра: ${k}^{{3}} = {res}$.' if what == 'объём'
               else f'Площадь поверхности пропорциональна квадрату ребра: ${k}^{{2}} = {res}$.')
        return {'kind': kind, 'k': k, 'what': what}, F(res), text, sol, '', f'Куб: рёбра ×{k}, {what}'
    if kind in ('prism_v', 'prism_s'):
        val = rng.randint(2, 120)
        given_small = rng.random() < 0.5
        ratio = 4 if kind == 'prism_v' else 2
        res = F(val * ratio) if given_small else F(val, ratio)
        if not is_dec(res):
            return None
        what = 'Объём' if kind == 'prism_v' else 'Площадь боковой поверхности'
        if given_small:
            text = (f'Через среднюю линию основания треугольной призмы проведена плоскость, параллельная боковому ребру. '
                    f'{what} отсечённой треугольной призмы равен{"" if kind == "prism_v" else "а"} ${val}$. Найдите '
                    f'{"объём" if kind == "prism_v" else "площадь боковой поверхности"} исходной призмы.')
        else:
            text = (f'{what} треугольной призмы равен{"" if kind == "prism_v" else "а"} ${val}$. Через среднюю линию основания призмы '
                    f'проведена плоскость, параллельная боковому ребру. Найдите {"объём" if kind == "prism_v" else "площадь боковой поверхности"} '
                    f'отсечённой треугольной призмы.')
        if kind == 'prism_v':
            sol = ('Высота у призм общая, а основание отсечённой — треугольник, отсекаемый средней линией: его площадь в 4 раза меньше. '
                   f'Объёмы относятся как $1 : 4$, ответ: ${n(res)}$.')
        else:
            sol = ('Высота у призм общая, а периметр основания отсечённой призмы вдвое меньше (стороны малого треугольника — '
                   f'половины сторон большого). Площади боковых поверхностей относятся как $1 : 2$, ответ: ${n(res)}$.')
        return {'kind': kind, 'val': val, 'small': given_small}, res, text, sol, '', f'Отсечённая призма: {"объём" if kind == "prism_v" else "бок. поверхность"} {val}, {"дана малая" if given_small else "дана исходная"}'
    if kind == 'cylcone':
        val = rng.randint(2, 150)
        given = rng.choice(['cyl', 'cone'])
        res = F(val, 3) if given == 'cyl' else F(3 * val)
        if not is_dec(res):
            return None
        text = (f'Цилиндр и конус имеют общие основание и высоту. Объём {"цилиндра" if given == "cyl" else "конуса"} равен ${val}$. '
                f'Найдите объём {"конуса" if given == "cyl" else "цилиндра"}.')
        sol = f'$V_{{\\text{{кон}}}} = \\frac{{1}}{{3}}Sh$, $V_{{\\text{{цил}}}} = Sh$, поэтому объём конуса втрое меньше. Ответ: ${n(res)}$.'
        return {'kind': kind, 'val': val, 'given': given}, res, text, sol, cyl_cone_svg(), f'Цилиндр и конус: дан объём {"цилиндра" if given == "cyl" else "конуса"} {val}'
    if kind == 'spherecyl':
        val = rng.randint(2, 120)
        given = rng.choice(['sphere', 'cyl'])
        res = F(3 * val, 2) if given == 'sphere' else F(2 * val, 3)
        if not is_dec(res):
            return None
        text = (f'Шар вписан в цилиндр. Объём {"шара" if given == "sphere" else "цилиндра"} равен ${val}$. Найдите объём '
                f'{"цилиндра" if given == "sphere" else "шара"}.')
        sol = (f'Радиус цилиндра равен радиусу шара $R$, высота — $2R$: $V_{{\\text{{цил}}}} = 2\\pi R^{{3}}$, '
               f'$V_{{\\text{{шара}}}} = \\frac{{4}}{{3}}\\pi R^{{3}}$, отношение $\\frac{{3}}{{2}}$. Ответ: ${n(res)}$.')
        return {'kind': kind, 'val': val, 'given': given}, res, text, sol, cyl_cone_svg(sphere=True), f'Шар в цилиндре: дан объём {"шара" if given == "sphere" else "цилиндра"} {val}'
    if kind == 'conecut':
        V = rng.choice([8 * k for k in range(1, 30)] + [16, 24, 40, 56, 64, 80, 96, 120, 160])
        ask = rng.choice(['small', 'frustum'])
        res = F(V, 8) if ask == 'small' else F(7 * V, 8)
        text = (f'Объём конуса равен ${V}$. Через середину высоты параллельно основанию конуса проведено сечение, которое является '
                f'основанием меньшего конуса с той же вершиной. Найдите объём ' + ('меньшего конуса.' if ask == 'small' else 'оставшейся части (усечённого конуса).'))
        sol = ('Меньший конус подобен исходному с коэффициентом $\\frac{1}{2}$, объём меньше в $2^{3} = 8$ раз: '
               f'$\\frac{{{V}}}{{8}} = {n(F(V, 8))}$.' + ('' if ask == 'small' else f' Усечённый конус: ${V} - {n(F(V, 8))} = {n(res)}$.'))
        return {'kind': kind, 'V': V, 'ask': ask}, res, text, sol, '', f'Конус: V = {V}, {"малый конус" if ask == "small" else "усечённый"}'
    if kind == 'vessel':
        h = rng.randint(4, 120)
        k = rng.choice([2, 3, 4, 5])
        dirn = rng.choice(['wider', 'narrower'])
        res = F(h, k * k) if dirn == 'wider' else F(h * k * k)
        if not is_dec(res) or res > 200:
            return None
        text = (f'В цилиндрическом сосуде уровень жидкости достигает ${h}$ см. На какой высоте будет находиться уровень жидкости, '
                f'если её перелить во второй цилиндрический сосуд, диаметр которого в ${k}$ раза {"больше" if dirn == "wider" else "меньше"} '
                f'диаметра первого? Ответ дайте в сантиметрах.')
        sol = (f'Объём жидкости не меняется, а площадь дна изменяется в ${k}^{{2}} = {k * k}$ раза. Высота меняется обратно: '
               + (f'$\\frac{{{h}}}{{{k * k}}} = {n(res)}$ см.' if dirn == 'wider' else f'${h} \\cdot {k * k} = {n(res)}$ см.'))
        return {'kind': kind, 'h': h, 'k': k, 'dir': dirn}, res, text, sol, '', f'Сосуд: {h} см, диаметр в {k} раза {"больше" if dirn == "wider" else "меньше"}'
    if kind == 'pyr':
        a, h = rng.randint(2, 20), rng.randint(2, 30)
        V = F(a * a * h, 3)
        if not is_dec(V):
            return None
        text = f'Сторона основания правильной четырёхугольной пирамиды равна ${a}$, а высота равна ${h}$. Найдите объём пирамиды.'
        sol = f'$V = \\frac{{1}}{{3}} S_{{\\text{{осн}}}} h = \\frac{{1}}{{3}} \\cdot {a}^{{2}} \\cdot {h} = {n(V)}$.'
        return {'kind': kind, 'a': a, 'h': h}, V, text, sol, '', f'Правильная пирамида: a = {a}, h = {h}'
    a, b, c = rng.randint(2, 12), rng.randint(2, 12), rng.randint(2, 12)
    V = F(a * b * c, 6)
    if not is_dec(V):
        return None
    text = (f'Найдите объём многогранника, вершинами которого являются точки $A$, $B$, $D$, $A_{{1}}$ прямоугольного параллелепипеда '
            f'$ABCDA_{{1}}B_{{1}}C_{{1}}D_{{1}}$, у которого $AB = {a}$, $AD = {b}$, $AA_{{1}} = {c}$.')
    sol = (f'Это треугольная пирамида $A_{{1}}ABD$: основание — прямоугольный треугольник $ABD$ площадью $\\frac{{{a} \\cdot {b}}}{{2}}$, '
           f'высота $AA_{{1}} = {c}$. $V = \\frac{{1}}{{3}} \\cdot \\frac{{{a * b}}}{{2}} \\cdot {c} = {n(V)}$.')
    return {'kind': 'tetra', 'a': a, 'b': b, 'c': c}, V, text, sol, box_svg(), f'Пирамида из вершин параллелепипеда: {a}, {b}, {c}'


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
            raise SystemExit(f'№3, {kind}: не удалось подобрать задачу')
        out.append(item(3, k, level, TOPIC, title, text, sol, ans(x), sp, extra=pic))
    emit(out)


if __name__ == '__main__':
    main()
