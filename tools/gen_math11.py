#!/usr/bin/env python3
"""Генератор задач ЕГЭ-2027 по профильной математике, №11 (текстовая задача), для банка stackly.

    python3 tools/gen_math11.py > /tmp/m11.json      # 40 задач повышенного уровня

Как в демоверсии и банке ФИПИ: движение по реке, велосипедисты в пробеге, работа (детали, трубы), растворы
и сплавы, средняя скорость, проценты. Задача строится от ответа: сначала выбираются скорости, объёмы, доли,
потом из них — данные условия. В описании <!--spec:…--> — уравнение задачи на Python («check»):
tests/test_bank_math.py подставляет в него ответ x.
"""
import random, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathkit import F, ans, n, item, emit, is_dec, plural

SEED = 20270111
TOPIC = 'Текстовая задача'
KINDS = ['river', 'cyclists', 'parts', 'pipes', 'mix', 'alloy', 'avg', 'percent', 'meet', 'chase']
PLAN = [('П', k) for k in KINDS for _ in range(4)]


def h(x):
    return f'{n(x)} {plural(x if F(x).denominator == 1 else 2, "час", "часа", "часов")}'


def make(rng, kind):
    if kind == 'river':
        v, u = rng.randint(8, 30), rng.randint(1, 5)
        if u >= v:
            return None
        S = rng.choice([s for s in range(20, 400) if all(F(s, x).denominator in (1, 2, 4, 5) for x in (v + u, v - u))] or [None])
        if S is None:
            return None
        stop = rng.choice([0, 1, 2, 3, 5, 10])
        T = F(S, v + u) + F(S, v - u) + stop
        if not is_dec(T):
            return None
        ask = rng.choice(['v', 'u'])
        if ask == 'v':
            text = (f'Теплоход проходит по течению реки до пункта назначения {S} км и после стоянки возвращается в пункт '
                    f'отправления. Найдите скорость теплохода в неподвижной воде, если скорость течения равна {u} км/ч, '
                    f'стоянка длится {h(stop)}, а в пункт отправления теплоход возвращается через {h(T)} после отплытия из него. '
                    f'Ответ дайте в км/ч.') if stop else (
                    f'Моторная лодка прошла против течения реки {S} км и вернулась в пункт отправления, затратив на обратный путь '
                    f'на {h(F(S, v - u) - F(S, v + u))} меньше. Найдите скорость лодки в неподвижной воде, если скорость течения '
                    f'равна {u} км/ч. Ответ дайте в км/ч.')
            if stop:
                chk = f'abs({S}/(x+{u}) + {S}/(x-{u}) + {stop} - {float(T)}) < 1e-9 and x > {u}'
                sol = (f'Пусть $x$ км/ч — скорость в неподвижной воде. В движении теплоход был ${n(T)} - {stop} = {n(T - stop)}$ ч: '
                       f'$\\frac{{{S}}}{{x + {u}}} + \\frac{{{S}}}{{x - {u}}} = {n(T - stop)}$. Положительный корень $x > {u}$: ${v}$ км/ч.')
            else:
                dt = F(S, v - u) - F(S, v + u)
                if not is_dec(dt):
                    return None
                chk = f'abs({S}/(x-{u}) - {S}/(x+{u}) - {float(dt)}) < 1e-9 and x > {u}'
                sol = (f'$\\frac{{{S}}}{{x - {u}}} - \\frac{{{S}}}{{x + {u}}} = {n(dt)}$, откуда '
                       f'${n(dt)}(x^{{2}} - {u * u}) = {2 * S * u}$, $x^{{2}} = {v * v}$, $x = {v}$ км/ч.')
            return chk, F(v), text, sol, f'Река: S = {S}, течение {u}, {"стоянка " + str(stop) if stop else "разница времени"}'
        text = (f'Теплоход, скорость которого в неподвижной воде равна {v} км/ч, проходит по течению реки {S} км и после '
                f'стоянки возвращается в исходный пункт. Найдите скорость течения, если стоянка длится {h(stop)}, а в исходный '
                f'пункт теплоход возвращается через {h(T)} после отплытия из него. Ответ дайте в км/ч.')
        if not stop:
            return None
        chk = f'abs({S}/({v}+x) + {S}/({v}-x) + {stop} - {float(T)}) < 1e-9 and 0 < x < {v}'
        sol = (f'$\\frac{{{S}}}{{{v} + x}} + \\frac{{{S}}}{{{v} - x}} = {n(T - stop)}$, то есть '
               f'$\\frac{{{2 * S * v}}}{{{v * v} - x^{{2}}}} = {n(T - stop)}$, $x^{{2}} = {u * u}$, $x = {u}$ км/ч.')
        return chk, F(u), text, sol, f'Течение: v = {v}, S = {S}, стоянка {stop}'
    if kind == 'cyclists':
        v2 = rng.randint(8, 30)
        d = rng.randint(2, 10)
        D = rng.choice([s for s in range(40, 300, 5) if F(s, v2).denominator in (1, 2) and F(s, v2 + d).denominator in (1, 2)] or [None])
        if D is None:
            return None
        dt = F(D, v2) - F(D, v2 + d)
        if not is_dec(dt) or dt <= 0:
            return None
        text = (f'Два велосипедиста одновременно отправились в {D}-километровый пробег. Первый ехал со скоростью, на {d} км/ч '
                f'большей, чем скорость второго, и прибыл к финишу на {h(dt)} раньше второго. Найдите скорость велосипедиста, '
                f'пришедшего к финишу первым. Ответ дайте в км/ч.')
        sol = (f'Пусть $x$ км/ч — скорость первого. $\\frac{{{D}}}{{x - {d}}} - \\frac{{{D}}}{{x}} = {n(dt)}$, '
               f'откуда ${n(dt)}x(x - {d}) = {D * d}$; положительный корень $x = {v2 + d}$ км/ч.')
        return f'abs({D}/(x-{d}) - {D}/x - {float(dt)}) < 1e-9 and x > {d}', F(v2 + d), text, sol, f'Велосипедисты: {D} км, разница {d} км/ч'
    if kind == 'parts':
        r2 = rng.randint(3, 25)
        a = rng.randint(1, 6)
        N = rng.choice([x for x in range(20, 400) if x % r2 == 0 and x % (r2 + a) == 0] or [None])
        if N is None:
            return None
        dt = F(N, r2) - F(N, r2 + a)
        text = (f'Заказ на изготовление {N} деталей первый рабочий выполняет на {h(dt)} быстрее, чем второй. Сколько деталей '
                f'за час изготавливает второй рабочий, если известно, что первый за час изготавливает на {a} '
                f'{plural(a, "деталь", "детали", "деталей")} больше?')
        sol = (f'Пусть второй делает $x$ деталей в час. $\\frac{{{N}}}{{x}} - \\frac{{{N}}}{{x + {a}}} = {n(dt)}$, '
               f'то есть ${n(dt)}x(x + {a}) = {N * a}$; положительный корень $x = {r2}$.')
        return f'abs({N}/x - {N}/(x+{a}) - {float(dt)}) < 1e-9 and x > 0', F(r2), text, sol, f'Детали: {N}, разница {a} в час'
    if kind == 'pipes':
        t1, t2 = rng.sample([2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 24, 30, 40, 60], 2)
        t = F(t1 * t2, t1 + t2)
        if not is_dec(t):
            return None
        text = (f'Первая труба наполняет бассейн за {h(t1)}, а обе трубы, работая вместе, — за {h(t)}. За сколько часов '
                f'наполняет бассейн одна вторая труба?')
        sol = (f'За час обе трубы вместе наполняют $\\frac{{1}}{{{n(t)}}}$ бассейна, первая — $\\frac{{1}}{{{t1}}}$. Вторая: '
               f'$\\frac{{1}}{{{n(t)}}} - \\frac{{1}}{{{t1}}} = \\frac{{1}}{{{t2}}}$, то есть {t2} ч.')
        return f'abs(1/{t1} + 1/x - 1/{float(t)}) < 1e-12', F(t2), text, sol, f'Трубы: {t1} ч и вместе {n(t)} ч'
    if kind == 'mix':
        m1, m2 = rng.randint(2, 20), rng.randint(2, 20)
        p1, p2 = rng.sample(range(5, 96, 5), 2)
        p = F(m1 * p1 + m2 * p2, m1 + m2)
        if not is_dec(p):
            return None
        text = (f'Смешали {m1} {plural(m1, "литр", "литра", "литров")} '
                f'{p1}-процентного водного раствора некоторого вещества с {m2} {"литром" if m2 % 10 == 1 and m2 % 100 != 11 else "литрами"} {p2}-процентного '
                f'водного раствора этого же вещества. Сколько процентов составляет концентрация получившегося раствора?')
        sol = (f'Вещества в смеси: ${n(F(m1 * p1, 100))} + {n(F(m2 * p2, 100))} = {n(F(m1 * p1 + m2 * p2, 100))}$ л из ${m1 + m2}$ л, '
               f'концентрация $\\frac{{{n(F(m1 * p1 + m2 * p2, 100))}}}{{{m1 + m2}}} \\cdot 100\\% = {n(p)}\\%$.')
        return f'abs(({m1}*{p1} + {m2}*{p2}) - x*({m1}+{m2})) < 1e-9', p, text, sol, f'Растворы: {m1} л {p1}% и {m2} л {p2}%'
    if kind == 'alloy':
        # первый сплав p1% меди, второй p2%; масса второго больше на d кг; получили сплав p%; найти массу третьего
        p1, p2 = sorted(rng.sample(range(5, 60, 5), 2))
        m1 = rng.randint(2, 30)
        d = rng.randint(1, 15)
        m2 = m1 + d
        p = F(m1 * p1 + m2 * p2, m1 + m2)
        if not is_dec(p):
            return None
        text = (f'Имеется два сплава. Первый сплав содержит {p1}% меди, второй — {p2}% меди. Масса второго сплава больше '
                f'массы первого на {d} кг. Из этих двух сплавов получили третий сплав, содержащий {n(p)}% меди. '
                f'Найдите массу третьего сплава. Ответ дайте в килограммах.')
        sol = (f'Пусть масса первого $x$ кг, второго $x + {d}$. Медь: ${n(F(p1, 100))}x + {n(F(p2, 100))}(x + {d}) = {n(p / 100)}(2x + {d})$, '
               f'откуда $x = {m1}$ и масса третьего сплава $2 \\cdot {m1} + {d} = {m1 + m2}$ кг.')
        return (f'abs({p1}*((x-{d})/2) + {p2}*((x+{d})/2) - {float(p)}*x) < 1e-9', F(m1 + m2), text, sol,
                f'Сплавы: {p1}% и {p2}%, разница {d} кг')
    if kind == 'avg':
        v1, v2, v3 = rng.sample(range(30, 121, 5), 3)
        t1, t2, t3 = rng.randint(1, 4), rng.randint(1, 4), rng.randint(1, 4)
        V = F(v1 * t1 + v2 * t2 + v3 * t3, t1 + t2 + t3)
        if not is_dec(V):
            return None
        text = (f'Первые {h(t1)} автомобиль ехал со скоростью {v1} км/ч, следующие {h(t2)} — со скоростью {v2} км/ч, а затем '
                f'{h(t3)} — со скоростью {v3} км/ч. Найдите среднюю скорость автомобиля на протяжении всего пути. Ответ дайте в км/ч.')
        sol = (f'Средняя скорость — весь путь, делённый на всё время: $\\frac{{{v1} \\cdot {t1} + {v2} \\cdot {t2} + {v3} \\cdot {t3}}}'
               f'{{{t1} + {t2} + {t3}}} = \\frac{{{v1 * t1 + v2 * t2 + v3 * t3}}}{{{t1 + t2 + t3}}} = {n(V)}$ км/ч.')
        return (f'abs(x*{t1 + t2 + t3} - ({v1}*{t1} + {v2}*{t2} + {v3}*{t3})) < 1e-9', V, text, sol,
                f'Средняя скорость: {v1}, {v2}, {v3}')
    if kind == 'percent':
        p, q = rng.choice([10, 20, 25, 30, 40, 50]), rng.choice([10, 20, 25, 30, 40, 50])
        x0 = rng.randint(4, 200) * 100
        fin = F(x0) * (100 + p) * (100 - q) / 10000
        if not is_dec(fin) or fin.denominator != 1:
            return None
        text = (f'Цену товара повысили на {p}%, а затем новую цену снизили на {q}%. После этого товар стал стоить {n(fin)} рублей. '
                f'Сколько рублей стоил товар первоначально?')
        sol = (f'Цена умножилась на ${n(F(100 + p, 100))}$, затем на ${n(F(100 - q, 100))}$: '
               f'$x \\cdot {n(F(100 + p, 100) * F(100 - q, 100))} = {n(fin)}$, $x = {x0}$ руб.')
        return f'abs(x*{(100 + p) * (100 - q)}/10000 - {float(fin)}) < 1e-6', F(x0), text, sol, f'Проценты: +{p}%, −{q}%, итог {n(fin)}'
    if kind == 'meet':
        v1, v2 = rng.randint(3, 25), rng.randint(3, 25)
        t = F(rng.randint(1, 12), 2)
        D = (v1 + v2) * t
        if not is_dec(D):
            return None
        text = (f'Из двух городов, расстояние между которыми равно {n(D)} км, навстречу друг другу одновременно выехали два '
                f'велосипедиста. Скорость первого {v1} км/ч, второго — {v2} км/ч. Через сколько часов они встретятся?')
        sol = f'Скорость сближения ${v1} + {v2} = {v1 + v2}$ км/ч, время до встречи $\\frac{{{n(D)}}}{{{v1 + v2}}} = {n(t)}$ ч.'
        return f'abs(x*({v1}+{v2}) - {float(D)}) < 1e-9', t, text, sol, f'Навстречу: {n(D)} км, {v1} и {v2}'
    # chase: велосипедист выехал, через t0 ч за ним мотоциклист; догнал через t ч; найти скорость велосипедиста
    vb = rng.randint(8, 25)
    vm = vb + rng.randint(10, 50)
    t0 = F(rng.randint(1, 4), 2)
    t = vb * t0 / (vm - vb)
    if not is_dec(t):
        return None
    text = (f'Из пункта А выехал велосипедист, а через {h(t0)} вслед за ним выехал мотоциклист со скоростью {vm} км/ч. '
            f'Мотоциклист догнал велосипедиста через {h(t)} после своего выезда. Найдите скорость велосипедиста. Ответ дайте в км/ч.')
    sol = (f'К моменту встречи пути равны: $x({n(t0)} + {n(t)}) = {vm} \\cdot {n(t)}$, откуда '
           f'$x = \\frac{{{n(vm * t)}}}{{{n(t0 + t)}}} = {vb}$ км/ч.')
    return f'abs(x*({float(t0)}+{float(t)}) - {vm}*{float(t)}) < 1e-9', F(vb), text, sol, f'Вдогонку: {vm} км/ч, фора {n(t0)} ч'


def main():
    rng = random.Random(SEED)
    out, titles = [], set()
    for k, (level, kind) in enumerate(PLAN, 1):
        for _ in range(20000):
            r = make(rng, kind)
            if r is None:
                continue
            check, x, text, sol, title = r
            if title in titles or not is_dec(x) or x <= 0:
                continue
            titles.add(title)
            break
        else:
            raise SystemExit(f'№11, {kind}: не удалось подобрать задачу')
        out.append(item(11, k, level, TOPIC, title, text, sol, ans(x), {'kind': kind, 'check': check}))
    emit(out)


if __name__ == '__main__':
    main()
