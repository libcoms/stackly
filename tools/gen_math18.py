#!/usr/bin/env python3
"""Генератор задач ЕГЭ-2027 по профильной математике, №18 (планиметрия: доказательство и вычисление, 3 балла).

    python3 tools/gen_math18.py > /tmp/m18.json      # 16 задач повышенного уровня

Пункт а — доказательство (общее, верно при любых размерах), пункт б — вычисление с подобранными числами:
высота прямоугольного треугольника (CH² = AH · HB), радиус вписанной окружности прямоугольного треугольника,
свойство биссектрисы, параллелограмм середин сторон четырёхугольника (периметр — сумма диагоналей).
В описании <!--spec:…--> — данные фигуры; tests/test_bank_math.py строит фигуру в координатах и считает ответ.
"""
import random, sys, os, math
from fractions import Fraction as F
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathkit import n, ans, item2, emit, is_dec

SEED = 20270118
TOPIC = 'Планиметрия: доказательство и вычисление'
KINDS = ['height', 'incircle', 'bisector', 'varignon']
PLAN = [('П', k) for k in KINDS for _ in range(4)]
TRIPLES = [(3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25), (20, 21, 29), (9, 40, 41), (6, 8, 10), (12, 16, 20)]


def make(rng, kind):
    if kind == 'height':
        p, q = rng.choice([(1, 4), (1, 9), (4, 9), (2, 8), (4, 16), (9, 16), (3, 12), (1, 16), (8, 18), (5, 20), (3, 27), (16, 25)])
        h = math.isqrt(p * q)
        text = (f'В прямоугольном треугольнике $ABC$ с прямым углом $C$ проведена высота $CH$.<br>а) Докажите, что $CH^{{2}} = AH \\cdot HB$.'
                f'<br>б) Найдите $CH$, если $AH = {p}$, $HB = {q}$.')
        sol = (f'<p><b>а)</b> $\\angle ACH = 90^\\circ - \\angle A = \\angle B$, поэтому прямоугольные треугольники $ACH$ и $CBH$ подобны '
               f'по острому углу: $\\frac{{AH}}{{CH}} = \\frac{{CH}}{{HB}}$, откуда $CH^{{2}} = AH \\cdot HB$.</p>'
               f'<p><b>б)</b> $CH = \\sqrt{{{p} \\cdot {q}}} = \\sqrt{{{p * q}}} = {h}$.</p>')
        return {'kind': kind, 'p': p, 'q': q}, F(h), text, sol, f'Высота прямоугольного треугольника: {p} и {q}'
    if kind == 'incircle':
        a, b, c = rng.choice(TRIPLES)
        k = rng.choice([1, 1, 2, 3])
        a, b, c = a * k, b * k, c * k
        r = F(a + b - c, 2)
        text = (f'В прямоугольный треугольник $ABC$ с катетами $BC = a$, $AC = b$ и гипотенузой $AB = c$ вписана окружность.'
                f'<br>а) Докажите, что её радиус $r = \\frac{{a + b - c}}{{2}}$.<br>б) Найдите $r$, если $a = {a}$, $b = {b}$.')
        sol = (f'<p><b>а)</b> Пусть окружность касается $BC$, $AC$, $AB$ в точках $K$, $L$, $M$, $I$ — её центр. $IKCL$ — квадрат '
               f'(три прямых угла и $IK = IL = r$), поэтому $CK = CL = r$. Отрезки касательных из одной точки равны: $BK = BM$, '
               f'$AL = AM$. Тогда $c = AM + MB = AL + BK = (b - r) + (a - r)$, откуда $r = \\frac{{a + b - c}}{{2}}$.</p>'
               f'<p><b>б)</b> $c = \\sqrt{{{a}^{{2}} + {b}^{{2}}}} = {c}$, $r = \\frac{{{a} + {b} - {c}}}{{2}} = {n(r)}$.</p>')
        return {'kind': kind, 'a': a, 'b': b}, r, text, sol, f'Вписанная окружность: катеты {a} и {b}'
    if kind == 'bisector':
        ab, ac = rng.sample(range(3, 16), 2)
        bc = rng.randint(abs(ab - ac) + 1, ab + ac - 1)
        bl = F(bc * ab, ab + ac)
        if not is_dec(bl):
            return None
        text = (f'В треугольнике $ABC$ проведена биссектриса $AL$.<br>а) Докажите, что $\\frac{{BL}}{{LC}} = \\frac{{AB}}{{AC}}$.'
                f'<br>б) Найдите $BL$, если $AB = {ab}$, $AC = {ac}$, $BC = {bc}$.')
        sol = (f'<p><b>а)</b> Проведём через $C$ прямую, параллельную $AL$; пусть она пересекает прямую $AB$ в точке $K$. '
               f'$\\angle AKC = \\angle BAL$ (соответственные), $\\angle ACK = \\angle LAC$ (накрест лежащие), а $\\angle BAL = \\angle LAC$, '
               f'поэтому треугольник $AKC$ равнобедренный: $AK = AC$. По теореме о пропорциональных отрезках '
               f'$\\frac{{BL}}{{LC}} = \\frac{{BA}}{{AK}} = \\frac{{AB}}{{AC}}$.</p>'
               f'<p><b>б)</b> $BL = BC \\cdot \\frac{{AB}}{{AB + AC}} = {bc} \\cdot \\frac{{{ab}}}{{{ab + ac}}} = {n(bl)}$.</p>')
        return {'kind': kind, 'ab': ab, 'ac': ac, 'bc': bc}, bl, text, sol, f'Биссектриса: AB = {ab}, AC = {ac}, BC = {bc}'
    d1, d2 = rng.randint(3, 30), rng.randint(3, 30)
    text = (f'Диагонали выпуклого четырёхугольника $ABCD$ равны ${d1}$ и ${d2}$. $K$, $L$, $M$, $N$ — середины сторон $AB$, $BC$, $CD$, $DA$.'
            f'<br>а) Докажите, что $KLMN$ — параллелограмм.<br>б) Найдите периметр $KLMN$.')
    sol = (f'<p><b>а)</b> $KL$ — средняя линия треугольника $ABC$: $KL \\parallel AC$ и $KL = \\frac{{AC}}{{2}}$. $NM$ — средняя линия '
           f'треугольника $ADC$: $NM \\parallel AC$ и $NM = \\frac{{AC}}{{2}}$. Противоположные стороны $KL$ и $NM$ параллельны и равны — '
           f'$KLMN$ параллелограмм.</p><p><b>б)</b> Аналогично $KN = LM = \\frac{{BD}}{{2}}$. Периметр $2 \\cdot \\frac{{AC}}{{2}} + 2 \\cdot '
           f'\\frac{{BD}}{{2}} = AC + BD = {d1} + {d2} = {d1 + d2}$.</p>')
    return {'kind': 'varignon', 'd1': d1, 'd2': d2}, F(d1 + d2), text, sol, f'Середины сторон: диагонали {d1} и {d2}'


def main():
    rng = random.Random(SEED)
    out, titles = [], set()
    for k, (level, kind) in enumerate(PLAN, 1):
        for _ in range(20000):
            r = make(rng, kind)
            if r is None:
                continue
            sp, x, text, sol, title = r
            if title in titles:
                continue
            titles.add(title)
            break
        else:
            raise SystemExit(f'№18, {kind}: не удалось подобрать задачу')
        out.append(item2(18, k, level, TOPIC, title, text, sol + f'<p>Ответ: б) ${n(x)}$.</p>', ans(x), sp, auto=True))
    emit(out)


if __name__ == '__main__':
    main()
