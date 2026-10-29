#!/usr/bin/env python3
"""Генератор задач ЕГЭ №27 (кластеризация частиц, формат 2027 года) для банка stackly.

    python3 tools/gen_task27.py > /tmp/task27.json      # 12 задач высокого уровня

Как в демоверсии 2027: в файле 27.txt у каждой частицы координаты x и y, проекции скорости Vx и Vy, масса m
и признак (римская цифра I–VII); числа с десятичной запятой через табуляцию. Частицы делятся на K кластеров
по кинетической энергии E = m(Vx² + Vy²)/2: в кластере энергии любых двух частиц отличаются не больше чем на R.
Промежутки между кластерами меньше R (как в демоверсии), поэтому делить «по разрыву» нельзя — только от самой
лёгкой частицы кластера; разбиение при этом единственно (ширина кластера + промежуток > R). В каждом кластере
нечётное число частиц — центр (сумма |ΔE| минимальна) единственный. Ответ — одна строка из двух чисел:
целые части Q1 × 10 000 и Q2 × 10 000. Решение на Python запускается на своём файле и должно вывести ответ.
Описание задачи — комментарий <!--spec:…-->; тест tests/test_bank_task27.py пересчитывает ответ в точных дробях
и проверяет единственность разбиения. Генерация детерминирована (seed).
"""
import json, math, os, random, subprocess, sys, tempfile

SEED = 20271027
ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII']
N_TASKS = 12
Q1 = {'dmax': 'наибольшее евклидово расстояние между частицами одного кластера, имеющими признак {f}',
      'dmin': 'наименьшее евклидово расстояние между частицами одного кластера, имеющими признак {f}',
      'dcen': 'наибольшее евклидово расстояние от центра кластера до частицы этого же кластера'}
Q2 = {'emax': 'максимальное значение кинетической энергии для центра кластера',
      'emin': 'минимальное значение кинетической энергии для центра кластера',
      'esum': 'сумма кинетических энергий центров всех кластеров',
      'mavg': 'среднее арифметическое масс центров всех кластеров'}


def fmt(v):
    return f'{v:.6f}'.rstrip('0').rstrip('.').replace('.', ',')


def particle(rng, e):
    """Частица с кинетической энергией около e; значения округлены до 6 знаков, как в файле."""
    while True:
        m = round(rng.uniform(0.2, 2.0), 6)
        v = math.sqrt(2 * e / m)
        a = rng.uniform(0, 2 * math.pi)
        vx, vy = round(v * math.cos(a), 6), round(v * math.sin(a), 6)
        if max(abs(vx), abs(vy)) <= 100:
            x, y = round(rng.uniform(-30, 30), 6), round(rng.uniform(-30, 30), 6)
            return [x, y, vx, vy, m, rng.choice(ROMAN)]


def energy(p):
    return p[4] * (p[2] ** 2 + p[3] ** 2) / 2


def make_data(rng, K, R):
    """Кластеры по энергии: ширина w_i < R, промежуток g < R, но w_i + g > R и g + w_(i+1) > R."""
    widths = [rng.uniform(0.62, 0.93) * R for _ in range(K)]
    lo = rng.uniform(1.0, 6.0)
    clusters = []
    for i, w in enumerate(widths):
        n = rng.randrange(101, 302, 2)
        es = [lo, lo + w] + [lo + rng.uniform(0.02, 0.98) * w for _ in range(n - 2)]
        clusters.append([particle(rng, e) for e in es])
        if i + 1 < K:
            need = R - min(w, widths[i + 1])
            lo = lo + w + rng.uniform(need + 0.04 * R, 0.9 * R)
    return clusters


def split(ps, R):
    ps = sorted(ps, key=energy)
    out = [[ps[0]]]
    for p in ps[1:]:
        if energy(p) - energy(out[-1][0]) <= R:
            out[-1].append(p)
        else:
            out.append([p])
    return out


def center(cl):
    return min(cl, key=lambda p: sum(abs(energy(p) - energy(q)) for q in cl))


def q_value(sp, cls):
    cens = [center(c) for c in cls]
    if sp['q1'] in ('dmax', 'dmin'):
        ds = [math.dist(a[:2], b[:2]) for c in cls for i, a in enumerate(c) for b in c[i + 1:]
              if a[5] == sp['f'] and b[5] == sp['f']]
        v1 = max(ds) if sp['q1'] == 'dmax' else min(ds)
    else:
        v1 = max(math.dist(cen[:2], p[:2]) for cen, c in zip(cens, cls) for p in c)
    es = [energy(c) for c in cens]
    v2 = {'emax': max(es), 'emin': min(es), 'esum': sum(es), 'mavg': sum(c[4] for c in cens) / len(cens)}[sp['q2']]
    return v1, v2


def safe(v):
    x = v * 10000
    return abs(x - round(x)) > 1e-4


