#!/usr/bin/env python3
"""Выгрузка открытого банка ФИПИ (ЕГЭ, профильная математика) для ВНУТРЕННЕГО использования: образцы формулировок
по номерам заданий — по ним пишем генераторы банка stackly. В продукт и в git задания ФИПИ не попадают: всё
скачанное лежит в tools/fipi_math/ (папка в .gitignore). Загрузка и разбор страниц — как в tools/fipi_bank.py.

    python3 tools/fipi_math.py fetch            # страницы банка → tools/fipi_math/pages/ (кэш, пауза между запросами)
    python3 tools/fipi_math.py parse            # страницы → tasks.json; формулы MathML переводятся в строку: (a)/(b), x^2, √(x)
    python3 tools/fipi_math.py split            # задания по номерам ЕГЭ-2027 → by_number/NN.json и NN.md

Нумерация — по проекту демоверсии 2027 года: часть 1 — №1–13 (краткий ответ), часть 2 — №14–20.
Номера в банке нет, он определяется по тексту условия (правила ниже); не распознанное — в 00.
"""
import html, json, os, re, sys, time
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fipi_bank as fb

PROJ = 'AC437B34557F88EA4115D2F374B0A07B'          # «Математика. Профильный уровень» в банке ЕГЭ
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fipi_math')


