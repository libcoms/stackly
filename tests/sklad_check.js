// Проверка игры «Склад» (public/sklad.js) без браузера: node tests/sklad_check.js
// Решение каждого уровня проходит его при любых коробках, стартовый код — нет, ошибки объясняются по-русски.
'use strict';
const path = require('path');
const assert = require('assert');
const S = require(path.join(__dirname, '..', 'public', 'sklad.js'));

let fails = 0;
function check(name, fn) {
  try { fn(); console.log('ok   ' + name); }
  catch (e) { fails++; console.log('FAIL ' + name + '\n     ' + e.message); }
}
const L = id => S.LEVELS.find(l => l.id === id);
const run = (id, code, seed = 7) => S.simulate(L(id), code, { seed });
const why = r => r.misses.join(' ') || r.error || r.state;

check('уровни: id с 101, номера подряд, уровень открывается после предыдущего', () => {
  S.ORDER.forEach((id, i) => { const l = L(id); assert.ok(id >= 101 && id <= 200); assert.strictEqual(l.num, i + 1); assert.strictEqual(l.need, i ? S.ORDER[i - 1] : 0); });
});
for (const id of S.ORDER) {
  const lv = L(id);
  check(`уровень ${lv.num} «${lv.title}»: решение проходит при любых коробках, стартовый код — нет`, () => {
    for (const seed of [1, 2, 3, 4, 5, 6, 7, 8]) {
      const r = run(id, lv.solution, seed);
      assert.strictEqual(r.state, 'win', `seed ${seed}: ${why(r)}`);
      if (lv.par) assert.ok(r.t <= lv.par && lv.par <= lv.limit, `ходов ${r.t}, норма ${lv.par}`);
    }
    assert.notStrictEqual(run(id, lv.start).state, 'win', 'стартовый код уже проходит уровень');
  });
}
check('ошибки робота объясняются', () => {
  assert.match(run(101, 'put()').error, /робот ничего не держит/);
  assert.match(run(101, 'take()\ntake()').error, /уже держит коробку/);
  assert.match(run(101, 'take()\nmove(East)\nput()').error, /пустой пол/);
  assert.match(run(101, 'move(North)').out.map(o => o.s).join(''), /упёрся в стену/);
  assert.match(why(run(101, 'take()')), /держит коробку «\d+» — поставьте её/);
  assert.match(run(101, 'box_color()').error, /откроется на уровне 5/);
});
check('проверки цели говорят, что не так', () => {
  const colorsSwapped = L(105).solution.replace('== Colors.Red', '== Colors.Blue');
  assert.match(why(run(105, colorsSwapped)), /стоит на стеллаже x = \d, а должна — на стеллаже x = \d/);
  assert.match(why(run(107, L(107).solution.replace('print(total)', 'print(0)'))), /общий вес партии/);
  assert.match(why(run(109, L(109).solution.replace('order.index(box_number()) + 1', '6 - order.index(box_number())'))), /Не по порядку/);
});

if (fails) { console.log(`\n${fails} проверок не прошло`); process.exit(1); }
console.log('\nвсе проверки склада прошли');
