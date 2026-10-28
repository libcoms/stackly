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
  const g = ip.run(F.parse(code), ip.top);
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
  assert.match(F.simulate(L(1), 'move(East)').error, /откроется на уровне 3/);
});
for (const lv of F.LEVELS) {
  if (!lv.solution) continue;
  check(`уровень ${lv.id} «${lv.title}»: решение проходит, стартовый код — нет`, () => {
    const r = F.simulate(lv, lv.solution);
    assert.strictEqual(r.state, 'win', `решение: ${r.state} ${r.error || ''} ${JSON.stringify(r.items)}`);
    assert.ok(r.t <= lv.par, `решение за ${r.t} ходов, норма ${lv.par}`);
    assert.ok(lv.par <= lv.limit);
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

if (fails) { console.log(`\n${fails} проверок не прошло`); process.exit(1); }
console.log('\nвсе проверки фермы прошли');