def code_for(sp):
    if sp['q1'] in ('dmax', 'dmin'):
        q1 = (f"q1 = {'max' if sp['q1'] == 'dmax' else 'min'}(dist(a[1:3], b[1:3]) for cl in clusters\n"
              f"         for i, a in enumerate(cl) for b in cl[i + 1:] if a[5] == b[5] == '{sp['f']}')")
    else:
        q1 = 'q1 = max(dist(c[1:3], p[1:3]) for c, cl in zip(centers, clusters) for p in cl)'
    q2 = {'emax': 'q2 = max(c[0] for c in centers)', 'emin': 'q2 = min(c[0] for c in centers)',
          'esum': 'q2 = sum(c[0] for c in centers)', 'mavg': 'q2 = sum(c[4] for c in centers) / len(centers)'}[sp['q2']]
    return f"""from math import dist

R = {sp['R']}
parts = []
for line in open('27.txt'):
    a = line.replace(',', '.').split()
    if a:
        x, y, vx, vy, m = map(float, a[:5])
        parts.append((m * (vx * vx + vy * vy) / 2, x, y, vx, m, a[5]))   # энергия — первым полем
parts.sort()

# кластер начинается с самой «лёгкой» частицы и берёт всех, чья энергия не дальше R от неё
clusters = [[parts[0]]]
for p in parts[1:]:
    if p[0] - clusters[-1][0][0] <= R:
        clusters[-1].append(p)
    else:
        clusters.append([p])

centers = [min(cl, key=lambda p: sum(abs(p[0] - q[0]) for q in cl)) for cl in clusters]
{q1}
{q2}
print(int(q1 * 10000), int(q2 * 10000))"""


def main():
    rng = random.Random(SEED)
    out = []
    combos = [(q1, q2) for q1 in Q1 for q2 in Q2]
    rng.shuffle(combos)
    for k in range(1, N_TASKS + 1):
        q1, q2 = combos[k - 1]
        while True:
            K, R = rng.randint(3, 5), rng.choice([1.0, 1.5, 2.0, 2.5, 3.0])
            true = make_data(rng, K, R)
            ps = [p for c in true for p in c]
            rng.shuffle(ps)
            cls = split(ps, R)
            if [sorted(map(tuple, c)) for c in cls] != [sorted(map(tuple, c)) for c in sorted(true, key=lambda c: energy(c[0]))]:
                continue
            sp = {'K': K, 'R': R, 'q1': q1, 'q2': q2, 'f': rng.choice(ROMAN[1:5])}
            v1, v2 = q_value(sp, cls)
            if safe(v1) and safe(v2):
                break
        ans = f'{int(v1 * 10000)} {int(v2 * 10000)}'
        rf = str(R).replace('.', ',')
        text = ('Рассматриваются частицы на плоскости, обладающие следующими характеристиками: декартовы координаты, '
                'вектор скорости, масса, а также признак, характеризующий внутреннее строение частицы, обозначаемый числами '
                'от I до VII (в римской системе счисления).<br>Учёный решил провести кластеризацию частиц по значениям их '
                'кинетической энергии, то есть разбить их множество на K непересекающихся непустых подмножеств (кластеров), '
                'таких, что модуль разности кинетических энергий любых двух частиц каждого подмножества не превосходит '
                'значения R. Гарантируется, что такое разбиение существует и единственно для заданного R.<br>Будем называть '
                'центром кластера такую его частицу, для которой сумма модулей разности кинетических энергий со всеми '
                'остальными частицами этого кластера минимальна. Для каждого кластера гарантируется единственность его центра.'
                '<br>В каждой строке текстового файла хранится информация об одной частице: координаты x и y, проекции вектора '
                'скорости Vx и Vy, масса m и признак. Значения разделяются одним или несколькими пробелами и/или символами '
                f'табуляции. Известно, что все описанные в файле частицы подразделяются ровно на {K} кластера'
                f'{"" if K < 5 else "ов"} (K = {K}) с R = {rf} для каждого.<br>Для каждого кластера определите его центр, '
                f'затем найдите два числа: Q1 — {Q1[q1].format(f=sp["f"])}, и Q2 — {Q2[q2]}.<br>В ответе запишите два числа '
                'в одну строку: сначала целую часть произведения Q1 × 10 000, затем целую часть произведения Q2 × 10 000.'
                '<br>Кинетическая энергия частицы массы m со скоростью (Vx; Vy): E = m(Vx² + Vy²)/2. Евклидово расстояние '
                'между точками A(x₁, y₁) и B(x₂, y₂): d = √((x₂ − x₁)² + (y₂ − y₁)²).')
        data = '\n'.join('\t'.join([fmt(v) for v in p[:5]] + [p[5]]) for p in ps)
        note = ('Промежутки между кластерами меньше R, поэтому делить по «разрыву больше R» нельзя: кластер набирается от '
                'самой лёгкой частицы, пока разница энергий не превышает R. Центр по сумме |ΔE| — это медиана энергий кластера.')
        title = f'Частицы: K = {K}, R = {rf}; ' + {'dmax': f'макс. расстояние ({sp["f"]})', 'dmin': f'мин. расстояние ({sp["f"]})',
                                                  'dcen': 'радиус от центра'}[q1] + ', ' + \
            {'emax': 'макс. энергия центра', 'emin': 'мин. энергия центра', 'esum': 'сумма энергий центров',
             'mavg': 'средняя масса центров'}[q2]
        out.append({'id': f'27-g{k:03d}', 'task': 27, 'level': 'В', 'title': title, 'text': text,
                    'extra': '<!--spec:' + json.dumps(sp, ensure_ascii=False, separators=(',', ':')) + '-->',
                    'code': code_for(sp), 'answer': ans, 'data': data, 'dname': '27.txt', 'note': note})
    with tempfile.TemporaryDirectory() as d:
        for p in out:
            open(os.path.join(d, '27.txt'), 'w').write(p['data'] + '\n')
            r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=300, cwd=d)
            if r.stdout.strip() != p['answer']:
                raise SystemExit(f"{p['id']}: решение даёт «{r.stdout.strip()}», ответ «{p['answer']}»\n{r.stderr}")
    print(json.dumps({'В': len(out), 'KB': sum(len(p['data']) for p in out) // 1024}), file=sys.stderr)
    sys.stdout.reconfigure(encoding='utf-8')
    json.dump(out, sys.stdout, ensure_ascii=False)


if __name__ == '__main__':
    main()
