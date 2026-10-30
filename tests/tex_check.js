// Формулы банка математики (public/tex.js) без браузера: node tests/tex_check.js
// Каждая формула $…$ в условии, чертеже и решении встроенных задач по математике должна разбираться без ошибок.
'use strict';
const fs = require('fs');
const path = require('path');
const T = require(path.join(__dirname, '..', 'public', 'tex.js'));

const src = fs.readFileSync(path.join(__dirname, '..', 'content', 'ege.js'), 'utf8');
const m = /^window\.BANK = (\[.*\]);\r?$/m.exec(src);
const bank = JSON.parse(m[1]).filter(p => p.subject === 'Математика');
let fails = 0, formulas = 0;
for (const p of bank) {
  for (const key of ['text', 'extra', 'sol']) {
    const s = String(p[key] || '').replace(/<!--spec:.*?-->/, '');
    for (const f of s.matchAll(/\$([^$]+)\$/g)) {
      formulas++;
      try { T.parse(f[1]); } catch (e) { fails++; if (fails < 20) console.log(`FAIL ${p.id} ${key}: ${e.message}`); }
    }
    if ((s.match(/\$/g) || []).length % 2) { fails++; console.log(`FAIL ${p.id} ${key}: непарный $`); }
  }
}
// разборы методички по математике (window.MATH_EGE): все строки, кроме названий, проходят через texify
const vm = require('vm');
const ctx = { window: {} };
vm.runInNewContext(src, ctx);
const guide = ctx.window.MATH_EGE || [];
if (guide.length < 20) { fails++; console.log(`FAIL разборов математики ${guide.length}, ожидалось 20`); }
const walk = (v, where) => {
  if (typeof v === 'string') {
    if (/[\f\v\b]/.test(v)) { fails++; console.log(`FAIL ${where}: управляющий символ — TeX в обычных кавычках?`); }
    if ((v.match(/\$/g) || []).length % 2) { fails++; console.log(`FAIL ${where}: непарный $`); }
    for (const f of v.matchAll(/\$([^$]+)\$/g)) { formulas++; try { T.parse(f[1]); } catch (e) { fails++; console.log(`FAIL ${where}: ${e.message}`); } }
  } else if (Array.isArray(v)) v.forEach((x, i) => walk(x, `${where}[${i}]`));
  else if (v && typeof v === 'object') for (const k in v) walk(v[k], `${where}.${k}`);
};
guide.forEach(t => walk(t, `разбор ${t.n}`));
// сам рендерер
const must = [[String.raw`\frac{1}{2}`, 'class="fr"'], [String.raw`30^\circ`, '30°'], [String.raw`\sqrt[3]{8}`, 'class="ri"'], [String.raw`\log_{2} 8`, '<sub>2</sub>']];
for (const [f, part] of must) if (!T.parse(f).includes(part)) { fails++; console.log(`FAIL рендер ${f}`); }
try { T.parse(String.raw`\unknown`); fails++; console.log('FAIL неизвестная команда не дала ошибку'); } catch (e) { }
console.log(`задач ${bank.length}, формул ${formulas}, ошибок ${fails}`);
process.exit(fails ? 1 : 0);
