#!/usr/bin/env python3
"""Telegram-бот stackly для преподавателей (и напоминаний ученикам).

Только стандартная библиотека Python 3.10+. Работает отдельным сервисом (deploy/stackly-bot.service) рядом с API
и с той же базой SQLite. API в Telegram не ходит: он ставит сообщения в очередь tg_outbox, бот их отправляет.

Что умеет:
  * уведомления преподавателю: ученик выполнил ДЗ, новый ученик в группе;
  * сводка, когда прошёл срок ДЗ (кто сдал, кто нет), и вечерняя сводка за день;
  * команды: /groups — группы и коды, /hw — задания с прогрессом, /student Имя — статистика ученика,
    /settings — какие уведомления присылать, /stop — отключить бота;
  * кнопка «Напомнить не сдавшим»: сообщение ученикам, которые подключили бота.
Ученику бот присылает напоминания преподавателя и по /hw показывает, что осталось сделать.
Для преподавателя бот работает на тарифе Про (и пробном Про).

Аккаунт привязывается одноразовой ссылкой t.me/<бот>?start=<токен>: её выдаёт кабинет на сайте (POST /api/tg/link).

Переменные окружения (кроме тех, что у API, — база общая):
  STACKLY_TG_TOKEN      токен бота от @BotFather; без него сервис сразу завершается
  STACKLY_TG_BOT        имя бота без @ (нужно API для ссылки привязки)
  STACKLY_TG_API        адрес Bot API (по умолчанию https://api.telegram.org; в тестах — заглушка)
  STACKLY_TG_POLL       сколько секунд ждать новых сообщений в одном запросе (25)
  STACKLY_TG_TICK       пауза между отправками очереди, секунд (2)
  STACKLY_TG_PERIOD     как часто проверять сроки и вечернюю сводку, секунд (60)
  STACKLY_TG_DIGEST     час вечерней сводки по Москве (20)
"""
import calendar, json, os, re, sys, threading, time, urllib.error, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stackly_api as A        # noqa: E402 — общие база, тарифы и очередь

TOKEN = A.TG_TOKEN
API = os.environ.get('STACKLY_TG_API', 'https://api.telegram.org').rstrip('/')
POLL = int(os.environ.get('STACKLY_TG_POLL', '25'))
TICK = float(os.environ.get('STACKLY_TG_TICK', '2'))
PERIOD = float(os.environ.get('STACKLY_TG_PERIOD', '60'))
DIGEST_HOUR = int(os.environ.get('STACKLY_TG_DIGEST', '20'))
REMIND_GAP = 6 * 3600          # «Напомнить» по одному заданию — не чаще раза в 6 часов
MONTHS = ('января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря')
PREF_NAMES = {'done': 'Ученик выполнил задание', 'join': 'Новый ученик в группе', 'due': 'Сводка, когда прошёл срок', 'digest': f'Вечерняя сводка в {DIGEST_HOUR}:00'}
log = A.log
esc = A.tg_esc
db = A.db


class TgError(Exception):
    def __init__(self, code, text):
        super().__init__(f'{code}: {text}')
        self.code = code


def tg(method, **params):
    """Вызов Bot API; ошибка Telegram — TgError с кодом, сеть — OSError."""
    req = urllib.request.Request(f'{API}/bot{TOKEN}/{method}', data=json.dumps(params, ensure_ascii=False).encode(),
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=POLL + 15) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        try:
            res = json.load(e)
        except ValueError:
            res = {'ok': False, 'error_code': e.code, 'description': str(e)}
    if not res.get('ok'):
        raise TgError(res.get('error_code'), res.get('description'))
    return res['result']


def say(chat_id, text, markup=None, edit=None):
    """Ответ на команду — сразу, без очереди; edit — id сообщения, которое нужно заменить."""
    p = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
    if markup:
        p['reply_markup'] = markup
    if edit:
        tg('editMessageText', message_id=edit, **p)
    else:
        tg('sendMessage', **p)


# ---------------------------------------------------------------- данные
def fmt_due(ts):
    t = time.gmtime(ts + A.METRIC_TZ)
    return f'{t.tm_mday} {MONTHS[t.tm_mon - 1]}, {t.tm_hour:02}:{t.tm_min:02}'


def linked(chat_id):
    return db().execute('SELECT u.*, l.chat_id, l.prefs FROM tg_links l JOIN users u ON u.id = l.user_id WHERE l.chat_id = ?',
                        (chat_id,)).fetchone()


