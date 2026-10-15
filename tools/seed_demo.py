#!/usr/bin/env python3
"""Демо-данные для локального просмотра: учитель, группа учеников с историей занятий за ~5 недель и ДЗ.

    python3 tools/seed_demo.py                       # заполнить tools/.dev.db (её использует dev_server.py)
    python3 tools/seed_demo.py --teacher me@mail.ru  # другой учитель
    python3 tools/seed_demo.py --db path/to.db

Повторный запуск пересоздаёт демо-учеников (почты @demo.example.com) и демо-группы учителя.
Учитель, если его ещё нет, создаётся с паролем demo1234; существующему только выдаётся роль teacher.
Все демо-ученики входят с паролем demo1234. На рабочей базе не запускайте.
"""
import argparse, json, os, random, re, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = 'demo1234'
DEMO_DOMAIN = '@demo.example.com'
GROUP = 'Демо-группа 11А'
DAYS_BACK = 35

# имя, почта, доля активных дней, действий за день, доля верных ответов
STUDENTS = [
    ('Демо-ученик', 'student', .9, (2, 4), .85),
    ('Аня Смирнова (демо)', 'anya', .8, (2, 4), .9),
    ('Илья Петров (демо)', 'ilya', .6, (1, 4), .75),
    ('Маша Козлова (демо)', 'masha', .5, (1, 3), .7),
    ('Дима Орлов (демо)', 'dima', .35, (1, 3), .6),
    ('Катя Волкова (демо)', 'katya', .2, (1, 2), .55),
]


def content_ids():
    with open(os.path.join(ROOT, 'content', 'ege.js'), encoding='utf-8') as f:
        bank = [(i, int(t)) for i, t in re.findall(r'"id": "([^"]+)", "task": (\d+)', f.read())]
    with open(os.path.join(ROOT, 'public', 'index.html'), encoding='utf-8') as f:
        py = sorted({int(x) for x in re.findall(r'^T\(\{ id: (\d+)', f.read(), re.M)})
    bank.sort(key=lambda x: (x[1], x[0]))
    return [i for i, _ in bank], py, list(range(1, 28))


def simulate(rnd, bank, py, ege, p_active, pace, acc, now, main):
    """История одного ученика в формате snapshot() из public/index.html. Возвращает (data, время первого закрытия пункта)."""
    att, days, events, done_at = {}, {}, [], {}
    solved, studied, read = [], [], []
    queues = {'a': list(bank), 's': list(py), 'r': list(ege)}
    for back in range(DAYS_BACK, -1, -1):
        always = main and back <= 6                     # у главного демо-ученика серия последних дней
        if not always and rnd.random() > p_active:
            continue
        base = time.mktime(time.localtime(now - back * 86400)[:3] + (0, 0, 0, 0, 0, -1))
        start = base + rnd.randint(15, 19) * 3600 + rnd.randint(0, 3599)
        if back == 0:
            start = min(start, now - 3 * 3600)
        t = start
        for _ in range(rnd.randint(*pace)):
            t += rnd.randint(60, 900)
            if back == 0 and t > now - 60:
                break
            kinds = [k for k in 'asr' if queues[k]]
            if not kinds:
                break
            kind = rnd.choices(kinds, weights=[{'a': 4, 's': 2, 'r': 1}[k] for k in kinds])[0]
            item, key = queues[kind][0], DAY_KEY(t)
            ms = int(t * 1000)
            if kind == 'a':
                ok = rnd.random() < acc
                a = att.setdefault(item, {'n': 0, 'c': 0, 'first': ms, 'ok': 0})
                a['n'] += 1
                if ok:
                    a['c'] += 1
                    a['ok'] = a['ok'] or ms
                    solved.append(queues['a'].pop(0)); done_at[('bank', item)] = t
                days[key] = days.get(key, 0) + 1
            else:
                ok = True
                (studied if kind == 's' else read).append(queues[kind].pop(0))
                done_at[('py' if kind == 's' else 'ege', item)] = t
                days[key] = days.get(key, 0) + 1
            events.append({'t': ms, 'k': kind, 'id': str(item), 'ok': int(ok)})
    data = {'v': 1, 'solved': solved, 'studied': studied, 'ege': read, 'att': att, 'days': days,
            'events': events[-120:], 'since': int((now - (DAYS_BACK + 3) * 86400) * 1000)}
    return data, done_at


