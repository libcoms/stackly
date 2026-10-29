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
// сам рендерер
const must = [[String.raw`\frac{1}{2}`, 'class="fr"'], [String.raw`30^\circ`, '30°'], [String.raw`\sqrt[3]{8}`, 'class="ri"'], [String.raw`\log_{2} 8`, '<sub>2</sub>']];
for (const [f, part] of must) if (!T.parse(f).includes(part)) { fails++; console.log(`FAIL рендер ${f}`); }
try { T.parse(String.raw`\unknown`); fails++; console.log('FAIL неизвестная команда не дала ошибку'); } catch (e) { }
console.log(`задач ${bank.length}, формул ${formulas}, ошибок ${fails}`);
process.exit(fails ? 1 : 0);