def hw_status(h):
    """Кому выдано задание и кто уже сделал: ([(id, имя)], {id})."""
    to = json.loads(h['students'])
    rec = [(r['id'], r['name']) for r in db().execute(
        'SELECT u.id, u.name FROM group_members m JOIN users u ON u.id = m.user_id WHERE m.group_id = ? ORDER BY u.name COLLATE NOCASE',
        (h['group_id'],)) if not to or r['id'] in to]
    done = {r['user_id'] for r in db().execute('SELECT user_id FROM homework_done WHERE hw_id = ?', (h['id'],))}
    return rec, done


def names(xs, limit=15):
    xs = list(xs)
    return ', '.join(esc(x) for x in xs[:limit]) + (f' и ещё {len(xs) - limit}' if len(xs) > limit else '')


def remind_kb(hw_id):
    return {'inline_keyboard': [[{'text': '🔔 Напомнить не сдавшим', 'callback_data': f'r:{hw_id}'}]]}


def own_hw(u, hw_id):
    h = db().execute('SELECT h.*, g.name AS group_name, g.teacher_id FROM homework h JOIN study_groups g ON g.id = h.group_id WHERE h.id = ?',
                     (hw_id,)).fetchone()
    return h if h and (h['teacher_id'] == u['id'] or u['role'] == 'admin') else None


def link_hint():
    site = A.ORIGIN or 'сайте stackly'
    return f'Чтобы подключить бота, откройте {esc(site)} → «Кабинет» → блок «Telegram» и нажмите «Подключить».'


# ---------------------------------------------------------------- команды
HELP_TEACHER = ('<b>Команды</b>\n/hw — задания и кто сдал\n/groups — группы и коды для учеников\n'
                '/student Имя — статистика ученика\n/settings — какие уведомления присылать\n/stop — отключить бота')
HELP_STUDENT = '<b>Команды</b>\n/hw — что осталось сделать\n/stop — отключить бота'


def cmd_start(chat, token, username):
    if not token:
        u = linked(chat)
        return say(chat, ('Бот уже подключён.\n\n' + (HELP_STUDENT if u['role'] == 'student' else HELP_TEACHER)) if u else
                   'Привет! Это бот stackly.\n\n' + link_hint())
    now = int(time.time())
    r = db().execute('SELECT user_id FROM tg_tokens WHERE token_hash = ? AND expires > ?', (A.sha(token), now)).fetchone()
    if not r:
        return say(chat, 'Ссылка устарела или уже использована. Возьмите новую в кабинете на сайте.')
    db().execute('DELETE FROM tg_tokens WHERE token_hash = ?', (A.sha(token),))
    # один чат — один аккаунт: прежняя привязка этого чата или этого аккаунта заменяется
    db().execute('DELETE FROM tg_links WHERE chat_id = ? OR user_id = ?', (chat, r['user_id']))
    db().execute("INSERT INTO tg_links (user_id, chat_id, username, prefs, linked) VALUES (?,?,?,'{}',?)", (r['user_id'], chat, username or '', now))
    u = linked(chat)
    if u['role'] == 'student':
        say(chat, f'Готово, <b>{esc(u["name"])}</b>! Сюда придут напоминания преподавателя о домашних заданиях.\n\n{HELP_STUDENT}')
    else:
        say(chat, f'Готово, <b>{esc(u["name"])}</b>! Буду присылать, кто сдал задания, кто вступил в группы, '
                  f'сводку по срокам и вечернюю сводку за день.\n\n{HELP_TEACHER}')


def cmd_groups(chat, u):
    rows = db().execute('SELECT g.name, g.code, (SELECT COUNT(*) FROM group_members m WHERE m.group_id = g.id) AS n '
                        'FROM study_groups g WHERE g.teacher_id = ? ORDER BY g.created DESC', (u['id'],)).fetchall()
    if not rows:
        return say(chat, 'Групп пока нет. Создайте группу на сайте в разделе «Учителю».')
    say(chat, '<b>Ваши группы</b>\n' + '\n'.join(f'• {esc(r["name"])} — {r["n"]} уч., код <code>{esc(r["code"])}</code>' for r in rows)
        + '\n\nУченик вводит код в кабинете на сайте.')


