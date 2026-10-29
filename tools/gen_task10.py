#!/usr/bin/env python3
"""Генератор задач ЕГЭ №10 (IP-адреса и маски, формат 2027 года) для банка stackly.

    python3 tools/gen_task10.py > /tmp/task10.json      # 50 задач: 26 базовых, 16 средних, 8 сложных

Как в демоверсии 2027: по адресу узла и маске найти адрес сети (наибольший адрес узла, широковещательный адрес)
и записать в ответе сумму числовых значений его октетов; а также число адресов, байт маски по адресу сети,
адреса с условием на двоичную запись, число возможных масок. Решение на Python (модуль ipaddress) запускается
и должно вывести ответ. Описание задачи хранится комментарием <!--spec:…--> — тест tests/test_bank_task10.py
проверяет ответы своей реализацией на битовых операциях. Генерация детерминирована (seed).
"""
import json, os, random, subprocess, sys
from ipaddress import ip_address, ip_network

SEED = 20271010
DEF = ('В терминологии сетей TCP/IP маской сети называют двоичное число, которое показывает, какая часть IP-адреса '
       'узла сети относится к адресу сети, а какая — к адресу узла в этой сети. Адрес сети получается в результате '
       'применения поразрядной конъюнкции к заданному адресу узла и его маске. ')
BCAST = ('Широковещательным адресом называется специализированный адрес, в котором на месте нулей в маске стоят '
         'единицы. Адрес сети и широковещательный адрес не могут быть использованы для адресации сетевых устройств. ')
SUMNOTE = 'В ответе укажите сумму числовых значений октетов найденного IP-адреса.'
PLAN = ([('Б', 'net')] * 8 + [('Б', 'top')] * 6 + [('Б', 'bcast')] * 5 + [('Б', 'hosts')] * 7
        + [('П', 'mask_byte')] * 5 + [('П', 'mask_sum_max')] * 4 + [('П', 'ones')] * 7
        + [('В', 'ones_halves')] * 4 + [('В', 'masks_count')] * 4)
BYTE = {1: 'первого', 2: 'второго', 3: 'третьего', 4: 'четвёртого'}
NUMW = {3: 'трём', 4: 'четырём', 5: 'пяти', 6: 'шести', 7: 'семи'}


def mask_of(p):
    return str(ip_network(f'0.0.0.0/{p}').netmask)


def rand_ip(rng):
    return f'{rng.randint(11, 223)}.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}'


def osum(a):
    return sum(map(int, str(a).split('.')))


def make(rng, fam):
    ip = rand_ip(rng)
    if fam in ('net', 'top', 'bcast', 'hosts'):
        p = rng.randint(17, 29) if fam != 'hosts' else rng.randint(18, 30)
        net = ip_network(f'{ip}/{p}', strict=False)
        sp = {'fam': fam, 'ip': ip, 'p': p}
        ans = {'net': osum(net.network_address), 'top': osum(net.broadcast_address - 1),
               'bcast': osum(net.broadcast_address), 'hosts': net.num_addresses - 2}[fam]
        return sp, ans
    if fam in ('mask_byte', 'mask_sum_max', 'masks_count'):
        # адрес сети задан, маска — нет; для «чему равен байт» подходящая маска должна быть одна
        while True:
            ip = rand_ip(rng)
            p = rng.randint(17, 28) if fam != 'mask_byte' else rng.randint(17, 23)
            net = ip_network(f'{ip}/{p}', strict=False)
            ok = [q for q in range(33) if ip_network(f'{ip}/{q}', strict=False).network_address == net.network_address]
            if fam == 'mask_byte' and len(ok) == 1:
                return {'fam': fam, 'ip': ip, 'net': str(net.network_address), 'byte': 3}, int(mask_of(ok[0]).split('.')[2])
            if fam == 'mask_sum_max' and len(ok) >= 2:
                return {'fam': fam, 'ip': ip, 'net': str(net.network_address)}, osum(mask_of(min(ok)))
            if fam == 'masks_count' and len(ok) >= 2:
                return {'fam': fam, 'ip': ip, 'net': str(net.network_address)}, len(ok)
    if fam == 'ones':
        p = rng.randint(20, 26)
        k = rng.choice([3, 4, 5, 6, 7])
        mode = rng.choice(['mod0', 'notmod0', 'mod0'])
        net = ip_network(f'{ip}/{p}', strict=False)
        sp = {'fam': fam, 'net': str(net.network_address), 'p': p, 'k': k, 'mode': mode}
        hit = [a for a in net if (f'{int(a):032b}'.count('1') % k == 0) == (mode == 'mod0')]
        return sp, len(hit)
    if fam == 'ones_halves':
        p = rng.randint(20, 25)
        net = ip_network(f'{ip}/{p}', strict=False)
        cmp_ = rng.choice(['gt', 'lt', 'eq'])
        sp = {'fam': fam, 'net': str(net.network_address), 'p': p, 'cmp': cmp_}
        def ok(a):
            b = f'{int(a):032b}'
            l, r = b[:16].count('1'), b[16:].count('1')
            return {'gt': l > r, 'lt': l < r, 'eq': l == r}[cmp_]
        hit = [a for a in net.hosts() if ok(a)]
        return sp, len(hit)
    raise ValueError(fam)


