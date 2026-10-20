#!/usr/bin/env python3
"""Выгрузка открытого банка ФИПИ (ЕГЭ, информатика) для ВНУТРЕННЕГО использования: образцы формулировок по
номерам заданий — по ним сверяем генераторы банка stackly и ищем новые типы задач. В продукт и в git задания
ФИПИ не попадают: всё скачанное лежит в tools/fipi/ (папка в .gitignore).

    python3 tools/fipi_bank.py fetch            # страницы банка → tools/fipi/pages/ (кэш, пауза между запросами)
    python3 tools/fipi_bank.py parse            # страницы → tools/fipi/tasks.json: текст, HTML, КЭС, картинки, файлы
    python3 tools/fipi_bank.py split            # задания по номерам ЕГЭ → tools/fipi/by_number/NN.json и NN.md (шаблон номера)
    python3 tools/fipi_bank.py assets 9 24      # скачать картинки и архивы с данными для указанных номеров

Номера заданий ЕГЭ в банке ФИПИ нет — только темы КЭС. Номер определяется правилами ниже (тема + ключевые
слова условия); старые форматы, которых в нынешнем ЕГЭ нет, — в 99.json; не распознанное — в 00.json.
"""
import html, json, os, re, sys, time, urllib.parse, urllib.request

PROJ = 'B9ACA5BBB2E19E434CD6BEC25284C67F'          # «Информатика и ИКТ» в банке ЕГЭ
BASE = 'https://ege.fipi.ru/bank/'
FILES = 'https://ege.fipi.ru/'                       # картинки и архивы: пути docs/… от корня сайта (qfiles_location='../../')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fipi')
PAGESIZE = 100
PAUSE = 2.0                                          # секунд между запросами: банк — чужой сервер
UA = 'Mozilla/5.0 (compatible; stackly-research)'


def get(url, data=None):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data else None,
                                 headers={'User-Agent': UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except OSError as e:
            if attempt == 3:
                raise
            print(f'  повтор после ошибки: {e}', file=sys.stderr)
            time.sleep(5 * (attempt + 1))


# ------------------------------------------------------------------ fetch
def fetch():
    pages = os.path.join(OUT, 'pages')
    os.makedirs(pages, exist_ok=True)
    first = get(BASE + 'questions.php', {'proj': PROJ, 'page': 0, 'pagesize': PAGESIZE}).decode('cp1251')
    total = int(re.search(r'setQCount\((\d+)\)', first).group(1))
    n = -(-total // PAGESIZE)
    print(f'заданий в банке: {total}, страниц по {PAGESIZE}: {n}', file=sys.stderr)
    for p in range(n):
        path = os.path.join(pages, f'{p:03d}.html')
        if os.path.exists(path):
            continue
        body = first if p == 0 else get(BASE + 'questions.php', {'proj': PROJ, 'page': p, 'pagesize': PAGESIZE}).decode('cp1251')
        open(path, 'w', encoding='utf-8').write(body)
        print(f'  страница {p + 1}/{n}', file=sys.stderr)
        time.sleep(PAUSE)


# ------------------------------------------------------------------ parse
TAG = r'<(?=[A-Za-z/!])[^>]*>'                       # «1 < N < 26» в условиях — не тег


def cell(fragment):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(TAG, ' ', fragment)).replace('\xa0', ' ')).strip()


