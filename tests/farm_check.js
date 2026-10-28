// Проверка игры «Ферма» (public/farm.js) без браузера: node tests/farm_check.js
// Интерпретатор считает как Python, решение каждого уровня проходит его в норму ходов, стартовый код — нет,
// а обходные решения без приёма, которому учит уровень, не укладываются в лимит.
'use strict';
const path = require('path');
const assert = require('assert');
const F = require(path.join(__dirname, '..', 'public', 'farm.js'));

let fails = 0;
function check(name, fn) {
  try { fn(); console.log('ok   ' + name); }
  catch (e) { fails++; console.log('FAIL ' + name + '\n     ' + e.message); }
}
function py(code) {
  const out = [], ip = new F.Interp({ print: s => out.push(s), idleOps: 200000 });
  const g = ip.exec(F.parse(code));
  try { while (!g.next().done); } catch (e) { if (e instanceof F.PyError && e.line == null) e.line = ip.line; throw e; }   // как Run.fail
  return out.join('');
}
function pyErr(code) {
  try { py(code); } catch (e) { if (e instanceof F.PyError) return e.type + ':' + e.line; throw e; }
  return 'нет ошибки';
}
const L = id => F.LEVELS.find(l => l.id === id);

check('арифметика как в Python', () => {
  assert.strictEqual(py('print(7 // 2, -7 // 2, 7 % 3, -7 % 3, 7 / 2, 4 / 2, 2 ** 10, 2 ** -1)'), '3 -4 1 2 3.5 2.0 1024 0.5\n');
  assert.strictEqual(py('print(round(2.5), round(3.5), int("12"), int(3.9), 0.1 + 0.2, 1 == 1.0, True + 1)'), '2 4 12 3 0.30000000000000004 True 2\n');
});
check('строки, списки, словари, кортежи', () => {
  assert.strictEqual(py('a = [3, 1, 2]\na.sort()\nprint(a, a[-1], a[1:], a[::-1], len(a), sum(a))'), '[1, 2, 3] 3 [2, 3] [3, 2, 1] 3 6\n');
  assert.strictEqual(py('d = {"x": 1}\nd["y"] = 2\nprint(d, d.get("z", 0), "x" in d, list(d.keys()))'), "{'x': 1, 'y': 2} 0 True ['x', 'y']\n");
  assert.strictEqual(py('print((1,), (1, 2), None, "ab" * 3, str(5) + "a", "a,b".split(","), "-".join(["x", "y"]))'), "(1,) (1, 2) None ababab 5a ['a', 'b'] x-y\n");
  assert.strictEqual(py('print([i * i for i in range(5) if i % 2 == 0], list(range(10, 0, -3)), sorted([3, 1, 2], reverse=True))'), '[0, 4, 16] [10, 7, 4, 1] [3, 2, 1]\n');
  assert.strictEqual(py('print(max([[1, "a"], [3, "b"], [2, "c"]]), min(3, 1, 2), max(["a", "abc", "ab"], key=len))'), "[3, 'b'] 1 abc\n");
});
check('функции, global, распаковка, f-строки', () => {
  assert.strictEqual(py('def f(x, y=10):\n    return x + y\nprint(f(1), f(1, y=2))'), '11 3\n');
  assert.strictEqual(py('n = 0\ndef inc():\n    global n\n    n += 1\ninc()\ninc()\nprint(n)'), '2\n');
  assert.strictEqual(py('x, y = 1, 2\nx, y = y, x\nprint(x, y, f"{x}+{y}={x + y}", f"{1/3:.2f}")'), '2 1 2+1=3 0.33\n');
  assert.strictEqual(py('def fact(n):\n    if n <= 1:\n        return 1\n    return n * fact(n - 1)\nprint(fact(10))'), '3628800\n');
  assert.strictEqual(py('i = 0\nwhile True:\n    i += 1\n    if i == 3:\n        continue\n    if i > 5:\n        break\nprint(i, 3 < 4 < 5, "a" if i > 1 else "b")'), '6 True a\n');
});
check('ошибки с номером строки', () => {
  const cases = {
    'x = 1\ny = x + "a"': 'TypeError:2', 'harvst()': 'NameError:1', 'if x = 1:\n    pass': 'SyntaxError:1',
    'while True\n    pass': 'SyntaxError:1', 'for i in range(3):\nprint(i)': 'IndentationError:2',
    'def f():\n    n += 1\nn = 0\nf()': 'UnboundLocalError:2', 'a = [1]\nprint(a[5])': 'IndexError:2', 'print(1/0)': 'ZeroDivisionError:1',
    '  x = 1': 'IndentationError:1', 'print("abc)': 'SyntaxError:1', 'x = (1, 2': 'SyntaxError:1', 'break': 'SyntaxError:1',
    'def f():\n    return f()\nf()': 'RecursionError:2', 'while True:\n    pass': 'TimeoutError:2', 'x = 5\nx()': 'TypeError:2',
  };
  for (const [code, want] of Object.entries(cases)) assert.strictEqual(pyErr(code), want, JSON.stringify(code));
  assert.match(F.simulate(L(1), 'harvst()').error, /имелось в виду «harvest»/);
  assert.match(F.simulate(L(1), 'move(East)').error, /откроется на уровне 2/);
});
check('длинные числа, побитовые операции, форматы, множества, словари — как в Python', () => {
  // ожидаемый вывод получен запуском того же кода в CPython 3.14
  assert.strictEqual(py('print(2 ** 100, 3 ** 50 - 1, -(2 ** 70) // 3, (2 ** 70) % 7, 10 ** 20 // 10 ** 18)'), '1267650600228229401496703205376 717897987691852588770248 -393530540239137101142 2 100\n');
  assert.strictEqual(py("x = 4 ** 2020 + 2 ** 2017 - 15\ns = ''\nwhile x > 0:\n    s = str(x % 2) + s\n    x //= 2\nprint(s.count('1'), len(s))"), '2015 4041\n');
  assert.strictEqual(py("print(bin(37), bin(37)[2:], int('100101', 2), hex(255), int('ff', 16), f'{37:b}', f'{5:08b}', f'{255:x}', f'{3.14159:.2f}', format(10, 'b'))"), '0b100101 100101 37 0xff 255 100101 00000101 ff 3.14 1010\n');
  assert.strictEqual(py('print(5 & 3, 5 | 3, 5 ^ 3, ~5, 1 << 10, 1024 >> 3)'), '1 7 6 -6 1024 128\n');
  assert.strictEqual(py("st = {1, 2, 3} | {3, 4}\nst.add(9)\nprint(len(st), 4 in st, {x % 3 for x in range(10)}, set('hello') == set('lehol'))"), '5 True {0, 1, 2} True\n');
  assert.strictEqual(py("d = {c: 0 for c in 'abc'}\nd['a'] += 2\nprint(d, sorted(d.items(), key=lambda kv: -kv[1])[0])"), "{'a': 2, 'b': 0, 'c': 0} ('a', 2)\n");
  assert.strictEqual(py("print(list(map(int, '1 2 3'.split())), sum(map(int, str(9875))), list(filter(lambda v: v % 2, range(7))))"), '[1, 2, 3] 29 [1, 3, 5]\n');
  assert.strictEqual(py("s = '1' * 50\nwhile '11' in s:\n    s = s.replace('11', '2', 1)\nprint(s)"), '2222222222222222222222222\n');
  assert.strictEqual(py("print(*[1, 2, 3], sep='-')"), '1-2-3\n');
});
check('import, itertools, lru_cache, глубокая рекурсия', () => {
  assert.strictEqual(py("from itertools import product, permutations, combinations\nprint(len(list(product('АБВ', repeat=3))), len(list(permutations('abcd'))), len(list(combinations(range(5), 2))))"), '27 24 10\n');
  assert.strictEqual(py("from functools import lru_cache\n@lru_cache(None)\ndef F(n):\n    if n <= 1:\n        return n\n    return F(n - 1) + F(n - 2)\nprint(F(200))"), '280571172992510140037611932413038677189525\n');
  assert.strictEqual(py('import sys\nsys.setrecursionlimit(5000)\ndef G(n):\n    if n < 3:\n        return 1\n    return G(n - 1) + n\nprint(G(3000))'), '4501498\n');
  assert.strictEqual(pyErr('def G(n):\n    return G(n - 1)\nG(5)'), 'RecursionError:2');           // без setrecursionlimit — 1000, как в Python
  assert.strictEqual(pyErr('import numpy'), 'ImportError:1');
  assert.strictEqual(py("import math\nprint(math.isqrt(10 ** 20 + 5), math.sqrt(16), math.gcd(12, 18), math.ceil(2.1), math.floor(-2.1))"), '10000000000 4.0 6 3 -3\n');
});
check('главы: каждый уровень ровно в одной, номера идут подряд, уровень открывается после предыдущего', () => {
  assert.deepStrictEqual([...F.ORDER].sort((a, b) => a - b), F.LEVELS.map(l => l.id).sort((a, b) => a - b));
  F.ORDER.forEach((id, i) => { const l = L(id); assert.strictEqual(l.num, i + 1); if (!l.sandbox) assert.strictEqual(l.need, i ? F.ORDER[i - 1] : 0); });
});
check('первые шаги: типичные ошибки новичка объясняются, а не просто «не пройдено»', () => {
  const miss = (id, code) => { const r = F.simulate(L(id), code); assert.notStrictEqual(r.state, 'win', code); return r.misses.join(' ') || r.error || r.state; };
  assert.match(miss(36, "print('Привет, ферма!')\nprint(56)"), /Пусть умножает Python/);
  assert.match(miss(36, "print('Привет ферма')\nprint(7 * 8)"), /В журнале должно быть: «Привет, ферма!», «56»\. А программа вывела: «Привет ферма», «56»/);
  assert.match(miss(37, 'print(12)\nprint(24)'), /bags = 12/);
  assert.match(miss(38, 'harvest()\nmove(East)\nharvest()\nmove(East)\nharvest()\nprint(3)'), /count = count \+ 1/);
  assert.match(miss(39, L(35).solution + 'move(East)\nharvest()\nmove(East)\nharvest()\n'), /цикл(ом)? for/);
  assert.match(miss(40, L(40).start), /А программа вывела: «0», «1», «2», «3», «4»/);
  assert.strictEqual(F.simulate(L(41), L(41).start).state, 'limit');                      // while True не кончается
  assert.match(miss(41, "while num_items(Items.Hay) <= 7:\n    harvest()\nprint('Готово')"), /ровно 7, а собрано 8/);
  assert.match(miss(42, 'for i in range(6):\n    if can_harvest():\n        harvest()\n    move(East)'), /должно быть «куст», а там «пусто»/);
  assert.match(miss(43, 'for i in range(8):\n    plant(Entities.Tree)\n    move(East)'), /x = 3 должно быть «куст», а там «дерево»/);
});
check('карта уровней в index.html (ссылки из учебника) совпадает с farm.js', () => {
  const html = require('fs').readFileSync(path.join(__dirname, '..', 'public', 'index.html'), 'utf8');
  const m = /const FARM_LV = (\[.*\]);/.exec(html);
  assert.ok(m, 'в index.html нет FARM_LV');
  const got = JSON.parse(m[1].replace(/'/g, '"'));
  const want = F.ORDER.map(id => L(id)).map(l => [l.id, l.num, l.title, l.py]);
  assert.deepStrictEqual(got, want, 'обновите FARM_LV в index.html по LEVELS из farm.js');
});
for (const lv of F.LEVELS) {
  if (!lv.solution) continue;
  check(`уровень ${lv.num} «${lv.title}»: решение проходит, стартовый код — нет`, () => {
    const r = F.simulate(lv, lv.solution);
    assert.strictEqual(r.state, 'win', `решение: ${r.state} ${r.error || ''} ${JSON.stringify(r.items)}`);
    if (lv.par) assert.ok(r.t <= lv.par && lv.par <= lv.limit, `решение за ${r.t} ходов, норма ${lv.par}`);
    const s = F.simulate(lv, lv.start);
    assert.notStrictEqual(s.state, 'win', 'стартовый код уже проходит уровень');
  });
}
check('шахматный лес: без чередования деревьев и кустов не уложиться', () => {
  const sol = L(8).solution, branch = /if \(x \+ y\) % 2 == 0:\n\s+plant\(Entities\.Tree\)\n\s+else:\n\s+plant\(Entities\.Bush\)/;
  for (const only of ['Tree', 'Bush']) assert.notStrictEqual(F.simulate(L(8), sol.replace(branch, `plant(Entities.${only})`)).state, 'win', only);
});
check('подсолнухи: без сортировки не уложиться', () => {
  const naive = L(11).start + '    for i in range(n):\n        for j in range(n):\n            while not can_harvest():\n                pass\n            harvest()\n            move(North)\n        move(East)\n';
  assert.strictEqual(F.simulate(L(11), naive).state, 'limit');
});
check('тыквы: без уборки сгнивших не уложиться', () => {
  assert.notStrictEqual(F.simulate(L(10), L(10).start).state, 'win');
});

check('подсказки: команды уровня, наборы, свои имена, методы; не в строке и не в комментарии', () => {
  const names = (code, avail = {}) => { const r = F.complete(code, code.length, avail); return r ? r.items.map(i => i.name) : []; };
  const lv5 = { api: L(5).api };
  assert.deepStrictEqual(names('har', lv5), ['harvest']);
  assert.deepStrictEqual(names('pl', lv5), []);                                   // plant() на уровне 5 ещё закрыта
  assert.ok(names('mo', lv5).includes('move'));
  assert.strictEqual(names('move(N', lv5)[0], 'North');                         // направления — раньше слов Python
  assert.ok(names('plant(Entities.', { api: L(10).api }).includes('Pumpkin'));
  assert.ok(!names('plant(Entities.', { api: ['plant'], plants: ['Grass', 'Bush'] }).includes('Pumpkin'));
  assert.ok(names('def goto(x, y):\n    pass\ngo', lv5).includes('goto'));
  assert.ok(names('cells = []\ncel', lv5).includes('cells'));
  assert.deepStrictEqual(names('a = [1]\na.app', lv5), ['append']);
  assert.deepStrictEqual(names('# har', lv5), []);
  assert.deepStrictEqual(names('print("har', lv5), []);
  assert.deepStrictEqual(names('def har', lv5), []);
  const ins = it => F.insertion(it).text;
  const pick = (code, n, avail = lv5) => F.complete(code, code.length, avail).items.find(i => i.name === n);
  assert.strictEqual(ins(pick('har', 'harvest')), 'harvest()');
  assert.deepStrictEqual(F.insertion(pick('mo', 'move')), { text: 'move()', back: 1 });
  assert.strictEqual(ins(pick('whi', 'while')), 'while ');
  assert.strictEqual(F.signature('move(', 5, lv5)[0], 'move(направление)');
  assert.strictEqual(F.signature('print(len(a), ', 14, lv5)[0], 'print(значение, …)');
  assert.strictEqual(F.signature('def go(x, y):\n    pass\ngo(1, ', 26, lv5)[0], 'go(x, y)');
  assert.strictEqual(F.signature('harvest()', 9, lv5), null);
});
check('своя ферма: улучшения покупаются за урожай и открывают команды, растения и поле', () => {
  let save = { t: 0, items: {}, up: {} };
  const sb = F.sandbox(save);
  assert.strictEqual(sb.w, 3);
  assert.ok(!sb.api.includes('plant'));
  assert.strictEqual(F.buy(save, 'plant'), null);                                  // нечем платить
  const r = F.simulate({ ...sb, limit: 400 }, L(12).start);
  assert.ok(r.items.Hay >= 20, 'стартовая программа приносит сено');
  save = { ...save, items: r.items };
  assert.strictEqual(F.buy(save, 'trees'), null);                                  // сначала «Посадка»
  save = F.buy(save, 'plant');
  assert.ok(save && save.up.plant === 1 && save.items.Hay === r.items.Hay - 20);
  assert.ok(F.sandbox(save).api.includes('plant'));
  assert.match(F.simulate({ ...F.sandbox(save), limit: 10 }, 'plant(Entities.Tree)').error, /LockedError.*«Деревья»/);
  assert.match(F.simulate({ ...F.sandbox(save), limit: 10 }, 'till()').error, /после улучшения «Вспашка»/);
  save.items.Hay = 1000; save.items.Wood = 1000;
  save = F.buy(F.buy(save, 'size'), 'size');
  assert.strictEqual(F.sandbox(save).w, 5);
  save = F.buy(save, 'grow');
  assert.ok(F.sandbox(save).grow.Bush < 6);
  assert.strictEqual(F.upState(save, F.UPGRADES.find(u => u.id === 'sun')).st, 'locked');
  // все улучшения в итоге покупаются, у каждого «нужно» — существующее улучшение
  const ids = new Set(F.UPGRADES.map(u => u.id));
  F.UPGRADES.forEach(u => (u.need || []).forEach(n => assert.ok(ids.has(n), u.id + ' → ' + n)));
  let rich = { t: 0, items: { Hay: 1e6, Wood: 1e6, Carrot: 1e6, Pumpkin: 1e6, Power: 1e6 }, up: {} };
  for (let i = 0; i < 40; i++) for (const u of F.UPGRADES) rich = F.buy(rich, u.id) || rich;
  F.UPGRADES.forEach(u => assert.strictEqual(F.upState(rich, u).st, 'done', u.id));
  const full = F.sandbox(rich);
  assert.strictEqual(full.w, F.SIZES[F.SIZES.length - 1]);
  assert.strictEqual(F.simulate({ ...full, limit: 3000 }, L(11).solution).error, undefined);   // все команды открыты
});

if (fails) { console.log(`\n${fails} проверок не прошло`); process.exit(1); }
console.log('\nвсе проверки фермы прошли');
