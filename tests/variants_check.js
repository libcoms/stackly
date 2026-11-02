// Variant navigation must use the saved order, survive direct URLs and never fall back to the full bank.
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
const src = fs.readFileSync(path.join(__dirname, '..', 'public', 'index.html'), 'utf8');
const between = (a,b) => src.slice(src.indexOf(a),src.indexOf(b,src.indexOf(a)));
const bank = [{id:'1-first',task:1,title:'First'},{id:'1-other',task:1,title:'Outside variant'}, {id:'2-second',task:2,title:'Second'}];
const variant = {id:7,title:'Пробник <май>',bank:['1-first','2-second'],created:1800000000};
const ctx = {BANK:bank, EGE:[], mathBy:{}, I:{chevL:'',chev:'',arrow:''}, pnum:{}, solved:new Set(),
  esc:s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
  psubj:p=>'Информатика', psnum:()=>0, gameSet:()=>null, probHTML:p=>'<article>'+p.title+'</article>',
  inGroup:(p,g)=>p.task===g.task,bankGroupHref:p=>'#bank-'+p.task,
  dotsHTML:()=>'', markHTML:()=>'', ptag:()=>'', plural:(n,a,b,c)=>c,
  fmtAgo:()=> 'сегодня'};
vm.createContext(ctx);
vm.runInContext(between('  const rowHTML =','  const segHTML =') + between('  function pageTask(', '  function pageSet(') + between('  const variantGroups =','  function variantCounts('),ctx);
const html = vm.runInContext(`variantsHTML([${JSON.stringify(variant)}], 'teach-variant-7')`,ctx);
assert(html.includes('#teach-variant-7/p-1-first'),'Opening a variant task loses its context');
const first = vm.runInContext(`variantsHTML([${JSON.stringify(variant)}], 'teach-variant-7/p-1-first')`,ctx);
assert(first.includes('#teach-variant-7/p-2-second'),'Next must be second task in variant, not another task 1 from bank');
assert(!first.includes('#p-1-other'),'Task outside variant must not enter navigation');
assert(first.includes('href="#teach-variant-7"'),'Back link must return to variant');
const second = vm.runInContext(`variantsHTML([${JSON.stringify(variant)}], 'teach-variant-7/p-2-second')`,ctx);
assert(second.includes('#teach-variant-7/p-1-first'),'Previous must stay in variant');
assert(second.includes('К варианту'),'Last task must return to variant');
const missing = vm.runInContext(`variantsHTML([${JSON.stringify(variant)}], 'teach-variant-7/p-1-other')`,ctx);
assert(!missing.includes('<article>'),'A task not in variant must not render as part of it');
const ordinary = vm.runInContext(`pageTask(BANK[0])`,ctx);
assert(ordinary.includes('#p-1-other'),'Normal bank navigation must still work');
console.log('Variant entry, next/previous, direct routes, back, membership and normal bank navigation: OK');