def build(sp):
    f = sp['fam']
    if f in ('net', 'top', 'bcast', 'hosts'):
        m = mask_of(sp['p'])
        if f == 'net':
            text = DEF + f'Даны адрес узла <b>{sp["ip"]}</b> и маска <b>{m}</b>. Найдите адрес сети. ' + SUMNOTE
            ttl = f'Адрес сети: {sp["ip"]}/{sp["p"]}'
            body = 'print(sum(map(int, str(net.network_address).split("."))))'
        elif f == 'top':
            text = (DEF + BCAST + f'Сеть задана IP-адресом одного из входящих в неё узлов <b>{sp["ip"]}</b> и сетевой маской '
                    f'<b>{m}</b>. Найдите наибольший в данной сети IP-адрес, который может быть назначен компьютеру. ' + SUMNOTE)
            ttl = f'Наибольший адрес узла: {sp["ip"]}/{sp["p"]}'
            body = 'print(sum(map(int, str(net.broadcast_address - 1).split("."))))'
        elif f == 'bcast':
            text = (DEF + BCAST + f'Даны адрес узла <b>{sp["ip"]}</b> и маска <b>{m}</b>. Найдите широковещательный адрес '
                    'этой сети. ' + SUMNOTE)
            ttl = f'Широковещательный адрес: {sp["ip"]}/{sp["p"]}'
            body = 'print(sum(map(int, str(net.broadcast_address).split("."))))'
        else:
            text = (DEF + BCAST + f'Сеть задана IP-адресом одного из входящих в неё узлов <b>{sp["ip"]}</b> и маской '
                    f'<b>{m}</b>. Сколько в этой сети IP-адресов, которые можно назначить компьютерам? В ответе укажите только число.')
            ttl = f'Адреса для узлов: {sp["ip"]}/{sp["p"]}'
            body = 'print(net.num_addresses - 2)'
        code = f"from ipaddress import ip_network\n\nnet = ip_network('{sp['ip']}/{m}', strict=False)\n{body}"
        note = {'net': 'Адрес сети = адрес AND маска: октеты, где в маске 255, переписываются, где 0 — обнуляются, '
                       'в «неполном» октете берётся поразрядная конъюнкция.',
                'top': 'Наибольший адрес узла — широковещательный адрес минус один: все «узловые» биты единицы, кроме последнего.',
                'bcast': 'Широковещательный адрес: в «узловой» части (где в маске нули) все биты равны единице.',
                'hosts': f'Нулей в маске 32 − {sp["p"]} = {32 - sp["p"]}, адресов 2^{32 - sp["p"]}, без адреса сети и широковещательного — на два меньше.'}[f]
        return text, code, note, ttl
    if f in ('mask_byte', 'mask_sum_max', 'masks_count'):
        head = DEF + f'Для узла с IP-адресом <b>{sp["ip"]}</b> адрес сети равен <b>{sp["net"]}</b>. '
        search = (f"from ipaddress import ip_network\n\nok = [p for p in range(33)\n      "
                  f"if str(ip_network('{sp['ip']}/' + str(p), strict=False).network_address) == '{sp['net']}']\n")
        if f == 'mask_byte':
            text = head + f'Чему равен {BYTE[sp["byte"]]} слева байт маски? Ответ запишите в виде десятичного числа.'
            code = search + "print(str(ip_network('0.0.0.0/' + str(ok[0])).netmask).split('.')[2])"
            ttl = f'Байт маски: {sp["ip"]} → {sp["net"]}'
            note = 'Сравни третьи байты адреса узла и адреса сети в двоичной записи: маска должна сохранить совпадающее начало и обнулить остальное.'
        elif f == 'mask_sum_max':
            text = (head + 'Известно, что количество адресов в этой сети наибольшее из возможных. Найдите маску сети '
                    'и запишите в ответе сумму числовых значений её октетов.')
            code = search + "print(sum(map(int, str(ip_network('0.0.0.0/' + str(min(ok))).netmask).split('.'))))"
            ttl = f'Самая короткая маска: {sp["ip"]} → {sp["net"]}'
            note = 'Адресов больше всего у сети с самой короткой маской (наименьшим числом единиц), при которой адрес сети ещё получается тем же.'
        else:
            text = head + 'Сколько различных значений может принимать маска этой сети? В ответе укажите только число.'
            code = search + 'print(len(ok))'
            ttl = f'Число возможных масок: {sp["ip"]} → {sp["net"]}'
            note = 'Подходит каждая длина маски, при которой конъюнкция даёт тот же адрес сети: от наименьшей допустимой до той, где обнуляются все «лишние» единицы адреса узла.'
        return text, code, note, ttl
    m = mask_of(sp['p'])
    if f == 'ones':
        cond = 'кратно' if sp['mode'] == 'mod0' else 'не кратно'
        text = (DEF + f'Сеть задана IP-адресом <b>{sp["net"]}</b> и маской сети <b>{m}</b>. Сколько в этой сети IP-адресов, '
                f'для которых количество единиц в двоичной записи IP-адреса {cond} {sp["k"]}? В ответе укажите только число.')
        op = '==' if sp['mode'] == 'mod0' else '!='
        code = (f"from ipaddress import ip_network\n\nnet = ip_network('{sp['net']}/{m}')\n"
                f"print(sum(1 for a in net if f'{{int(a):032b}}'.count('1') % {sp['k']} {op} 0))")
        ttl = f'Единицы {cond} {sp["k"]}: {sp["net"]}/{sp["p"]}'
        note = 'Перебери все адреса сети: в ней 2^(32 − длина маски) адресов, для каждого посчитай единицы в 32-битной записи.'
        return text, code, note, ttl
    rel = {'gt': 'больше, чем', 'lt': 'меньше, чем', 'eq': 'столько же, сколько'}[sp['cmp']]
    text = (DEF + BCAST + f'Сеть задана IP-адресом <b>{sp["net"]}</b> и маской сети <b>{m}</b>. Сколько в этой сети '
            f'IP-адресов, которые можно назначить компьютерам, у которых в двоичной записи двух левых байтов единиц {rel} '
            'в двоичной записи двух правых байтов? В ответе укажите только число.')
    op = {'gt': '>', 'lt': '<', 'eq': '=='}[sp['cmp']]
    code = (f"from ipaddress import ip_network\n\nnet = ip_network('{sp['net']}/{m}')\ncnt = 0\nfor a in net.hosts():          "
            f"# без адреса сети и широковещательного\n    b = f'{{int(a):032b}}'\n    if b[:16].count('1') {op} b[16:].count('1'):\n"
            f"        cnt += 1\nprint(cnt)")
    ttl = f'Левые и правые байты ({op}): {sp["net"]}/{sp["p"]}'
    note = 'net.hosts() перебирает только адреса, которые можно назначить узлам. Левые 16 бит — b[:16], правые — b[16:].'
    return text, code, note, ttl