def cmd_hw(chat, u):
    now = int(time.time())
    hws = db().execute('SELECT h.*, g.name AS group_name FROM homework h JOIN study_groups g ON g.id = h.group_id '
                       'WHERE g.teacher_id = ? AND (h.due IS NULL OR h.due > ?) ORDER BY COALESCE(h.due, h.created + 315360000) LIMIT 10',
                       (u['id'], now - 3 * 86400)).fetchall()
    if not hws:
        return say(chat, 'Активных заданий нет. Выдайте задание на сайте — здесь появится, кто его сдал.')
    say(chat, '<b>Задания</b> — по одному сообщению, под каждым кнопка напоминания')
    for h in hws:
        rec, done = hw_status(h)
        miss = [n for i, n in rec if i not in done]
        due = f'срок {fmt_due(h["due"])}' + (' — прошёл' if h['due'] and h['due'] < now else '') if h['due'] else 'без срока'
        text = (f'📘 <b>{esc(h["title"])}</b> · {esc(h["group_name"])}\n{due}\nСдали {len(rec) - len(miss)} из {len(rec)}'
                + (f'\nНе сдали: {names(miss)}' if miss else ''))
        say(chat, text, remind_kb(h['id']) if miss else None)


def cmd_student(chat, u, q):
    q = q.strip()
    if not q:
        return say(chat, 'Напишите имя: <code>/student Аня</code>')
    rows = db().execute('SELECT DISTINCT s.id, s.name FROM group_members m JOIN study_groups g ON g.id = m.group_id JOIN users s ON s.id = m.user_id '
                        'WHERE g.teacher_id = ? AND ulower(s.name) LIKE ? ORDER BY s.name COLLATE NOCASE LIMIT 5',
                        (u['id'], '%' + q.lower().replace('%', '').replace('_', '') + '%')).fetchall()
    if not rows:
        return say(chat, f'В ваших группах нет ученика «{esc(q)}».')
    out = []
    for s in rows:
        data, updated = A.load_progress(s['id'])
        st = A.summary(data, updated)
        hws = [h for h in A.assigned_homework(s['id']) if h['teacher_id'] == u['id']]
        done = {r['hw_id'] for r in db().execute('SELECT hw_id FROM homework_done WHERE user_id = ?', (s['id'],))}
        last = 'ещё не заходил' if not updated else 'сегодня' if updated > time.time() - 86400 else f'{int((time.time() - updated) // 86400)} дн. назад'
        out.append(f'👤 <b>{esc(s["name"])}</b>\nЗаданий сдано: {sum(h["id"] in done for h in hws)} из {len(hws)}\n'
                   f'Решено задач: {st["solved"]}, точность: {"—" if st["accuracy"] is None else str(st["accuracy"]) + "%"}\n'
                   f'Серия: {st["streak"]} дн. · последний раз: {last}')
    say(chat, '\n\n'.join(out))


def settings_kb(prefs):
    return {'inline_keyboard': [[{'text': ('✅ ' if prefs[k] else '▫️ ') + n, 'callback_data': f'p:{k}'}] for k, n in PREF_NAMES.items()]}


def cmd_settings(chat, u, edit=None):
    say(chat, '<b>Уведомления</b>\nНажмите, чтобы включить или выключить.', settings_kb(A.tg_prefs(u)), edit)


def cmd_student_hw(chat, u):
    done = {r['hw_id'] for r in db().execute('SELECT hw_id FROM homework_done WHERE user_id = ?', (u['id'],))}
    todo = [h for h in A.assigned_homework(u['id']) if h['id'] not in done]
    if not todo:
        return say(chat, 'Все задания выполнены 🎉')
    say(chat, '<b>Осталось сделать</b>\n' + '\n'.join(
        f'• {esc(h["title"])} · {esc(h["group_name"])} — {"до " + fmt_due(h["due"]) if h["due"] else "без срока"}' for h in todo)
        + (f'\n\nОткрыть: {esc(A.ORIGIN)}/#hw' if A.ORIGIN else ''))


def on_message(m):
    chat = m['chat']['id']
    if m['chat'].get('type') != 'private':
        return
    text = (m.get('text') or '').strip()
    mm = re.match(r'^/(\w+)(?:@\w+)?(?:\s+(.*))?$', text, re.S)
    cmd, arg = (mm.group(1).lower(), (mm.group(2) or '').strip()) if mm else ('', '')
    if cmd == 'start':
        return cmd_start(chat, arg, (m.get('from') or {}).get('username'))
    u = linked(chat)
    if not u:
        return say(chat, link_hint())
    if cmd == 'stop':
        db().execute('DELETE FROM tg_links WHERE chat_id = ?', (chat,))
        return say(chat, 'Бот отключён. Подключить снова можно в кабинете на сайте.')
    if u['role'] == 'student':
        return cmd_student_hw(chat, u) if cmd == 'hw' else say(chat, HELP_STUDENT)
    if not A.plan_of(u)['active']:
        return say(chat, 'Telegram-бот для преподавателей входит в тариф Про. Тариф можно продлить у администратора платформы.')
    handlers = {'groups': lambda: cmd_groups(chat, u), 'hw': lambda: cmd_hw(chat, u), 'student': lambda: cmd_student(chat, u, arg),
                'settings': lambda: cmd_settings(chat, u)}
    return handlers[cmd]() if cmd in handlers else say(chat, HELP_TEACHER)


