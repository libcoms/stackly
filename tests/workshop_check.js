// Проверка игры «Мастерская переменных» (public/workshop.js) без браузера: node tests/workshop_check.js
// Решение каждого уровня проходит его при любых данных, стартовый код — нет; память и события шагов видны сцене.
'use strict';
const path = require('path');
const assert = require('assert');
const W = require(path.join(__dirname, '..', 'public', 'workshop.js'));
const Farm = require(path.join(__dirname, '..', 'public', 'farm.js'));

let fails = 0;
function check(name, fn) {
  try { fn(); console.log('ok   ' + name); }
  catch (e) { fails++; console.log('FAIL ' + name + '\n     ' + e.message); }
}
const L = id => W.LEVELS.find(l => l.id === id);
const run = (id, code, seed = 7) => W.simulate(L(id), code, { seed });
const why = r => r.misses.join(' ') || r.error || r.state;
const SEEDS = Array.from({ length: 20 }, (_, i) => i + 1);
// все события программы — как их получает сцена
function events(id, code, seed = 7) {
  const r = new Farm.Run(L(id), code, { game: W.CORE, seed }), evs = [];
  while (r.state === 'run') { const ev = r.step(); if (ev && !ev.idle) evs.push({ ...ev, mem: r.world.mem.map(c => c.name + '=' + c.s), frame: r.world.frame && r.world.frame.mem.map(c => c.name + '=' + c.s) }); }
  return { r, evs };
}

check('уровни: id с 201, номера подряд, уровень открывается после предыдущего', () => {
  W.ORDER.forEach((id, i) => { const l = L(id); assert.ok(id >= 201 && id <= 300); assert.strictEqual(l.num, i + 1); assert.strictEqual(l.need, i ? W.ORDER[i - 1] : 0); });
  assert.strictEqual(W.LEVELS.length, W.ORDER.length);
});
for (const id of W.ORDER) {
  const lv = L(id);
  check(`уровень ${lv.num} «${lv.title}»: решение проходит при любых данных, стартовый код — нет`, () => {
    for (const seed of SEEDS) {
      const r = run(id, lv.solution, seed);
      assert.strictEqual(r.state, 'win', `seed ${seed}: ${why(r)}`);
    }
    assert.ok(SEEDS.some(seed => run(id, lv.start, seed).state !== 'win'), 'стартовый код уже проходит уровень');
    assert.ok(lv.text && lv.learn.length === 3 && lv.hint && lv.task && lv.api.length, 'у уровня есть текст, справка, подсказка и цель');
  });
}
check('ящики: x = 5, потом x = x + 1 — один ящик, значение меняется', () => {
  const { evs } = events(201, 'x = 5\nx = x + 1\n');
  assert.deepStrictEqual(evs.map(e => e.a), ['set', 'set']);
  assert.deepStrictEqual(evs.map(e => e.mem.join()), ['x=5', 'x=6']);
  assert.deepStrictEqual(evs[1].g, ['x']);
});
check('типы жетонов: число, дробь, строка, True, список', () => {
  const t = v => W.cell('v', v).t;
  const { r } = events(201, 'a = 3\nb = 7 / 2\nc = "кот"\nd = 3 > 2\ne = [1, 2]\n');
  assert.deepStrictEqual(r.world.mem.map(c => c.t), ['int', 'float', 'str', 'bool', 'list']);
  assert.deepStrictEqual(r.world.mem.map(c => c.s), ['3', '3.5', "'кот'", 'True', '[1, 2]']);
  assert.deepStrictEqual(r.world.mem[4].items, ['1', '2']);
  assert.strictEqual(t(null), 'none');
});
check('условие и цикл: лампа и счётчик кругов', () => {
  const { r, evs } = events(214, 'k = 0\nwhile k < 3:\n    k = k + 1\nif k == 3:\n    print("да")\n');
  const tests = evs.filter(e => e.a === 'test');
  assert.deepStrictEqual(tests.map(e => e.ok), [true, true, true, false, true]);
  assert.strictEqual(tests[0].src, 'k < 3');
  assert.strictEqual(tests[4].src, 'k == 3');
  assert.deepStrictEqual(r.world.screen, ['да']);
  assert.ok(evs.some(e => e.a === 'print' && e.out));
  const f = events(214, 'for i in range(3):\n    pass\n').evs;
  assert.deepStrictEqual(f.map(e => e.a + e.n), ['loop1', 'loop2', 'loop3']);
});
check('функция: стол с локальными ящиками появляется на вызов и исчезает после return', () => {
  const { r, evs } = events(225, L(225).solution);
  const call = evs.find(e => e.a === 'call');
  assert.strictEqual(call.fn, 'price');
  assert.deepStrictEqual(call.frame.map(s => s.split('=')[0]), ['count', 'cost']);
  const ret = evs.find(e => e.a === 'ret');
  assert.deepStrictEqual(ret.frame, null);
  assert.ok(evs.some(e => e.frame && e.frame.some(s => s.startsWith('total='))));
  assert.ok(!r.world.mem.some(c => c.name === 'total'), 'локальный total не попал на общую полку');
  assert.strictEqual(r.world.frame, null);
});
check('проверки цели говорят, что не так', () => {
  assert.match(why(run(201, '')), /Ящика «x» на полке нет/);
  assert.match(why(run(201, 'x = 6')), /должно лежать число 5, а лежит число 6/);
  assert.match(why(run(207, 'n = text * 2')), /лежит строка .* превратите строку в число с помощью int\(\)/);
  assert.match(why(run(208, 'each = candies / kids\nrest = candies % kids')), /дробное число .*\/\//);
  assert.match(why(run(212, 'biggest = max(a, b)\nif a: pass')), /без max\(\)/);
  assert.match(why(run(209, 'print("Сумма:", a + b)')), /На экране должно быть/);
  assert.match(run(218, L(218).start).state, /limit/);
  assert.match(why(run(224, L(224).start)), /TypeError/);
});
check('данные уровня одинаковые на сцене и в программе', () => {
  const lv = L(203), w = W.CORE.world(lv, 42), r = run(203, 'total = a + b', 42);
  assert.strictEqual(r.state, 'win');
  assert.deepStrictEqual(w.mem.map(c => c.name), ['a', 'b']);
});

if (fails) { console.log(`\n${fails} проверок не прошло`); process.exit(1); }
console.log('\nвсе проверки мастерской прошли');