def DAY_KEY(t):
    return time.strftime('%Y-%m-%d', time.localtime(t))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--db', default=os.path.join(ROOT, 'tools', '.dev.db'))
    ap.add_argument('--teacher', default='dglumov4@gmail.com')
    ap.add_argument('--seed', type=int, default=7)
    args = ap.parse_args()
    if args.db.startswith('/var/lib/'):
        sys.exit('Похоже на рабочую базу — демо-данные туда не пишем.')

    os.environ['STACKLY_DB'] = args.db
    sys.path.insert(0, os.path.join(ROOT, 'app'))
    import stackly_api as api
    api.migrate()
    con, now, rnd = api.db(), time.time(), random.Random(args.seed)
    bank, py, ege = content_ids()
    pw = api.hash_password(PASSWORD)

    con.execute('BEGIN')
    teacher = con.execute('SELECT id, role FROM users WHERE email = ?', (args.teacher.lower(),)).fetchone()
    if teacher:
        tid = teacher['id']
        if teacher['role'] == 'student':
            con.execute("UPDATE users SET role = 'teacher' WHERE id = ?", (tid,))
        teacher_note = 'существующий аккаунт, пароль прежний'
    else:
        tid = con.execute("INSERT INTO users (email, name, pw_hash, created, role) VALUES (?,?,?,?,'teacher')",
                          (args.teacher.lower(), 'Учитель', pw, int(now) - 60 * 86400)).lastrowid
        teacher_note = 'пароль ' + PASSWORD
    con.execute('DELETE FROM users WHERE email LIKE ?', ('%' + DEMO_DOMAIN,))
    con.execute("DELETE FROM study_groups WHERE teacher_id = ? AND name LIKE 'Демо%'", (tid,))

    gid = con.execute('INSERT INTO study_groups (teacher_id, name, code, created) VALUES (?,?,?,?)',
                      (tid, GROUP, api.new_group_code(), int(now) - 40 * 86400)).lastrowid
    day = 86400
    homework = [  # название, пункты, создано (дней назад), срок (дней назад; минус — в будущем)
        ('Графы и таблицы истинности', {'bank': bank[:6], 'py': py[:3], 'ege': ege[:2]}, 30, 23),
        ('Системы счисления', {'bank': bank[6:12], 'py': py[3:6], 'ege': ege[2:5]}, 21, 12),
        ('Обработка строк', {'bank': bank[12:18], 'py': py[6:9], 'ege': ege[5:7]}, 10, 2),
        ('Перебор и рекурсия', {'bank': bank[18:24], 'ege': ege[7:9]}, 2, -5),
    ]
    hws = []
    for title, items, created, due in homework:
        c = int(now - created * day)
        hid = con.execute('INSERT INTO homework (group_id, title, comment, items, students, due, created, updated) '
                          "VALUES (?,?,?,?,'[]',?,?,?)",
                          (gid, title, 'Демо-задание', json.dumps(items), int(now - due * day), c, c)).lastrowid
        hws.append((hid, items))

    for i, (name, login, p_active, pace, acc) in enumerate(STUDENTS):
        uid = con.execute("INSERT INTO users (email, name, pw_hash, created, role) VALUES (?,?,?,?,'student')",
                          (login + DEMO_DOMAIN, name, pw, int(now - (DAYS_BACK + 3) * day))).lastrowid
        con.execute('INSERT INTO group_members VALUES (?,?,?)', (gid, uid, int(now - (DAYS_BACK + 2) * day)))
        data, done_at = simulate(rnd, bank, py, ege, p_active, pace, acc, now, main=i == 0)
        last = max((e['t'] for e in data['events']), default=int(now * 1000)) // 1000
        con.execute('INSERT INTO progress VALUES (?,?,?)', (uid, json.dumps(data, ensure_ascii=False), last))
        for hid, items in hws:
            keys = [(k, x) for k in ('bank', 'py', 'ege') for x in items.get(k, [])]
            if keys and all(k in done_at for k in keys):
                con.execute('INSERT INTO homework_done VALUES (?,?,?)', (hid, uid, int(max(done_at[k] for k in keys))))
        s = api.summary(data, last)
        print(f'  {name:<22} {login + DEMO_DOMAIN:<28} задач {s["solved"]:>2}, тем {s["studied"]:>2}, '
              f'разборов {s["ege"]:>2}, серия {s["streak"]}, точность {s["accuracy"]}%')
    con.execute('COMMIT')
    print(f'\nГотово: {args.db}\nУчитель: {args.teacher} ({teacher_note})\nУченики: пароль {PASSWORD}\n'
          'Запуск: python3 tools/dev_server.py, затем http://127.0.0.1:8000')


if __name__ == '__main__':
    main()