def on_callback(c):
    msg = c.get('message') or {}
    chat = (msg.get('chat') or {}).get('id')
    answer = lambda text: tg('answerCallbackQuery', callback_query_id=c['id'], text=text)
    u = linked(chat) if chat else None
    if not u or u['role'] == 'student' or not A.plan_of(u)['active']:
        return answer('Недоступно')
    kind, _, val = (c.get('data') or '').partition(':')
    if kind == 'p' and val in A.TG_PREFS:
        prefs = A.tg_prefs(u)
        prefs[val] = not prefs[val]
        db().execute('UPDATE tg_links SET prefs = ? WHERE chat_id = ?', (json.dumps(prefs), chat))
        cmd_settings(chat, linked(chat), edit=msg.get('message_id'))
        return answer('Сохранено')
    if kind == 'r' and val.isdigit():
        h = own_hw(u, int(val))
        if not h:
            return answer('Задание не найдено')
        return answer(remind(u, h))
    answer('')


def remind(u, h):
    """Напоминание ученикам, которые не сдали задание и подключили бота. Возвращает текст для всплывашки."""
    now = int(time.time())
    key = f'remind:{h["id"]}'
    last = db().execute('SELECT ts FROM tg_sent WHERE key = ?', (key,)).fetchone()
    if last and last['ts'] > now - REMIND_GAP:
        return 'Уже напоминали за последние 6 часов'
    rec, done = hw_status(h)
    miss = [i for i, _ in rec if i not in done]
    if not miss:
        return 'Все уже сдали'
    chats = db().execute(f'SELECT chat_id FROM tg_links WHERE user_id IN ({",".join("?" * len(miss))})', miss).fetchall()
    due = f'Срок: {fmt_due(h["due"])}.' if h['due'] else ''
    for r in chats:
        A.tg_queue(r['chat_id'], f'🔔 Напоминание от преподавателя {esc(u["name"])}: задание «{esc(h["title"])}» · {esc(h["group_name"])}. {due}'
                   + (f'\nОткрыть: {esc(A.ORIGIN)}/#hw-{h["id"]}' if A.ORIGIN else ''))
    db().execute('INSERT INTO tg_sent VALUES (?,?) ON CONFLICT(key) DO UPDATE SET ts = excluded.ts', (key, now))
    off = len(miss) - len(chats)
    return f'Напомнили: {len(chats)}' + (f'. Без Telegram: {off}' if off else '')


# ---------------------------------------------------------------- фоновые задачи
def flush():
    """Отправляет очередь. Чат недоступен (бота заблокировали) — привязку удаляем."""
    for r in db().execute('SELECT * FROM tg_outbox ORDER BY id LIMIT 25').fetchall():
        try:
            say(r['chat_id'], r['text'], json.loads(r['markup']) if r['markup'] else None)
        except TgError as e:
            if e.code in (400, 403):
                db().execute('DELETE FROM tg_links WHERE chat_id = ?', (r['chat_id'],))
            elif e.code == 429:
                return                       # Telegram просит подождать — дошлём на следующем круге
            elif r['tries'] < 4:
                db().execute('UPDATE tg_outbox SET tries = tries + 1 WHERE id = ?', (r['id'],))
                continue
        except OSError:
            return                           # нет сети — попробуем позже, сообщения остаются в очереди
        db().execute('DELETE FROM tg_outbox WHERE id = ?', (r['id'],))


def due_summaries(now=None):
    """Срок задания прошёл — один раз присылаем преподавателю, кто сдал. Старше двух суток не трогаем (после простоя)."""
    now = int(now or time.time())
    for h in db().execute('SELECT h.*, g.name AS group_name, g.teacher_id FROM homework h JOIN study_groups g ON g.id = h.group_id '
                          'WHERE h.due BETWEEN ? AND ?', (now - 2 * 86400, now)).fetchall():
        if not db().execute('INSERT OR IGNORE INTO tg_sent VALUES (?,?)', (f'due:{h["id"]}', now)).rowcount:
            continue
        rec, done = hw_status(h)
        if not rec:
            continue
        miss = [n for i, n in rec if i not in done]
        A.tg_teacher(h['teacher_id'], 'due', f'⏰ Прошёл срок задания «{esc(h["title"])}» · {esc(h["group_name"])}\n'
                     f'Сдали {len(rec) - len(miss)} из {len(rec)}' + (f'\nНе сдали: {names(miss)}' if miss else ' — все 🎉'),
                     remind_kb(h['id']) if miss else None)