def fetch():
    pages = os.path.join(OUT, 'pages')
    os.makedirs(pages, exist_ok=True)
    q = lambda p: fb.get(fb.BASE + 'questions.php', {'proj': PROJ, 'page': p, 'pagesize': fb.PAGESIZE}).decode('cp1251')
    first = q(0)
    total = int(re.search(r'setQCount\((\d+)\)', first).group(1))
    n = -(-total // fb.PAGESIZE)
    print(f'заданий в банке: {total}, страниц по {fb.PAGESIZE}: {n}', file=sys.stderr)
    for p in range(n):
        path = os.path.join(pages, f'{p:03d}.html')
        if os.path.exists(path):
            continue
        open(path, 'w', encoding='utf-8').write(first if p == 0 else q(p))
        print(f'  страница {p + 1}/{n}', file=sys.stderr)
        time.sleep(fb.PAUSE)


# ------------------------------------------------------------------ MathML → строка
def _wrap(s):
    return s if re.fullmatch(r'[\w.,]+|√?\(.*\)', s) and s.count('(') == s.count(')') else f'({s})'


def _ml(e):
    tag = e.tag.split('}')[-1].split(':')[-1]
    kids = [c for c in e if c.tag.split(':')[-1] != 'annotation']
    if tag in ('mi', 'mn', 'mtext', 'ms'):
        return (e.text or '').replace(' ', ' ').replace(' ', '').strip() or ' '
    if tag == 'mo':
        t = (e.text or '').strip().replace('−', '−')
        return f' {t} ' if t in ('=', '<', '>', '≤', '≥', '≠', '+', '−', '⋅', '·', '×') else t
    if tag == 'mfrac':
        return f'{_wrap(_ml(kids[0]))}/{_wrap(_ml(kids[1]))}'
    if tag == 'msup':
        return f'{_ml(kids[0])}^{_wrap(_ml(kids[1]))}'
    if tag == 'msub':
        return f'{_ml(kids[0])}_{_wrap(_ml(kids[1]))}'
    if tag == 'msubsup':
        return f'{_ml(kids[0])}_{_wrap(_ml(kids[1]))}^{_wrap(_ml(kids[2]))}'
    if tag == 'msqrt':
        return f'√({"".join(_ml(c) for c in kids)})'
    if tag == 'mroot':
        return f'root{_wrap(_ml(kids[1]))}({_ml(kids[0])})'
    if tag in ('mover', 'munder', 'munderover'):
        base = _ml(kids[0])
        mark = _ml(kids[1]).strip() if len(kids) > 1 else ''
        return f'vec({base})' if mark in ('→', '⟶') else base if tag == 'mover' else f'{base}_{_wrap(_ml(kids[1]))}' + (f'^{_wrap(_ml(kids[2]))}' if len(kids) > 2 else '')
    if tag == 'mfenced':
        return f'{e.get("open", "(")}{e.get("separators", ",")[:1].join(_ml(c) for c in kids)}{e.get("close", ")")}'
    if tag == 'mtable':
        return '{ ' + '; '.join(_ml(r) for r in kids) + ' }'
    if tag == 'mtd':
        return ' '.join(_ml(c) for c in kids)
    return ''.join(_ml(c) for c in kids)


def mathml_text(fragment):
    src = re.sub(r'<(/?)m:', r'<\1', fragment)
    src = re.sub(r'&(?!#|amp;|lt;|gt;|quot;|apos;)(\w+);', lambda m: html.unescape(m.group(0)), src)
    try:
        s = _ml(ET.fromstring(src))
    except ET.ParseError:
        s = fb.cell(fragment)
    s = re.sub(r'\s+', ' ', s).strip()
    return ' ' + html.escape(s, quote=False) + ' '      # дальше текст проходит через text_of, который снимает теги


def parse():
    pages = os.path.join(OUT, 'pages')
    tasks, seen = [], set()
    for name in sorted(os.listdir(pages)):
        s = open(os.path.join(pages, name), encoding='utf-8').read()
        starts = [m.start() for m in re.finditer(r'<div class="qblock[^"]*" id=', s)] + [len(s)]
        for a, b in zip(starts, starts[1:]):
            block = re.sub(r'(?is)<m:math\b.*?</m:math>', lambda m: mathml_text(m.group(0)), s[a:b])
            t = fb.parse_block(block)
            t['html'] = ''                            # исходный HTML с MathML есть в pages/, в json не дублируем
            if t['qid'] not in seen:
                seen.add(t['qid'])
                tasks.append(t)
    json.dump(tasks, open(os.path.join(OUT, 'tasks.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'заданий разобрано: {len(tasks)}', file=sys.stderr)


# ------------------------------------------------------------------ split
# Номера ЕГЭ-2027 по спецификации ФИПИ (обобщённый план варианта): номер → (тема, уровень, макс. балл).
# Отличия от 2026: новые №6 (случайная величина) и №13 (текстовые и финансовые задачи с кратким ответом, бывший №16
# части 2 в упрощённом виде) и №17 (моделирование: наибольшее/наименьшее значение величины из физики и жизни);
# экстремум и наибольшее значение функции (бывший №12) вошли в №9. Остальные номера сдвинулись: 2026 №6–11 → №7–12,
# №13–15 → №14–16, №17–19 → №18–20. Банк ФИПИ пока в формате 2026 года: №6 в нём нет, а финансовые задачи
# лежат среди развёрнутых. Правила (номер, выражение) ниже — первое подошедшее.
EGE2027 = {
    1: ('Планиметрия', 'Б', 1), 2: ('Векторы', 'Б', 1), 3: ('Стереометрия', 'Б', 1),
    4: ('Вероятность случайного события', 'Б', 1),
    5: ('Вероятность: сложение и умножение, полная вероятность', 'П', 1),
    6: ('Случайная величина: распределение, матожидание, дисперсия', 'П', 1),
    7: ('Простейшие уравнения', 'Б', 1), 8: ('Вычисления и преобразования', 'Б', 1),
    9: ('Производная, экстремум, первообразная', 'Б', 1), 10: ('Прикладная задача по формуле', 'П', 1),
    11: ('Текстовая задача', 'П', 1), 12: ('Графики функций', 'П', 1), 13: ('Текстовые и финансовые задачи', 'П', 1),
    14: ('Уравнение с отбором корней', 'П', 2), 15: ('Стереометрия: доказательство и вычисление', 'П', 3),
    16: ('Неравенство', 'П', 2), 17: ('Моделирование: оптимизация', 'П', 2),
    18: ('Планиметрия: доказательство и вычисление', 'П', 3), 19: ('Параметр', 'В', 4), 20: ('Числа и их свойства', 'В', 4),
}
TOPICS = {n: t for n, (t, _, _) in EGE2027.items()}
STEREO = (r'(?i)призм|пирамид|параллелепипед|куб[аеуо]?\b|цилиндр|конус|шар\b|шара|сфер|тетраэдр|многогранник|'
          r'тел[ао] вращения|A_1|B_1|C_1|D_1|SABC|сечени')
PLANE = r'(?i)треугольник|четырёхугольник|окружност|трапеци|параллелограмм|ромб|уг(ол|л)|площадь|хорд|биссектрис|медиан'
SHORT = [
    (6, r'(?i)математическ\w* ожидани|дисперси|случайн\w* величин|распределени\w* вероятност'),
    (12, r'(?i)изображ\w* график\w* (функци\w* )?вида|графики (двух )?(линейных )?функций|f\(x\) = (kx|ax|a√|k/x|log_a|a\^x)'),
    (9, r"(?i)производн|касательн|f'\(x\)|точк\w* (максимума|минимума)|(наибольшее|наименьшее) значение функции|первообразн"),
    (2, r'(?i)вектор'),
    (3, STEREO),
    (5, r'(?i)вероятност.*(независим|хотя бы|обе?\b|оба|оди?н? из|стрел|ламп|автомат|кубик|монет|батаре|дважды|два раза|'
        r'подряд|выйдет|перегор|исправ|ошибочн|диагност|больн|точн\w* 1|окажется\s+(больше|меньше))'),
    (4, r'(?i)вероятност|наугад|случайн\w* (образом|выбран)'),
    (1, PLANE),
    (10, r'(?i)по закону|по формуле|вычисля\w* по|формул\w* [a-zа-я]\s*=|задаётся формулой|определяется выражением|экспериментально'),
    (11, r'(?i)км/ч|скорост|теплоход|лодк|велосипедист|рабоч|бригад|сплав|раствор|сосуд|концентрац|процент|%|'
         r'заказ|детал|насос|труб|бассейн|автомобил\w* (выехал|проехал)|пешеход|поезд|мотоциклист.*(выехал|догнал)'),
    (7, r'(?i)корень уравнения|корни уравнения|решите уравнение'),
    (8, r'(?i)значение выражения|найдите (tg|ctg|sin|cos)|найдите значение'),
    (10, r'.'),                                       # остальные с кратким ответом — формулы из жизни и физики
]
LONG = [
    (19, r'(?i)найдите все значения\s*(параметра\s*)?a?\b|при каждом из которых|все значения параметра'),
    (17, r'(?i)ценн\w* бумаг|завод|фабрик|прибыл|затрат|рабочи\w* .*(час|зарплат)|комбинат|руд|акци|наибольш\w* .*доход|оптималь'),
    (13, r'(?i)кредит|вклад|банк|долг'),
    (15, STEREO),
    (16, r'(?i)решите неравенство|решите систему неравенств'),
    (14, r'(?i)решите уравнение|корни этого уравнения'),
    (18, PLANE),
    (20, r'.'),
]


def number_of(t):
    text = re.sub(r'\s+', ' ', t['text'])
    for n, rx in (SHORT if t['kind'] == 'Краткий ответ' else LONG):
        if re.search(rx, text):
            return n
    return 0


def overview(n, g, path):
    kinds = {}
    for t in g:
        key = re.sub(r'[\d−]+', '#', re.sub(r'\s+', ' ', t['text']))[:50]
        kinds.setdefault(key, []).append(t)
    out = [f'# № {n:02d}. {TOPICS.get(n, "не распознано")}: {len(g)} заданий открытого банка ФИПИ (внутреннее использование)', '']
    for i, (key, ts) in enumerate(sorted(kinds.items(), key=lambda kv: -len(kv[1])), 1):
        t = ts[0]
        out += [f'## {i}. {key}… — {len(ts)} шт.', '',
                f'Пример: задание {t["qid"]}, КЭС {", ".join(t["kes"]) or "—"}' + (f', картинок: {len(t["images"])}' if t['images'] else '') + '.',
                '', '```', t['text'], '```', '']
    open(path, 'w', encoding='utf-8').write('\n'.join(out))


def split():
    tasks = json.load(open(os.path.join(OUT, 'tasks.json'), encoding='utf-8'))
    groups = {}
    for t in tasks:
        t['ege'] = number_of(t)
        groups.setdefault(t['ege'], []).append(t)
    d = os.path.join(OUT, 'by_number')
    os.makedirs(d, exist_ok=True)
    for name in os.listdir(d):
        os.remove(os.path.join(d, name))
    lines = ['# Открытый банк ФИПИ, профильная математика, по номерам ЕГЭ-2027 (внутреннее использование)', '',
             f'Всего заданий: {len(tasks)}. Номер определён правилами tools/fipi_math.py; 00 — не распознано.', '',
             '| № | тема | заданий | с картинками | пример |', '|---|---|---|---|---|']
    for n in sorted(groups):
        g = groups[n]
        json.dump(g, open(os.path.join(d, f'{n:02d}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        overview(n, g, os.path.join(d, f'{n:02d}.md'))
        sample = re.sub(r'\s+', ' ', g[0]['text'])[:100].replace('|', '/')
        lines.append(f'| {n:02d} | {TOPICS.get(n, "—")} | {len(g)} | {sum(bool(t["images"]) for t in g)} | {sample}… |')
    open(os.path.join(OUT, 'README.md'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('\n'.join(lines[4:]))


if __name__ == '__main__':
    cmd, *args = sys.argv[1:] or ['help']
    if cmd == 'fetch':
        fetch()
    elif cmd == 'parse':
        parse()
    elif cmd == 'split':
        split()
    else:
        print(__doc__)