def text_of(fragment):
    s = re.sub(r'(?is)<(script|style)\b.*?</\1>', ' ', fragment)
    # строка таблицы — одна строка текста, ячейки через « | »
    s = re.sub(r'(?is)<tr\b[^>]*>(.*?)</tr>',
               lambda m: '\n' + ' | '.join(cell(c) for c in re.findall(r'(?is)<t[dh]\b[^>]*>(.*?)</t[dh]>', m.group(1))) + '\n', s)
    s = re.sub(r'(?i)<br\s*/?>|</p>|</li>|</h\d>', '\n', s)
    s = re.sub(TAG, '', s)
    s = html.unescape(s).replace('\xa0', ' ')
    s = re.sub(r'[ \t\r\f\v]+\n', '\n', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return re.sub(r'[ \t]{2,}', ' ', s).strip()


def parse_block(block):
    qid = re.search(r"class=\"qblock[^\"]*\" id='q([^']+)'", block).group(1)
    guid = re.search(r'name="guid" value="([0-9A-Fa-f]+)"', block).group(1)
    cell = re.search(r"(?is)class='cell_0'>(.*?)<TR bgcolor=\"#FFFFFF\">", block)
    body = cell.group(1) if cell else ''
    images = re.findall(r"ShowPicture[A-Z]*\('([^']+)'", body)
    files = sorted(set(re.findall(r"""['"](docs/[^'"]+\.(?:zip|xlsx?|ods|txt|csv|docx?))['"]""", body)))
    kes = [text_of(d) for d in re.findall(r'(?is)КЭС:</td><td class="param-row">(.*?)</td>', block)]
    kes = [k for k in re.split(r'\n', '\n'.join(kes)) if k.strip()] if kes else []
    kes_codes = [k.split(' ', 1)[0] for k in kes]
    kind = re.search(r'Тип ответа:</td><td>([^<]*)<', block)
    return {'qid': qid, 'guid': guid, 'kes': kes_codes, 'kes_text': kes, 'kind': kind.group(1).strip() if kind else '',
            'text': text_of(body), 'html': body.strip(), 'images': images, 'files': files}


def parse():
    pages = os.path.join(OUT, 'pages')
    tasks, seen = [], set()
    for name in sorted(os.listdir(pages)):
        s = open(os.path.join(pages, name), encoding='utf-8').read()
        starts = [m.start() for m in re.finditer(r'<div class="qblock[^"]*" id=', s)] + [len(s)]
        for a, b in zip(starts, starts[1:]):
            t = parse_block(s[a:b])
            if t['qid'] not in seen:
                seen.add(t['qid'])
                tasks.append(t)
    json.dump(tasks, open(os.path.join(OUT, 'tasks.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'заданий разобрано: {len(tasks)}', file=sys.stderr)


# ------------------------------------------------------------------ split
# Правила (номер, регулярное выражение по тексту условия). Срабатывает первое подошедшее. Темы КЭС в банке
# проставлены неаккуратно (игры помечены «Графами»), поэтому номер определяется по тексту, а КЭС — только запасной
# признак (KES ниже). 99 — задания старых форматов, которых в нынешнем ЕГЭ нет: выбор ответа, развёрнутый ответ,
# массив в программе, «что напечатает программа», количество путей в графе, подпоследовательности старого №27.
OLD = 99
RULES = [
    (20, r'(?is)(задани\w* 19|предыдущем задании).*Петя не может выиграть за один ход|(задани\w* 19|предыдущем задании).*у Пети есть выигрышная стратегия'),
    (21, r'(?is)(задани\w* 19|предыдущем задании).*(у Вани есть выигрышная стратегия|Ваня не может|Ваня выигрывает)'),
    (19, r'(?is)Два игрока.*(куч|камн|позици)|(куч|камн)\w*.*Петя.*Ваня'),
    (OLD, r'(?is)одномерный целочисленный массив|будет (напечатано|выведено) в результате выполнения|при каком (наименьшем|'
          r'наибольшем) введённом значении|различных путей|в одном направлении, указанном стрелк|непрерывн\w* '
          r'подпоследовательност|показания прибора|без упаковки|архиватор|Чертёжник|лабиринт|Запишите порядок команд|'
          r'при вводе которого|печатает (два|три) числа|алгоритм получает на вход|На вход алгоритма подаётся натуральное '
          r'число x|языке запросов поискового сервера|наборов значений логических переменных|Цепочки символов \(строки\) '
          r'создаются|Автомат получает на вход|Дан фрагмент электронной таблицы\. Из ячейки|Исполнитель МТ|Сколько существует натуральных чисел x, для которых'),
    (27, r'(?i)кластер|звёздн\w* (неб|скоплен)|центр\w* (кластера|скопления)|аномали'),
    (22, r'(?i)ID процесса|процесс\w* .*параллельно|время выполнения процесса'),
    (2, r'(?i)таблиц\w* истинности|логическ\w* функци\w* F'),
    (13, r'(?i)маск\w* сети|IP-адрес|TCP/IP'),
    (3, r'(?i)базы данных|база данных|Движение товаров'),
    (16, r'(?i)F\(n\)|F\(\d+\)|рекурсивн|алгоритм вычисления значени\w* функци'),
    (25, r'(?i)соответству\w* маске|маской числа|(?<![а-яё])делител|M\(N\)|простых множител'),
    (24, r'(?is)текстов\w* файл.*(символ|букв|подстрок|цепочк)|файл\w* .*состоит .*(символ|букв)'),
    (18, r'(?is)Робот.*(клетк|квадрат)|(клетк|квадрат).*Робот'),
    (17, r'(?is)прилагаемых файлов.*последовательност|Рассматривается множество целых чисел, принадлежащих'),
    (9, r'(?i)электронн\w* таблиц'),
    (10, r'(?i)текст\w* .*(документ|повест|роман|рассказ|произведени)|сколько раз встречается'),
    (26, r'(?i)прилагаемых (к заданию )?файлов'),
    (23, r'(?i)сколько существует программ|количество программ|траектори\w* вычислени|траекторию'),
    (12, r'(?i)Редактор|заменить\s*\(|нашлось\s*\('),
    (6, r'(?i)Черепах'),
    (5, r'(?is)число R|строит по нему новое число'),
    (15, r'(?i)ДЕЛ\s*\(|тождественно истинн|отрезк\w* (P|Q|A)|\bx\s*&\s*A|& A\b|поразрядн\w* конъюнкци'),
    (1, r'(?is)схем\w* дорог.*(граф|таблиц)|(граф|таблиц).*схем\w* дорог|населённ\w* пункт\w*.*таблиц|сведения о дорогах'),
    (4, r'(?i)условию Фано|условие Фано|неравномерн\w* (двоичн\w* )?код|кодов\w* слов'),
    (7, r'(?i)растров|пиксел|звук|оцифров|дискретизац|видео|скорост\w* передачи|передач\w* .*канал'),
    (11, r'(?i)парол|идентификатор|серийн\w* номер|автомобильн\w* номер|номер\w* .*(байт|бит)|(байт|бит)\w* .*сведени'),
    (8, r'(?i)алфавитном порядке|сколько существует|сколько (различных )?(слов|чисел|кодов|комбинаций)|составляет \w*слова|'
        r'Сколько можно составить|Определите количество .*чисел'),
    (14, r'(?i)систем\w* счислени|значение арифметического выражения'),
    (23, r'(?i)Исполнитель .*(команд|преобразует число)'),
]
# запасной признак: тема КЭС → номер, если текст не подошёл ни под одно правило
KES = {'1.2': 13, '2.1': 4, '2.2': 11, '2.3': 14, '2.6': 7, '2.7': 15, '2.15': 19, '3.7': 16, '4.5': 3, '4.6': 10,
       '1.1': 22, '3.9': 24, '3.4': 25}


def number_of(t):
    if t['kind'] != 'Краткий ответ':
        return OLD
    text = re.sub(r'\s+', ' ', t['text'])            # в условиях переносы строк встречаются посреди фраз
    for n, rx in RULES:
        if re.search(rx, text):
            return n
    for k in t['kes']:
        if k in KES:
            return KES[k]
    return 0


def overview(n, g, path):
    """Шаблон номера: какие формулировки встречаются (по началу условия), сколько заданий каждой, полный пример."""
    intro = 'Задание выполняется с использованием прилагаемых (к заданию )?файлов. '
    kinds = {}
    for t in g:
        key = re.sub(r'\d+', '#', re.sub(intro, '', re.sub(r'\s+', ' ', t['text']).lstrip('| ')))[:45]   # цифры не различаем
        kinds.setdefault(key, []).append(t)
    out = [f'# № {n:02d}: {len(g)} заданий открытого банка ФИПИ (внутреннее использование)', '']
    for i, (key, ts) in enumerate(sorted(kinds.items(), key=lambda kv: -len(kv[1])), 1):
        t = ts[0]
        extra = (f', картинок: {len(t["images"])}' if t['images'] else '') + (f', файлов: {len(t["files"])}' if t['files'] else '')
        out += [f'## {i}. {key}… — {len(ts)} шт.', '', f'Пример: задание {t["qid"]}, КЭС {", ".join(t["kes"]) or "—"}{extra}.',
                f'Ещё: {", ".join(x["qid"] for x in ts[1:8])}{" …" if len(ts) > 8 else ""}' if len(ts) > 1 else '', '',
                '```', t['text'], '```', '']
    open(path, 'w', encoding='utf-8').write('\n'.join(out))


def split():
    tasks = json.load(open(os.path.join(OUT, 'tasks.json'), encoding='utf-8'))
    groups = {}
    for t in tasks:
        t['ege'] = number_of(t)
        groups.setdefault(t['ege'], []).append(t)
    d = os.path.join(OUT, 'by_number')
    os.makedirs(d, exist_ok=True)
    for name in os.listdir(d):                        # старые файлы от прошлой разбивки
        os.remove(os.path.join(d, name))
    lines = ['# Открытый банк ФИПИ по номерам ЕГЭ (внутреннее использование)', '',
             f'Всего заданий: {len(tasks)}. Номер определён правилами tools/fipi_bank.py; 00 — не распознано, 99 — старые форматы.', '',
             '| № | заданий | с картинками | с файлами | пример |', '|---|---|---|---|---|']
    for n in sorted(groups):
        g = groups[n]
        json.dump(g, open(os.path.join(d, f'{n:02d}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        overview(n, g, os.path.join(d, f'{n:02d}.md'))
        sample = re.sub(r'\s+', ' ', g[0]['text'])[:110].replace('|', '/')
        lines.append(f'| {n:02d} | {len(g)} | {sum(bool(t["images"]) for t in g)} | {sum(bool(t["files"]) for t in g)} | {sample}… |')
    open(os.path.join(OUT, 'README.md'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('\n'.join(lines[4:]), file=sys.stderr)


# ------------------------------------------------------------------ assets
def assets(numbers):
    d = os.path.join(OUT, 'by_number')
    for n in numbers:
        g = json.load(open(os.path.join(d, f'{int(n):02d}.json'), encoding='utf-8'))
        for t in g:
            for path in t['images'] + t['files']:
                local = os.path.join(OUT, 'assets', f'{int(n):02d}', t['qid'], os.path.basename(path))
                if os.path.exists(local):
                    continue
                os.makedirs(os.path.dirname(local), exist_ok=True)
                try:
                    body = get(FILES + urllib.parse.quote(path))
                except OSError as e:
                    print(f'  {t["qid"]}: {path} — {e}', file=sys.stderr)
                    continue
                open(local, 'wb').write(body)
                time.sleep(PAUSE / 2)
        print(f'№{n}: готово', file=sys.stderr)


if __name__ == '__main__':
    cmd, *args = sys.argv[1:] or ['help']
    if cmd == 'fetch':
        fetch()
    elif cmd == 'parse':
        parse()
    elif cmd == 'split':
        split()
    elif cmd == 'assets':
        assets(args)
    else:
        print(__doc__)