def main():
    rng = random.Random(SEED)
    out, titles = [], set()
    for k, (level, fam) in enumerate(PLAN, 1):
        while True:
            sp, ans = make(rng, fam)
            text, code, note, ttl = build(sp)
            if ttl not in titles:
                titles.add(ttl)
                break
        meta = json.dumps(sp, ensure_ascii=False, separators=(',', ':'))
        out.append({'id': f'10-g{k:03d}', 'task': 10, 'level': level, 'title': ttl, 'text': text,
                    'extra': f'<!--spec:{meta}-->', 'code': code, 'answer': str(ans), 'data': '', 'dname': '', 'note': note})
    for p in out:
        r = subprocess.run([sys.executable, '-c', p['code']], capture_output=True, text=True, timeout=120,
                           encoding='utf-8', env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        if r.stdout.strip() != p['answer']:
            raise SystemExit(f"{p['id']}: решение даёт «{r.stdout.strip()}», ответ «{p['answer']}»\n{r.stderr}\n{p['code']}")
    stat = {}
    for p in out:
        stat[p['level']] = stat.get(p['level'], 0) + 1
    print(json.dumps(stat, ensure_ascii=False), file=sys.stderr)
    sys.stdout.reconfigure(encoding='utf-8')
    json.dump(out, sys.stdout, ensure_ascii=False)


if __name__ == '__main__':
    main()