def digests(now=None):
    """Вечерняя сводка за день — после DIGEST_HOUR по Москве, раз в день, только если было что-то новое."""
    now = int(now or time.time())
    if time.gmtime(now + A.METRIC_TZ).tm_hour < DIGEST_HOUR:
        return
    day = A.metric_day(now)
    start = calendar.timegm(time.strptime(day, '%Y-%m-%d')) - A.METRIC_TZ
    for t in db().execute("SELECT u.*, l.prefs, l.chat_id FROM tg_links l JOIN users u ON u.id = l.user_id "
                          "WHERE l.digest_day != ? AND u.role IN ('teacher', 'admin')", (day,)).fetchall():
        db().execute('UPDATE tg_links SET digest_day = ? WHERE user_id = ?', (day, t['id']))
        if not A.tg_prefs(t)['digest'] or not A.plan_of(t)['active']:
            continue
        done = db().execute('SELECT u.name, h.title, g.name AS grp FROM homework_done d JOIN homework h ON h.id = d.hw_id '
                            'JOIN study_groups g ON g.id = h.group_id JOIN users u ON u.id = d.user_id '
                            'WHERE g.teacher_id = ? AND d.done_at >= ? ORDER BY d.done_at', (t['id'], start)).fetchall()
        joined = db().execute('SELECT u.name, g.name AS grp FROM group_members m JOIN study_groups g ON g.id = m.group_id '
                              'JOIN users u ON u.id = m.user_id WHERE g.teacher_id = ? AND m.joined >= ?', (t['id'], start)).fetchall()
        soon = db().execute('SELECT h.*, g.name AS group_name FROM homework h JOIN study_groups g ON g.id = h.group_id '
                            'WHERE g.teacher_id = ? AND h.due BETWEEN ? AND ? ORDER BY h.due', (t['id'], now, now + 86400)).fetchall()
        if not (done or joined or soon):
            continue
        parts = ['🌙 <b>Сводка за день</b>']
        if done:
            parts.append(f'Выполнено заданий: {len(done)}\n' + '\n'.join(f'• {esc(r["name"])} — «{esc(r["title"])}» · {esc(r["grp"])}' for r in done[:15])
                         + (f'\n… и ещё {len(done) - 15}' if len(done) > 15 else ''))
        if joined:
            parts.append('Новые ученики: ' + names(f'{r["name"]} ({r["grp"]})' for r in joined))
        for h in soon:
            rec, ok = hw_status(h)
            parts.append(f'⏳ Завтра срок «{esc(h["title"])}» · {esc(h["group_name"])}: сдали {len(ok & {i for i, _ in rec})} из {len(rec)}')
        A.tg_queue(t['chat_id'], '\n\n'.join(parts))


def jobs():
    last = 0.0
    while True:
        try:
            flush()
            if time.time() - last >= PERIOD:
                last = time.time()
                due_summaries()
                digests()
                db().execute('DELETE FROM tg_tokens WHERE expires < ?', (int(last),))
                db().execute('DELETE FROM tg_sent WHERE ts < ?', (int(last) - 30 * 86400,))
        except Exception:
            log.exception('бот: фоновая задача')
        time.sleep(TICK)


def main():
    if not TOKEN:
        log.info('STACKLY_TG_TOKEN не задан — Telegram-бот выключен')
        return
    A.migrate()
    try:
        tg('setMyCommands', commands=[{'command': 'hw', 'description': 'Задания и кто сдал'}, {'command': 'groups', 'description': 'Группы и коды'},
                                      {'command': 'student', 'description': 'Статистика ученика'}, {'command': 'settings', 'description': 'Уведомления'},
                                      {'command': 'stop', 'description': 'Отключить бота'}])
    except (TgError, OSError) as e:
        log.warning('бот: не удалось задать команды: %s', e)
    threading.Thread(target=jobs, daemon=True).start()
    log.info('Telegram-бот stackly запущен')
    offset = 0
    while True:
        try:
            updates = tg('getUpdates', offset=offset, timeout=POLL, allowed_updates=['message', 'callback_query'])
        except (TgError, OSError) as e:
            log.warning('бот: getUpdates: %s', e)
            time.sleep(5)
            continue
        for up in updates:
            offset = up['update_id'] + 1
            try:
                if 'message' in up:
                    on_message(up['message'])
                elif 'callback_query' in up:
                    on_callback(up['callback_query'])
            except Exception:
                log.exception('бот: обработка %s', up.get('update_id'))


if __name__ == '__main__':
    main()
