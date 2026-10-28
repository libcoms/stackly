/* stackly · Ферма: дрон на грядках слушается программы на Python.
   Свой интерпретатор подмножества Python (eval и внешние скрипты сайту запрещает CSP), поле с растениями,
   уровни от первой команды до списков и сортировки, экран игры. В браузере — window.StacklyFarm,
   в node — module.exports (проверка уровней в tests/farm_check.js). */
(function (root) {
  'use strict';

  /* ═════════════ ИНТЕРПРЕТАТОР ═════════════ */
  class PyError extends Error { constructor(type, msg, line) { super(msg); this.type = type; this.line = line; } }
  const E = (type, msg, line) => new PyError(type, msg, line);

  // значения: int — число JS, float — F, str — строка, list — массив, tuple — Tup, dict — Dict, None — null
  class F { constructor(v) { this.v = v; } }
  class Tup { constructor(a) { this.a = a; } }
  class Range { constructor(a, b, s) { this.a = a; this.b = b; this.s = s; } get n() { return Math.max(0, Math.ceil((this.b - this.a) / this.s)); } }
  class Const { constructor(group, name, ru) { this.group = group; this.name = name; this.ru = ru; } }
  class NS { constructor(name, attrs) { this.name = name; this.attrs = attrs; } }
  class Fn { constructor(def, closure) { this.def = def; this.closure = closure; } }
  class Bi { constructor(name, fn, gen) { this.name = name; this.fn = fn; this.gen = !!gen; } }
  class Dict {
    constructor() { this.m = new Map(); }
    get(k) { const e = this.m.get(hkey(k)); return e && e[1]; }
    has(k) { return this.m.has(hkey(k)); }
    set(k, v) { this.m.set(hkey(k), [k, v]); }
    del(k) { this.m.delete(hkey(k)); }
    keys() { return [...this.m.values()].map(e => e[0]); }
  }
  class PySet {
    constructor(xs) { this.m = new Map(); if (xs) for (const x of xs) this.add(x); }
    add(x) { this.m.set(hkey(x), x); }
    has(x) { return this.m.has(hkey(x)); }
    del(x) { return this.m.delete(hkey(x)); }
    vals() { return [...this.m.values()]; }
  }
  // файл из данных уровня: open('17.txt')
  class PyFile {
    constructor(name, text) { this.name = name; this.lines = text.split(/(?<=\n)/); this.pos = 0; this.closed = false; }
    rest() { const r = this.lines.slice(this.pos); this.pos = this.lines.length; return r; }
  }
  class Ret { constructor(v) { this.v = v; } }
  const BREAK = { brk: 1 }, CONT = { cont: 1 }, IDLE = { idle: 1 };

  const isBool = x => typeof x === 'boolean';
  const isInt = x => typeof x === 'number' || typeof x === 'bigint' || isBool(x);
  const isNum = x => isInt(x) || x instanceof F;
  const nv = x => x instanceof F ? x.v : typeof x === 'bigint' ? Number(x) : +x;
  // целые: число JS, пока точно; больше 2^53 — BigInt (как длинная арифметика Python)
  const big = x => typeof x === 'bigint' ? x : BigInt(+x);
  const norm = b => (b >= -9007199254740991n && b <= 9007199254740991n) ? Number(b) : b;
  function tn(x) {
    if (x === null || x === undefined) return 'NoneType';
    if (isBool(x)) return 'bool';
    if (typeof x === 'number' || typeof x === 'bigint') return 'int';
    if (x instanceof PySet) return 'set';
    if (x instanceof PyFile) return 'file';
    if (x instanceof F) return 'float';
    if (typeof x === 'string') return 'str';
    if (Array.isArray(x)) return 'list';
    if (x instanceof Tup) return 'tuple';
    if (x instanceof Dict) return 'dict';
    if (x instanceof Range) return 'range';
    if (x instanceof Fn || x instanceof Bi) return 'function';
    if (x instanceof Const) return x.group;
    return 'object';
  }
  function hkey(k) {
    if (isNum(k)) return 'n' + (typeof k === 'bigint' ? k.toString() : nv(k));
    if (typeof k === 'string') return 's' + k;
    if (k === null) return 'N';
    if (k instanceof Tup) return 't(' + k.a.map(hkey).join(',') + ')';
    if (k instanceof Const) return 'c' + k.group + '.' + k.name;
    throw E('TypeError', `значение типа ${tn(k)} нельзя сделать ключом словаря`);
  }
  function fmtFloat(v) {
    if (!isFinite(v)) return isNaN(v) ? 'nan' : v > 0 ? 'inf' : '-inf';
    if (Number.isInteger(v) && Math.abs(v) < 1e16) return v.toFixed(1);
    return String(v).replace(/e([+-])(\d)$/, 'e$10$2');
  }
  function reprStr(s) {
    const q = s.includes("'") && !s.includes('"') ? '"' : "'";
    return q + s.replace(/\\/g, '\\\\').replace(/\n/g, '\\n').replace(/\t/g, '\\t').replace(new RegExp(q, 'g'), '\\' + q) + q;
  }
  function repr(x) {
    if (typeof x === 'string') return reprStr(x);
    if (Array.isArray(x)) return '[' + x.map(repr).join(', ') + ']';
    if (x instanceof Tup) return '(' + x.a.map(repr).join(', ') + (x.a.length === 1 ? ',)' : ')');
    if (x instanceof Dict) return '{' + [...x.m.values()].map(([k, v]) => repr(k) + ': ' + repr(v)).join(', ') + '}';
    if (x instanceof PySet) return x.m.size ? '{' + x.vals().map(repr).join(', ') + '}' : 'set()';
    return pystr(x);
  }
  function pystr(x) {
    if (x === null || x === undefined) return 'None';
    if (isBool(x)) return x ? 'True' : 'False';
    if (typeof x === 'number' || typeof x === 'bigint') return String(x);
    if (x instanceof PyFile) return `<file '${x.name}'>`;
    if (x instanceof F) return fmtFloat(x.v);
    if (typeof x === 'string') return x;
    if (x instanceof Range) return `range(${x.a}, ${x.b}${x.s !== 1 ? ', ' + x.s : ''})`;
    if (x instanceof Fn) return `<function ${x.def.name}>`;
    if (x instanceof Bi) return `<built-in function ${x.name}>`;
    if (x instanceof Const) return x.group + '.' + x.name;
    if (x instanceof NS) return x.name;
    return repr(x);
  }
  function truthy(x) {
    if (x === null || x === undefined) return false;
    if (isBool(x)) return x;
    if (typeof x === 'number') return x !== 0;
    if (typeof x === 'bigint') return x !== 0n;
    if (x instanceof PySet) return x.m.size > 0;
    if (x instanceof F) return x.v !== 0;
    if (typeof x === 'string' || Array.isArray(x)) return x.length > 0;
    if (x instanceof Tup) return x.a.length > 0;
    if (x instanceof Dict) return x.m.size > 0;
    if (x instanceof Range) return x.n > 0;
    return true;
  }
  function eq(a, b) {
    if (isNum(a) && isNum(b)) return a instanceof F || b instanceof F ? nv(a) === nv(b) : typeof a === 'bigint' || typeof b === 'bigint' ? big(a) === big(b) : +a === +b;
    if (a instanceof PySet && b instanceof PySet) return a.m.size === b.m.size && [...a.m.keys()].every(k => b.m.has(k));
    if (Array.isArray(a) && Array.isArray(b) || a instanceof Tup && b instanceof Tup) {
      const x = a.a || a, y = b.a || b;
      return x.length === y.length && x.every((v, i) => eq(v, y[i]));
    }
    if (a instanceof Dict && b instanceof Dict) return a.m.size === b.m.size && [...a.m].every(([k, [, v]]) => b.m.has(k) && eq(v, b.m.get(k)[1]));
    if (a instanceof Range && b instanceof Range) return a.a === b.a && a.b === b.b && a.s === b.s;
    return a === b || (a == null && b == null);
  }
  const OPN = { '<': '<', '>': '>', '<=': '<=', '>=': '>=' };
  function order(a, b, op) {
    // -1, 0, 1; бросает TypeError, если сравнивать нельзя
    if (isNum(a) && isNum(b)) {
      if (!(a instanceof F || b instanceof F) && (typeof a === 'bigint' || typeof b === 'bigint')) { const x = big(a), y = big(b); return x < y ? -1 : x > y ? 1 : 0; }
      const x = nv(a), y = nv(b); return x < y ? -1 : x > y ? 1 : 0;
    }
    if (typeof a === 'string' && typeof b === 'string') return a < b ? -1 : a > b ? 1 : 0;
    if (Array.isArray(a) && Array.isArray(b) || a instanceof Tup && b instanceof Tup) {
      const x = a.a || a, y = b.a || b;
      for (let i = 0; i < Math.min(x.length, y.length); i++) { if (!eq(x[i], y[i])) return order(x[i], y[i], op); }
      return x.length - y.length < 0 ? -1 : x.length > y.length ? 1 : 0;
    }
    throw E('TypeError', `«${OPN[op] || '<'}» нельзя применить к значениям типов ${tn(a)} и ${tn(b)}`);
  }
  function contains(c, x) {
    if (typeof c === 'string') { if (typeof x !== 'string') throw E('TypeError', `проверять «in» у строки можно только для строки, а не ${tn(x)}`); return c.includes(x); }
    if (Array.isArray(c)) return c.some(v => eq(v, x));
    if (c instanceof Tup) return c.a.some(v => eq(v, x));
    if (c instanceof Dict) return c.has(x);
    if (c instanceof PySet) return c.has(x);
    if (c instanceof Range) { if (!isInt(x)) return false; const v = +x; return c.s > 0 ? v >= c.a && v < c.b && (v - c.a) % c.s === 0 : v <= c.a && v > c.b && (c.a - v) % -c.s === 0; }
    throw E('TypeError', `у значения типа ${tn(c)} нельзя проверить «in»`);
  }
  function arith(op, a, b) {
    const fl = a instanceof F || b instanceof F;
    if (!fl && ['&', '|', '^', '<<', '>>'].includes(op)) {
      const x = big(a), y = big(b);
      if ((op === '<<' || op === '>>') && y < 0n) throw E('ValueError', 'сдвиг на отрицательное число битов');
      return norm(op === '&' ? x & y : op === '|' ? x | y : op === '^' ? x ^ y : op === '<<' ? x << y : x >> y);
    }
    if (['&', '|', '^', '<<', '>>'].includes(op)) throw E('TypeError', `операция «${op}» работает только с целыми числами`);
    const x = nv(a), y = nv(b);
    if (op === '/') { if (y === 0) throw E('ZeroDivisionError', 'деление на ноль'); return new F(x / y); }
    if ((op === '//' || op === '%') && y === 0) throw E('ZeroDivisionError', op === '//' ? 'целочисленное деление на ноль' : 'остаток от деления на ноль');
    if (fl) {
      switch (op) {
        case '+': return new F(x + y); case '-': return new F(x - y); case '*': return new F(x * y);
        case '//': return new F(Math.floor(x / y)); case '%': return new F(x - y * Math.floor(x / y)); case '**': return new F(Math.pow(x, y));
      }
    }
    // целые: сначала обычными числами, при переполнении — BigInt
    if (typeof a !== 'bigint' && typeof b !== 'bigint') {
      let r;
      switch (op) {
        case '+': r = x + y; break; case '-': r = x - y; break; case '*': r = x * y; break;
        case '//': r = Math.floor(x / y); break; case '%': r = x - y * Math.floor(x / y); break;
        case '**': if (y < 0) return new F(Math.pow(x, y)); r = Math.pow(x, y); break;
      }
      if (Number.isSafeInteger(r) && (op !== '//' || Math.abs(x) < 4503599627370496)) return r;
    }
    const A = big(a), B = big(b);
    switch (op) {
      case '+': return norm(A + B); case '-': return norm(A - B); case '*': return norm(A * B);
      case '//': { let q = A / B; if (A % B !== 0n && (A < 0n) !== (B < 0n)) q -= 1n; return norm(q); }
      case '%': { let m = A % B; if (m !== 0n && (m < 0n) !== (B < 0n)) m += B; return norm(m); }
      case '**': if (B < 0n) return new F(Math.pow(x, y)); if (B > 100000n) throw E('OverflowError', 'слишком большая степень'); return norm(A ** B);
    }
  }
  function binop(op, a, b) {
    if (isNum(a) && isNum(b)) return arith(op, a, b);
    if (a instanceof PySet && b instanceof PySet && ['|', '&', '-', '^'].includes(op)) {
      const r = new PySet();
      if (op === '|') { a.vals().forEach(x => r.add(x)); b.vals().forEach(x => r.add(x)); }
      if (op === '&') a.vals().forEach(x => { if (b.has(x)) r.add(x); });
      if (op === '-') a.vals().forEach(x => { if (!b.has(x)) r.add(x); });
      if (op === '^') { a.vals().forEach(x => { if (!b.has(x)) r.add(x); }); b.vals().forEach(x => { if (!a.has(x)) r.add(x); }); }
      return r;
    }
    if (op === '+') {
      if (typeof a === 'string' && typeof b === 'string') return a + b;
      if (Array.isArray(a) && Array.isArray(b)) return a.concat(b);
      if (a instanceof Tup && b instanceof Tup) return new Tup(a.a.concat(b.a));
      if (typeof a === 'string' || typeof b === 'string') throw E('TypeError', `нельзя сложить ${tn(a)} и ${tn(b)}. Чтобы склеить текст с числом, превратите число в строку: str(x)`);
    }
    if (op === '*') {
      const rep = (s, n) => { if (!isInt(n)) return null; n = Math.max(0, +n); if (typeof s === 'string') return s.repeat(n); if (Array.isArray(s)) { let o = []; for (let i = 0; i < n; i++) o = o.concat(s); return o; } return null; };
      const r = rep(a, b) ?? rep(b, a);
      if (r !== null) return r;
    }
    const NAMES = { '+': 'сложить', '-': 'вычесть', '*': 'умножить', '/': 'разделить', '//': 'разделить', '%': 'взять остаток от', '**': 'возвести в степень' };
    throw E('TypeError', NAMES[op] ? `нельзя ${NAMES[op]} значения типов ${tn(a)} и ${tn(b)} (операция «${op}»)` : `операция «${op}» не работает со значениями типов ${tn(a)} и ${tn(b)}`);
  }
  function index(len, i) {
    if (!isInt(i)) throw E('TypeError', `индекс должен быть целым числом, а не ${tn(i)}`);
    let k = +i; if (k < 0) k += len;
    if (k < 0 || k >= len) throw E('IndexError', `индекс ${+i} за пределами: элементов всего ${len}`);
    return k;
  }
  function getitem(o, k) {
    if (Array.isArray(o)) return o[index(o.length, k)];
    if (o instanceof Tup) return o.a[index(o.a.length, k)];
    if (typeof o === 'string') return o[index(o.length, k)];
    if (o instanceof Range) { const i = index(o.n, k); return o.a + i * o.s; }
    if (o instanceof Dict) { if (!o.has(k)) throw E('KeyError', `ключа ${repr(k)} нет в словаре`); return o.get(k); }
    throw E('TypeError', `у значения типа ${tn(o)} нет элементов по индексу [ ]`);
  }
  function setitem(o, k, v) {
    if (Array.isArray(o)) { o[index(o.length, k)] = v; return; }
    if (o instanceof Dict) { o.set(k, v); return; }
    if (typeof o === 'string') throw E('TypeError', 'строку нельзя менять по индексу: соберите новую строку');
    if (o instanceof Tup) throw E('TypeError', 'кортеж нельзя менять: используйте список [ ]');
    throw E('TypeError', `у значения типа ${tn(o)} нет элементов по индексу [ ]`);
  }
  function slice(o, lo, hi, st) {
    const seq = Array.isArray(o) ? o : o instanceof Tup ? o.a : typeof o === 'string' ? o : null;
    if (!seq) throw E('TypeError', `срез [a:b] нельзя взять у значения типа ${tn(o)}`);
    for (const v of [lo, hi, st]) if (v !== null && !isInt(v)) throw E('TypeError', 'границы среза должны быть целыми числами');
    const n = seq.length, s = st === null ? 1 : +st;
    if (s === 0) throw E('ValueError', 'шаг среза не может быть нулём');
    const fix = (v, d, neg) => { if (v === null) return d; v = +v; if (v < 0) v += n; return neg ? Math.min(Math.max(v, -1), n - 1) : Math.min(Math.max(v, 0), n); };
    const a = fix(lo, s > 0 ? 0 : n - 1, s < 0), b = fix(hi, s > 0 ? n : -1, s < 0);
    const out = [];
    for (let i = a; s > 0 ? i < b : i > b; i += s) out.push(seq[i]);
    return typeof o === 'string' ? out.join('') : o instanceof Tup ? new Tup(out) : out;
  }
  function* rangeIter(r) { for (let i = r.a; r.s > 0 ? i < r.b : i > r.b; i += r.s) yield i; }
  function iter(v) {
    if (Array.isArray(v)) return v;
    if (v instanceof Tup) return v.a;
    if (typeof v === 'string') return [...v];
    if (v instanceof Range) return rangeIter(v);
    if (v instanceof Dict) return v.keys();
    if (v instanceof PySet) return v.vals();
    if (v instanceof PyFile) return v.rest();
    throw E('TypeError', `значение типа ${tn(v)} нельзя перебрать в цикле for`);
  }
  const reEsc = s => s.replace(/[\\\]^-]/g, '\\$&');
  function lev(a, b) {
    const d = Array.from({ length: a.length + 1 }, (_, i) => [i]);
    for (let j = 1; j <= b.length; j++) d[0][j] = j;
    for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++)
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1].toLowerCase() === b[j - 1].toLowerCase() ? 0 : 1));
    return d[a.length][b.length];
  }
  function suggest(name, names) {
    let best = null, bd = 3;
    for (const n of names) { if (n.startsWith('_')) continue; const d = lev(name, n); if (d < bd && d < Math.max(2, n.length / 2)) { bd = d; best = n; } }
    return best ? `. Может быть, имелось в виду «${best}»?` : '';
  }

  /* ── токены ── */
  const OPS2 = ['**=', '//=', '<<=', '>>=', '**', '//', '<<', '>>', '==', '!=', '<=', '>=', '+=', '-=', '*=', '/=', '%=', '|=', '&=', '^=', '->'];
  const OPS1 = '+-*/%<>=()[]{}:,.;|&^~@';
  const AUG = /^(\+|-|\*|\/|\/\/|%|\*\*|\||&|\^|<<|>>)=$/;
  function tokenize(src, base = 0) {
    src = src.replace(/\r\n?/g, '\n').replace(/\t/g, '    ');
    const out = [], ind = [0];
    let p = 0, line = 1, depth = 0, bol = true;
    const push = (t, v, ln = line) => out.push({ t, v, line: ln + base });
    const fail = (msg, ln = line) => E('SyntaxError', msg, ln + base);
    function readString(pre) {
      const q = src[p], triple = src.substr(p, 3) === q + q + q, startLine = line;
      p += triple ? 3 : 1;
      let s = '';
      for (;;) {
        if (p >= src.length) throw fail('строка не закрыта кавычкой', startLine);
        const ch = src[p];
        if (triple ? src.substr(p, 3) === q + q + q : ch === q) { p += triple ? 3 : 1; break; }
        if (ch === '\n') { if (!triple) throw fail(`строка не закрыта: в конце не хватает кавычки ${q}`, startLine); line++; }
        if (ch === '\\' && !pre.includes('r')) {
          const n = src[p + 1]; p += 2;
          if (n === '\n') { line++; continue; }
          s += { n: '\n', t: '\t', '\\': '\\', "'": "'", '"': '"', '0': '\0' }[n] ?? '\\' + n;
          continue;
        }
        s += ch; p++;
      }
      push(pre.includes('f') ? 'FSTR' : 'STR', s, startLine);
    }
    while (p < src.length) {
      if (bol && depth === 0) {
        let col = 0; while (src[p] === ' ') { col++; p++; }
        if (p >= src.length) break;
        if (src[p] === '\n' || src[p] === '#') {        // пустая строка или комментарий — отступ не важен
          while (p < src.length && src[p] !== '\n') p++;
          p++; line++; continue;
        }
        if (col > ind[ind.length - 1]) { ind.push(col); push('INDENT'); }
        else {
          while (col < ind[ind.length - 1]) { ind.pop(); push('DEDENT'); }
          if (col !== ind[ind.length - 1]) throw E('IndentationError', 'отступ не совпадает ни с одним уровнем выше', line + base);
        }
        bol = false;
      }
      const c = src[p];
      if (c === '\n') { if (depth === 0) { push('NL'); bol = true; } p++; line++; continue; }
      if (c === ' ') { p++; continue; }
      if (c === '#') { while (p < src.length && src[p] !== '\n') p++; continue; }
      if (c === '\\' && src[p + 1] === '\n') { p += 2; line++; continue; }
      if (/\d/.test(c) || (c === '.' && /\d/.test(src[p + 1] || ''))) {
        const m = /^(?:\d[\d_]*(?:\.[\d_]*)?(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)/.exec(src.slice(p, p + 64));
        const s = m[0].replace(/_/g, '');
        push('NUM', /[.eE]/.test(s) ? new F(parseFloat(s)) : parseInt(s, 10));
        p += m[0].length;
        if (/[A-Za-z_]/.test(src[p] || '')) throw fail(`после числа сразу идут буквы: «${m[0]}${src[p]}…». Между ними нужен знак операции`);
        continue;
      }
      if (/[A-Za-z_\u0400-\u04FF]/.test(c)) {
        const w = /^[A-Za-z_\u0400-\u04FF][\w\u0400-\u04FF]*/.exec(src.slice(p, p + 200))[0];
        if (/^[fFrR]{1,2}$/.test(w) && (src[p + w.length] === '"' || src[p + w.length] === "'")) { p += w.length; readString(w.toLowerCase()); continue; }
        push('NAME', w); p += w.length; continue;
      }
      if (c === '"' || c === "'") { readString(''); continue; }
      const s3 = src.substr(p, 3), s2 = src.substr(p, 2);
      const op = OPS2.find(o => o === s3 || o === s2);
      if (op) { push('OP', op); p += op.length; continue; }
      if (OPS1.includes(c)) {
        if ('([{'.includes(c)) depth++;
        else if (')]}'.includes(c)) depth = Math.max(0, depth - 1);
        push('OP', c); p++; continue;
      }
      if (c === '\u00A0') { p++; continue; }
      throw fail(`непонятный символ «${c}»`);
    }
    if (!bol) push('NL');
    while (ind.length > 1) { ind.pop(); push('DEDENT'); }
    push('EOF');
    return out;
  }

  /* ── разбор ── */
  const KEYWORDS = new Set('False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield'.split(' '));
  const UNSUPPORTED = { class: 'классы', try: 'try/except', except: 'try/except', finally: 'try/finally', yield: 'yield', del: 'del', assert: 'assert', raise: 'raise', nonlocal: 'nonlocal', async: 'async', await: 'await' };
  class Parser {
    constructor(toks) { this.t = toks; this.i = 0; this.loops = 0; this.funcs = 0; }
    get cur() { return this.t[this.i]; }
    is(t, v) { const c = this.t[this.i]; return c.t === t && (v === undefined || c.v === v); }
    op(v) { return this.is('OP', v); }
    kw(v) { return this.is('NAME', v); }
    next() { return this.t[this.i++]; }
    eatOp(v) { if (this.op(v)) { this.i++; return true; } return false; }
    fail(msg, line) { return E('SyntaxError', msg, line || this.cur.line); }
    want(v, msg) { if (this.op(v)) return this.next(); throw this.fail(msg || `здесь ожидалось «${v}»`); }
    desc(t) { return t.t === 'NL' ? 'конец строки' : t.t === 'EOF' ? 'конец программы' : t.t === 'INDENT' ? 'отступ' : t.t === 'DEDENT' ? 'конец блока' : `«${t.t === 'STR' ? reprStr(t.v) : pystr(t.v)}»`; }

    program() {
      const body = [];
      while (!this.is('EOF')) body.push(...this.statement());
      return body;
    }
    statement() {
      const c = this.cur;
      if (c.t === 'INDENT') throw E('IndentationError', 'лишний отступ в начале строки', c.line);
      if (c.t === 'OP' && c.v === '@') {                         // @lru_cache(None) перед def
        const decos = [];
        while (this.eatOp('@')) { decos.push(this.expr()); this.endLine(); }
        if (!this.kw('def')) throw this.fail('после строки с @ должна идти функция def');
        const d = this.defStmt(); d.decos = decos; return [d];
      }
      if (c.t === 'NAME') {
        switch (c.v) {
          case 'if': return [this.ifStmt()];
          case 'while': return [this.whileStmt()];
          case 'for': return [this.forStmt()];
          case 'def': return [this.defStmt()];
          case 'elif': case 'else': throw this.fail(`«${c.v}» без «if»: проверьте, что отступ у ${c.v} такой же, как у своего if`);
          case 'import': case 'from': { const st = this.importStmt(); this.endLine(); return [st]; }
          case 'with': return [this.withStmt()];
        }
        if (UNSUPPORTED[c.v]) throw this.fail(`${UNSUPPORTED[c.v]} в игре пока не поддерживаются`);
      }
      const out = [this.simple()];
      while (this.eatOp(';')) { if (this.is('NL')) break; out.push(this.simple()); }
      this.endLine();
      return out;
    }
    endLine() {
      if (this.is('NL')) { this.i++; return; }
      if (this.is('EOF') || this.is('DEDENT')) return;
      const c = this.cur;
      if (c.t === 'OP' && c.v === '=') throw this.fail('здесь нельзя ставить «=». Для сравнения нужно «==»');
      throw this.fail(`непонятно, что делать с ${this.desc(c)}. Возможно, пропущена запятая, скобка или знак операции`);
    }
    simple() {
      const c = this.cur, line = c.line;
      if (c.t === 'NAME') {
        if (c.v === 'pass') { this.i++; return { k: 'pass', line }; }
        if (c.v === 'break' || c.v === 'continue') {
          this.i++;
          if (!this.loops) throw this.fail(`${c.v} можно писать только внутри цикла`, line);
          return { k: c.v, line };
        }
        if (c.v === 'return') {
          this.i++;
          if (!this.funcs) throw this.fail('return можно писать только внутри функции (def)', line);
          return { k: 'return', e: this.is('NL') || this.is('EOF') || this.op(';') ? null : this.exprList(), line };
        }
        if (c.v === 'global') {
          this.i++; const names = [];
          do { if (!this.is('NAME')) throw this.fail('после global нужно имя переменной'); names.push(this.next().v); } while (this.eatOp(','));
          return { k: 'global', names, line };
        }
      }
      const e = this.exprList();
      if (this.op('=')) {
        const targets = [e];
        let value;
        while (this.eatOp('=')) { value = this.exprList(); targets.push(value); }
        targets.pop();
        targets.forEach(t => this.checkTarget(t));
        return { k: 'assign', targets, value, line };
      }
      const c2 = this.cur;
      if (c2.t === 'OP' && AUG.test(c2.v)) {
        this.i++;
        if (!['name', 'index', 'attr'].includes(e.k)) throw this.fail(`слева от «${c2.v}» должна быть переменная`, line);
        return { k: 'aug', target: e, op: c2.v.slice(0, -1), value: this.exprList(), line };
      }
      return { k: 'expr', e, line };
    }
    checkTarget(t) {
      if (t.k === 'name') { if (KEYWORDS.has(t.id)) throw this.fail(`«${t.id}» — служебное слово, им нельзя назвать переменную`, t.line); return; }
      if (t.k === 'index' || t.k === 'attr') return;
      if (t.k === 'tuple' || t.k === 'list') { t.items.forEach(x => this.checkTarget(x)); return; }
      if (t.k === 'call') throw this.fail('вызову функции нельзя присвоить значение. Для сравнения нужно «==»', t.line);
      throw this.fail('слева от «=» должна быть переменная. Для сравнения нужно «==»', t.line);
    }
    suite(head) {
      if (!this.op(':')) {
        if (this.op('=')) throw this.fail(`в условии ${head} нужно «==», а «=» — это присваивание`);
        throw this.fail(`в конце строки с ${head} нужно двоеточие «:»`);
      }
      this.i++;
      if (!this.is('NL')) {                                   // тело на той же строке: if x: harvest()
        const out = [this.simple()];
        while (this.eatOp(';')) { if (this.is('NL')) break; out.push(this.simple()); }
        this.endLine();
        return out;
      }
      this.i++;
      if (!this.is('INDENT')) throw E('IndentationError', `после строки с ${head} и двоеточием нужна строка с отступом (4 пробела)`, this.cur.line);
      this.i++;
      const body = [];
      while (!this.is('DEDENT') && !this.is('EOF')) body.push(...this.statement());
      if (this.is('DEDENT')) this.i++;
      return body;
    }
    ifStmt() {
      const line = this.next().line, branches = [];
      let test = this.expr();
      branches.push([test, this.suite('if')]);
      let orelse = null;
      for (;;) {
        if (this.kw('elif')) { this.i++; test = this.expr(); branches.push([test, this.suite('elif')]); continue; }
        if (this.kw('else')) { this.i++; orelse = this.suite('else'); }
        break;
      }
      return { k: 'if', branches, orelse, line };
    }
    whileStmt() {
      const line = this.next().line, test = this.expr();
      this.loops++; const body = this.suite('while'); this.loops--;
      return { k: 'while', test, body, line };
    }
    forStmt() {
      const line = this.next().line;
      const target = this.targetList();
      if (!this.kw('in')) throw this.fail('в цикле for нужно слово in: for i in range(5):');
      this.i++;
      const it = this.exprList();
      this.loops++; const body = this.suite('for'); this.loops--;
      return { k: 'for', target, iter: it, body, line };
    }
    targetList() {
      const items = [];
      do {
        if (!this.is('NAME') || KEYWORDS.has(this.cur.v)) throw this.fail('после for нужно имя переменной: for i in range(5):');
        items.push({ k: 'name', id: this.next().v, line: this.cur.line });
      } while (this.eatOp(','));
      return items.length === 1 ? items[0] : { k: 'tuple', items, line: items[0].line };
    }
    defStmt() {
      const line = this.next().line;
      if (!this.is('NAME') || KEYWORDS.has(this.cur.v)) throw this.fail('после def нужно имя функции: def go():');
      const name = this.next().v;
      if (!this.op('(')) throw this.fail(`после имени функции нужны скобки: def ${name}():`);
      this.i++;
      const params = [], defaults = [];
      while (!this.op(')')) {
        if (!this.is('NAME') || KEYWORDS.has(this.cur.v)) throw this.fail('в скобках после def — имена параметров через запятую');
        params.push(this.next().v);
        if (this.eatOp('=')) defaults.push(this.expr());
        else if (defaults.some(d => d !== undefined)) throw this.fail('параметры без значения по умолчанию пишутся перед параметрами со значением');
        else defaults.push(undefined);
        if (!this.eatOp(',')) break;
      }
      this.want(')', 'не закрыта скобка в строке с def');
      const loops = this.loops; this.loops = 0; this.funcs++;
      const body = this.suite('def');
      this.loops = loops; this.funcs--;
      const loc = new Set(params), glob = new Set();
      scanLocals(body, loc, glob);
      glob.forEach(g => loc.delete(g));
      return { k: 'def', name, params, defaults, body, locals: loc, globals: glob, line };
    }

    exprList() {
      const line = this.cur.line, first = this.expr();
      if (!this.op(',')) return first;
      const items = [first];
      while (this.eatOp(',')) { if (this.endsList()) break; items.push(this.expr()); }
      return { k: 'tuple', items, line };
    }
    endsList() { const c = this.cur; return c.t === 'NL' || c.t === 'EOF' || c.t === 'OP' && (['=', ')', ']', ':', ';'].includes(c.v) || AUG.test(c.v)); }
    importStmt() {
      const line = this.cur.line, from = this.next().v === 'from';
      const name = () => { if (!this.is('NAME')) throw this.fail('здесь нужно имя модуля'); let n = this.next().v; while (this.eatOp('.')) n += '.' + this.next().v; return n; };
      if (!from) {
        const mods = [];
        do { const m = name(); let as = null; if (this.kw('as')) { this.i++; as = this.next().v; } mods.push([m, as]); } while (this.eatOp(','));
        return { k: 'import', mods, line };
      }
      const mod = name();
      if (!this.kw('import')) throw this.fail('в строке from нужно слово import: from math import sqrt');
      this.i++;
      if (this.eatOp('*')) return { k: 'from', mod, names: '*', line };
      const paren = this.eatOp('('), names = [];
      do { if (paren && this.op(')')) break; const n = this.next().v; let as = null; if (this.kw('as')) { this.i++; as = this.next().v; } names.push([n, as]); } while (this.eatOp(','));
      if (paren) this.want(')');
      return { k: 'from', mod, names, line };
    }
    withStmt() {
      const line = this.next().line, items = [];
      do { const e = this.expr(); let as = null; if (this.kw('as')) { this.i++; as = this.targetList(); } items.push([e, as]); } while (this.eatOp(','));
      return { k: 'with', items, body: this.suite('with'), line };
    }
    expr() {
      if (this.kw('lambda')) {
        const line = this.next().line, params = [], defaults = [];
        while (!this.op(':')) {
          if (!this.is('NAME')) throw this.fail('после lambda — имена параметров: lambda x: x * 2');
          params.push(this.next().v);
          defaults.push(this.eatOp('=') ? this.expr() : undefined);
          if (!this.eatOp(',')) break;
        }
        this.want(':', 'в lambda после параметров нужно двоеточие');
        const body = this.expr();
        return { k: 'lambda', def: { name: '<lambda>', params, defaults, body: [{ k: 'return', e: body, line }], locals: new Set(params), globals: new Set(), line }, line };
      }
      const line = this.cur.line, e = this.orTest();
      if (this.kw('if')) {
        this.i++;
        const test = this.orTest();
        if (!this.kw('else')) throw this.fail('в выражении «a if условие else b» не хватает else');
        this.i++;
        return { k: 'cond', test, a: e, b: this.expr(), line };
      }
      return e;
    }
    orTest() { let e = this.andTest(); while (this.kw('or')) { const line = this.next().line; e = { k: 'bool', op: 'or', a: e, b: this.andTest(), line }; } return e; }
    andTest() { let e = this.notTest(); while (this.kw('and')) { const line = this.next().line; e = { k: 'bool', op: 'and', a: e, b: this.notTest(), line }; } return e; }
    notTest() { if (this.kw('not')) { const line = this.next().line; return { k: 'not', a: this.notTest(), line }; } return this.comparison(); }
    comparison() {
      const line = this.cur.line, items = [this.bitor()], ops = [];
      for (;;) {
        const c = this.cur;
        if (c.t === 'OP' && ['<', '>', '==', '!=', '<=', '>='].includes(c.v)) { this.i++; ops.push(c.v); }
        else if (this.kw('in')) { this.i++; ops.push('in'); }
        else if (this.kw('not') && this.t[this.i + 1].t === 'NAME' && this.t[this.i + 1].v === 'in') { this.i += 2; ops.push('not in'); }
        else if (this.kw('is')) { this.i++; if (this.kw('not')) { this.i++; ops.push('is not'); } else ops.push('is'); }
        else break;
        items.push(this.bitor());
      }
      return ops.length ? { k: 'cmp', ops, items, line } : items[0];
    }
    binLevel(next, ops) { let e = next(); while (ops.some(o => this.op(o))) { const t = this.next(); e = { k: 'bin', op: t.v, a: e, b: next(), line: t.line }; } return e; }
    bitor() { return this.binLevel(() => this.bitxor(), ['|']); }
    bitxor() { return this.binLevel(() => this.bitand(), ['^']); }
    bitand() { return this.binLevel(() => this.shift(), ['&']); }
    shift() { return this.binLevel(() => this.arith(), ['<<', '>>']); }
    arith() { let e = this.term(); while (this.op('+') || this.op('-')) { const t = this.next(); e = { k: 'bin', op: t.v, a: e, b: this.term(), line: t.line }; } return e; }
    term() { let e = this.factor(); while (this.op('*') || this.op('/') || this.op('//') || this.op('%')) { const t = this.next(); e = { k: 'bin', op: t.v, a: e, b: this.factor(), line: t.line }; } return e; }
    factor() {
      if (this.op('-') || this.op('+') || this.op('~')) { const t = this.next(); return { k: 'un', op: t.v, a: this.factor(), line: t.line }; }
      return this.power();
    }
    power() {
      const e = this.primary();
      if (this.op('**')) { const t = this.next(); return { k: 'bin', op: '**', a: e, b: this.factor(), line: t.line }; }
      return e;
    }
    primary() {
      let e = this.atom();
      for (;;) {
        const line = this.cur.line;
        if (this.op('(')) { this.i++; e = this.callArgs(e, line); }
        else if (this.op('[')) {
          this.i++;
          e = this.subscript(e, line);
        }
        else if (this.op('.')) {
          this.i++;
          if (!this.is('NAME')) throw this.fail('после точки нужно имя');
          e = { k: 'attr', obj: e, name: this.next().v, line };
        }
        else return e;
      }
    }
    subscript(obj, line) {
      let lo = null, hi = null, st = null, isSlice = false;
      if (!this.op(':')) lo = this.expr();
      if (this.eatOp(':')) {
        isSlice = true;
        if (!this.op(']') && !this.op(':')) hi = this.expr();
        if (this.eatOp(':') && !this.op(']')) st = this.expr();
      }
      this.want(']', 'не закрыта квадратная скобка ]');
      return isSlice ? { k: 'slice', obj, lo, hi, st, line } : { k: 'index', obj, idx: lo, line };
    }
    callArgs(fn, line) {
      const args = [], kw = [];
      while (!this.op(')')) {
        if (this.is('NAME') && this.t[this.i + 1].t === 'OP' && this.t[this.i + 1].v === '=') {
          const name = this.next().v; this.i++;
          kw.push([name, this.expr()]);
        } else if (this.op('*')) {
          this.i++; args.push({ k: 'star', e: this.expr(), line: this.cur.line });
        } else {
          if (kw.length) throw this.fail('обычные аргументы пишутся перед именованными (name=…)');
          const a = this.expr();
          if (this.kw('for')) { args.push(this.comp(a, 'gen', line)); break; }
          args.push(a);
        }
        if (!this.eatOp(',')) break;
      }
      if (!this.op(')')) {
        if (this.is('NL') || this.is('EOF')) throw this.fail('не закрыта скобка: в конце вызова не хватает «)»', line);
        throw this.fail(`между аргументами функции нужна запятая, а здесь ${this.desc(this.cur)}`);
      }
      this.i++;
      return { k: 'call', fn, args, kw, line };
    }
    comp(elt, kind, line) {
      const fors = [];
      while (this.kw('for')) {
        this.i++;
        const target = this.targetList();
        if (!this.kw('in')) throw this.fail('в генераторе нужно in: [x for x in a]');
        this.i++;
        const it = this.orTest(), conds = [];
        while (this.kw('if')) { this.i++; conds.push(this.orTest()); }
        fors.push({ target, iter: it, conds });
      }
      return { k: 'comp', kind, elt, fors, line };
    }
    atom() {
      const c = this.cur, line = c.line;
      if (c.t === 'NUM') { this.i++; return { k: 'num', v: c.v, line }; }
      if (c.t === 'STR' || c.t === 'FSTR') {
        const parts = [];
        while (this.is('STR') || this.is('FSTR')) { const t = this.next(); if (t.t === 'STR') parts.push(t.v); else parts.push(...fparts(t.v, t.line)); }
        return parts.every(p => typeof p === 'string') ? { k: 'str', v: parts.join(''), line } : { k: 'fstr', parts, line };
      }
      if (c.t === 'NAME') {
        if (c.v === 'True' || c.v === 'False' || c.v === 'None') { this.i++; return { k: 'const', v: c.v === 'None' ? null : c.v === 'True', line }; }
        if (KEYWORDS.has(c.v)) throw this.fail(`«${c.v}» здесь быть не может`);
        this.i++; return { k: 'name', id: c.v, line };
      }
      if (c.t === 'OP') {
        if (c.v === '(') {
          this.i++;
          if (this.eatOp(')')) return { k: 'tuple', items: [], line };
          const first = this.expr();
          if (this.kw('for')) { const g = this.comp(first, 'gen', line); this.want(')'); return g; }
          if (this.eatOp(')')) return first;
          const items = [first];
          while (this.eatOp(',')) { if (this.op(')')) break; items.push(this.expr()); }
          this.want(')', 'не закрыта круглая скобка )');
          return { k: 'tuple', items, line };
        }
        if (c.v === '[') {
          this.i++;
          if (this.eatOp(']')) return { k: 'list', items: [], line };
          const first = this.expr();
          if (this.kw('for')) { const g = this.comp(first, 'list', line); this.want(']', 'не закрыта квадратная скобка ]'); return g; }
          const items = [first];
          while (this.eatOp(',')) { if (this.op(']')) break; items.push(this.expr()); }
          this.want(']', 'не закрыта квадратная скобка ]. Элементы списка разделяются запятыми');
          return { k: 'list', items, line };
        }
        if (c.v === '{') {
          this.i++;
          if (this.eatOp('}')) return { k: 'dict', pairs: [], line };
          const first = this.expr();
          if (!this.op(':')) {                                   // множество {1, 2} или {x for x in a}
            if (this.kw('for')) { const g = this.comp(first, 'set', line); this.want('}', 'не закрыта фигурная скобка }'); return g; }
            const items = [first];
            while (this.eatOp(',')) { if (this.op('}')) break; items.push(this.expr()); }
            this.want('}', 'не закрыта фигурная скобка }');
            return { k: 'set', items, line };
          }
          this.i++;
          const v0 = this.expr();
          if (this.kw('for')) { const g = this.comp(v0, 'dict', line); g.key = first; this.want('}', 'не закрыта фигурная скобка }'); return g; }
          const pairs = [[first, v0]];
          while (this.eatOp(',')) {
            if (this.op('}')) break;
            const k = this.expr();
            this.want(':', 'в словаре пары пишутся через двоеточие: {"a": 1}');
            pairs.push([k, this.expr()]);
          }
          this.want('}', 'не закрыта фигурная скобка }');
          return { k: 'dict', pairs, line };
        }
      }
      if (c.t === 'NL' || c.t === 'EOF') throw this.fail('строка оборвалась: не хватает значения после знака');
      if (c.t === 'INDENT') throw E('IndentationError', 'лишний отступ', line);
      throw this.fail(`здесь не может быть ${this.desc(c)}`);
    }
  }
  function scanLocals(body, out, glob) {
    const names = t => { if (t.k === 'name') out.add(t.id); else if (t.k === 'tuple' || t.k === 'list') t.items.forEach(names); };
    for (const s of body) {
      if (s.k === 'assign') s.targets.forEach(names);
      else if (s.k === 'aug') names(s.target);
      else if (s.k === 'for') { names(s.target); scanLocals(s.body, out, glob); }
      else if (s.k === 'while') scanLocals(s.body, out, glob);
      else if (s.k === 'if') { s.branches.forEach(b => scanLocals(b[1], out, glob)); if (s.orelse) scanLocals(s.orelse, out, glob); }
      else if (s.k === 'def') out.add(s.name);
      else if (s.k === 'with') { s.items.forEach(([, as]) => as && names(as)); scanLocals(s.body, out, glob); }
      else if (s.k === 'import') s.mods.forEach(([m, as]) => out.add(as || m.split('.')[0]));
      else if (s.k === 'from' && s.names !== '*') s.names.forEach(([n, as]) => out.add(as || n));
      else if (s.k === 'global') s.names.forEach(n => glob.add(n));
    }
  }
  // f"…{x}…": текст и выражения; формат поддерживается только вида {x:.2f}
  function fparts(s, line) {
    const parts = [];
    let i = 0, txt = '';
    while (i < s.length) {
      const c = s[i];
      if (c === '{' && s[i + 1] === '{') { txt += '{'; i += 2; continue; }
      if (c === '}' && s[i + 1] === '}') { txt += '}'; i += 2; continue; }
      if (c === '}') throw E('SyntaxError', 'в f-строке лишняя «}»', line);
      if (c !== '{') { txt += c; i++; continue; }
      let j = i + 1, depth = 0, q = '';
      for (; j < s.length; j++) {
        const d = s[j];
        if (q) { if (d === q) q = ''; continue; }
        if (d === '"' || d === "'") q = d;
        else if ('([{'.includes(d)) depth++;
        else if (')]'.includes(d) || (d === '}' && depth)) depth--;
        else if (d === '}') break;
      }
      if (j >= s.length) throw E('SyntaxError', 'в f-строке не закрыта «{»', line);
      let inner = s.slice(i + 1, j), spec = '';
      const m = /^(.*?[^!=<>]):([<>^]?0?\d*(?:\.\d+)?[bdoxXf%]?)$/.exec(inner);
      if (m) { inner = m[1]; spec = m[2]; }
      if (!inner.trim()) throw E('SyntaxError', 'в f-строке пустые скобки {}', line);
      const P = new Parser(tokenize(inner.trim(), line - 1));
      const e = P.expr();
      if (!P.is('NL') && !P.is('EOF')) throw E('SyntaxError', 'непонятное выражение в {} f-строки', line);
      if (txt) parts.push(txt);
      txt = '';
      parts.push({ k: 'fmt', e, spec, line });
      i = j + 1;
    }
    if (txt) parts.push(txt);
    return parts;
  }
  function parse(src) { return new Parser(tokenize(src)).program(); }

  /* ── выполнение: всё — генераторы, команда дрону уступает ход (yield), так поле анимируется по шагам ── */
  const NOW = typeof performance !== 'undefined' ? () => performance.now() : () => Date.now();
  class Interp {
    constructor(opt = {}) {
      this.globals = new Map(); this.builtins = new Map();
      this.ops = 0; this.lastAct = 0; this.idleOps = opt.idleOps || 1500000; this.maxOps = opt.maxOps || Infinity; this.depth = 0; this.line = 0;
      this.maxDepth = 1000; this.hardDepth = 20000; this.files = opt.files || {};
      this.print = opt.print || (() => { });
      this.rng = opt.rng || Math.random;
      this.top = { vars: this.globals, isGlobal: true };
      installBuiltins(this);
    }
    def(name, fn, gen) { this.builtins.set(name, new Bi(name, fn, gen)); }
    lookup(name, sc, line) {
      if (!sc.isGlobal) {
        if (sc.vars.has(name)) return sc.vars.get(name);
        if (sc.locals.has(name)) throw E('UnboundLocalError', `переменной «${name}» внутри функции ещё не присвоено значение. Если это переменная всей программы, напишите в начале функции: global ${name}`, line);
        if (!sc.globalNames.has(name)) for (let s = sc.parent; s; s = s.parent) if (s.vars.has(name)) return s.vars.get(name);
      }
      if (this.globals.has(name)) return this.globals.get(name);
      if (this.builtins.has(name)) return this.builtins.get(name);
      const known = [...this.globals.keys(), ...this.builtins.keys()];
      if (!sc.isGlobal) { known.push(...sc.vars.keys()); for (let s = sc.parent; s; s = s.parent) known.push(...s.vars.keys()); }
      throw E('NameError', `имя «${name}» не определено${suggest(name, known)}`, line);
    }
    assign(name, v, sc) {
      if (sc.isGlobal || sc.globalNames.has(name)) this.globals.set(name, v);
      else sc.vars.set(name, v);
    }
    *run(body, sc) { for (const s of body) yield* this.stmt(s, sc); }
    *stmt(s, sc) {
      this.line = s.line;
      if (++this.ops % 20000 === 0) {
        if (this.ops - this.lastAct > this.idleOps) throw E('TimeoutError', 'программа долго работает, а дрон стоит на месте. Похоже на бесконечный цикл без команд дрону', s.line);
        if (this.ops > this.maxOps) throw E('TimeoutError', 'программа считает слишком долго. Похоже на бесконечный цикл или слишком большой перебор' + (this.depth > 0 ? '. Если функция много раз вызывает саму себя с одними и теми же числами, запомните ответы: @lru_cache(None)' : ''), s.line);
        yield IDLE;
      }
      switch (s.k) {
        case 'expr': yield* this.ev(s.e, sc); return;
        case 'assign': { const v = yield* this.ev(s.value, sc); for (const t of s.targets) yield* this.store(t, v, sc); return; }
        case 'aug': {
          const cur = yield* this.ev(s.target, sc), v = yield* this.ev(s.value, sc);
          if (Array.isArray(cur) && s.op === '+') { cur.push(...iter(v)); return; }
          this.line = s.line;
          yield* this.store(s.target, binop(s.op, cur, v), sc);
          return;
        }
        case 'if':
          for (const [test, body] of s.branches) if (truthy(yield* this.ev(test, sc))) return yield* this.run(body, sc);
          if (s.orelse) yield* this.run(s.orelse, sc);
          return;
        case 'while':
          for (;;) {
            this.line = s.line;
            if (!truthy(yield* this.ev(s.test, sc))) return;
            try { yield* this.run(s.body, sc); }
            catch (e) { if (e === BREAK) return; if (e !== CONT) throw e; }
          }
        case 'for': {
          const it = iter(yield* this.ev(s.iter, sc));
          for (const x of it) {
            this.line = s.line;
            yield* this.store(s.target, x, sc);
            try { yield* this.run(s.body, sc); }
            catch (e) { if (e === BREAK) return; if (e !== CONT) throw e; }
          }
          return;
        }
        case 'def': {
          let f = new Fn(s, sc.isGlobal ? null : sc);
          for (const d of [...(s.decos || [])].reverse()) f = yield* this.call(yield* this.ev(d, sc), [f], {});
          this.assign(s.name, f, sc); return;
        }
        case 'import':
          for (const [m, as] of s.mods) this.assign(as || m.split('.')[0], pyModule(this, m), sc);
          return;
        case 'from': {
          const mod = pyModule(this, s.mod);
          if (s.names === '*') { for (const [k, v] of Object.entries(mod.attrs)) this.assign(k, v, sc); return; }
          for (const [n, as] of s.names) {
            if (!(n in mod.attrs)) throw E('ImportError', `в модуле ${s.mod} нет «${n}»${suggest(n, Object.keys(mod.attrs))}`);
            this.assign(as || n, mod.attrs[n], sc);
          }
          return;
        }
        case 'with': {
          const opened = [];
          for (const [e, as] of s.items) { const v = yield* this.ev(e, sc); opened.push(v); if (as) yield* this.store(as, v, sc); }
          try { yield* this.run(s.body, sc); }
          finally { opened.forEach(v => { if (v instanceof PyFile) v.closed = true; }); }
          return;
        }
        case 'return': throw new Ret(s.e ? yield* this.ev(s.e, sc) : null);
        case 'break': throw BREAK;
        case 'continue': throw CONT;
        case 'pass': case 'global': return;
      }
    }
    *store(t, v, sc) {
      if (t.k === 'name') { this.assign(t.id, v, sc); return; }
      if (t.k === 'tuple' || t.k === 'list') {
        const vals = [...iter(v)];
        if (vals.length !== t.items.length) throw E('ValueError', `слева ${t.items.length} ${t.items.length < 5 ? 'переменные' : 'переменных'}, а значений справа — ${vals.length}`, t.line);
        for (let i = 0; i < vals.length; i++) yield* this.store(t.items[i], vals[i], sc);
        return;
      }
      if (t.k === 'index') { const o = yield* this.ev(t.obj, sc), k = yield* this.ev(t.idx, sc); setitem(o, k, v); return; }
      throw E('TypeError', 'этому выражению нельзя присвоить значение', t.line);
    }
    *ev(e, sc) {
      switch (e.k) {
        case 'num': case 'str': case 'const': return e.v;
        case 'name': return this.lookup(e.id, sc, e.line);
        case 'fstr': {
          let s = '';
          for (const p of e.parts) {
            if (typeof p === 'string') { s += p; continue; }
            const v = yield* this.ev(p.e, sc);
            s += p.spec ? fmtSpec(v, p.spec) : pystr(v);
          }
          return s;
        }
        case 'list': { const a = []; for (const x of e.items) a.push(yield* this.ev(x, sc)); return a; }
        case 'tuple': { const a = []; for (const x of e.items) a.push(yield* this.ev(x, sc)); return new Tup(a); }
        case 'dict': { const d = new Dict(); for (const [k, v] of e.pairs) { const kk = yield* this.ev(k, sc); d.set(kk, yield* this.ev(v, sc)); } return d; }
        case 'comp': {
          const out = [], inner = { vars: new Map(), locals: new Set(), globalNames: new Set(), parent: sc.isGlobal ? null : sc, isGlobal: false };
          yield* this.compLoop(e, 0, inner, out);
          if (e.kind === 'set') return new PySet(out);
          if (e.kind === 'dict') { const d = new Dict(); out.forEach(([k, v]) => d.set(k, v)); return d; }
          return out;
        }
        case 'set': { const r = new PySet(); for (const x of e.items) r.add(yield* this.ev(x, sc)); return r; }
        case 'lambda': return new Fn(e.def, sc.isGlobal ? null : sc);
        case 'bool': {
          const a = yield* this.ev(e.a, sc);
          if (e.op === 'and') return truthy(a) ? yield* this.ev(e.b, sc) : a;
          return truthy(a) ? a : yield* this.ev(e.b, sc);
        }
        case 'not': return !truthy(yield* this.ev(e.a, sc));
        case 'un': {
          const v = yield* this.ev(e.a, sc);
          if (!isNum(v)) throw E('TypeError', `знак «${e.op}» нельзя поставить перед значением типа ${tn(v)}`, e.line);
          if (e.op === '~') { if (v instanceof F) throw E('TypeError', 'знак «~» работает только с целыми числами'); return norm(~big(v)); }
          return e.op === '-' ? (v instanceof F ? new F(-v.v) : typeof v === 'bigint' ? norm(-v) : -v) : (v instanceof F || typeof v === 'bigint' ? v : +v);
        }
        case 'bin': { const a = yield* this.ev(e.a, sc), b = yield* this.ev(e.b, sc); return binop(e.op, a, b); }
        case 'cmp': {
          let left = yield* this.ev(e.items[0], sc);
          for (let i = 0; i < e.ops.length; i++) {
            const right = yield* this.ev(e.items[i + 1], sc), op = e.ops[i];
            let r;
            switch (op) {
              case '==': r = eq(left, right); break;
              case '!=': r = !eq(left, right); break;
              case 'in': r = contains(right, left); break;
              case 'not in': r = !contains(right, left); break;
              case 'is': r = left === right || (left == null && right == null); break;
              case 'is not': r = !(left === right || (left == null && right == null)); break;
              default: { const o = order(left, right, op); r = op === '<' ? o < 0 : op === '>' ? o > 0 : op === '<=' ? o <= 0 : o >= 0; }
            }
            if (!r) return false;
            left = right;
          }
          return true;
        }
        case 'cond': return truthy(yield* this.ev(e.test, sc)) ? yield* this.ev(e.a, sc) : yield* this.ev(e.b, sc);
        case 'attr': return this.getattr(yield* this.ev(e.obj, sc), e.name);
        case 'index': { const o = yield* this.ev(e.obj, sc); return getitem(o, yield* this.ev(e.idx, sc)); }
        case 'slice': {
          const o = yield* this.ev(e.obj, sc);
          const lo = e.lo ? yield* this.ev(e.lo, sc) : null, hi = e.hi ? yield* this.ev(e.hi, sc) : null, st = e.st ? yield* this.ev(e.st, sc) : null;
          return slice(o, lo, hi, st);
        }
        case 'call': {
          const fn = yield* this.ev(e.fn, sc), args = [], kw = {};
          // all(… for …) и any(… for …) останавливаются на первом ответе, как в Python
          if (fn instanceof Bi && (fn === this.builtins.get('all') || fn === this.builtins.get('any')) && e.args.length === 1 && e.args[0].k === 'comp' && e.args[0].kind === 'gen') {
            const isAll = fn.name === 'all', STOP = {}, inner = { vars: new Map(), locals: new Set(), globalNames: new Set(), parent: sc.isGlobal ? null : sc, isGlobal: false };
            try { yield* this.compLoop(e.args[0], 0, inner, { push: v => { if (truthy(v) !== isAll) throw STOP; } }); }
            catch (x) { if (x !== STOP) throw x; return !isAll; }
            return isAll;
          }
          for (const a of e.args) { if (a.k === 'star') args.push(...iter(yield* this.ev(a.e, sc))); else args.push(yield* this.ev(a, sc)); }
          for (const [k, v] of e.kw) kw[k] = yield* this.ev(v, sc);
          this.line = e.line;
          return yield* this.call(fn, args, kw, e.fn);
        }
      }
      throw E('SyntaxError', 'неизвестное выражение', e.line);
    }
    *compLoop(e, i, sc, out) {
      if (i === e.fors.length) { out.push(e.kind === 'dict' ? [yield* this.ev(e.key, sc), yield* this.ev(e.elt, sc)] : yield* this.ev(e.elt, sc)); return; }
      const f = e.fors[i];
      for (const x of iter(yield* this.ev(f.iter, sc))) {
        if (++this.ops % 20000 === 0) yield* this.stmt({ k: 'pass', line: e.line }, sc);
        yield* this.store(f.target, x, sc);
        let ok = true;
        for (const c of f.conds) if (!truthy(yield* this.ev(c, sc))) { ok = false; break; }
        if (ok) yield* this.compLoop(e, i + 1, sc, out);
      }
    }
    *call(fn, args, kw, node) {
      if (fn instanceof Bi) { const r = fn.fn.call(this, args, kw); return fn.gen ? yield* r : r; }
      // вызов своей функции не вкладывается в стек JS: просьба уходит наверх в drive(), там свой стек кадров
      if (fn instanceof Fn) return yield { $call: fn, args, kw };
      const what = node && node.k === 'name' ? `«${node.id}» — это ${tn(fn)}, а не функция` : `значение типа ${tn(fn)} нельзя вызвать как функцию`;
      throw E('TypeError', what + (fn instanceof Const ? '. Скобки () не нужны' : ''));
    }
    // кадр функции: параметры, тело, return
    *frame(fn, args, kw) {
      {
        const d = fn.def, line = this.line;
        if (args.length > d.params.length) throw E('TypeError', `функция ${d.name}() принимает ${d.params.length} ${plural(d.params.length, 'аргумент', 'аргумента', 'аргументов')}, а передано ${args.length}`);
        const sc = { vars: new Map(), locals: d.locals, globalNames: d.globals, parent: fn.closure, isGlobal: false };
        for (let i = 0; i < d.params.length; i++) {
          const p = d.params[i];
          if (i < args.length) { if (p in kw) throw E('TypeError', `аргумент «${p}» передан дважды`); sc.vars.set(p, args[i]); }
          else if (p in kw) sc.vars.set(p, kw[p]);
          else if (d.defaults[i] !== undefined) sc.vars.set(p, yield* this.ev(d.defaults[i], fn.closure || this.top));
          else throw E('TypeError', `функции ${d.name}() не хватает аргумента «${p}»`);
        }
        for (const k of Object.keys(kw)) if (!d.params.includes(k)) throw E('TypeError', `у функции ${d.name}() нет параметра «${k}»`);
        if (++this.depth > this.maxDepth) { this.depth = 0; throw E('RecursionError', `слишком глубокая рекурсия: больше ${this.maxDepth} вызовов подряд. Проверьте, что у рекурсии есть условие остановки`); }
        try { yield* this.run(d.body, sc); return null; }
        catch (e) {
          if (e instanceof Ret) return e.v;
          if (e instanceof PyError && e.line == null) e.line = this.line;
          throw e;
        }
        finally { this.depth = Math.max(0, this.depth - 1); this.line = line; }
      }
    }
    // «батут»: выполняет программу, держа кадры функций в своём стеке — рекурсия в тысячи вызовов не переполняет стек JS.
    // Наверх (в Run) отдаёт только ходы дрона и паузы IDLE
    *drive(gen) {
      const stack = [gen];
      let send, err = null;
      while (stack.length) {
        const g = stack[stack.length - 1];
        let r;
        try { r = err ? g.throw(err) : g.next(send); err = null; }
        catch (e) { stack.pop(); if (!stack.length) throw e; err = e; send = undefined; continue; }
        if (r.done) { stack.pop(); send = r.value; continue; }
        if (r.value && r.value.$call) { stack.push(this.frame(r.value.$call, r.value.args, r.value.kw)); send = undefined; continue; }
        send = yield r.value;
      }
      return send;
    }
    exec(body) { return this.drive(this.run(body, this.top)); }
    getattr(o, name) {
      if (o instanceof NS) {
        if (name in o.attrs) return o.attrs[name];
        throw E('AttributeError', `у ${o.name} нет «${name}»${suggest(name, Object.keys(o.attrs))}`);
      }
      const m = methods(this, o, name);
      if (m) return m;
      throw E('AttributeError', `у значения типа ${tn(o)} нет метода «${name}»`);
    }
    // вызов функции из встроенных (key= у sorted, max, min)
    *callKey(fn, x) { return fn ? yield* this.call(fn, [x], {}) : x; }
  }
  const plural = (n, a, b, c) => { const m10 = n % 10, m100 = n % 100; return m10 === 1 && m100 !== 11 ? a : m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20) ? b : c; };
  function needArgs(name, args, lo, hi = lo) {
    if (args.length < lo || args.length > hi) throw E('TypeError', `${name}() ${lo === hi ? `принимает ${lo === 0 ? 'ноль' : lo} ${plural(lo, 'аргумент', 'аргумента', 'аргументов')}` : `принимает от ${lo} до ${hi} аргументов`}, а передано ${args.length}`);
  }
  function toInt(x, base) {
    if (typeof x === 'string') {
      const s = x.trim().replace(/_/g, ''), b = base === undefined ? 10 : +base;
      const ok = b === 10 ? /^[+-]?\d+$/.test(s) : new RegExp(`^[+-]?[0-9a-z]+$`, 'i').test(s) && [...s.replace(/^[+-]/, '').toLowerCase()].every(c => parseInt(c, 36) < b);
      if (!ok) throw E('ValueError', `int() не может превратить строку ${reprStr(x)} в целое число`);
      const r = parseInt(s, b);
      if (Number.isSafeInteger(r)) return r;
      let v = 0n; const neg = s[0] === '-';                     // длинное число: по цифрам
      for (const ch of s.replace(/^[+-]/, '').toLowerCase()) v = v * BigInt(b) + BigInt(parseInt(ch, 36));
      return norm(neg ? -v : v);
    }
      if (isNum(x)) return typeof x === 'bigint' ? x : x instanceof F ? (Number.isSafeInteger(Math.trunc(x.v)) ? Math.trunc(x.v) : norm(BigInt(Math.trunc(x.v)))) : +x;
    throw E('TypeError', `int() не умеет превращать в число значение типа ${tn(x)}`);
  }
  function* sortKeyed(ip, list, key, reverse) {
    const keyed = [];
    for (const x of list) keyed.push([yield* ip.callKey(key, x), x]);
    keyed.sort((a, b) => order(a[0], b[0], '<'));
    if (reverse) keyed.reverse();
    return keyed.map(k => k[1]);
  }
  function* extreme(ip, name, args, kw, sign) {
    let list = args.length === 1 ? [...iter(args[0])] : args;
    if (!list.length) { if ('default' in kw) return kw.default; throw E('ValueError', `${name}() получила пустую последовательность`); }
    let best = list[0], bk = yield* ip.callKey(kw.key, best);
    for (let i = 1; i < list.length; i++) { const k = yield* ip.callKey(kw.key, list[i]); if (order(k, bk, '<') * sign > 0) { best = list[i]; bk = k; } }
    return best;
  }
  function installBuiltins(ip) {
    ip.def('print', (args, kw) => { ip.print(args.map(pystr).join(kw.sep !== undefined ? pystr(kw.sep) : ' ') + (kw.end !== undefined ? pystr(kw.end) : '\n')); return null; });
    ip.def('range', args => {
      needArgs('range', args, 1, 3);
      args.forEach(a => { if (!isInt(a)) throw E('TypeError', `range() принимает только целые числа, а получила ${tn(a)}`); });
      const [a, b, s] = args.length === 1 ? [0, +args[0], 1] : [+args[0], +args[1], args.length > 2 ? +args[2] : 1];
      if (s === 0) throw E('ValueError', 'шаг range() не может быть нулём');
      return new Range(a, b, s);
    });
    ip.def('len', args => {
      needArgs('len', args, 1);
      const x = args[0];
      if (typeof x === 'string' || Array.isArray(x)) return x.length;
      if (x instanceof Tup) return x.a.length;
      if (x instanceof Dict) return x.m.size;
      if (x instanceof Range) return x.n;
      if (x instanceof PySet) return x.m.size;
      throw E('TypeError', `у значения типа ${tn(x)} нет длины`);
    });
    ip.def('abs', args => { needArgs('abs', args, 1); if (!isNum(args[0])) throw E('TypeError', `abs() ждёт число, а не ${tn(args[0])}`); const x = args[0]; return x instanceof F ? new F(Math.abs(x.v)) : typeof x === 'bigint' ? (x < 0n ? -x : x) : Math.abs(x); });
    ip.def('min', function* (args, kw) { return yield* extreme(ip, 'min', args, kw, -1); }, true);
    ip.def('max', function* (args, kw) { return yield* extreme(ip, 'max', args, kw, 1); }, true);
    ip.def('sum', args => { needArgs('sum', args, 1, 2); let s = args.length > 1 ? args[1] : 0; for (const x of iter(args[0])) s = binop('+', s, x); return s; });
    ip.def('int', args => { needArgs('int', args, 0, 2); return args.length ? toInt(args[0], args[1]) : 0; });
    ip.def('float', args => {
      needArgs('float', args, 0, 1);
      const x = args.length ? args[0] : 0;
      if (typeof x === 'string') { const s = x.trim(); if (!/^[+-]?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?$/i.test(s)) throw E('ValueError', `float() не может превратить строку ${reprStr(x)} в число`); return new F(parseFloat(s)); }
      if (!isNum(x)) throw E('TypeError', `float() не умеет превращать в число значение типа ${tn(x)}`);
      return new F(nv(x));
    });
    ip.def('str', args => (needArgs('str', args, 0, 1), args.length ? pystr(args[0]) : ''));
    ip.def('bool', args => (needArgs('bool', args, 0, 1), args.length ? truthy(args[0]) : false));
    ip.def('list', args => (needArgs('list', args, 0, 1), args.length ? [...iter(args[0])] : []));
    ip.def('tuple', args => (needArgs('tuple', args, 0, 1), new Tup(args.length ? [...iter(args[0])] : [])));
    ip.def('dict', () => new Dict());
    ip.def('sorted', function* (args, kw) { needArgs('sorted', args, 1); return yield* sortKeyed(ip, [...iter(args[0])], kw.key, truthy(kw.reverse)); }, true);
    ip.def('reversed', args => (needArgs('reversed', args, 1), [...iter(args[0])].reverse()));
    ip.def('enumerate', args => { needArgs('enumerate', args, 1, 2); const st = args.length > 1 ? +args[1] : 0; return [...iter(args[0])].map((x, i) => new Tup([i + st, x])); });
    ip.def('zip', args => { const ls = args.map(a => [...iter(a)]), n = ls.length ? Math.min(...ls.map(l => l.length)) : 0; return Array.from({ length: n }, (_, i) => new Tup(ls.map(l => l[i]))); });
    ip.def('round', args => {
      needArgs('round', args, 1, 2);
      const v = nv(args[0]);
      if (args.length > 1 && args[1] !== null) { const p = Math.pow(10, +args[1]); return new F(Math.round(v * p) / p); }
      const r = Math.round(v);
      return Math.abs(v % 1) === 0.5 ? 2 * Math.round(v / 2) : r;                // как в Python: 2.5 → 2
    });
    ip.def('divmod', args => (needArgs('divmod', args, 2), new Tup([binop('//', args[0], args[1]), binop('%', args[0], args[1])])));
    ip.def('pow', args => (needArgs('pow', args, 2), binop('**', args[0], args[1])));
    ip.def('any', args => (needArgs('any', args, 1), [...iter(args[0])].some(truthy)));
    ip.def('all', args => (needArgs('all', args, 1), [...iter(args[0])].every(truthy)));
    ip.def('chr', args => (needArgs('chr', args, 1), String.fromCodePoint(+args[0])));
    ip.def('ord', args => { needArgs('ord', args, 1); if (typeof args[0] !== 'string' || [...args[0]].length !== 1) throw E('TypeError', 'ord() ждёт один символ'); return args[0].codePointAt(0); });
    ip.def('type', args => (needArgs('type', args, 1), `<class '${tn(args[0])}'>`));
    ip.def('random', args => (needArgs('random', args, 0), new F(ip.rng())));
    ip.def('set', args => (needArgs('set', args, 0, 1), new PySet(args.length ? iter(args[0]) : [])));
    const toBase = (name, b, pre) => args => {
      needArgs(name, args, 1); const x = args[0];
      if (!isInt(x)) throw E('TypeError', `${name}() работает только с целыми числами`);
      const v = big(x); return (v < 0n ? '-' : '') + pre + (v < 0n ? -v : v).toString(b);
    };
    ip.def('bin', toBase('bin', 2, '0b')); ip.def('oct', toBase('oct', 8, '0o')); ip.def('hex', toBase('hex', 16, '0x'));
    ip.def('format', args => (needArgs('format', args, 1, 2), args.length > 1 ? fmtSpec(args[0], pystr(args[1])) : pystr(args[0])));
    ip.def('map', function* (args) {
      if (args.length < 2) throw E('TypeError', 'map() ждёт функцию и список: map(int, s.split())');
      const ls = args.slice(1).map(a => [...iter(a)]), n = Math.min(...ls.map(l => l.length)), out = [];
      for (let i = 0; i < n; i++) out.push(yield* ip.call(args[0], ls.map(l => l[i]), {}));
      return out;
    }, true);
    ip.def('filter', function* (args) {
      needArgs('filter', args, 2); const out = [];
      for (const x of iter(args[1])) if (args[0] === null ? truthy(x) : truthy(yield* ip.call(args[0], [x], {}))) out.push(x);
      return out;
    }, true);
    ip.def('isinstance', args => { needArgs('isinstance', args, 2); const t = args[1]; const n = t instanceof Bi ? t.name : ''; return n === 'int' ? isInt(args[0]) && !isBool(args[0]) : n === 'str' ? typeof args[0] === 'string' : n === 'list' ? Array.isArray(args[0]) : n === 'float' ? args[0] instanceof F : false; });
    ip.def('open', (args, kw) => {
      if (!args.length) throw E('TypeError', 'open() ждёт имя файла: open(\'17.txt\')');
      const name = pystr(args[0]).replace(/^.*[\\/]/, '');
      if (!(name in ip.files)) throw E('FileNotFoundError', `файла «${name}» нет. ${Object.keys(ip.files).length ? 'На этом уровне есть: ' + Object.keys(ip.files).join(', ') : 'На этом уровне файлов нет'}`);
      return new PyFile(name, ip.files[name]);
    });
    ip.def('input', () => { throw E('RuntimeError', 'input() в игре не работает: дрону некого спрашивать. Задайте значение в программе: n = 5'); });
  }
  const bm = (name, fn, gen) => new Bi(name, fn, gen);
  // формат f"{x:08b}", format(x, '.2f')
  function fmtSpec(v, spec) {
    const m = /^([<>^])?(0)?(\d+)?(?:\.(\d+))?([bdoxXf%])?$/.exec(spec);
    if (!m) throw E('ValueError', `непонятный формат «${spec}»`);
    const [, align, zero, width, prec, type] = m;
    let s;
    if ('bdoxX'.includes(type || '_')) {
      if (!isInt(v)) throw E('ValueError', `формат «${type}» подходит только для целых чисел`);
      const b = big(v), a = b < 0n ? -b : b;
      s = (b < 0n ? '-' : '') + (type === 'd' ? a.toString() : type === 'b' ? a.toString(2) : type === 'o' ? a.toString(8) : type === 'x' ? a.toString(16) : a.toString(16).toUpperCase());
    } else if (type === 'f' || type === '%') {
      if (!isNum(v)) throw E('ValueError', `формат «${type}» подходит только для чисел`);
      s = (nv(v) * (type === '%' ? 100 : 1)).toFixed(prec === undefined ? 6 : +prec) + (type === '%' ? '%' : '');
    } else if (prec !== undefined && v instanceof F) s = nv(v).toFixed(+prec);
    else s = pystr(v);
    const w = +(width || 0);
    if (s.length >= w) return s;
    if (zero && !align) { const neg = s[0] === '-'; return (neg ? '-' : '') + s.slice(neg ? 1 : 0).padStart(w - (neg ? 1 : 0), '0'); }
    const al = align || (isNum(v) ? '>' : '<');
    if (al === '<') return s.padEnd(w);
    if (al === '>') return s.padStart(w);
    const l = Math.floor((w - s.length) / 2); return ' '.repeat(l) + s + ' '.repeat(w - s.length - l);
  }
  // модули: math, itertools, functools, sys
  function pyModule(ip, name) {
    if (ip.mods && ip.mods[name]) return ip.mods[name];
    const num = x => { if (!isNum(x)) throw E('TypeError', `нужно число, а не ${tn(x)}`); return nv(x); };
    const fl = f => args => new F(f(...args.map(num)));
    const memo = fn => {
      const cache = new Map();
      const w = bm(fn.def ? fn.def.name : fn.name, function* (args, kw) {
        const k = args.map(hkey).join('|') + (Object.keys(kw).length ? '|' + JSON.stringify(Object.keys(kw)) + Object.values(kw).map(hkey).join('|') : '');
        if (cache.has(k)) return cache.get(k);
        const v = yield* ip.call(fn, args, kw); cache.set(k, v); return v;
      }, true);
      return w;
    };
    const cacheDeco = bm('lru_cache', args => {
      if (args[0] instanceof Fn || args[0] instanceof Bi) return memo(args[0]);
      return bm('lru_cache', a => memo(a[0]));
    });
    const prodOf = (pools, out, cur, i) => { if (i === pools.length) { out.push(new Tup(cur.slice())); return; } for (const x of pools[i]) { cur.push(x); prodOf(pools, out, cur, i + 1); cur.pop(); } };
    const LIMIT = 3000000;
    const M = {
      math: {
        sqrt: fl(Math.sqrt), floor: a => toInt(new F(Math.floor(num(a[0])))), ceil: a => toInt(new F(Math.ceil(num(a[0])))), trunc: a => toInt(a[0]),
        isqrt: a => { const n = big(a[0]); if (n < 0n) throw E('ValueError', 'isqrt() от отрицательного числа'); if (n < 9007199254740991n) return Math.floor(Math.sqrt(Number(n))) ** 2 > Number(n) ? Math.floor(Math.sqrt(Number(n))) - 1 : Math.floor(Math.sqrt(Number(n))); let x = BigInt(Math.floor(Math.sqrt(Number(n)))); while (x * x > n) x--; while ((x + 1n) * (x + 1n) <= n) x++; return norm(x); },
        gcd: a => { let x = big(a[0] || 0), y = big(a[1] || 0); x = x < 0n ? -x : x; y = y < 0n ? -y : y; while (y) [x, y] = [y, x % y]; return norm(x); },
        lcm: a => { let x = big(a[0]), y = big(a[1]); if (!x || !y) return 0; let g = x, h = y; while (h) [g, h] = [h, g % h]; return norm((x * y < 0n ? -x * y : x * y) / g); },
        log: a => new F(a.length > 1 ? Math.log(num(a[0])) / Math.log(num(a[1])) : Math.log(num(a[0]))), log2: fl(Math.log2), log10: fl(Math.log10),
        pow: fl(Math.pow), fabs: fl(Math.abs), factorial: a => { let r = 1n; for (let i = 2n; i <= big(a[0]); i++) r *= i; return norm(r); },
        prod: a => { let r = 1; for (const x of iter(a[0])) r = binop('*', r, x); return r; },
        sin: fl(Math.sin), cos: fl(Math.cos), tan: fl(Math.tan), atan2: fl(Math.atan2), hypot: fl(Math.hypot), dist: a => new F(Math.hypot(...[...iter(a[0])].map((x, i) => num(x) - num([...iter(a[1])][i])))),
        pi: new F(Math.PI), e: new F(Math.E), inf: new F(Infinity),
      },
      itertools: {
        product: (args, kw) => {
          const pools = args.map(a => [...iter(a)]), rep = kw.repeat !== undefined ? +kw.repeat : 1, all = [];
          for (let i = 0; i < rep; i++) all.push(...pools);
          if (all.reduce((n, p) => n * p.length, 1) > LIMIT) throw E('MemoryError', 'слишком много вариантов для перебора');
          const out = []; prodOf(all, out, [], 0); return out;
        },
        permutations: args => {
          const pool = [...iter(args[0])], r = args.length > 1 && args[1] !== null ? +args[1] : pool.length, out = [], used = Array(pool.length).fill(false), cur = [];
          const go = () => { if (out.length > LIMIT) throw E('MemoryError', 'слишком много вариантов для перебора'); if (cur.length === r) { out.push(new Tup(cur.slice())); return; } for (let i = 0; i < pool.length; i++) if (!used[i]) { used[i] = true; cur.push(pool[i]); go(); cur.pop(); used[i] = false; } };
          go(); return out;
        },
        combinations: args => {
          const pool = [...iter(args[0])], r = +args[1], out = [], cur = [];
          const go = st => { if (cur.length === r) { out.push(new Tup(cur.slice())); return; } for (let i = st; i < pool.length; i++) { cur.push(pool[i]); go(i + 1); cur.pop(); } };
          go(0); return out;
        },
      },
      functools: { lru_cache: cacheDeco, cache: cacheDeco },
      sys: { setrecursionlimit: a => { ip.maxDepth = Math.max(100, Math.min(ip.hardDepth || 3000, +a[0])); return null; }, getrecursionlimit: () => ip.maxDepth, maxsize: 9007199254740991 },
      fnmatch: {
        fnmatch: a => new RegExp('^' + pystr(a[1]).replace(/[.+^${}()|\\]/g, '\\$&').replace(/\*/g, '.*').replace(/\?/g, '.') + '$').test(pystr(a[0])),
      },
    };
    M.functools.reduce = bm('reduce', function* (a) { const xs = [...iter(a[1])]; let acc = a.length > 2 ? a[2] : xs.shift(); for (const x of xs) acc = yield* ip.call(a[0], [acc, x], {}); return acc; }, true);
    if (!M[name]) throw E('ImportError', `модуль «${name}» в игре недоступен. Есть: math, itertools, functools, sys, fnmatch`);
    const attrs = {};
    for (const [k, v] of Object.entries(M[name])) attrs[k] = typeof v === 'function' ? bm(k, v) : v;
    ip.mods = ip.mods || {};
    return (ip.mods[name] = new NS(name, attrs));
  }
  function methods(ip, o, name) {
    if (Array.isArray(o)) switch (name) {
      case 'append': return bm(name, a => { needArgs('append', a, 1); o.push(a[0]); return null; });
      case 'extend': return bm(name, a => { needArgs('extend', a, 1); o.push(...iter(a[0])); return null; });
      case 'insert': return bm(name, a => { needArgs('insert', a, 2); let i = +a[0]; if (i < 0) i = Math.max(0, o.length + i); o.splice(Math.min(i, o.length), 0, a[1]); return null; });
      case 'pop': return bm(name, a => { needArgs('pop', a, 0, 1); if (!o.length) throw E('IndexError', 'pop() из пустого списка'); const i = a.length ? index(o.length, a[0]) : o.length - 1; return o.splice(i, 1)[0]; });
      case 'remove': return bm(name, a => { needArgs('remove', a, 1); const i = o.findIndex(x => eq(x, a[0])); if (i < 0) throw E('ValueError', `в списке нет ${repr(a[0])}`); o.splice(i, 1); return null; });
      case 'index': return bm(name, a => { needArgs('index', a, 1); const i = o.findIndex(x => eq(x, a[0])); if (i < 0) throw E('ValueError', `в списке нет ${repr(a[0])}`); return i; });
      case 'count': return bm(name, a => (needArgs('count', a, 1), o.filter(x => eq(x, a[0])).length));
      case 'sort': return bm(name, function* (a, kw) { needArgs('sort', a, 0); const r = yield* sortKeyed(ip, o, kw.key, truthy(kw.reverse)); o.splice(0, o.length, ...r); return null; }, true);
      case 'reverse': return bm(name, () => { o.reverse(); return null; });
      case 'copy': return bm(name, () => o.slice());
      case 'clear': return bm(name, () => { o.length = 0; return null; });
    }
    if (typeof o === 'string') switch (name) {
      case 'upper': return bm(name, () => o.toUpperCase());
      case 'lower': return bm(name, () => o.toLowerCase());
      case 'strip': return bm(name, a => a.length && a[0] !== null ? o.replace(new RegExp(`^[${reEsc(pystr(a[0]))}]+|[${reEsc(pystr(a[0]))}]+$`, 'g'), '') : o.trim());
      case 'lstrip': return bm(name, a => a.length && a[0] !== null ? o.replace(new RegExp(`^[${reEsc(pystr(a[0]))}]+`), '') : o.trimStart());
      case 'rstrip': return bm(name, a => a.length && a[0] !== null ? o.replace(new RegExp(`[${reEsc(pystr(a[0]))}]+$`), '') : o.trimEnd());
      case 'isalpha': return bm(name, () => o.length > 0 && /^\p{L}+$/u.test(o));
      case 'isalnum': return bm(name, () => o.length > 0 && /^[\p{L}\d]+$/u.test(o));
      case 'isupper': return bm(name, () => o !== o.toLowerCase() && o === o.toUpperCase());
      case 'islower': return bm(name, () => o !== o.toUpperCase() && o === o.toLowerCase());
      case 'rfind': return bm(name, a => o.lastIndexOf(pystr(a[0])));
      case 'index': return bm(name, a => { const i = o.indexOf(pystr(a[0])); if (i < 0) throw E('ValueError', `подстроки ${repr(a[0])} нет в строке`); return i; });
      case 'zfill': return bm(name, a => o.padStart(+a[0], '0'));
      case 'title': return bm(name, () => o.replace(/\p{L}+/gu, w => w[0].toUpperCase() + w.slice(1).toLowerCase()));
      case 'capitalize': return bm(name, () => o.charAt(0).toUpperCase() + o.slice(1).toLowerCase());
      case 'split': return bm(name, a => a.length && a[0] !== null ? o.split(pystr(a[0])) : o.split(/\s+/).filter(Boolean));
      case 'splitlines': return bm(name, () => o.split(/\r?\n/).filter((x, i, arr) => i < arr.length - 1 || x));
      case 'join': return bm(name, a => { needArgs('join', a, 1); const xs = [...iter(a[0])]; xs.forEach(x => { if (typeof x !== 'string') throw E('TypeError', `join() склеивает только строки, а встретилось значение типа ${tn(x)}`); }); return xs.join(o); });
      case 'replace': return bm(name, a => {
        needArgs('replace', a, 2, 3);
        const f = pystr(a[0]), t = pystr(a[1]);
        if (a.length < 3 || +a[2] < 0) return o.split(f).join(t);
        let r = o, n = +a[2], from = 0, out = '';                 // replace(что, на что, сколько раз)
        while (n-- > 0) { const i = r.indexOf(f, from); if (i < 0) break; out += r.slice(from, i) + t; from = i + f.length; if (!f.length) { out += r[i] || ''; from++; } }
        return out + r.slice(from);
      });
      case 'startswith': return bm(name, a => o.startsWith(pystr(a[0])));
      case 'endswith': return bm(name, a => o.endsWith(pystr(a[0])));
      case 'find': return bm(name, a => o.indexOf(pystr(a[0])));
      case 'count': return bm(name, a => o.split(pystr(a[0])).length - 1);
      case 'isdigit': return bm(name, () => /^\d+$/.test(o));
    }
    if (o instanceof Dict) switch (name) {
      case 'get': return bm(name, a => { needArgs('get', a, 1, 2); return o.has(a[0]) ? o.get(a[0]) : a.length > 1 ? a[1] : null; });
      case 'keys': return bm(name, () => o.keys());
      case 'values': return bm(name, () => [...o.m.values()].map(e => e[1]));
      case 'items': return bm(name, () => [...o.m.values()].map(e => new Tup([e[0], e[1]])));
      case 'pop': return bm(name, a => { needArgs('pop', a, 1, 2); if (!o.has(a[0])) { if (a.length > 1) return a[1]; throw E('KeyError', `ключа ${repr(a[0])} нет в словаре`); } const v = o.get(a[0]); o.del(a[0]); return v; });
      case 'copy': return bm(name, () => { const d = new Dict(); o.m.forEach((v, k) => d.m.set(k, v.slice())); return d; });
      case 'setdefault': return bm(name, a => { if (!o.has(a[0])) o.set(a[0], a.length > 1 ? a[1] : null); return o.get(a[0]); });
      case 'update': return bm(name, a => { const src = a[0]; if (src instanceof Dict) src.m.forEach(([k, v]) => o.set(k, v)); else for (const t of iter(src)) { const [k, v] = iter(t); o.set(k, v); } return null; });
    }
    if (o instanceof PySet) switch (name) {
      case 'add': return bm(name, a => { needArgs('add', a, 1); o.add(a[0]); return null; });
      case 'remove': return bm(name, a => { if (!o.del(a[0])) throw E('KeyError', `в множестве нет ${repr(a[0])}`); return null; });
      case 'discard': return bm(name, a => { o.del(a[0]); return null; });
      case 'update': return bm(name, a => { a.forEach(x => { for (const v of iter(x)) o.add(v); }); return null; });
      case 'pop': return bm(name, () => { const v = o.vals()[0]; if (v === undefined) throw E('KeyError', 'pop() из пустого множества'); o.del(v); return v; });
      case 'union': return bm(name, a => a.reduce((r, x) => binop('|', r, x instanceof PySet ? x : new PySet(iter(x))), new PySet(o.vals())));
      case 'intersection': return bm(name, a => a.reduce((r, x) => binop('&', r, x instanceof PySet ? x : new PySet(iter(x))), new PySet(o.vals())));
      case 'difference': return bm(name, a => a.reduce((r, x) => binop('-', r, x instanceof PySet ? x : new PySet(iter(x))), new PySet(o.vals())));
      case 'issubset': return bm(name, a => o.vals().every(v => contains(a[0], v)));
      case 'copy': return bm(name, () => new PySet(o.vals()));
      case 'clear': return bm(name, () => { o.m.clear(); return null; });
    }
    if (o instanceof PyFile) switch (name) {
      case 'read': return bm(name, () => o.rest().join(''));
      case 'readline': return bm(name, () => o.pos < o.lines.length ? o.lines[o.pos++] : '');
      case 'readlines': return bm(name, () => o.rest());
      case 'close': return bm(name, () => { o.closed = true; return null; });
    }
    return null;
  }

  /* ═════════════ ФЕРМА ═════════════ */
  // grow — сколько ходов растёт растение; soil — растёт только на вспаханной земле
  const ENT = {
    Grass: { ru: 'Трава', grow: 3, item: 'Hay', n: 1 },
    Bush: { ru: 'Куст', grow: 6, item: 'Wood', n: 1 },
    Tree: { ru: 'Дерево', grow: 40, item: 'Wood', n: 5 },
    Carrot: { ru: 'Морковь', grow: 6, item: 'Carrot', n: 1, soil: 1 },
    Pumpkin: { ru: 'Тыква', grow: 8, item: 'Pumpkin', n: 1, soil: 1 },
    Sunflower: { ru: 'Подсолнух', grow: 6, item: 'Power', n: 1, soil: 1 },
    Dead_Pumpkin: { ru: 'Сгнившая тыква' },
  };
  const ITEMS = { Hay: 'Сено', Wood: 'Древесина', Carrot: 'Морковь', Pumpkin: 'Тыквы', Power: 'Энергия' };
  const DIRS = { North: [0, 1, 'север'], East: [1, 0, 'восток'], South: [0, -1, 'юг'], West: [-1, 0, 'запад'] };
  const C = {
    Entities: Object.fromEntries(Object.keys(ENT).map(k => [k, new Const('Entities', k, ENT[k].ru)])),
    Items: Object.fromEntries(Object.keys(ITEMS).map(k => [k, new Const('Items', k, ITEMS[k])])),
    Grounds: { Grassland: new Const('Grounds', 'Grassland', 'трава'), Soil: new Const('Grounds', 'Soil', 'вспаханная земля') },
    Dirs: Object.fromEntries(Object.keys(DIRS).map(k => [k, new Const('Direction', k, DIRS[k][2])])),
  };
  function rng32(seed) {
    let a = seed >>> 0;
    return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }
  // неверный ответ в answer(): программа останавливается, уровень не пройден
  class WrongAnswer { constructor(given, n, got) { this.given = given; this.n = n; this.got = got; } }
  class World {
    constructor(lv, seed, data) {
      this.lv = lv; this.w = lv.w; this.h = lv.h; this.t = 0; this.x = 0; this.y = 0;
      this.items = { ...(lv.items || {}) }; this.rng = rng32(seed);           // в своей ферме урожай копится между запусками
      this.cells = Array.from({ length: this.w * this.h }, () => ({ g: 'grass', e: { type: 'Grass', at: -1e6 } }));
      this.data = data || null; this.solved = false;
      if (data && data.signs) data.signs.forEach((v, i) => { this.cells[i].sign = v; });
    }
    cell(x = this.x, y = this.y) { return this.cells[y * this.w + x]; }
    grow(type, x, y) {
      let g = (this.lv.grow && this.lv.grow[type]) ?? ENT[type].grow;
      if (type === 'Tree') {                                  // соседние деревья мешают друг другу расти
        let n = 0;
        for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
          const nx = x + dx, ny = y + dy;
          if (nx >= 0 && ny >= 0 && nx < this.w && ny < this.h && this.cell(nx, ny).e?.type === 'Tree') n++;
        }
        g *= 1 + n;
      }
      return g;
    }
    kind(x = this.x, y = this.y) {
      const e = this.cell(x, y).e;
      if (!e) return null;
      if (e.type === 'Pumpkin' && e.dies && this.t - e.at >= this.grow('Pumpkin', x, y)) return 'Dead_Pumpkin';
      return e.type;
    }
    progress(x, y) { const e = this.cell(x, y).e; if (!e) return 0; return Math.max(0, Math.min(1, (this.t - e.at) / Math.max(1, this.grow(e.type, x, y)))); }
    ripe(x = this.x, y = this.y) { const k = this.kind(x, y); return !!k && k !== 'Dead_Pumpkin' && this.t - this.cell(x, y).e.at >= this.grow(k, x, y); }
    put(c, type) {
      c.e = { type, at: this.t };
      if (type === 'Pumpkin') c.e.dies = this.rng() < 0.25;
      if (type === 'Sunflower') c.e.petals = 7 + Math.floor(this.rng() * 9);
    }
    clear(c) { c.e = null; if (c.g === 'grass') this.put(c, 'Grass'); }
    add(item, n) { this.items[item] = (this.items[item] || 0) + n * (this.lv.mul || 1); }
    done() { if (this.lv.answer) return this.solved; const g = this.lv.goal; return !!g && Object.keys(g).every(k => (this.items[k] || 0) >= g[k]); }
  }

  /* ── команды дрону: каждая — один ход ── */
  const GAME = ['harvest', 'can_harvest', 'move', 'get_world_size', 'plant', 'till', 'get_ground_type', 'get_pos_x', 'get_pos_y', 'get_entity_type', 'num_items', 'measure', 'scan', 'get_label', 'answer'];
  const FREE = new Set(['get_world_size', 'get_pos_x', 'get_pos_y', 'num_items']);
  function installGame(ip, w, lv, run) {
    for (const [k, v] of Object.entries(C.Dirs)) ip.builtins.set(k, v);
    ip.builtins.set('Entities', new NS('Entities', C.Entities));
    ip.builtins.set('Items', new NS('Items', C.Items));
    ip.builtins.set('Grounds', new NS('Grounds', C.Grounds));
    const act = (a, extra) => { ip.lastAct = ip.ops; w.t++; return { a, x: w.x, y: w.y, ...extra }; };
    const impl = {
      *harvest(args) {
        needArgs('harvest', args, 0);
        const c = w.cell(), k = w.kind();
        let got = null;
        if (k && w.ripe()) {
          const d = ENT[k];
          let n = d.n;
          if (k === 'Sunflower') {
            const max = Math.max(...w.cells.filter(x => x.e && x.e.type === 'Sunflower').map(x => x.e.petals));
            n = c.e.petals >= max ? 5 : 1;
          }
          w.add(d.item, n); got = { item: d.item, n };
        } else if (k && k !== 'Dead_Pumpkin') run.note('unripe', 'Растение ещё не созрело и погибло. Перед harvest() проверяйте can_harvest()');
        if (c.e) w.clear(c);
        yield act('harvest', { got });
        return !!got;
      },
      *can_harvest(args) { needArgs('can_harvest', args, 0); const r = w.ripe(); yield act('look'); return r; },
      *move(args) {
        needArgs('move', args, 1);
        const d = args[0];
        if (!(d instanceof Const) || d.group !== 'Direction') throw E('TypeError', 'move() ждёт направление: North, East, South или West');
        const [dx, dy] = DIRS[d.name], nx = (w.x + dx + w.w) % w.w, ny = (w.y + dy + w.h) % w.h;
        const wrap = nx !== w.x + dx || ny !== w.y + dy;
        w.x = nx; w.y = ny;
        yield act('move', { wrap });
        return true;
      },
      get_world_size(args) { needArgs('get_world_size', args, 0); return w.w; },
      *plant(args) {
        needArgs('plant', args, 1);
        const p = args[0];
        if (!(p instanceof Const) || p.group !== 'Entities' || p.name === 'Dead_Pumpkin') throw E('TypeError', 'plant() ждёт растение, например plant(Entities.Bush)');
        const c = w.cell();
        let ok = true;
        if (lv.plants && !lv.plants.includes(p.name)) {
          const u = UPGRADES.find(x => x.gives && (x.gives.plants || []).includes(p.name));
          throw E('LockedError', `растение «${ENT[p.name].ru}» пока закрыто: купите улучшение «${u ? u.title : '?'}»`);
        }
        if (ENT[p.name].soil && c.g !== 'soil') { ok = false; run.note('soil', `${ENT[p.name].ru} растёт только на вспаханной земле: сначала till()`); }
        else if (c.e && c.e.type !== 'Grass') ok = false;
        if (ok) w.put(c, p.name);
        yield act('plant', { ok });
        return ok;
      },
      *till(args) {
        needArgs('till', args, 0);
        const c = w.cell();
        c.g = c.g === 'grass' ? 'soil' : 'grass';
        c.e = null; w.clear(c);
        yield act('till');
        return null;
      },
      *get_ground_type(args) { needArgs('get_ground_type', args, 0); const g = w.cell().g; yield act('look'); return g === 'soil' ? C.Grounds.Soil : C.Grounds.Grassland; },
      get_pos_x(args) { needArgs('get_pos_x', args, 0); return w.x; },
      get_pos_y(args) { needArgs('get_pos_y', args, 0); return w.y; },
      *get_entity_type(args) { needArgs('get_entity_type', args, 0); const k = w.kind(); yield act('look'); return k ? C.Entities[k] : null; },
      num_items(args) {
        needArgs('num_items', args, 1);
        if (!(args[0] instanceof Const) || args[0].group !== 'Items') throw E('TypeError', 'num_items() ждёт вид урожая, например num_items(Items.Hay)');
        return w.items[args[0].name] || 0;
      },
      *scan(args) { needArgs('scan', args, 0); const v = w.cell().sign; yield act('look'); return v === undefined ? null : v; },
      *get_label(args) { needArgs('get_label', args, 0); yield act('look'); return (w.data && w.data.label) || ''; },
      *answer(args) {
        const exp = (w.data && w.data.expect) || [];
        if (!lv.answer) throw E('NameError', 'answer() нужна только на уровнях-задачах');
        const ok = args.length === exp.length && args.every((v, i) => eq(v, exp[i]));
        yield act('answer', { ok });
        if (!ok) throw new WrongAnswer(args.map(repr).join(', '), exp.length, args.length);
        w.solved = true;
        return null;
      },
      *measure(args) { needArgs('measure', args, 0); const e = w.cell().e; yield act('look'); return e && e.type === 'Sunflower' ? e.petals : null; },
    };
    for (const name of GAME) {
      const open = !lv.api || lv.api.includes(name);
      if (!open) {
        const at = LEVELS.find(l => l.api && l.api.includes(name)), u = UPGRADES.find(x => x.gives && (x.gives.api || []).includes(name));
        const when = lv.sandbox ? `после улучшения «${u ? u.title : '?'}»` : at ? `на уровне ${at.id}` : 'позже';
        ip.builtins.set(name, new Bi(name, () => { throw E('NameError', `команда ${name}() откроется ${when}`); }));
      } else ip.builtins.set(name, new Bi(name, impl[name], impl[name].constructor.name === 'GeneratorFunction'));
    }
  }

  /* ── запуск программы на уровне: step() — до следующего хода дрона ── */
  class Run {
    constructor(lv, code, opt = {}) {
      this.lv = lv; this.out = []; this.notes = new Set();
      this.data = opt.data || (lv.gen ? lv.gen(rng32((opt.seed ?? lv.id * 7919 + 13) + 77)) : null);
      this.world = new World(lv, opt.seed ?? lv.id * 7919 + 13, this.data);
      // уровень-задача: программа может долго считать без команд дрону, но не бесконечно
      this.ip = new Interp({ print: s => this.print(s), rng: this.world.rng, files: (this.data && this.data.files) || {}, idleOps: lv.answer ? Infinity : 0, maxOps: opt.maxOps || (lv.answer ? 2500000 : Infinity) });
      for (const [k, v] of Object.entries((this.data && this.data.vars) || {})) this.ip.globals.set(k, v);
      installGame(this.ip, this.world, lv, this);
      this.state = 'run';
      try { this.gen = this.ip.exec(parse(code)); }
      catch (e) { this.fail(e); }
    }
    print(s) { if (this.out.length < 400) this.out.push({ k: 'out', s }); }
    note(key, s) { if (!this.notes.has(key)) { this.notes.add(key); this.out.push({ k: 'note', s }); } }
    fail(e) {
      this.state = 'error';
      if (e instanceof WrongAnswer) { this.state = 'wrong'; this.wrong = e; return; }
      if (e instanceof PyError) { this.error = e; if (e.line == null) e.line = this.ip.line; }
      else if (e instanceof RangeError) this.error = E('RecursionError', 'слишком глубокая рекурсия', this.ip.line);
      else if (e === BREAK || e === CONT || e instanceof Ret) this.error = E('SyntaxError', 'break, continue или return не на своём месте', this.ip.line);
      else { this.error = E('InternalError', 'что-то пошло не так в самой игре. Перезагрузите страницу', this.ip.line); if (typeof console !== 'undefined') console.error(e); }
    }
    step() {
      if (this.state !== 'run') return null;
      let r;
      try { r = this.gen.next(); } catch (e) { this.fail(e); return null; }
      if (r.done) { this.state = this.world.done() ? 'win' : 'end'; return null; }
      if (r.value === IDLE) return r.value;
      if (this.world.done()) this.state = 'win';
      else if (this.world.t >= this.lv.limit) this.state = 'limit';
      return r.value;
    }
  }
  // без экрана: прогнать программу до конца (тест уровней)
  function simulate(lv, code, opt) {
    const r = new Run(lv, code, opt);
    while (r.state === 'run') r.step();
    return { state: r.state, t: r.world.t, items: r.world.items, error: r.error && `${r.error.type} (строка ${r.error.line}): ${r.error.message}`, out: r.out, wrong: r.wrong && r.wrong.given, data: r.data };
  }

  /* ═════════════ УРОВНИ ═════════════ */
  const L = (s) => s.replace(/^\n/, '').replace(/\n\s*$/, '\n');
  const LEVELS = [
    {
      id: 1, title: 'Первый урожай', concept: 'вызов функции', w: 1, h: 1, goal: { Hay: 1 }, limit: 50, par: 1, api: ['harvest'],
      text: 'Дрон стоит на клетке со спелой травой. Программа — это команды, которые он выполнит по порядку. Команда <code>harvest()</code> собирает урожай с клетки под дроном.',
      learn: ['Вызов функции', 'harvest()', 'Имя функции и круглые скобки. Без скобок Python не поймёт, что функцию нужно выполнить.'],
      start: '# Напишите команду под этой строкой и нажмите «Запустить»\n',
      hint: 'Одна строка: <code>harvest()</code>',
      solution: 'harvest()\n',
    },
    {
      id: 2, title: 'Снова и снова', concept: 'цикл while', w: 1, h: 1, goal: { Hay: 10 }, limit: 200, par: 10, api: ['harvest'], grow: { Grass: 1 },
      text: 'Трава здесь отрастает за один ход. Соберите 10 сена. Можно написать <code>harvest()</code> десять раз, но программисты так не делают: повторять команды умеет цикл.',
      learn: ['Цикл while', 'while True:\n    harvest()', 'Всё, что написано с отступом под <code>while True:</code>, повторяется снова и снова. Отступ — 4 пробела (клавиша Tab). Игра остановит дрона, когда цель выполнена.'],
      start: '',
      hint: 'Две строки: <code>while True:</code> и под ней с отступом <code>harvest()</code>',
      solution: 'while True:\n    harvest()\n',
    },
    {
      id: 3, title: 'Шаг в сторону', concept: 'команды по порядку', w: 3, h: 1, goal: { Hay: 12 }, limit: 400, par: 0, api: ['harvest', 'move'],
      text: 'Теперь у дрона три клетки, а трава растёт 3 хода. Если рвать её на одном месте, она не успеет вырасти. Собирайте и переходите на соседнюю клетку.',
      learn: ['Направления', 'move(East)', 'В скобки передают направление: <code>North</code> — вверх, <code>South</code> — вниз, <code>East</code> — вправо, <code>West</code> — влево. Дойдя до края поля, дрон выходит с другой стороны.'],
      start: 'while True:\n    harvest()\n',
      hint: 'В цикле две команды: <code>harvest()</code>, затем <code>move(East)</code>',
      solution: 'while True:\n    harvest()\n    move(East)\n',
    },
    {
      id: 4, title: 'Сначала проверь', concept: 'условие if', w: 1, h: 1, goal: { Hay: 5 }, limit: 200, par: 0, api: ['harvest', 'can_harvest'], grow: { Grass: 4 },
      text: 'Эта программа уже написана, но сено не копится. Запустите её и посмотрите, что происходит с травой. Незрелое растение погибает, если его сорвать: нужно дождаться, пока оно вырастет.',
      learn: ['Условие if', 'if can_harvest():\n    harvest()', '<code>can_harvest()</code> отвечает <code>True</code> или <code>False</code>: созрело ли растение. Команды с отступом под <code>if</code> выполняются, только когда ответ <code>True</code>.'],
      start: 'while True:\n    harvest()\n',
      hint: 'Внутри цикла: <code>if can_harvest():</code>, а под ним ещё глубже <code>harvest()</code> — это 8 пробелов',
      solution: 'while True:\n    if can_harvest():\n        harvest()\n',
    },
    {
      id: 5, title: 'Обход поля', concept: 'цикл for и range', w: 4, h: 4, goal: { Hay: 40 }, limit: 1500, par: 0, api: ['harvest', 'can_harvest', 'move', 'get_world_size'], grow: { Grass: 20 },
      text: 'Поле 4×4, трава растёт 20 ходов. Обойдите всё поле: пройдите столбец вверх, шагните вправо, и так каждый столбец.',
      learn: ['Цикл for', 'for i in range(4):\n    move(North)', '<code>range(4)</code> — это числа 0, 1, 2, 3, поэтому тело цикла выполнится 4 раза. <code>get_world_size()</code> возвращает размер поля, чтобы не писать 4 вручную. Цикл внутри цикла обойдёт все клетки.'],
      start: 'while True:\n    for i in range(get_world_size()):\n        # здесь один столбец: проверить, собрать, шагнуть вверх\n        move(North)\n    move(East)\n',
      hint: 'Внутри <code>for</code>: <code>if can_harvest():</code> → <code>harvest()</code>, затем <code>move(North)</code>. После цикла — <code>move(East)</code>. Внешний цикл уже есть: <code>while True</code>.',
      solution: 'while True:\n    for i in range(get_world_size()):\n        if can_harvest():\n            harvest()\n        move(North)\n    move(East)\n',
    },
    {
      id: 6, title: 'Кусты', concept: 'аргументы функции', w: 4, h: 4, goal: { Wood: 24 }, limit: 2000, par: 0, api: ['harvest', 'can_harvest', 'move', 'get_world_size', 'plant'],
      text: 'Из кустов получается древесина. Сажайте куст на каждую клетку, а созревшие — собирайте. Куст растёт 6 ходов.',
      learn: ['Значение как аргумент', 'plant(Entities.Bush)', 'Функции <code>plant()</code> нужно сказать, что сажать. <code>Entities</code> — набор растений: <code>Entities.Bush</code> — куст, <code>Entities.Grass</code> — трава. Если клетка занята, <code>plant()</code> ничего не делает и возвращает <code>False</code>.'],
      start: 'n = get_world_size()\nwhile True:\n    for i in range(n):\n        for j in range(n):\n            if can_harvest():\n                harvest()\n            move(North)\n        move(East)\n',
      hint: 'После сбора урожая (на том же уровне отступа, что и <code>if</code>) добавьте <code>plant(Entities.Bush)</code>',
      solution: 'n = get_world_size()\nwhile True:\n    for i in range(n):\n        for j in range(n):\n            if can_harvest():\n                harvest()\n            plant(Entities.Bush)\n            move(North)\n        move(East)\n',
    },
    {
      id: 7, title: 'Морковь', concept: 'сравнение ==', w: 4, h: 4, goal: { Carrot: 30 }, limit: 2500, par: 0, api: ['harvest', 'can_harvest', 'move', 'get_world_size', 'plant', 'till', 'get_ground_type'],
      text: 'Морковь растёт только на вспаханной земле. Команда <code>till()</code> вспахивает траву, а если позвать её на пашне ещё раз — вернёт траву. Поэтому пахать нужно, только если под дроном трава.',
      learn: ['Сравнение ==', 'if get_ground_type() == Grounds.Grassland:\n    till()', 'Два знака <code>==</code> спрашивают «равно ли?», а один <code>=</code> кладёт значение в переменную. <code>Grounds.Grassland</code> — трава, <code>Grounds.Soil</code> — пашня.'],
      start: 'n = get_world_size()\nwhile True:\n    for i in range(n):\n        for j in range(n):\n            if can_harvest():\n                harvest()\n            plant(Entities.Carrot)\n            move(North)\n        move(East)\n',
      hint: 'Перед <code>plant(Entities.Carrot)</code>: если земля под дроном — трава, вызовите <code>till()</code>',
      solution: 'n = get_world_size()\nwhile True:\n    for i in range(n):\n        for j in range(n):\n            if get_ground_type() == Grounds.Grassland:\n                till()\n            if can_harvest():\n                harvest()\n            plant(Entities.Carrot)\n            move(North)\n        move(East)\n',
    },
    {
      id: 8, title: 'Шахматный лес', concept: 'остаток %, else', w: 4, h: 4, goal: { Wood: 120 }, limit: 330, par: 0, api: ['harvest', 'can_harvest', 'move', 'get_world_size', 'plant', 'get_pos_x', 'get_pos_y'],
      text: 'Дерево даёт 5 древесины, но растёт 40 ходов, а каждое соседнее дерево (слева, справа, сверху или снизу) добавляет ещё 40. Сажайте деревья в шахматном порядке, а между ними — кусты.',
      learn: ['Остаток от деления и else', 'if (x + y) % 2 == 0:\n    plant(Entities.Tree)\nelse:\n    plant(Entities.Bush)', '<code>%</code> — остаток от деления: <code>5 % 2</code> равно 1. У клеток шахматной доски сумма координат то чётная, то нечётная. <code>get_pos_x()</code> и <code>get_pos_y()</code> — координаты дрона, (0, 0) — левый нижний угол. Ветка <code>else</code> выполняется, когда условие ложно.'],
      start: 'n = get_world_size()\nwhile True:\n    for i in range(n):\n        for j in range(n):\n            if can_harvest():\n                harvest()\n            x = get_pos_x()\n            y = get_pos_y()\n            # дерево или куст?\n            move(North)\n        move(East)\n',
      hint: 'После <code>y = get_pos_y()</code>: <code>if (x + y) % 2 == 0:</code> — дерево, <code>else:</code> — куст',
      solution: 'n = get_world_size()\nwhile True:\n    for i in range(n):\n        for j in range(n):\n            if can_harvest():\n                harvest()\n            x = get_pos_x()\n            y = get_pos_y()\n            if (x + y) % 2 == 0:\n                plant(Entities.Tree)\n            else:\n                plant(Entities.Bush)\n            move(North)\n        move(East)\n',
    },
    {
      id: 9, title: 'Свои функции', concept: 'def и return', w: 6, h: 6, goal: { Hay: 40, Wood: 40, Carrot: 40 }, limit: 4000, par: 0, api: ['harvest', 'can_harvest', 'move', 'get_world_size', 'plant', 'till', 'get_ground_type', 'get_pos_x', 'get_pos_y'],
      text: 'Нужно всё сразу: сено, древесина и морковь — по 40. Разделите поле на полосы: в левых столбцах трава, в средних кусты, в правых морковь. Программа станет длинной — разложите её на свои функции.',
      learn: ['Своя функция', 'def crop():\n    if get_pos_x() < 2:\n        return Entities.Grass\n    return Entities.Bush', '<code>def</code> создаёт новую команду. <code>return</code> возвращает ответ туда, где функцию позвали, и сразу её завершает. Параметры в скобках — значения, которые функция получает: <code>def tend(plant_type):</code>.'],
      start: 'n = get_world_size()\n\ndef crop():\n    # какое растение нужно в столбце get_pos_x()?\n    return Entities.Grass\n\ndef tend(kind):\n    if can_harvest():\n        harvest()\n    # вспахать для моркови и посадить kind\n\nwhile True:\n    for i in range(n):\n        for j in range(n):\n            tend(crop())\n            move(North)\n        move(East)\n',
      hint: 'В <code>crop()</code>: <code>x &lt; 2</code> — трава, <code>x &lt; 4</code> — куст, иначе морковь. В <code>tend()</code>: если <code>kind == Entities.Carrot</code> и земля — трава, вызовите <code>till()</code>; если <code>kind != Entities.Grass</code>, посадите <code>plant(kind)</code>.',
      solution: 'n = get_world_size()\n\ndef crop():\n    x = get_pos_x()\n    if x < 2:\n        return Entities.Grass\n    if x < 4:\n        return Entities.Bush\n    return Entities.Carrot\n\ndef tend(kind):\n    if can_harvest():\n        harvest()\n    if kind == Entities.Carrot and get_ground_type() == Grounds.Grassland:\n        till()\n    if kind != Entities.Grass:\n        plant(kind)\n\nwhile True:\n    for i in range(n):\n        for j in range(n):\n            tend(crop())\n            move(North)\n        move(East)\n',
    },
    {
      id: 10, title: 'Тыквы', concept: 'elif', w: 5, h: 5, goal: { Pumpkin: 100 }, limit: 3000, par: 0, api: ['harvest', 'can_harvest', 'move', 'get_world_size', 'plant', 'till', 'get_ground_type', 'get_pos_x', 'get_pos_y', 'get_entity_type'],
      text: 'Тыквы растут на пашне 8 ходов, но примерно каждая четвёртая сгнивает. Сгнившая тыква занимает клетку, и новая на её месте не посадится — её нужно убрать: <code>harvest()</code> расчищает клетку.',
      learn: ['elif', 'k = get_entity_type()\nif k == Entities.Dead_Pumpkin:\n    harvest()\nelif can_harvest():\n    harvest()', '<code>elif</code> — «а иначе, если». Python проверяет условия сверху вниз и выполняет первую подходящую ветку. <code>get_entity_type()</code> сообщает, что растёт под дроном, или <code>None</code>, если клетка пуста.'],
      start: 'n = get_world_size()\nwhile True:\n    for i in range(n):\n        for j in range(n):\n            if get_ground_type() == Grounds.Grassland:\n                till()\n            if can_harvest():\n                harvest()\n            plant(Entities.Pumpkin)\n            move(North)\n        move(East)\n',
      hint: 'Перед <code>if can_harvest()</code> проверьте, не сгнила ли тыква: <code>if get_entity_type() == Entities.Dead_Pumpkin:</code> → <code>harvest()</code>, а проверку спелости сделайте веткой <code>elif</code>',
      solution: 'n = get_world_size()\nwhile True:\n    for i in range(n):\n        for j in range(n):\n            if get_ground_type() == Grounds.Grassland:\n                till()\n            if get_entity_type() == Entities.Dead_Pumpkin:\n                harvest()\n            elif can_harvest():\n                harvest()\n            plant(Entities.Pumpkin)\n            move(North)\n        move(East)\n',
    },
    {
      id: 11, title: 'Подсолнухи', concept: 'списки и сортировка', w: 4, h: 4, goal: { Power: 200 }, limit: 620, par: 0, api: ['harvest', 'can_harvest', 'move', 'get_world_size', 'plant', 'till', 'get_ground_type', 'get_pos_x', 'get_pos_y', 'get_entity_type', 'measure'],
      text: 'Подсолнух даёт энергию: 5, если на поле нет подсолнуха с бо́льшим числом лепестков, и 1 в остальных случаях. <code>measure()</code> считает лепестки под дроном. Запишите подсолнухи в список, отсортируйте и собирайте, начиная с самого большого.',
      learn: ['Списки', 'cells = []\ncells.append([measure(), get_pos_x(), get_pos_y()])\ncells.sort(reverse=True)\nfor c in cells:\n    print(c[0])', 'Список хранит много значений по порядку. <code>append()</code> добавляет в конец, <code>sort(reverse=True)</code> сортирует от большего к меньшему (списки сравниваются по первому элементу), <code>c[1]</code> — элемент с номером 1, счёт с нуля.'],
      start: 'n = get_world_size()\n\ndef goto(x, y):\n    while get_pos_x() != x:\n        move(East)\n    while get_pos_y() != y:\n        move(North)\n\ndef plant_all():\n    for i in range(n):\n        for j in range(n):\n            if get_ground_type() == Grounds.Grassland:\n                till()\n            plant(Entities.Sunflower)\n            move(North)\n        move(East)\n\nwhile True:\n    plant_all()\n    cells = []\n    # обойдите поле и запишите [лепестки, x, y] каждого подсолнуха\n    # отсортируйте и соберите по порядку: goto(...), дождаться can_harvest(), harvest()\n',
      hint: 'Обход как в <code>plant_all()</code>, только вместо посадки — <code>cells.append([measure(), get_pos_x(), get_pos_y()])</code>. Потом <code>cells.sort(reverse=True)</code> и <code>for c in cells:</code> → <code>goto(c[1], c[2])</code>, <code>while not can_harvest(): pass</code>, <code>harvest()</code>.',
      solution: 'n = get_world_size()\n\ndef goto(x, y):\n    while get_pos_x() != x:\n        move(East)\n    while get_pos_y() != y:\n        move(North)\n\ndef plant_all():\n    for i in range(n):\n        for j in range(n):\n            if get_ground_type() == Grounds.Grassland:\n                till()\n            plant(Entities.Sunflower)\n            move(North)\n        move(East)\n\nwhile True:\n    plant_all()\n    cells = []\n    for i in range(n):\n        for j in range(n):\n            cells.append([measure(), get_pos_x(), get_pos_y()])\n            move(North)\n        move(East)\n    cells.sort(reverse=True)\n    for c in cells:\n        goto(c[1], c[2])\n        while not can_harvest():\n            pass\n        harvest()\n',
    },
    {
      id: 12, title: 'Своя ферма', concept: 'дерево улучшений', w: 3, h: 3, goal: null, limit: 1e7, par: 0, need: 6, sandbox: true,
      text: 'Здесь урожай не пропадает: всё собранное копится в амбаре между запусками. Тратьте его на улучшения (кнопка «+» справа вверху): новые команды, растения, поле побольше, удобрение. Начинаете с поля 3×3 и травы.',
      learn: ['Цикл, который не кончается', 'while True:\n    for i in range(get_world_size()):\n        if can_harvest():\n            harvest()\n        move(North)\n    move(East)', 'Программа работает, пока вы её не остановите кнопкой ■. Амбар сохраняется сам. Купили улучшение — допишите программу, чтобы им пользоваться.'],
      start: '# Своя ферма: урожай копится в амбаре, за него покупаются улучшения (кнопка «+»)\nwhile True:\n    if can_harvest():\n        harvest()\n    move(North)\n',
      hint: 'Сначала копите сено на «Посадку» и «Расширение поля». Потом кусты дают древесину для деревьев и вспашки.',
      solution: null,
    },
  ];
  /* ═════════════ УРОВНИ-ЗАДАЧИ: темы Python и задания ЕГЭ, которые решаются кодом ═════════════
     gen(r) — данные на один заход (r — генератор случайных чисел): таблички signs, строка label, файлы files,
     переменные vars, которые уже есть в программе, и ответ expect. Ответ считается здесь же на JS, независимо от решения */
  const ri = (r, a, b) => a + Math.floor(r() * (b - a + 1));
  const pickR = (r, a) => a[Math.floor(r() * a.length)];
  const strR = (r, n, abc) => Array.from({ length: n }, () => pickR(r, abc)).join('');
  const digSum = n => String(n).split('').reduce((a, c) => a + +c, 0);
  const divCount = n => { let k = 0; for (let d = 1; d * d <= n; d++) if (n % d === 0) k += d * d === n ? 1 : 2; return k; };
  const until = (r, make, ok) => { for (let i = 0; i < 200; i++) { const d = make(r); if (ok(d)) return d; } throw new Error('данные уровня не сгенерировались'); };
  const DRONE = ['move', 'get_world_size', 'get_pos_x', 'get_pos_y'];
  const LOGIC = [
    ['(x → y) ∧ (¬z ∨ w)', (x, y, z, w) => (!x || y) && (!z || w)],
    ['(x ∨ ¬y) ≡ (z → w)', (x, y, z, w) => (x || !y) === (!z || w)],
    ['¬(x ∧ y) ∨ (z ≡ w)', (x, y, z, w) => !(x && y) || (z === w)],
    ['(x → (y ∧ ¬w)) ∧ (z ∨ y)', (x, y, z, w) => (!x || (y && !w)) && (z || y)],
    ['((x → z) ∨ ¬y) ∧ (w ≡ x)', (x, y, z, w) => ((!x || z) || !y) && (w === x)],
    ['(y → x) ∧ ¬(z ∧ ¬w) ∧ (x ∨ z)', (x, y, z, w) => (!y || x) && !(z && !w) && (x || z)],
  ];
  const VOWELS = 'АЕЁИОУЫЭЮЯ';
  const TASKS = [
    {
      id: 13, title: 'Перепись грядок', concept: 'переменная-накопитель', w: 4, h: 4, answer: true, limit: 2000, api: [...DRONE, 'scan', 'answer'],
      gen: r => { const signs = Array.from({ length: 16 }, () => ri(r, 1, 50)); return { signs, expect: [signs.reduce((a, b) => a + b, 0)] }; },
      text: 'На каждой грядке стоит табличка — сколько мешков с неё собрали. Обойдите поле, читайте таблички командой <code>scan()</code> и сдайте общую сумму: <code>answer(сумма)</code>.',
      learn: ['Переменная-накопитель', 'total = 0\ntotal = total + scan()\ntotal += scan()     # то же самое\nanswer(total)', 'Переменная хранит значение между шагами цикла. Начните с нуля и прибавляйте каждое число. <code>total += x</code> — короткая запись <code>total = total + x</code>.'],
      start: 'n = get_world_size()\ntotal = 0\nfor i in range(n):\n    for j in range(n):\n        # прочитайте табличку и прибавьте к total\n        move(North)\n    move(East)\nanswer(total)\n',
      hint: 'В пустую строку: <code>total += scan()</code>',
      solution: 'n = get_world_size()\ntotal = 0\nfor i in range(n):\n    for j in range(n):\n        total += scan()\n        move(North)\n    move(East)\nanswer(total)\n',
    },
    {
      id: 14, title: 'Лучшая грядка', concept: 'счётчик, максимум, and', w: 5, h: 5, answer: true, limit: 2000, api: [...DRONE, 'scan', 'answer'],
      gen: r => until(r, r => { const signs = Array.from({ length: 25 }, () => ri(r, 10, 999)); const v = signs.filter(x => x % 3 === 0 && x % 9 !== 0); return { signs, expect: [v.length, Math.max(...v)] }; }, d => d.expect[0] >= 2),
      text: 'Найдите таблички, числа на которых делятся на 3, но не делятся на 9. Сдайте, сколько их, и наибольшее из них: <code>answer(количество, наибольшее)</code>.',
      learn: ['Счётчик и максимум', 'cnt = 0\nbest = 0\nv = scan()\nif v % 3 == 0 and v % 9 != 0:\n    cnt += 1\n    best = max(best, v)', '<code>v % 3 == 0</code> — «делится на 3 без остатка», <code>!=</code> — «не равно», <code>and</code> — оба условия сразу. Счётчик растёт на 1, максимум обновляет <code>max()</code>. Так считают в задании 17.'],
      start: 'n = get_world_size()\ncnt = 0\nbest = 0\nfor i in range(n):\n    for j in range(n):\n        v = scan()\n        # проверьте v и обновите cnt и best\n        move(North)\n    move(East)\nanswer(cnt, best)\n',
      hint: 'После <code>v = scan()</code>: <code>if v % 3 == 0 and v % 9 != 0:</code>, внутри <code>cnt += 1</code> и <code>best = max(best, v)</code>',
      solution: 'n = get_world_size()\ncnt = 0\nbest = 0\nfor i in range(n):\n    for j in range(n):\n        v = scan()\n        if v % 3 == 0 and v % 9 != 0:\n            cnt += 1\n            best = max(best, v)\n        move(North)\n    move(East)\nanswer(cnt, best)\n',
    },
    {
      id: 15, title: 'Цифры на бирках', concept: 'цифры числа: % 10 и // 10', w: 4, h: 4, answer: true, limit: 2000, api: [...DRONE, 'scan', 'answer'],
      gen: r => { const signs = Array.from({ length: 16 }, () => ri(r, 100, 99999)); return { signs, expect: [signs.filter(v => digSum(v) > 20).length] }; },
      text: 'У скольких табличек сумма цифр числа больше 20? Сдайте ответ: <code>answer(количество)</code>.',
      learn: ['Цифры числа', 'n = 4705\ns = 0\nwhile n > 0:\n    s += n % 10\n    n //= 10\nprint(s)   # 16', '<code>n % 10</code> — последняя цифра, <code>n // 10</code> — число без неё. Деление <code>/</code> дало бы дробь 470.5, поэтому для цифр нужно <code>//</code>. Цикл <code>while n &gt; 0</code> перебирает все цифры — так разбирают числа в заданиях 5, 14 и 25.'],
      start: 'n = get_world_size()\ncount = 0\nfor i in range(n):\n    for j in range(n):\n        v = scan()\n        # посчитайте сумму цифр v\n        move(North)\n    move(East)\nanswer(count)\n',
      hint: 'Заведите <code>s = 0</code>, затем <code>while v &gt; 0:</code> → <code>s += v % 10</code>, <code>v //= 10</code>. После цикла: <code>if s &gt; 20: count += 1</code>',
      solution: 'n = get_world_size()\ncount = 0\nfor i in range(n):\n    for j in range(n):\n        v = scan()\n        s = 0\n        while v > 0:\n            s += v % 10\n            v //= 10\n        if s > 20:\n            count += 1\n        move(North)\n    move(East)\nanswer(count)\n',
    },
    {
      id: 16, title: 'Делители', concept: 'range, break, math.isqrt', w: 3, h: 3, answer: true, limit: 100, api: ['answer'],
      gen: r => { const L = ri(r, 2000, 6000), Rr = L + 1000, v = []; for (let n = L; n <= Rr; n++) if (divCount(n) === 4) v.push(n); return { vars: { L, R: Rr }, expect: [v.length, v[v.length - 1]] }; },
      text: d => `Ящики раскладывают по полкам поровну. Найдите среди чисел от ${d.vars.L} до ${d.vars.R} те, у которых ровно четыре делителя (вместе с 1 и самим числом). Сдайте, сколько их, и наибольшее: <code>answer(количество, наибольшее)</code>.`,
      learn: ['Делители и break', 'import math\nk = 0\nfor d in range(1, math.isqrt(n) + 1):\n    if n % d == 0:\n        k += 1 if d * d == n else 2\n    if k > 4:\n        break', 'Делители ходят парами: d и n // d, поэтому хватит перебрать d до корня из n — <code>math.isqrt(n)</code>. <code>range(a, b)</code> не включает b, отсюда «+ 1». <code>break</code> прерывает цикл, когда делителей уже больше, чем нужно. Так решают задание 25.'],
      start: 'import math\n\ncount = 0\nbiggest = 0\nfor n in range(L, R + 1):\n    # посчитайте делители n\n    pass\nanswer(count, biggest)\n',
      hint: 'Внутри цикла по n: <code>k = 0</code>, перебор d как в примере, затем <code>if k == 4: count += 1; biggest = n</code>',
      solution: 'import math\n\ncount = 0\nbiggest = 0\nfor n in range(L, R + 1):\n    k = 0\n    for d in range(1, math.isqrt(n) + 1):\n        if n % d == 0:\n            k += 1 if d * d == n else 2\n        if k > 4:\n            break\n    if k == 4:\n        count += 1\n        biggest = n\nanswer(count, biggest)\n',
    },
    {
      id: 17, title: 'Соседние грядки', concept: 'список, append, пары соседей', w: 12, h: 1, answer: true, limit: 2000, api: [...DRONE, 'scan', 'answer'],
      gen: r => until(r, r => {
        const signs = Array.from({ length: 12 }, () => ri(r, 1, 100)); let c = 0, m = 0;
        for (let i = 0; i < 11; i++) { const a = signs[i], b = signs[i + 1]; if ((a % 2 === 0) !== (b % 2 === 0) && a + b > 100) { c++; m = Math.max(m, a + b); } }
        return { signs, expect: [c, m] };
      }, d => d.expect[0] >= 1),
      text: 'Грядки стоят в один ряд. Найдите пары соседних табличек, в которых ровно одно число чётное, а сумма пары больше 100. Сдайте количество таких пар и наибольшую сумму: <code>answer(количество, сумма)</code>.',
      learn: ['Список и соседи', 'a = []\nfor i in range(get_world_size()):\n    a.append(scan())\n    move(East)\nfor i in range(len(a) - 1):\n    print(a[i], a[i + 1])', 'Сначала соберите числа в список <code>append()</code>, потом перебирайте пары <code>a[i]</code>, <code>a[i + 1]</code> — до <code>len(a) - 1</code>, иначе выйдете за край. «Ровно одно чётное»: <code>(a % 2 == 0) != (b % 2 == 0)</code>. Главный приём задания 17.'],
      start: 'a = []\nfor i in range(get_world_size()):\n    a.append(scan())\n    move(East)\nprint(a)\n\ncount = 0\nbest = 0\n# переберите пары соседей\nanswer(count, best)\n',
      hint: '<code>for i in range(len(a) - 1):</code> → <code>x, y = a[i], a[i + 1]</code>, условие <code>(x % 2 == 0) != (y % 2 == 0) and x + y &gt; 100</code>',
      solution: 'a = []\nfor i in range(get_world_size()):\n    a.append(scan())\n    move(East)\n\ncount = 0\nbest = 0\nfor i in range(len(a) - 1):\n    x, y = a[i], a[i + 1]\n    if (x % 2 == 0) != (y % 2 == 0) and x + y > 100:\n        count += 1\n        best = max(best, x + y)\nanswer(count, best)\n',
    },
    {
      id: 18, title: 'Метки сортов', concept: 'строки: len, индексы, count', w: 3, h: 3, answer: true, limit: 100, api: ['get_label', 'answer'],
      gen: r => { const s = strR(r, ri(r, 40, 60), 'BCGPT'); return { label: s, expect: [s.length, s.split('P').length - 1, s[s.length - 1]] }; },
      text: 'На амбаре табличка с метками сортов: B — куст, C — морковь, G — трава, P — тыква, T — дерево. Прочитайте её командой <code>get_label()</code> и сдайте длину строки, сколько в ней букв P и последнюю букву: <code>answer(длина, количество, буква)</code>.',
      learn: ['Строки', "s = get_label()\nprint(len(s))\nprint(s[0], s[-1])\nprint(s.count('P'))", "<code>len(s)</code> — длина, <code>s[0]</code> — первый символ, <code>s[-1]</code> — последний (счёт с конца). <code>s.count('P')</code> — сколько раз встречается. <code>print()</code> показывает в журнале, что лежит в переменной."],
      start: 's = get_label()\nprint(s)\n',
      hint: "<code>answer(len(s), s.count('P'), s[-1])</code>",
      solution: "s = get_label()\nanswer(len(s), s.count('P'), s[-1])\n",
    },
    {
      id: 19, title: 'Самая длинная полоса', concept: 'поиск ошибок в цикле', w: 3, h: 3, answer: true, limit: 100, api: ['get_label', 'answer'],
      gen: r => {
        let s = strR(r, 300, 'BCGPTGG'), m = 0, c = 0;
        for (const ch of s) { c = ch === 'G' ? c + 1 : 0; m = Math.max(m, c); }
        s += 'C' + 'G'.repeat(m + ri(r, 1, 3));                   // самая длинная полоса — в конце строки
        return { label: s, expect: [s.length - s.lastIndexOf('C') - 1] };
      },
      text: 'На табличке длинная строка меток. Найдите самую длинную полосу подряд идущих букв G. Программа уже написана, но в ней ошибка — ответ получается неверный. Найдите и исправьте её.',
      learn: ['Поиск ошибок в цикле', "for ch in s:\n    if ch == 'G':\n        cur += 1\n        best = max(best, cur)\n    else:\n        cur = 0", 'Проверьте, что программа делает на последнем символе: если строка кончается на G, полоса так и не попадёт в best. Надёжнее обновлять максимум сразу, когда полоса растёт. Символы сравниваются как строки: <code>ch == \'G\'</code>. Так считают в задании 24.'],
      start: "s = get_label()\nbest = 0\ncur = 0\nfor ch in s:\n    if ch == 'G':\n        cur += 1\n    else:\n        best = max(best, cur)\n        cur = 0\nanswer(best)\n",
      hint: 'Перенесите <code>best = max(best, cur)</code> в ветку, где <code>cur</code> растёт — или повторите её после цикла',
      solution: "s = get_label()\nbest = 0\ncur = 0\nfor ch in s:\n    if ch == 'G':\n        cur += 1\n        best = max(best, cur)\n    else:\n        cur = 0\nanswer(best)\n",
    },
    {
      id: 20, title: 'Редактор семян', concept: 'while и replace', w: 3, h: 3, answer: true, limit: 100, api: ['answer'],
      gen: r => {
        const N = ri(r, 60, 130); let s = '8'.repeat(N);
        while (s.includes('222') || s.includes('888')) s = s.includes('222') ? s.replace('222', '8') : s.replace('888', '2');
        return { vars: { N }, expect: [s] };
      },
      text: d => `Строка из ${d.vars.N} восьмёрок. Пока в ней есть «222» или «888»: если есть «222», первое «222» заменяют на «8», иначе первое «888» заменяют на «2». Какая строка получится? Сдайте её: <code>answer(s)</code>.`,
      learn: ['while и replace', "s = '8' * N\nwhile '222' in s or '888' in s:\n    if '222' in s:\n        s = s.replace('222', '8', 1)\n    else:\n        s = s.replace('888', '2', 1)", "<code>s.replace(что, на что, 1)</code> заменяет только первое вхождение — как команда «заменить» исполнителя Редактор. Без третьего аргумента заменятся все сразу, и ответ выйдет другим. <code>'8' * N</code> — строка из N восьмёрок. Так решают задание 12."],
      start: "s = '8' * N\n# пока есть '222' или '888' ...\nanswer(s)\n",
      hint: 'Перепишите алгоритм из условия циклом <code>while</code> с <code>if/else</code> внутри, не забудьте третий аргумент <code>1</code> у <code>replace</code>',
      solution: "s = '8' * N\nwhile '222' in s or '888' in s:\n    if '222' in s:\n        s = s.replace('222', '8', 1)\n    else:\n        s = s.replace('888', '2', 1)\nanswer(s)\n",
    },
    {
      id: 21, title: 'Двоичные бирки', concept: 'bin(), срезы, int(s, 2)', w: 3, h: 3, answer: true, limit: 100, api: ['answer'],
      gen: r => {
        const X = ri(r, 150, 2000), Rf = n => { let b = n.toString(2); for (let k = 0; k < 2; k++) b += (b.split('1').length - 1) % 2; return parseInt(b, 2); };
        let n = 1; while (Rf(n) <= X) n++;
        return { vars: { X }, expect: [n] };
      },
      text: d => `Автомат печатает бирки: 1) строит двоичную запись числа N; 2) дописывает справа 0, если единиц в записи чётное число, иначе 1; 3) повторяет шаг 2 для новой записи; 4) получившаяся запись — двоичная запись числа R. Найдите наименьшее N, при котором R больше ${d.vars.X}. Сдайте: <code>answer(N)</code>.`,
      learn: ['Двоичная запись', "b = bin(13)[2:]     # '1101'\nb = f'{13:b}'       # то же самое\nb = b + str(b.count('1') % 2)\nr = int(b, 2)", "<code>bin(n)</code> даёт <code>'0b1101'</code>, срез <code>[2:]</code> отрезает «0b». <code>f'{n:b}'</code> — тоже двоичная запись. <code>int(b, 2)</code> переводит строку обратно в число. Так решают задание 5."],
      start: 'n = 1\nwhile True:\n    b = bin(n)[2:]\n    # дважды допишите бит чётности\n    r = int(b, 2)\n    if r > X:\n        break\n    n += 1\nanswer(n)\n',
      hint: "Повторите дважды: <code>b = b + str(b.count('1') % 2)</code>",
      solution: "n = 1\nwhile True:\n    b = bin(n)[2:]\n    for k in range(2):\n        b = b + str(b.count('1') % 2)\n    r = int(b, 2)\n    if r > X:\n        break\n    n += 1\nanswer(n)\n",
    },
    {
      id: 22, title: 'Системы счисления', concept: 'перевод в систему с основанием B', w: 3, h: 3, answer: true, limit: 100, api: ['answer'],
      gen: r => {
        const B = pickR(r, [3, 5, 7, 9, 16]), P = ri(r, 120, 260), Q = ri(r, 20, P - 20), C = ri(r, 2, 60);
        let x = BigInt(B) ** BigInt(P) + BigInt(B) ** BigInt(Q) - BigInt(C), k = 0;
        while (x > 0n) { if (x % BigInt(B) === BigInt(B - 1)) k++; x /= BigInt(B); }
        return { vars: { B, P, Q, C }, digit: '0123456789ABCDEF'[B - 1], expect: [k] };
      },
      text: d => `Значение выражения ${d.vars.B}<sup>${d.vars.P}</sup> + ${d.vars.B}<sup>${d.vars.Q}</sup> − ${d.vars.C} записали в системе счисления с основанием ${d.vars.B}. Сколько в этой записи цифр «${d.digit}»? Сдайте: <code>answer(количество)</code>.`,
      learn: ['Перевод в систему счисления', "DIG = '0123456789ABCDEF'\nx = 3 ** 100 + 5\ns = ''\nwhile x > 0:\n    s = DIG[x % 3] + s\n    x //= 3", "Остатки от деления на основание — цифры числа справа налево. Строка <code>DIG</code> превращает остаток 10 в «A», 15 в «F» (или <code>chr(ord('A') + d - 10)</code>). Python считает с числами любой длины, поэтому 3 ** 1000 — не проблема. Так решают задание 14."],
      start: "DIG = '0123456789ABCDEF'\nx = B ** P + B ** Q - C\ns = ''\n# переведите x в систему с основанием B\nprint(s)\n",
      hint: "Цикл <code>while x &gt; 0:</code> → <code>s = DIG[x % B] + s</code>, <code>x //= B</code>. Ответ: <code>s.count(DIG[B - 1])</code>",
      solution: "DIG = '0123456789ABCDEF'\nx = B ** P + B ** Q - C\ns = ''\nwhile x > 0:\n    s = DIG[x % B] + s\n    x //= B\nanswer(s.count(DIG[B - 1]))\n",
    },
    {
      id: 23, title: 'Журнал урожая', concept: 'чтение файла, списочное выражение', w: 3, h: 3, answer: true, limit: 100, api: ['answer'],
      gen: r => {
        const a = Array.from({ length: 2000 }, () => ri(r, 1, 10000)); let c = 0, m = 0;
        for (let i = 0; i < a.length - 1; i++) { const x = a[i], y = a[i + 1]; if ((x % 10 === 3) !== (y % 10 === 3)) { c++; m = Math.max(m, x + y); } }
        return { files: { '17.txt': a.join('\n') + '\n' }, expect: [c, m] };
      },
      text: 'В файле <code>17.txt</code> — урожай за 2000 дней, по числу в строке. Найдите пары соседних дней, в которых ровно одно из чисел оканчивается на 3. Сдайте количество таких пар и наибольшую сумму пары: <code>answer(количество, сумма)</code>.',
      learn: ['Чтение файла', "a = [int(x) for x in open('17.txt')]\nprint(len(a), a[:5])", '<code>open(имя)</code> открывает файл, цикл по нему даёт строки. <code>int(x)</code> превращает строку в число (перевод строки не мешает). Списочное выражение <code>[… for x in …]</code> собирает всё в одной строке. Последняя цифра — <code>x % 10</code>. Так начинают задание 17.'],
      start: "a = [int(x) for x in open('17.txt')]\nprint(len(a))\n",
      hint: 'Как на уровне «Соседние грядки»: перебор пар <code>a[i]</code>, <code>a[i + 1]</code>, условие <code>(x % 10 == 3) != (y % 10 == 3)</code>',
      solution: "a = [int(x) for x in open('17.txt')]\ncount = 0\nbest = 0\nfor i in range(len(a) - 1):\n    x, y = a[i], a[i + 1]\n    if (x % 10 == 3) != (y % 10 == 3):\n        count += 1\n        best = max(best, x + y)\nanswer(count, best)\n",
    },
    {
      id: 24, title: 'Таблица склада', concept: 'split, map, множества set', w: 3, h: 3, answer: true, limit: 100, api: ['answer'],
      gen: r => {
        const rows = Array.from({ length: 800 }, () => Array.from({ length: 6 }, () => ri(r, 1, 60))); let c = 0;
        for (const row of rows) {
          if (new Set(row).size !== 5) continue;
          const rep = row.find(x => row.filter(y => y === x).length === 2), other = row.filter(x => x !== rep);
          if (rep * 4 > other.reduce((a, b) => a + b, 0)) c++;
        }
        return { files: { '9.txt': rows.map(x => x.join('\t')).join('\n') + '\n' }, expect: [c] };
      },
      text: 'В файле <code>9.txt</code> — 800 строк по шесть чисел: так склад записывает партии. Сколько строк, в которых одно число повторяется ровно два раза, остальные четыре разные, и повторяющееся число больше среднего арифметического остальных четырёх? Сдайте: <code>answer(количество)</code>.',
      learn: ['Строки файла и множества', "for line in open('9.txt'):\n    row = list(map(int, line.split()))\n    if len(set(row)) == 5:\n        rep = [x for x in row if row.count(x) == 2][0]\n        other = [x for x in row if x != rep]", "<code>line.split()</code> режет строку по пробелам и табуляции, <code>map(int, …)</code> превращает куски в числа. <code>set(row)</code> — множество без повторов: если в нём 5 чисел из 6, повторяется ровно одно. Так решают задание 9."],
      start: "count = 0\nfor line in open('9.txt'):\n    row = list(map(int, line.split()))\n    # проверьте условие\nanswer(count)\n",
      hint: 'Среднее остальных: <code>sum(other) / 4</code>. Условие: <code>rep &gt; sum(other) / 4</code>',
      solution: "count = 0\nfor line in open('9.txt'):\n    row = list(map(int, line.split()))\n    if len(set(row)) == 5:\n        rep = [x for x in row if row.count(x) == 2][0]\n        other = [x for x in row if x != rep]\n        if rep > sum(other) / 4:\n            count += 1\nanswer(count)\n",
    },
    {
      id: 25, title: 'Коробки', concept: 'сортировка, жадный выбор', w: 3, h: 3, answer: true, limit: 100, api: ['answer'],
      gen: r => {
        const n = 400, a = Array.from({ length: n }, () => ri(r, 10, 300)), b = [...a].sort((x, y) => x - y);
        const kk = ri(r, 90, 170); let V = b.slice(0, kk).reduce((x, y) => x + y, 0) + ri(r, 0, b[kk] - 1);
        let k = 0, t = 0; for (const x of b) { if (t + x > V) break; t += x; k++; }
        const s0 = b.slice(0, k - 1).reduce((x, y) => x + y, 0); let best = 0;
        for (const x of b.slice(k - 1)) if (s0 + x <= V) best = Math.max(best, x);
        return { files: { '26.txt': `${n} ${V}\n` + a.join('\n') + '\n' }, expect: [k, best] };
      },
      text: 'В файле <code>26.txt</code> в первой строке — число коробок N и объём склада V, дальше — объёмы коробок. Какое наибольшее число коробок поместится на склад (сумма объёмов не больше V)? И какой наибольший объём может быть у самой большой коробки в таком наборе? Сдайте: <code>answer(количество, объём)</code>.',
      learn: ['Сортировка и жадный выбор', 'a.sort()\ntotal = 0\nk = 0\nfor x in a:\n    if total + x > V:\n        break\n    total += x\n    k += 1', 'Чтобы поместилось как можно больше коробок, берите самые маленькие: отсортируйте список <code>sort()</code> и набирайте, пока помещается. Потом замените последнюю коробку самой большой из тех, что ещё влезают. Это жадный алгоритм задания 26.'],
      start: "f = open('26.txt')\nn, V = map(int, f.readline().split())\na = [int(f.readline()) for i in range(n)]\n",
      hint: 'Второй ответ: <code>s = sum(a[:k - 1])</code>, затем наибольшее <code>x</code> из <code>a[k - 1:]</code>, при котором <code>s + x &lt;= V</code>',
      solution: "f = open('26.txt')\nn, V = map(int, f.readline().split())\na = [int(f.readline()) for i in range(n)]\na.sort()\ntotal = 0\nk = 0\nfor x in a:\n    if total + x > V:\n        break\n    total += x\n    k += 1\ns = sum(a[:k - 1])\nbest = max(x for x in a[k - 1:] if s + x <= V)\nanswer(k, best)\n",
    },
    {
      id: 26, title: 'Частые соседи', concept: 'словари dict, zip', w: 3, h: 3, answer: true, limit: 100, api: ['answer'],
      gen: r => until(r, r => {
        const s = strR(r, 3000, 'BCGPTGBC'), d = {};
        for (let i = 0; i < s.length - 1; i++) if (s[i] === 'G') d[s[i + 1]] = (d[s[i + 1]] || 0) + 1;
        const best = Object.entries(d).sort((a, b) => b[1] - a[1]);
        return { files: { '24.txt': s + '\n' }, expect: [best[0][0], best[0][1]], tie: best[1] && best[1][1] === best[0][1] };
      }, d => !d.tie),
      text: 'В файле <code>24.txt</code> — строка из 3000 меток сортов. Какая буква чаще всего стоит сразу после буквы G, и сколько раз? Сдайте: <code>answer(буква, количество)</code>.',
      learn: ['Словарь', "d = {}\nfor a, b in zip(s, s[1:]):\n    if a == 'G':\n        d[b] = d.get(b, 0) + 1\nbest = max(d, key=d.get)", 'Словарь хранит пары «ключ: значение». <code>d.get(b, 0)</code> вернёт 0, если ключа ещё нет. <code>zip(s, s[1:])</code> даёт пары соседних символов. Самый частый ключ — <code>max(d, key=d.get)</code>. Так считают в задании 24.'],
      start: "s = open('24.txt').read().strip()\nprint(len(s))\n",
      hint: 'Соберите словарь, как в примере, затем <code>answer(best, d[best])</code>',
      solution: "s = open('24.txt').read().strip()\nd = {}\nfor a, b in zip(s, s[1:]):\n    if a == 'G':\n        d[b] = d.get(b, 0) + 1\nbest = max(d, key=d.get)\nanswer(best, d[best])\n",
    },
    {
      id: 27, title: 'Датчики полива', concept: 'логика, itertools.product', w: 3, h: 3, answer: true, limit: 100, api: ['answer'],
      gen: r => {
        const t = Math.floor(r() * LOGIC.length); let c = 0;
        for (let m = 0; m < 16; m++) { const [x, y, z, w] = [8, 4, 2, 1].map(b => !!(m & b)); if (LOGIC[t][1](x, y, z, w)) c++; }
        return { formula: LOGIC[t][0], expect: [c] };
      },
      text: d => `Поливом управляют четыре датчика x, y, z, w — каждый выдаёт 0 или 1. Насос включается, когда истинна формула <b>F = ${d.formula}</b>. При скольких наборах (x, y, z, w) насос включён? Сдайте: <code>answer(количество)</code>.`,
      learn: ['Логика и перебор', "from itertools import product\n\ndef F(x, y, z, w):\n    return (x <= y) and (not z or w)\n\nfor x, y, z, w in product([0, 1], repeat=4):\n    print(x, y, z, w, F(x, y, z, w))", 'Импликация A → B в Python — <code>A &lt;= B</code>, эквивалентность A ≡ B — <code>A == B</code>, ¬ — <code>not</code>, ∧ — <code>and</code>, ∨ — <code>or</code>. <code>product([0, 1], repeat=4)</code> перебирает все 16 наборов вместо четырёх вложенных циклов. Так решают задание 2.'],
      start: 'from itertools import product\n\ndef F(x, y, z, w):\n    return False   # запишите формулу из условия\n\ncount = 0\nfor x, y, z, w in product([0, 1], repeat=4):\n    if F(x, y, z, w):\n        count += 1\nanswer(count)\n',
      hint: 'Только тело функции <code>F</code>: перепишите формулу знаками Python. Скобки ставьте как в условии',
      solution: null,                                   // формула своя на каждый заход — решение в тесте собирается из неё
    },
    {
      id: 28, title: 'Названия сортов', concept: 'перебор слов, set, zip', w: 3, h: 3, answer: true, limit: 100, api: ['answer'],
      gen: r => {
        const word = pickR(r, ['ТЫКВА', 'ПОЛЕ', 'СЕМЯ', 'ГРЯДКА', 'КОРМ']), L = word.length >= 5 ? 5 : 6, X = pickR(r, [...word]);
        let c = 0; const n = word.length, cur = Array(L).fill(0);
        for (let m = 0; m < n ** L; m++) {
          let v = m; for (let i = L - 1; i >= 0; i--) { cur[i] = word[v % n]; v = Math.floor(v / n); }
          if (cur.filter(ch => ch === X).length !== 1) continue;
          if (cur.some((ch, i) => i && ch === cur[i - 1])) continue;
          if (new Set(cur).size < 3) continue;
          c++;
        }
        return { vars: { LETTERS: word, L, X }, expect: [c] };
      },
      text: d => `Дрон придумывает названия сортов: слова длины ${d.vars.L} из букв слова «${d.vars.LETTERS}» (буквы можно повторять). Буква «${d.vars.X}» встречается ровно один раз, две одинаковые буквы рядом не стоят, и в слове не меньше трёх разных букв. Сколько таких слов? Сдайте: <code>answer(количество)</code>.`,
      learn: ['Перебор слов', "from itertools import product\nfor w in product(LETTERS, repeat=L):\n    s = ''.join(w)\n    same = any(a == b for a, b in zip(s, s[1:]))\n    kinds = len(set(s))", "<code>product(буквы, repeat=n)</code> перебирает все слова длины n. <code>''.join(w)</code> склеивает кортеж букв в строку. <code>zip(s, s[1:])</code> — пары соседних букв, <code>set(s)</code> — разные буквы слова. Так решают задание 8."],
      start: "from itertools import product\n\ncount = 0\nfor w in product(LETTERS, repeat=L):\n    s = ''.join(w)\n    # проверьте три условия\nanswer(count)\n",
      hint: "Условия: <code>s.count(X) == 1</code>, <code>not any(a == b for a, b in zip(s, s[1:]))</code>, <code>len(set(s)) &gt;= 3</code>",
      solution: "from itertools import product\n\ncount = 0\nfor w in product(LETTERS, repeat=L):\n    s = ''.join(w)\n    if s.count(X) == 1 and not any(a == b for a, b in zip(s, s[1:])) and len(set(s)) >= 3:\n        count += 1\nanswer(count)\n",
    },
    {
      id: 29, title: 'Параметр полива', concept: 'функция-условие, all(), перебор A', w: 3, h: 3, answer: true, limit: 100, api: ['answer'],
      gen: r => until(r, r => {
        const B = ri(r, 2, 20), C = ri(r, 2, 20), g = (a, b) => b ? g(b, a % b) : a, l = B * C / g(B, C);
        return { vars: { B, C }, lcm: l, expect: [l] };
      }, d => d.vars.B !== d.vars.C && d.lcm <= 300 && d.lcm !== d.vars.B && d.lcm !== d.vars.C),
      text: d => `Обозначим ДЕЛ(x, m) — «x делится на m без остатка». Найдите наибольшее натуральное A, при котором формула <b>ДЕЛ(x, A) ∨ (ДЕЛ(x, ${d.vars.B}) → ¬ДЕЛ(x, ${d.vars.C}))</b> истинна при любом натуральном x. Хватит проверить x от 1 до 999 и A до 999. Сдайте: <code>answer(A)</code>.`,
      learn: ['Функция-условие и перебор параметра', "def f(x, A):\n    return x % A == 0 or (x % B == 0) <= (x % C != 0)\n\nfor A in range(1, 1000):\n    if all(f(x, A) for x in range(1, 1000)):\n        best = A", '«Истинна при любом x» — проверьте функцией <code>all()</code>: она остановится на первом x, где формула ложна. ДЕЛ(x, A) — <code>x % A == 0</code>, импликация — <code>&lt;=</code>. <code>return</code> возвращает ответ функции. Так решают задание 15.'],
      start: 'def f(x, A):\n    return True   # запишите формулу\n\nbest = 0\nfor A in range(1, 1000):\n    # проверьте все x от 1 до 999\n    pass\nanswer(best)\n',
      hint: 'Тело функции — как в примере. В цикле: <code>if all(f(x, A) for x in range(1, 1000)): best = A</code>',
      solution: 'def f(x, A):\n    return x % A == 0 or (x % B == 0) <= (x % C != 0)\n\nbest = 0\nfor A in range(1, 1000):\n    if all(f(x, A) for x in range(1, 1000)):\n        best = A\nanswer(best)\n',
    },
    {
      id: 30, title: 'Самый богатый путь', concept: 'вложенные списки, динамика', w: 6, h: 6, answer: true, limit: 3000, api: [...DRONE, 'scan', 'answer'],
      gen: r => {
        const n = 6, signs = Array.from({ length: n * n }, () => ri(r, 1, 99)), g = (x, y) => signs[y * n + x];
        const dp = (pick) => { const t = []; for (let y = 0; y < n; y++) { t[y] = []; for (let x = 0; x < n; x++) { const c = []; if (x) c.push(t[y][x - 1]); if (y) c.push(t[y - 1][x]); t[y][x] = g(x, y) + (c.length ? pick(...c) : 0); } } return t[n - 1][n - 1]; };
        return { signs, expect: [dp(Math.max), dp(Math.min)] };
      },
      text: 'Дрон летит из левого нижнего угла в правый верхний и за один шаг сдвигается только вправо или вверх. На каждой клетке он собирает столько мешков, сколько написано на табличке (и на первой, и на последней). Какой наибольший и какой наименьший урожай можно собрать? Сдайте: <code>answer(наибольший, наименьший)</code>.',
      learn: ['Вложенные списки и динамика', "n = get_world_size()\ng = [[0] * n for y in range(n)]\n# g[y][x] = scan() при обходе\nbest = [[0] * n for y in range(n)]\nbest[0][0] = g[0][0]", 'Таблица — список списков, клетка — <code>g[y][x]</code>. Лучшая сумма до клетки = её число + лучшая из сумм соседа слева и соседа снизу. Заполняя таблицу по порядку, получите ответ в правом верхнем углу. Так решают задание 18.'],
      start: 'n = get_world_size()\ng = [[0] * n for y in range(n)]\nfor x in range(n):\n    for y in range(n):\n        g[y][x] = scan()\n        move(North)\n    move(East)\n\n# посчитайте наибольшую и наименьшую сумму\n',
      hint: 'Две таблицы <code>hi</code> и <code>lo</code>. Для каждой клетки: соседи <code>hi[y][x - 1]</code> (если x &gt; 0) и <code>hi[y - 1][x]</code> (если y &gt; 0); <code>hi[y][x] = g[y][x] + max(соседей)</code>',
      solution: 'n = get_world_size()\ng = [[0] * n for y in range(n)]\nfor x in range(n):\n    for y in range(n):\n        g[y][x] = scan()\n        move(North)\n    move(East)\n\ndef best(pick):\n    t = [[0] * n for y in range(n)]\n    for y in range(n):\n        for x in range(n):\n            prev = []\n            if x > 0:\n                prev.append(t[y][x - 1])\n            if y > 0:\n                prev.append(t[y - 1][x])\n            t[y][x] = g[y][x] + (pick(prev) if prev else 0)\n    return t[n - 1][n - 1]\n\nanswer(best(max), best(min))\n',
    },
    {
      id: 31, title: 'Рекурсивный рост', concept: 'рекурсия, @lru_cache', w: 3, h: 3, answer: true, limit: 100, api: ['answer'],
      gen: r => { const N = ri(r, 60, 95); let a = 1n, b = 2n; for (let n = 3; n <= N; n++) [a, b] = [b, b + 2n * a]; return { vars: { N }, expect: [norm(N === 1 ? 1n : N === 2 ? 2n : b)] }; },
      text: d => `Урожай сорта растёт по правилу: F(n) = n при n &lt; 3; F(n) = F(n − 1) + 2·F(n − 2) при n ≥ 3. Найдите F(${d.vars.N}). Сдайте: <code>answer(F(N))</code>.`,
      learn: ['Рекурсия и кэш', "from functools import lru_cache\n\n@lru_cache(None)\ndef F(n):\n    if n < 3:\n        return n\n    return F(n - 1) + 2 * F(n - 2)", 'Функция, которая вызывает саму себя, — рекурсия. Без кэша F(80) пересчитывает одни и те же значения миллиарды раз. <code>@lru_cache(None)</code> запоминает ответы, и всё считается мгновенно. Можно и вручную: словарь <code>memo</code> вне функции. Для глубокой рекурсии — <code>sys.setrecursionlimit(10000)</code>. Так решают задание 16.'],
      start: 'def F(n):\n    if n < 3:\n        return n\n    return F(n - 1) + 2 * F(n - 2)\n\nanswer(F(N))\n',
      hint: 'Запустите как есть — программа не дождётся ответа. Добавьте <code>from functools import lru_cache</code> и строку <code>@lru_cache(None)</code> над <code>def</code>',
      solution: 'from functools import lru_cache\n\n@lru_cache(None)\ndef F(n):\n    if n < 3:\n        return n\n    return F(n - 1) + 2 * F(n - 2)\n\nanswer(F(N))\n',
    },
    {
      id: 32, title: 'Программы дрона', concept: 'рекурсивный подсчёт путей', w: 3, h: 3, answer: true, limit: 100, api: ['answer'],
      gen: r => until(r, r => {
        const A = ri(r, 2, 4), C = ri(r, 9, 14), D = ri(r, C + 2, C + 8), B = ri(r, D + 4, D + 16);
        const f = (x, y, ban) => { const w = Array(y + 1).fill(0); w[x] = 1; for (let v = x; v < y; v++) { if (v === ban) w[v] = 0; if (v + 1 <= y) w[v + 1] += w[v]; if (v * 2 <= y) w[v * 2] += w[v]; } return y === ban ? 0 : w[y]; };
        return { vars: { A, B, C, D }, expect: [f(A, C, -1) * f(C, B, D)] };
      }, d => d.expect[0] > 0),
      text: d => `У дрона две команды: «прибавь 1» и «умножь на 2». Сколько существует программ, которые переводят число ${d.vars.A} в число ${d.vars.B}, при этом траектория вычислений проходит через ${d.vars.C} и не проходит через ${d.vars.D}? Сдайте: <code>answer(количество)</code>.`,
      learn: ['Рекурсивный подсчёт', 'def f(x, y):\n    if x > y:\n        return 0\n    if x == y:\n        return 1\n    return f(x + 1, y) + f(x * 2, y)\n\nprint(f(A, C) * f(C, B))', 'Программ из x в y столько, сколько программ после первой команды «+1» плюс после «×2». «Проходит через C» — перемножьте пути A→C и C→B. «Не проходит через D» — верните 0, когда x == D. Функция с параметрами получает разные x и y при каждом вызове. Так решают задание 23.'],
      start: 'def f(x, y):\n    if x > y:\n        return 0\n    if x == y:\n        return 1\n    return f(x + 1, y) + f(x * 2, y)\n\nanswer(f(A, C) * f(C, B))   # здесь не учтено D\n',
      hint: 'Добавьте в <code>f</code> первой строкой: <code>if x == D: return 0</code>',
      solution: 'def f(x, y):\n    if x == D:\n        return 0\n    if x > y:\n        return 0\n    if x == y:\n        return 1\n    return f(x + 1, y) + f(x * 2, y)\n\nanswer(f(A, C) * f(C, B))\n',
    },
    {
      id: 33, title: 'Куча урожая', concept: 'теория игр, рекурсия', w: 3, h: 3, answer: true, limit: 100, api: ['answer'],
      gen: r => until(r, r => {
        const W = ri(r, 25, 70), memo = new Map();
        const f = (s, m) => { if (s >= W) return m % 2 === 0; if (m === 0) return false; const k = s + ',' + m; if (memo.has(k)) return memo.get(k); const h = [f(s + 1, m - 1), f(s * 2, m - 1)]; const v = m % 2 ? h.some(Boolean) : h.every(Boolean); memo.set(k, v); return v; };
        const ok = []; for (let S = 1; S < W; S++) if (!f(S, 1) && f(S, 3)) ok.push(S);
        return { vars: { W }, expect: ok.slice(0, 2) };
      }, d => d.expect.length === 2),
      text: d => `Петя и Ваня по очереди добавляют в кучу мешки: можно добавить 1 мешок или удвоить кучу. Первым ходит Петя. Игра кончается, когда в куче ${d.vars.W} мешков или больше; выигрывает тот, кто сделал последний ход. В начале в куче S мешков (1 ≤ S &lt; ${d.vars.W}). Найдите два наименьших S, при которых Петя не может выиграть первым ходом, но выигрывает своим вторым ходом при любой игре Вани. Сдайте: <code>answer(S1, S2)</code>.`,
      learn: ['Игра рекурсией', 'def f(s, m):\n    if s >= W:\n        return m % 2 == 0\n    if m == 0:\n        return False\n    h = [f(s + 1, m - 1), f(s * 2, m - 1)]\n    return any(h) if m % 2 != 0 else all(h)', 'm — сколько ходов осталось сделать. На ходе Пети ему достаточно одного удачного хода — <code>any</code>, на ходе Вани Петя должен выиграть при любом его ходе — <code>all</code>. «Выигрывает первым ходом» — <code>f(s, 1)</code>, «вторым ходом» — <code>f(s, 3)</code>. Так решают задания 19–21.'],
      start: 'def f(s, m):\n    if s >= W:\n        return m % 2 == 0\n    if m == 0:\n        return False\n    h = [f(s + 1, m - 1), f(s * 2, m - 1)]\n    return any(h) if m % 2 != 0 else all(h)\n\nfound = []\n# переберите S\nanswer(found[0], found[1])\n',
      hint: '<code>for S in range(1, W):</code> → <code>if not f(S, 1) and f(S, 3): found.append(S)</code>',
      solution: 'def f(s, m):\n    if s >= W:\n        return m % 2 == 0\n    if m == 0:\n        return False\n    h = [f(s + 1, m - 1), f(s * 2, m - 1)]\n    return any(h) if m % 2 != 0 else all(h)\n\nfound = []\nfor S in range(1, W):\n    if not f(S, 1) and f(S, 3):\n        found.append(S)\nanswer(found[0], found[1])\n',
    },
  ];
  LEVELS.push(...TASKS);
  // главы, темы учебника Python (id из учебника на сайте) и номера заданий ЕГЭ
  const CHAPTERS = [
    { id: 1, title: 'Дрон и циклы', levels: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11] },
    { id: 2, title: 'Числа на табличках', levels: [13, 14, 15, 16, 17] },
    { id: 3, title: 'Строки и системы счисления', levels: [18, 19, 20, 21, 22] },
    { id: 4, title: 'Файлы, списки, словари', levels: [23, 24, 25, 26] },
    { id: 5, title: 'Перебор, функции, рекурсия', levels: [27, 28, 29, 30, 31, 32, 33] },
    { id: 6, title: 'Своя ферма', levels: [12] },
  ];
  const ORDER = CHAPTERS.flatMap(c => c.levels);
  const META = {
    1: [[1], []], 2: [[14], []], 3: [[1], []], 4: [[6], []], 5: [[11, 12, 17], []], 6: [[35], []], 7: [[6], []], 8: [[5, 6], []],
    9: [[34, 35, 36], []], 10: [[6, 8], []], 11: [[27, 29, 31], [26]], 12: [[], []],
    13: [[3, 4, 13], [17]], 14: [[5, 7, 13], [17]], 15: [[9, 14, 15], [5, 14]], 16: [[10, 12, 16], [25]], 17: [[27, 28, 30], [17]],
    18: [[2, 19, 21, 22], [24]], 19: [[18, 19, 24], [24]], 20: [[14, 22], [12]], 21: [[20, 25], [5]], 22: [[15, 26], [14]],
    23: [[39, 32], [17]], 24: [[23, 33, 40, 41], [9]], 25: [[29, 31], [26]], 26: [[42, 43], [24]],
    27: [[7, 34], [2]], 28: [[41, 43], [8]], 29: [[16, 36], [15]], 30: [[33, 17], [18]], 31: [[36, 37, 38], [16]], 32: [[35, 38], [23]], 33: [[38], [19, 20, 21]],
  };
  for (const l of LEVELS) {
    const c = CHAPTERS.find(x => x.levels.includes(l.id)), i = ORDER.indexOf(l.id);
    l.ch = c.id; l.py = META[l.id][0]; l.ege = META[l.id][1];
    if (l.need === undefined) l.need = i > 0 ? ORDER[i - 1] : 0;
  }
  // эталон уровня 27 — из формулы конкретного захода
  const logicPy = f => f.replace(/¬/g, 'not ').replace(/∧/g, 'and').replace(/∨/g, 'or').replace(/≡/g, '==').replace(/→/g, '<=');
  function solutionFor(lv, data) {
    if (lv.id === 27) return 'from itertools import product\n\ndef F(x, y, z, w):\n    return ' + logicPy(data.formula) + '\n\ncount = 0\nfor x, y, z, w in product([0, 1], repeat=4):\n    if F(x, y, z, w):\n        count += 1\nanswer(count)\n';
    return lv.solution;
  }

  const DOC = {
    harvest: ['harvest()', 'собрать урожай под дроном. Незрелое растение погибнет'],
    can_harvest: ['can_harvest()', '<code>True</code>, если растение под дроном созрело'],
    move: ['move(North)', 'шаг: <code>North</code>, <code>East</code>, <code>South</code>, <code>West</code>. С края поля — на другой край'],
    get_world_size: ['get_world_size()', 'размер поля в клетках'],
    plant: ['plant(Entities.Bush)', 'посадить: <code>Grass</code>, <code>Bush</code>, <code>Tree</code>, <code>Carrot</code>, <code>Pumpkin</code>, <code>Sunflower</code>'],
    till: ['till()', 'вспахать траву или вернуть траву на пашню'],
    get_ground_type: ['get_ground_type()', '<code>Grounds.Grassland</code> или <code>Grounds.Soil</code>'],
    get_pos_x: ['get_pos_x(), get_pos_y()', 'координаты дрона, (0, 0) — левый нижний угол'],
    get_entity_type: ['get_entity_type()', 'что растёт под дроном: <code>Entities.…</code> или <code>None</code>'],
    measure: ['measure()', 'число лепестков подсолнуха под дроном'],
    num_items: ['num_items(Items.Hay)', 'сколько собрано'],
    scan: ['scan()', 'число на табличке под дроном'],
    get_label: ['get_label()', 'строка с таблички на амбаре'],
    answer: ['answer(…)', 'сдать ответ: одно или несколько значений через запятую'],
  };
  // ход уровня со своим решением — норма для звезды; посчитана прогоном решений (tests/farm_check.js)
  const PAR = { 3: 23, 4: 22, 5: 128, 6: 167, 7: 239, 8: 235, 9: 717, 10: 934, 11: 498 };
  LEVELS.forEach(l => { if (!l.par && PAR[l.id]) l.par = PAR[l.id]; });

  /* ═════════════ ДЕРЕВО УЛУЧШЕНИЙ (своя ферма, уровень 12) ═════════════
     Сохранение: { t: время, items: {Hay: …}, up: {id: купленный уровень} } — в общем прогрессе как farmx */
  const SIZES = [3, 4, 5, 6, 7, 8];
  const BASE_API = ['harvest', 'can_harvest', 'move', 'get_world_size'];
  const UPGRADES = [
    { id: 'plant', title: 'Посадка', icon: 'Bush', text: '<code>plant()</code> и кусты — из них древесина', cost: { Hay: 20 }, gives: { api: ['plant'], plants: ['Grass', 'Bush'] } },
    { id: 'size', title: 'Расширение поля', icon: 'size', text: n => `поле ${SIZES[n + 1]}×${SIZES[n + 1]}`, levels: [{ Hay: 40 }, { Hay: 100, Wood: 40 }, { Wood: 150, Carrot: 60 }, { Carrot: 200, Pumpkin: 80 }, { Pumpkin: 250, Power: 80 }] },
    { id: 'count', title: 'Учёт', icon: 'count', text: '<code>num_items()</code> — сколько в амбаре', cost: { Hay: 30 }, gives: { api: ['num_items'] } },
    { id: 'pos', title: 'Координаты', icon: 'pos', text: '<code>get_pos_x()</code> и <code>get_pos_y()</code>', cost: { Hay: 60 }, need: ['plant'], gives: { api: ['get_pos_x', 'get_pos_y'] } },
    { id: 'trees', title: 'Деревья', icon: 'Tree', text: 'деревья: 5 древесины, но соседние мешают расти', cost: { Wood: 40 }, need: ['plant'], gives: { plants: ['Tree'] } },
    { id: 'till', title: 'Вспашка', icon: 'Carrot', text: '<code>till()</code>, <code>get_ground_type()</code> и морковь', cost: { Hay: 80, Wood: 50 }, need: ['plant'], gives: { api: ['till', 'get_ground_type'], plants: ['Carrot'] } },
    { id: 'grow', title: 'Удобрение', icon: 'grow', text: 'всё растёт на 20% быстрее', levels: [{ Hay: 150, Wood: 60 }, { Wood: 150, Carrot: 120 }, { Pumpkin: 150, Power: 60 }], need: ['plant'] },
    { id: 'sense', title: 'Сенсор', icon: 'sense', text: '<code>get_entity_type()</code> — что растёт под дроном', cost: { Carrot: 40 }, need: ['till'], gives: { api: ['get_entity_type'] } },
    { id: 'yield', title: 'Щедрый урожай', icon: 'yield', text: 'каждый сбор приносит вдвое больше', levels: [{ Wood: 200, Carrot: 150 }, { Pumpkin: 300, Power: 150 }], need: ['till'] },
    { id: 'pumpkin', title: 'Тыквы', icon: 'Pumpkin', text: 'тыквы; сгнившие убирайте <code>harvest()</code>', cost: { Carrot: 80, Wood: 80 }, need: ['sense'], gives: { plants: ['Pumpkin'] } },
    { id: 'sun', title: 'Подсолнухи', icon: 'Sunflower', text: 'подсолнухи и <code>measure()</code> — энергия', cost: { Pumpkin: 60, Carrot: 60 }, need: ['pumpkin'], gives: { api: ['measure'], plants: ['Sunflower'] } },
  ];
  const upMax = u => u.levels ? u.levels.length : 1;
  const upCost = (u, have) => have >= upMax(u) ? null : u.levels ? u.levels[have] : u.cost;
  function upState(save, u) {
    const have = (save.up || {})[u.id] || 0, cost = upCost(u, have);
    if (!cost) return { have, cost, st: 'done' };
    if ((u.need || []).some(n => !(save.up || {})[n])) return { have, cost, st: 'locked' };
    return { have, cost, st: Object.entries(cost).every(([k, n]) => ((save.items || {})[k] || 0) >= n) ? 'ready' : 'poor' };
  }
  // покупка: новое сохранение или null, если нельзя
  function buy(save, id) {
    const u = UPGRADES.find(x => x.id === id), s = u && upState(save, u);
    if (!s || s.st !== 'ready') return null;
    const items = { ...save.items };
    for (const [k, n] of Object.entries(s.cost)) items[k] -= n;
    return { t: Date.now(), items, up: { ...save.up, [id]: s.have + 1 } };
  }
  // уровень «своя ферма» под текущие улучшения
  function sandbox(save) {
    const up = (save && save.up) || {}, lvl = id => up[id] || 0, base = LEVELS.find(l => l.sandbox);
    const api = [...BASE_API], plants = ['Grass'];
    for (const u of UPGRADES) if (lvl(u.id) && u.gives) { api.push(...(u.gives.api || [])); plants.push(...(u.gives.plants || [])); }
    const size = SIZES[Math.min(SIZES.length - 1, lvl('size'))], f = Math.pow(0.8, lvl('grow'));
    const grow = Object.fromEntries(Object.entries(ENT).filter(([, d]) => d.grow).map(([k, d]) => [k, Math.max(1, Math.round(d.grow * f))]));
    return { ...base, w: size, h: size, api, plants, grow, mul: Math.pow(2, lvl('yield')), items: { ...((save && save.items) || {}) } };
  }

  /* ═════════════ ПОДСКАЗКИ В РЕДАКТОРЕ: автодополнение и справка по аргументам ═════════════ */
  const CDOC = {
    ...Object.fromEntries(Object.entries(DOC).map(([k, v]) => [k, [v[0].split(',')[0].replace(/\(.*\)/, k === 'move' ? '(направление)' : k === 'plant' ? '(растение)' : k === 'num_items' ? '(вид)' : '()'), v[1]]])),
    get_pos_y: ['get_pos_y()', 'координата дрона по вертикали, 0 — нижний ряд'],
  };
  const BDOC = {
    print: ['print(значение, …)', 'вывести значения в журнал'], range: ['range(n) · range(a, b, шаг)', 'числа 0…n−1 или от a до b−1'],
    len: ['len(x)', 'длина списка или строки'], abs: ['abs(x)', 'модуль числа'], min: ['min(a, b, …) · min(список)', 'наименьшее значение'],
    max: ['max(a, b, …) · max(список)', 'наибольшее значение'], sum: ['sum(список)', 'сумма'], int: ['int(x)', 'целое число из строки или дроби'],
    str: ['str(x)', 'строка из значения'], float: ['float(x)', 'дробное число'], list: ['list(x)', 'список из перебираемого'],
    sorted: ['sorted(список, reverse=False)', 'новый отсортированный список'], reversed: ['reversed(список)', 'элементы в обратном порядке'],
    enumerate: ['enumerate(список)', 'пары (номер, элемент)'], zip: ['zip(a, b)', 'пары из двух списков'], round: ['round(x)', 'округление'],
    random: ['random()', 'случайное число от 0 до 1'], bool: ['bool(x)', 'True или False'], dict: ['dict()', 'пустой словарь'], tuple: ['tuple(x)', 'кортеж'],
  };
  const MDOC = {
    append: ['.append(x)', 'добавить в конец списка'], pop: ['.pop(i)', 'убрать элемент (по умолчанию последний) и вернуть его'],
    sort: ['.sort(reverse=False)', 'отсортировать список на месте'], insert: ['.insert(i, x)', 'вставить x на место i'],
    remove: ['.remove(x)', 'убрать первое значение x'], index: ['.index(x)', 'номер первого x'], count: ['.count(x)', 'сколько раз встречается x'],
    reverse: ['.reverse()', 'развернуть список'], copy: ['.copy()', 'копия'], keys: ['.keys()', 'ключи словаря'], values: ['.values()', 'значения словаря'],
    items: ['.items()', 'пары (ключ, значение)'], get: ['.get(ключ, иначе)', 'значение по ключу или запасное'], split: ['.split(разделитель)', 'разрезать строку'],
    join: ['.join(список)', 'склеить строки'], upper: ['.upper()', 'ПРОПИСНЫМИ'], lower: ['.lower()', 'строчными'],
  };
  const KWDOC = {
    while: 'повторять, пока условие верно', for: 'перебрать значения: for i in range(n):', if: 'выполнить, если условие верно', elif: 'иначе, если…', else: 'иначе',
    def: 'своя функция: def имя(параметры):', return: 'вернуть ответ из функции', break: 'выйти из цикла', continue: 'к следующему шагу цикла',
    pass: 'ничего не делать', and: 'и', or: 'или', not: 'не', in: 'входит ли / перебор в for', True: 'истина', False: 'ложь', None: 'ничего', global: 'менять переменную всей программы из функции',
  };
  const NS_RU = { Entities: ENT, Items: ITEMS, Grounds: { Grassland: 'трава', Soil: 'вспаханная земля' } };
  // имена, которые ученик сам завёл в программе: функции (с параметрами) и переменные
  function userNames(code) {
    const out = new Map();
    for (const m of code.matchAll(/\bdef\s+([A-Za-z_]\w*)\s*\(([^)]*)\)/g)) {
      out.set(m[1], { kind: 'функция', doc: [`${m[1]}(${m[2].trim()})`, 'ваша функция'], args: !!m[2].trim() });
      for (const p of m[2].split(',')) { const n = p.split('=')[0].trim(); if (/^[A-Za-z_]\w*$/.test(n) && !out.has(n)) out.set(n, { kind: 'параметр' }); }
    }
    for (const m of code.matchAll(/^[ \t]*([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*(?:[-+*/%]|\/\/|\*\*)?=(?!=)/gm))
      for (const n of m[1].split(',')) { const k = n.trim(); if (!out.has(k) && !KEYWORDS.has(k)) out.set(k, { kind: 'переменная' }); }
    for (const m of code.matchAll(/\bfor\s+([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s+in\b/g))
      for (const n of m[1].split(',')) { const k = n.trim(); if (!out.has(k)) out.set(k, { kind: 'переменная' }); }
    return out;
  }
  function inCodePart(line) {           // курсор не внутри строки и не в комментарии
    let q = '';
    for (const ch of line) { if (q) { if (ch === q) q = ''; } else if (ch === '"' || ch === "'") q = ch; else if (ch === '#') return false; }
    return !q;
  }
  // варианты для слова перед курсором. avail: { api: [...], plants: [...] | null }
  function complete(code, caret, avail) {
    const before = code.slice(0, caret), line = before.slice(before.lastIndexOf('\n') + 1);
    if (!inCodePart(line)) return null;
    const m = /(?:([A-Za-z_]\w*|\)|\])\.)?([A-Za-z_]\w*)?$/.exec(line), obj = m[1], pre = m[2] || '';
    if (/\b(def|for|global)\s+[A-Za-z_]*$/.test(line) && !obj) return null;      // здесь пишут новое имя
    const api = avail.api || GAME, has = n => api.includes(n);
    let items = [];
    if (obj !== undefined) {
      if (NS_RU[obj]) {
        const ru = NS_RU[obj];
        items = Object.keys(ru).filter(n => obj !== 'Entities' || !avail.plants || avail.plants.includes(n === 'Dead_Pumpkin' ? 'Pumpkin' : n))
          .map(n => ({ name: n, kind: obj, doc: [`${obj}.${n}`, typeof ru[n] === 'string' ? ru[n] : ru[n].ru] }));
      } else if (/^\d+$/.test(obj)) return null;
      else items = Object.entries(MDOC).map(([n, d]) => ({ name: n, kind: 'метод', doc: d, call: true, args: !/\(\)$/.test(d[0]) }));
    } else {
      if (!pre) return null;
      const user = userNames(code.slice(0, caret - pre.length) + code.slice(caret));
      items = [
        ...GAME.filter(has).map(n => ({ name: n, kind: 'дрон', doc: CDOC[n], call: true, args: ['move', 'plant', 'num_items', 'answer'].includes(n) })),
        ...(has('move') ? Object.keys(DIRS).map(n => ({ name: n, kind: 'направление', doc: [n, `направление: ${DIRS[n][2]}`] })) : []),
        ...Object.keys(NS_RU).filter(n => n !== 'Grounds' || has('get_ground_type')).filter(n => n !== 'Items' || has('num_items')).filter(n => n !== 'Entities' || has('plant') || has('get_entity_type'))
          .map(n => ({ name: n, kind: 'набор', doc: [n + '.…', n === 'Entities' ? 'растения' : n === 'Items' ? 'виды урожая' : 'виды земли'], ns: true })),
        ...(avail.vars || []).map(n => ({ name: n, kind: 'дано', doc: [n, 'число из условия — уже есть в программе'] })),
        ...[...user].map(([n, u]) => ({ name: n, kind: u.kind, doc: u.doc || [n, u.kind === 'параметр' ? 'параметр функции' : 'ваша переменная'], call: u.kind === 'функция', args: u.args })),
        ...Object.keys(BDOC).map(n => ({ name: n, kind: 'Python', doc: BDOC[n], call: true, args: !/^\w+\(\)$/.test(BDOC[n][0]) })),
        ...Object.keys(KWDOC).map(n => ({ name: n, kind: 'слово', doc: [n, KWDOC[n]], kw: true })),
      ];
    }
    const low = pre.toLowerCase(), seen = new Set();
    items = items.filter(it => it.name.toLowerCase().startsWith(low) && it.name !== pre && !seen.has(it.name) && seen.add(it.name)).slice(0, 8);
    return items.length ? { from: caret - pre.length, pre, items } : null;
  }
  // что вставить при выборе: текст и где оставить курсор
  function insertion(it) {
    if (it.ns) return { text: it.name + '.', back: 0, again: true };
    if (it.call) return { text: it.name + '()', back: it.args ? 1 : 0 };
    if (it.kw) return { text: it.name + (['True', 'False', 'None', 'pass', 'break', 'continue'].includes(it.name) ? '' : ' '), back: 0 };
    return { text: it.name, back: 0 };
  }
  // справка по вызову, внутри скобок которого стоит курсор
  function signature(code, caret, avail) {
    const before = code.slice(0, caret), line = before.slice(before.lastIndexOf('\n') + 1);
    if (!inCodePart(line)) return null;
    let depth = 0;
    for (let i = line.length - 1; i >= 0; i--) {
      const ch = line[i];
      if (ch === ')' || ch === ']') depth++;
      else if (ch === '[') depth--;
      else if (ch === '(') {
        if (depth) { depth--; continue; }
        const m = /(\.)?([A-Za-z_]\w*)\s*$/.exec(line.slice(0, i));
        if (!m) return null;
        const n = m[2];
        if (m[1]) return MDOC[n] || null;
        const u = userNames(code).get(n);
        return ((avail.api || GAME).includes(n) && CDOC[n]) || BDOC[n] || (u && u.doc) || null;
      }
    }
    return null;
  }

  const api = { PyError, parse, tokenize, Interp, Run, World, simulate, LEVELS, CHAPTERS, ORDER, solutionFor, rng32, pystr, repr, UPGRADES, SIZES, upState, buy, sandbox, complete, signature, insertion };
  if (typeof module !== 'undefined' && module.exports) { module.exports = api; return; }

  /* ═════════════ ЭКРАН ИГРЫ: островок в 3D (Three.js), поверх — окна с заданием и кодом ═════════════ */
  const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  // Three.js лежит на сайте (public/vendor): внешние скрипты CSP не пускает. Грузится только на странице фермы
  const THREE_URL = '/vendor/three-0.160.0.module.min.js';
  let threeReq = null;
  const loadThree = () => threeReq || (threeReq = import(THREE_URL).catch(e => { threeReq = null; throw e; }));
  const reduceMotion = () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── сцена: парящий островок, грядки, растения, дрон ── */
  function scene3d(THREE, host, lv) {
    const W = lv.w, H = lv.h;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    host.appendChild(renderer.domElement);
    const scene = new THREE.Scene(), cam = new THREE.PerspectiveCamera(30, 1, 0.1, 300);
    scene.add(new THREE.HemisphereLight(0xe6eef4, 0x7a5a3c, 1.3));
    const sun = new THREE.DirectionalLight(0xffe4bd, 2.5), R = Math.max(W, H) * 0.8 + 1.6;
    sun.position.set(-R * 0.7, R * 2.2, R * 1.3); sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048);
    Object.assign(sun.shadow.camera, { left: -R, right: R, top: R, bottom: -R, near: 0.5, far: R * 7 });
    sun.shadow.bias = -0.0005; sun.shadow.normalBias = 0.03;
    scene.add(sun);
    const mats = new Map(), geos = [];
    const mat = c => { if (!mats.has(c)) mats.set(c, new THREE.MeshLambertMaterial({ color: c, flatShading: true })); return mats.get(c); };
    const G = g => (geos.push(g), g);
    const mesh = (geo, c, x = 0, y = 0, z = 0) => { const m = new THREE.Mesh(geo, mat(c)); m.position.set(x, y, z); m.castShadow = m.receiveShadow = true; return m; };
    const geo = {
      blade: G(new THREE.BoxGeometry(0.035, 1, 0.035).translate(0, 0.5, 0)),
      ico: G(new THREE.IcosahedronGeometry(1, 0)),
      trunk: G(new THREE.CylinderGeometry(0.06, 0.09, 0.42, 6).translate(0, 0.21, 0)),
      root: G(new THREE.ConeGeometry(0.08, 0.24, 6).rotateX(Math.PI)),
      leaf: G(new THREE.ConeGeometry(0.035, 0.3, 4).translate(0, 0.15, 0)),
      pump: G(new THREE.SphereGeometry(0.31, 10, 6)),
      stem: G(new THREE.CylinderGeometry(0.025, 0.035, 1, 5).translate(0, 0.5, 0)),
      disc: G(new THREE.CylinderGeometry(0.11, 0.11, 0.05, 10).rotateX(Math.PI / 2)),
      petal: G(new THREE.BoxGeometry(0.06, 0.15, 0.02).translate(0, 0.17, 0)),
      flatLeaf: G(new THREE.BoxGeometry(0.2, 0.02, 0.09).translate(0.1, 0, 0)),
      rock: G(new THREE.DodecahedronGeometry(1, 0)),
      grass: G(new THREE.BoxGeometry(0.93, 0.1, 0.93).translate(0, 0.05, 0)),
      soil: G(new THREE.BoxGeometry(0.93, 0.06, 0.93).translate(0, 0.03, 0)),
      ridge: G(new THREE.BoxGeometry(0.86, 0.07, 0.17).translate(0, 0.035, 0)),
    };
    const cx = x => x - (W - 1) / 2, cz = y => (H - 1) / 2 - y;

    // остров: земляной брусок с камнями на боках
    const island = new THREE.Group(); scene.add(island);
    island.add(mesh(G(new THREE.BoxGeometry(W + 0.14, 0.8, H + 0.14)), 0xD88A40, 0, -0.4, 0));
    const rr = rng32(W * 131 + H * 7);
    const rocks = (len, place) => {
      const n = Math.max(2, Math.round(len * 1.4));
      for (let i = 0; i < n; i++) {
        const s = 0.07 + rr() * 0.08, r = mesh(geo.rock, rr() < 0.5 ? 0xA79F8F : 0x938C7E);
        r.scale.set(s, s * 0.8, s); r.rotation.set(rr() * 3, rr() * 3, rr() * 3);
        place(r, (i + 0.5 + (rr() - 0.5) * 0.6) / n - 0.5, -0.22 - rr() * 0.42);
        island.add(r);
      }
    };
    rocks(W, (r, t, y) => r.position.set(t * W, y, H / 2 + 0.07));
    rocks(H, (r, t, y) => r.position.set(W / 2 + 0.07, y, t * H));
    rocks(H, (r, t, y) => r.position.set(-W / 2 - 0.07, y, t * H));

    const cells = [];
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const g = new THREE.Group(); g.position.set(cx(x), 0, cz(y)); island.add(g);
      cells.push({ g, ground: null, groundKind: '', plant: null, sig: '', cur: 0.3, target: 1, grass: false, x, y });
    }
    function setGround(c, soil) {
      if (c.ground) c.g.remove(c.ground);
      const gr = new THREE.Group();
      if (soil) {
        gr.add(mesh(geo.soil, 0xAF5F2A));
        for (const z of [-0.3, 0, 0.3]) gr.add(mesh(geo.ridge, 0xC77839, 0, 0.03, z));
      } else gr.add(mesh(geo.grass, [0x7E9C35, 0x86A43B, 0x77952F][(c.x * 7 + c.y * 3) % 3]));
      c.g.add(gr); c.ground = gr; c.groundKind = soil ? 'soil' : 'grass';
    }
    function plant(kind, seed, petals) {
      const r = rng32(seed), g = new THREE.Group();
      g.position.y = 0.1;
      if (kind === 'Grass') {
        for (let i = 0; i < 16; i++) {
          const b = mesh(geo.blade, [0xE8BC52, 0xD6A443, 0xF2CF6B][i % 3], (r() - 0.5) * 0.8, 0, (r() - 0.5) * 0.8);
          b.scale.y = 0.3 + r() * 0.28; b.rotation.set((r() - 0.5) * 0.3, r() * 3, (r() - 0.5) * 0.3); b.castShadow = false;
          g.add(b);
        }
      } else if (kind === 'Bush') {
        [[0, 0.2, 0, 0.23, 0x95BC44], [0.17, 0.14, 0.1, 0.16, 0x86AE3A], [-0.13, 0.13, 0.14, 0.15, 0x7FA636]].forEach(([x, y, z, s, c]) => {
          const m = mesh(geo.ico, c, x, y, z); m.scale.setScalar(s); m.rotation.set(r() * 3, r() * 3, 0); g.add(m);
        });
      } else if (kind === 'Tree') {
        g.add(mesh(geo.trunk, 0x7B5432));
        const a = mesh(geo.ico, 0x4F8F3A, 0, 0.66, 0); a.scale.set(0.36, 0.4, 0.36); a.rotation.y = r() * 3;
        const b = mesh(geo.ico, 0x62A345, 0.1, 0.86, 0.06); b.scale.setScalar(0.22);
        g.add(a, b);
      } else if (kind === 'Carrot') {
        for (const [ox, oz] of [[-0.16, 0.12], [0.17, -0.12]]) {
          g.add(mesh(geo.root, 0xEE8A2E, ox, 0.05, oz));
          for (let k = 0; k < 3; k++) { const l = mesh(geo.leaf, 0x5DA13D, ox, 0.12, oz); l.rotation.set((k - 1) * 0.45, k * 2.1, (k - 1) * 0.3); g.add(l); }
        }
      } else if (kind === 'Pumpkin') {
        const p = mesh(geo.pump, 0xEE9A34, 0, 0.22, 0); p.scale.set(1, 0.72, 1);
        const s = mesh(geo.stem, 0x6E7D2C, 0, 0.42, 0); s.scale.set(1, 0.12, 1);
        g.add(p, s);
      } else if (kind === 'Dead_Pumpkin') {
        const p = mesh(geo.pump, 0x8E7A5B, 0, 0.12, 0); p.scale.set(1.05, 0.42, 1.05); p.rotation.z = 0.2; g.add(p);
      } else if (kind === 'Sunflower') {
        const s = mesh(geo.stem, 0x4F8C36); s.scale.y = 0.56; g.add(s);
        for (const a of [0, Math.PI]) { const l = mesh(geo.flatLeaf, 0x5A9A3A, 0, 0.2, 0); l.rotation.set(0, a + 0.4, 0.35); g.add(l); }
        const head = new THREE.Group(); head.position.y = 0.58; head.rotation.x = -0.55;
        head.add(mesh(geo.disc, 0x6B3E1D));
        const n = petals || 10;
        for (let i = 0; i < n; i++) { const p = mesh(geo.petal, 0xF3C431); p.rotation.z = i * Math.PI * 2 / n; head.add(p); }
        g.add(head);
      }
      return g;
    }

    // дрон: соломенная шляпа на крестовине с четырьмя винтами
    const drone = new THREE.Group(), blades = [];
    drone.add(mesh(G(new THREE.CylinderGeometry(0.3, 0.33, 0.07, 10)), 0xE9A94C));
    drone.add(mesh(G(new THREE.CylinderGeometry(0.13, 0.17, 0.15, 10)), 0xE09A3F, 0, 0.1, 0));
    drone.add(mesh(G(new THREE.CylinderGeometry(0.05, 0.08, 0.06, 8)), 0xCF8936, 0, 0.2, 0));
    const armG = G(new THREE.BoxGeometry(1.05, 0.035, 0.055)), hubG = G(new THREE.CylinderGeometry(0.03, 0.03, 0.07, 6)), bladeG = G(new THREE.BoxGeometry(0.42, 0.012, 0.055));
    for (const a of [Math.PI / 4, -Math.PI / 4]) { const m = mesh(armG, 0x5A5236, 0, -0.03, 0); m.rotation.y = a; drone.add(m); }
    for (const [sx, sz] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) {
      const p = new THREE.Group(); p.position.set(sx * 0.37, 0.01, sz * 0.37);
      const b = mesh(bladeG, 0x4C452E, 0, 0.05, 0); b.rotation.y = sx * sz;
      p.add(mesh(hubG, 0x4C452E), b); drone.add(p); blades.push(b);
    }
    drone.scale.setScalar(0.95);
    scene.add(drone);

    const st = { fx: cx(0), fz: cz(0), tx: cx(0), tz: cz(0), t0: 0, dur: 0, act: -1e9, wx: 0, wy: 0 };
    drone.position.set(st.tx, 1.05, st.tz);
    let raf = 0, last = 0, size = { w: 1, h: 1 };
    function frame(t) {
      raf = requestAnimationFrame(frame);
      const dt = Math.min(0.1, (t - last) / 1000 || 0); last = t;
      const calm = reduceMotion();
      const k = st.dur ? Math.max(0, Math.min(1, (t - st.t0) / st.dur)) : 1, e = 1 - Math.pow(1 - k, 3);     // t кадра бывает чуть раньше t0
      drone.position.x = st.fx + (st.tx - st.fx) * e; drone.position.z = st.fz + (st.tz - st.fz) * e;
      const da = t - st.act, dip = da > 0 && da < 280 ? Math.sin(da / 280 * Math.PI) * 0.28 : 0;
      drone.position.y = 1.05 + (calm ? 0 : Math.sin(t / 420) * 0.035) - dip;
      drone.rotation.y = calm ? 0 : Math.sin(t / 900) * 0.08;
      for (const b of blades) b.rotation.y += calm ? 0.05 : 0.55;
      for (const c of cells) {
        if (!c.plant) continue;
        c.cur += (c.target - c.cur) * Math.min(1, dt * 7);
        if (c.grass) c.plant.scale.set(1, 0.12 + 0.88 * c.cur, 1);
        else c.plant.scale.setScalar(0.28 + 0.72 * c.cur);
      }
      renderer.render(scene, cam);
    }
    raf = requestAnimationFrame(frame);

    return {
      sync(w, ev, dur) {
        for (const c of cells) {
          const cell = w.cell(c.x, c.y), k = w.kind(c.x, c.y), petals = k === 'Sunflower' ? cell.e.petals : 0;
          if (c.groundKind !== cell.g) setGround(c, cell.g === 'soil');
          const sig = (k || '') + ':' + (cell.e ? cell.e.at : '') + ':' + petals;
          if (sig !== c.sig) {
            const was = c.sig.split(':')[0];
            c.sig = sig;
            if (c.plant) c.g.remove(c.plant);
            c.plant = k ? plant(k, c.x * 97 + c.y * 13 + (cell.e ? cell.e.at : 0), petals) : null;
            if (c.plant) c.g.add(c.plant);
            c.grass = k === 'Grass';
            c.cur = was === k && k !== 'Dead_Pumpkin' ? c.cur : 0.15;
          }
          c.target = k === 'Dead_Pumpkin' ? 1 : w.progress(c.x, c.y);
        }
        if (w.x !== st.wx || w.y !== st.wy) {
          const now = performance.now(), snap = !ev || ev.wrap || !dur;
          st.fx = snap ? cx(w.x) : drone.position.x; st.fz = snap ? cz(w.y) : drone.position.z;
          st.tx = cx(w.x); st.tz = cz(w.y); st.t0 = now; st.dur = snap ? 0 : dur;
          st.wx = w.x; st.wy = w.y;
        }
        if (ev && dur && ev.a !== 'move' && ev.a !== 'look') st.act = performance.now();
      },
      fit(free, far) {
        const w = host.clientWidth || 1, h = host.clientHeight || 1;
        size = { w, h };
        renderer.setSize(w, h, false);
        cam.aspect = w / h;
        const fw = Math.max(200, free ? free[1] - free[0] : w), mid = free ? (free[0] + free[1]) / 2 : w / 2;
        const t = Math.tan(cam.fov * Math.PI / 360), span = Math.max(W, H) + 0.9;
        const d = Math.max(span * 1.02 / (2 * t), span * 1.22 / (2 * t * fw / h)) * (far ? 1.3 : 1.12), el = 0.92;
        cam.position.set(0, d * Math.sin(el), d * Math.cos(el));
        cam.lookAt(0, 0.05, 0.12);
        cam.setViewOffset(w, h, w / 2 - mid, far ? -h * 0.08 : 0, w, h);     // на телефоне сверху счётчики — остров ниже
        cam.updateProjectionMatrix();
      },
      project(x, y, hgt = 0.5) {
        const v = new THREE.Vector3(cx(x), hgt, cz(y)).project(cam);
        return { x: (v.x + 1) / 2 * size.w, y: (1 - v.y) / 2 * size.h };
      },
      dispose() {
        cancelAnimationFrame(raf);
        geos.forEach(g => g.dispose()); mats.forEach(m => m.dispose());
        renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove();
      },
    };
  }

  /* ── запасной вид без WebGL: плоское поле из клеток ── */
  const GL = {
    Grass: '<path d="M12 33c1-6 0-11-3-15M20 33c0-7 1-13 4-18M28 33c-1-5 1-9 4-12" stroke="#E2B04A" stroke-width="3" fill="none" stroke-linecap="round"/>',
    Bush: '<circle cx="13.5" cy="25" r="8" fill="#86AE3A"/><circle cx="26.5" cy="25" r="8" fill="#7FA636"/><circle cx="20" cy="18" r="9.5" fill="#95BC44"/>',
    Tree: '<rect x="17.5" y="23" width="5" height="12" rx="1.5" fill="#7B5432"/><circle cx="20" cy="17" r="11.5" fill="#4F8F3A"/>',
    Carrot: '<path d="M20 12c-2-4-5-5-8-5M20 12c0-4 1-6 3-8M20 12c2-3 5-4 8-3" stroke="#5DA13D" stroke-width="2.6" fill="none" stroke-linecap="round"/><path d="M13.5 13.5h13L20 35z" fill="#EE8A2E"/>',
    Pumpkin: '<ellipse cx="20" cy="25" rx="14" ry="10" fill="#EE9A34"/><path d="M20 15.5v19" stroke="#C96A12" stroke-width="1.6"/>',
    Dead_Pumpkin: '<ellipse cx="20" cy="27" rx="13" ry="8" fill="#8E7A5B"/>',
    Sunflower: '<path d="M20 22v13" stroke="#4F8C36" stroke-width="2.6"/><circle cx="20" cy="16" r="10" fill="#F3C431"/><circle cx="20" cy="16" r="5" fill="#6B3E1D"/>',
  };
  function sceneFlat(host, lv) {
    const W = lv.w, H = lv.h, box = document.createElement('div');
    box.className = 'fg-flat'; box.style.cssText = `--w:${W};--h:${H}`;
    box.innerHTML = Array.from({ length: W * H }, () => '<div></div>').join('') + '<i class="fg-flat-drone"></i>';
    host.appendChild(box);
    const els = [...box.children].slice(0, W * H), dr = box.lastChild;
    return {
      sync(w) {
        for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
          const el = els[(H - 1 - y) * W + x], k = w.kind(x, y);
          el.className = w.cell(x, y).g === 'soil' ? 'soil' : '';
          const s = k || '';
          if (el.dataset.k !== s) { el.dataset.k = s; el.innerHTML = k ? `<svg viewBox="0 0 40 40">${GL[k]}</svg>` : ''; }
          el.style.setProperty('--g', k === 'Dead_Pumpkin' ? 1 : w.progress(x, y));
        }
        dr.style.left = (w.x + 0.5) / W * 100 + '%'; dr.style.top = (H - w.y - 0.5) / H * 100 + '%';
      },
      fit() { },
      project(x, y) { const r = box.getBoundingClientRect(), p = host.getBoundingClientRect(); return { x: r.left - p.left + (x + 0.5) / W * r.width, y: r.top - p.top + (H - y - 0.5) / H * r.height }; },
      dispose() { box.remove(); },
    };
  }

  /* ── иконки ── */
  const ITEM_SVG = {
    Hay: '<rect x="3" y="6" width="18" height="13" rx="3" fill="#E9B949"/><path d="M3 10.5h18M3 14.5h18" stroke="#C4922F" stroke-width="1.2"/><path d="M8 6v13M16 6v13" stroke="#8C5A1C" stroke-width="1.8"/>',
    Wood: '<rect x="2.5" y="8" width="16" height="9" rx="2" fill="#8E5B33"/><path d="M5 11h9M6 14h7" stroke="#764727" stroke-width="1.1"/><ellipse cx="18.5" cy="12.5" rx="3.2" ry="4.6" fill="#DDAB68"/><ellipse cx="18.5" cy="12.5" rx="1.4" ry="2.1" fill="#B07A44"/>',
    Carrot: '<path d="M14 7.5 5 21l12-9.5z" fill="#EE8A2E"/><path d="M8.5 15.5l2 1M10.5 12.5l2 1" stroke="#C86A10" stroke-width="1.2" stroke-linecap="round"/><path d="M15 8l2.5-5M15.5 9l5-2.5M14.5 8 14 3" stroke="#5DA13D" stroke-width="2" stroke-linecap="round"/>',
    Pumpkin: '<path d="M12 7c0-2 1-3 2.5-4" stroke="#6E7D2C" stroke-width="2" stroke-linecap="round" fill="none"/><ellipse cx="12" cy="14" rx="9.5" ry="7" fill="#EE9A34"/><path d="M12 7v14M7.5 8.5c-2 3-2 8 0 11M16.5 8.5c2 3 2 8 0 11" stroke="#C76E16" stroke-width="1.3" fill="none"/>',
    Power: '<path d="M13.5 2 5 13.5h6L10 22l9-12h-6.2z" fill="#F3C431" stroke="#B98A10" stroke-width="1.2" stroke-linejoin="round"/>',
  };
  const itemIcon = (k, s = 24) => `<svg viewBox="0 0 24 24" width="${s}" height="${s}" aria-hidden="true">${ITEM_SVG[k]}</svg>`;
  const svgI = (d, fill) => `<svg viewBox="0 0 24 24" aria-hidden="true" ${fill ? 'fill="currentColor"' : 'fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"'}>${d}</svg>`;
  const ICON = {
    play: svgI('<path d="M7 4.5v15l12-7.5z"/>', 1),
    step: svgI('<path d="M5 5.5v13l9-6.5z"/><rect x="16" y="5.5" width="3" height="13" rx="1"/>', 1),
    stop: svgI('<rect x="5.5" y="5.5" width="13" height="13" rx="1.5"/>', 1),
    pause: svgI('<rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/>', 1),
    reset: svgI('<path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3"/><path d="M4.5 4.5v4h4"/>'),
    min: svgI('<path d="M6 12h12"/>'),
    plus: svgI('<path d="M12 6v12M6 12h12"/>'),
    close: svgI('<path d="M7 7l10 10M17 7 7 17"/>'),
    grid: svgI('<rect x="4" y="4" width="6.5" height="6.5" rx="1"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1"/>'),
    info: svgI('<path d="M12 10.5v7"/><circle cx="12" cy="6.8" r=".6" fill="currentColor"/>'),
    task: svgI('<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 9h6M9 13h6M9 17h3"/>'),
    lock: svgI('<rect x="5.5" y="10.5" width="13" height="9.5" rx="2"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5"/>'),
    check: svgI('<path d="m5 12 5 5 9-10"/>'),
    star: svgI('<path d="m12 3.5 2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/>', 1),
    chevL: svgI('<path d="m14.5 6-6 6 6 6"/>'),
    chev: svgI('<path d="m9.5 6 6 6-6 6"/>'),
    file: svgI('<path d="M6 3.5h8l4 4V20.5H6z"/><path d="M14 3.5v4h4M9 12h6M9 16h6"/>'),
  };
  const SPEEDS = [['1×', 420, 1], ['3×', 160, 1], ['10×', 45, 1], ['Макс', 0, 400]];
  const CSS = `
.fm-host { padding: 12px clamp(8px, 1.6vw, 18px) 16px; }
.fg { position: relative; height: 640px; border-radius: 14px; overflow: hidden; color: #ECEEF1; font: 14px/1.5 var(--f-body); box-shadow: 0 20px 44px -28px rgb(20 40 60 / .7); isolation: isolate; }
.fg-stage { position: absolute; inset: 0; overflow: hidden; background: radial-gradient(110% 85% at 42% 42%, #93AEC1 0%, #7C99AE 50%, #6C889D 100%); }
.fg-view { position: absolute; inset: 0; }
.fg-stage canvas { display: block; width: 100%; height: 100%; touch-action: none; }
.fg-labels { position: absolute; inset: 0; pointer-events: none; z-index: 3; }
.fg-loading { position: absolute; inset: 0; display: grid; place-items: center; color: #fff; font-weight: 600; text-shadow: 0 1px 3px rgb(0 0 0 / .35); }
.fg-res { position: absolute; left: 16px; top: 14px; display: flex; gap: 16px; z-index: 5; pointer-events: none; }
.fg-res div { display: flex; flex-direction: column; align-items: center; gap: 3px; min-width: 38px; font: 700 13px/1 var(--f-body); color: #fff; text-shadow: 0 1px 2px rgb(0 0 0 / .5); font-variant-numeric: tabular-nums; }
.fg-res svg { width: 34px; height: 34px; filter: drop-shadow(0 2px 2px rgb(0 0 0 / .28)); }
.fg-res small { font-weight: 600; opacity: .75; font-size: 11px; }
.fg-turn { position: absolute; left: 16px; top: 70px; z-index: 5; padding: 4px 10px; border-radius: 5px; background: rgb(24 30 38 / .5); color: #fff; font: 600 13px/1.4 var(--f-body); font-variant-numeric: tabular-nums; }
.fg-turn b { font-size: 15px; }
.fg-tools { position: absolute; right: 14px; top: 14px; display: flex; gap: 8px; z-index: 6; }
.fg-tb { width: 40px; height: 40px; display: grid; place-items: center; padding: 0; border: 0; border-radius: 4px; background: #6B7B21; color: #fff; cursor: pointer; box-shadow: inset 0 2px 0 #8C9E33, inset 0 -3px 0 #4C5815, 0 3px 8px rgb(0 0 0 / .25); }
.fg-tb:hover { background: #788A27; }
.fg-tb svg { width: 20px; height: 20px; }
.fg-tb.on { background: #55621A; box-shadow: inset 0 2px 4px rgb(0 0 0 / .35); }
.fg-speed { position: absolute; left: 14px; bottom: 14px; z-index: 5; display: flex; gap: 3px; padding: 4px; border-radius: 6px; background: rgb(24 30 38 / .55); }
.fg-speed button { height: 30px; min-width: 40px; padding: 0 9px; border: 0; border-radius: 4px; background: none; color: #E4E8EC; font: 600 12.5px var(--f-body); cursor: pointer; }
.fg-speed button.on { background: #6B7B21; color: #fff; box-shadow: inset 0 -2px 0 #4C5815; }
.fg-win { position: absolute; z-index: 10; display: flex; flex-direction: column; min-width: 250px; background: rgb(30 31 35 / .95); border-radius: 4px; overflow: hidden; box-shadow: 0 16px 36px -12px rgb(10 20 30 / .6), 0 0 0 1px rgb(0 0 0 / .4); }
.fg-bar { flex: none; display: flex; align-items: center; gap: 5px; height: 34px; padding: 0 5px; background: #63676E; cursor: grab; touch-action: none; user-select: none; }
.fg-bar:active { cursor: grabbing; }
.fg-bar b { flex: 1; min-width: 0; padding-left: 5px; font: 600 13px/1 var(--f-body); color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.fg-b { flex: none; width: 24px; height: 24px; display: grid; place-items: center; padding: 0; border: 0; border-radius: 3px; background: #45484E; color: #fff; cursor: pointer; }
.fg-b svg { width: 13px; height: 13px; }
.fg-b:hover { filter: brightness(1.15); }
.fg-b.go { background: #6F8B1F; box-shadow: inset 0 -2px 0 #4E6414; }
.fg-b.stop { background: #D24E2B; box-shadow: inset 0 -2px 0 #9E3519; }
.fg-b.pause { background: #E3832C; box-shadow: inset 0 -2px 0 #AE5C15; }
.fg-b:disabled { opacity: .4; cursor: default; filter: none; }
.fg-body { flex: 1; min-height: 0; overflow: auto; padding: 14px 16px 16px; }
.fg-win.min > :not(.fg-bar) { display: none !important; }
.fg-win.min { height: auto !important; resize: none !important; }
.fg-task h3 { margin: 0 0 6px; font: 650 18px/1.25 var(--f-display); letter-spacing: -.01em; color: #fff; }
.fg-task p { margin: 0 0 10px; color: #CDD2D8; }
.fg-task code, .fg-help code, .fg-out code { font: 500 .9em var(--f-mono); background: #34363C; border: 0; border-radius: 3px; padding: 1px 4px; color: #F1F3F5; }
.fg-chip { display: inline-block; margin-bottom: 8px; padding: 2px 8px; border-radius: 3px; background: #4B5A18; color: #E3EEB0; font: 600 12px/1.5 var(--f-body); }
.fg-goal { display: grid; gap: 7px; margin: 4px 0 12px; }
.fg-goal div { display: grid; grid-template-columns: 22px 1fr auto; align-items: center; gap: 8px; font-size: 13px; font-variant-numeric: tabular-nums; }
.fg-goal i { grid-column: 2; height: 6px; border-radius: 3px; background: #3A3C42; overflow: hidden; }
.fg-goal i::after { content: ""; display: block; height: 100%; width: 100%; background: #8DB33A; border-radius: 3px; transform: scaleX(var(--p)); transform-origin: left; transition: transform .2s; }
.fg-goal div.ok span { color: #A9D35A; }
.fg-learn { margin-top: 4px; padding-top: 12px; border-top: 1px solid #3A3C42; }
.fg-learn h4 { margin: 0 0 7px; font: 600 13.5px var(--f-body); color: #fff; }
.fg-learn pre { margin: 0 0 8px; padding: 9px 11px; border-radius: 4px; background: #141518; color: #E6E9F0; font: 13px/1.6 var(--f-mono); overflow-x: auto; tab-size: 4; font-variant-ligatures: none; }
.fg-learn p { font-size: 13.5px; }
.fg-task details { margin-top: 6px; font-size: 13.5px; color: #CDD2D8; }
.fg-task summary { cursor: pointer; color: #C5DA6E; font-weight: 600; }
.fg-task details > div { margin-top: 6px; }
.fg-nav { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 14px; }
.fg-nav a, .fg-nav button { display: inline-flex; align-items: center; gap: 4px; height: 28px; padding: 0 10px; border: 0; border-radius: 3px; background: #3C3F45; color: #E6E9EC; font: 600 12.5px var(--f-body); text-decoration: none; cursor: pointer; }
.fg-nav a:hover, .fg-nav button:hover { background: #4A4D54; text-decoration: none; }
.fg-nav svg { width: 13px; height: 13px; }
.fg-nav .next { background: #6B7B21; color: #fff; }
.fg-code { resize: both; }
.fg-ed { position: relative; flex: 1; min-height: 140px; overflow: auto; background: #1B1C1F; }
.fg-ed-in { position: relative; display: flex; min-width: 100%; width: max-content; min-height: 100%; }
.fg-gut { position: sticky; left: 0; z-index: 2; flex: none; min-width: 36px; padding: 10px 8px 10px 10px; box-sizing: border-box; background: #1B1C1F; border-right: 1px solid #2B2D32; color: #5C616B; font: 13.5px/22px var(--f-mono); text-align: right; user-select: none; }
.fg-gut span { display: block; }
.fg-gut span.cur { color: #FFE38A; }
.fg-gut span.bad { color: #FF8A80; }
.fg-src { position: relative; flex: 1; min-width: 0; }
.fg-src pre, .fg-src textarea { margin: 0; padding: 10px 14px; border: 0; box-sizing: border-box; min-width: 100%; font: 13.5px/22px var(--f-mono); tab-size: 4; white-space: pre; letter-spacing: 0; font-variant-ligatures: none; font-feature-settings: "liga" 0, "calt" 0; }
.fg-src pre { position: absolute; left: 0; top: 0; pointer-events: none; color: #E6E9F0; background: none; }
.fg-src pre code { background: none; border: 0; border-radius: 0; padding: 0; color: inherit; font: inherit; }
.fg-src textarea { position: relative; display: block; width: 100%; resize: none; overflow: hidden; background: transparent; color: transparent; caret-color: #fff; outline: 0; }
.fg-src textarea::selection { background: rgb(140 170 255 / .35); color: transparent; }
.fg-src textarea[readonly] { caret-color: transparent; }
.fg-hl { position: absolute; left: 0; right: 0; height: 22px; display: none; background: rgb(255 255 255 / .1); box-shadow: inset 3px 0 0 #FFD84A; pointer-events: none; }
.fg-hl.bad { background: rgb(255 110 100 / .16); box-shadow: inset 3px 0 0 #FF7C72; }
.fg-out { flex: none; max-height: 34%; overflow: auto; padding: 8px 12px; border-top: 1px solid #2F3237; background: #232428; font-size: 13px; line-height: 1.5; }
.fg-out:empty { display: none; }
.fg-out > div { padding: 3px 0; }
.fg-out .o { font: 12.5px/1.5 var(--f-mono); color: #E6E9F0; white-space: pre-wrap; overflow-wrap: anywhere; }
.fg-out .n { color: #F5D46A; }
.fg-out .e { color: #FF9A90; }
.fg-out .e b { font-family: var(--f-mono); }
.fg-out .s { color: #AEB4BC; }
.fg-out .w { color: #A9D35A; font-weight: 600; }
.fg-out button.ln { padding: 0; border: 0; background: none; color: inherit; font: inherit; text-decoration: underline; cursor: pointer; }
.fg-tree { width: min(780px, calc(100% - 32px)) !important; }
.fg-tier { margin-bottom: 14px; }
.fg-tier h5 { margin: 0 0 8px; font: 600 12px/1.2 var(--f-body); color: #9CA2AB; text-transform: uppercase; letter-spacing: .04em; }
.fg-ups { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px; }
.fg-up { display: flex; flex-direction: column; gap: 7px; padding: 10px; border-radius: 4px; background: #2A2B30; box-shadow: inset 0 0 0 1px #3A3C42; }
.fg-up.ready { box-shadow: inset 0 0 0 1px #8DB33A; }
.fg-up.done { background: #2C3120; box-shadow: inset 0 0 0 1px #4B5A18; }
.fg-up.locked { opacity: .55; }
.fg-up .h { display: flex; align-items: center; gap: 8px; }
.fg-up .h i { flex: none; display: grid; place-items: center; width: 32px; height: 32px; border-radius: 3px; background: #3C3F45; }
.fg-up .h svg { width: 24px; height: 24px; }
.fg-up .h b { flex: 1; font-size: 14px; color: #fff; }
.fg-up .h small { color: #C5DA6E; font: 600 12px var(--f-mono); }
.fg-up p { margin: 0; font-size: 12.5px; line-height: 1.4; color: #CDD2D8; }
.fg-up p code { font: 500 .92em var(--f-mono); background: #34363C; border: 0; border-radius: 3px; padding: 0 3px; color: #F1F3F5; }
.fg-up .cost { display: flex; flex-wrap: wrap; gap: 4px 10px; font: 600 13px var(--f-body); font-variant-numeric: tabular-nums; }
.fg-up .cost span { display: inline-flex; align-items: center; gap: 3px; }
.fg-up .cost .no { color: #FF9A90; }
.fg-up .need { font-size: 12px; color: #9CA2AB; }
.fg-up .got { display: flex; align-items: center; gap: 5px; color: #A9D35A; font-weight: 600; font-size: 13px; }
.fg-up .got svg { width: 15px; height: 15px; }
.fg-up button { height: 28px; border: 0; border-radius: 3px; background: #6B7B21; color: #fff; font: 600 13px var(--f-body); cursor: pointer; box-shadow: inset 0 -2px 0 #4C5815; }
.fg-up button:disabled { background: #3C3F45; color: #8A9099; box-shadow: none; cursor: default; }
.fg-speed button:disabled { opacity: .35; cursor: default; }
.fg-cw { position: absolute; left: 0; top: 0; visibility: hidden; pointer-events: none; font: 13.5px/22px var(--f-mono); white-space: pre; font-variant-ligatures: none; }
.fg-ac { position: absolute; z-index: 20; min-width: 230px; max-width: min(420px, calc(100% - 12px)); background: #2A2B30; border-radius: 4px; box-shadow: 0 12px 26px rgb(0 0 0 / .5), 0 0 0 1px #46494F; overflow: hidden; }
.fg-ac ul { list-style: none; margin: 0; padding: 3px 0; }
.fg-ac li { display: flex; justify-content: space-between; align-items: baseline; gap: 14px; padding: 2px 10px; cursor: pointer; font: 13px/1.65 var(--f-mono); color: #D9DDE3; }
.fg-ac li b { color: #C5DA6E; font-weight: 700; }
.fg-ac li.on { background: #3A4219; color: #fff; }
.fg-ac li small { font: 11.5px var(--f-body); color: #9CA2AB; }
.fg-ac .dc { padding: 6px 10px 8px; border-top: 1px solid #3A3C42; font-size: 12.5px; line-height: 1.45; color: #CDD2D8; }
.fg-ac .dc > code { display: block; margin-bottom: 2px; padding: 0; border: 0; background: none; font: 600 12.5px var(--f-mono); color: #fff; }
.fg-ac .dc span code { font: 500 .92em var(--f-mono); background: #34363C; border: 0; border-radius: 3px; padding: 0 3px; color: #F1F3F5; }
.fg-ac.sig .dc { border-top: 0; }
.fg-tags { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 8px; }
.fg-tags .fg-chip { margin: 0; }
a.fg-chip.ege { background: #2D3A5C; color: #C9D6FF; text-decoration: none; }
a.fg-chip.ege:hover { background: #3A4A75; }
.fg-py { font-size: 13px; color: #9CA2AB !important; }
.fg-py a { color: #C5DA6E; }
.fg-data { margin: 4px 0 12px; padding: 10px 12px; border-radius: 4px; background: #26272C; box-shadow: inset 0 0 0 1px #3A3C42; font-size: 13.5px; }
.fg-data p { margin: 0 0 8px !important; color: #CDD2D8; }
.fg-data .fg-ans { color: #F5D46A; }
.fg-data code { word-break: break-all; }
.fg-file-b { display: flex; align-items: center; gap: 8px; width: 100%; margin-bottom: 6px; padding: 7px 10px; border: 0; border-radius: 3px; background: #3C3F45; color: #fff; font: 13px var(--f-body); text-align: left; cursor: pointer; }
.fg-file-b:hover { background: #4A4D54; }
.fg-file-b svg { width: 16px; height: 16px; flex: none; }
.fg-file-b b { font-family: var(--f-mono); }
.fg-file-b small { margin-left: auto; color: #AEB4BC; }
.fg-newdata { display: inline-flex; align-items: center; gap: 5px; height: 26px; padding: 0 9px; border: 0; border-radius: 3px; background: none; box-shadow: inset 0 0 0 1px #4A4D54; color: #CDD2D8; font: 600 12px var(--f-body); cursor: pointer; }
.fg-newdata svg { width: 13px; height: 13px; }
.fg-chap { display: flex; align-items: baseline; gap: 8px; margin: 14px 0 6px; font: 600 14px/1.3 var(--f-body); color: #fff; }
.fg-chap:first-of-type { margin-top: 2px; }
.fg-chap span { font: 600 11px var(--f-body); text-transform: uppercase; letter-spacing: .05em; color: #C5DA6E; }
.fg-file { width: min(640px, calc(100% - 32px)) !important; }
.fg-fileview { margin: 0; font: 12.5px/1.6 var(--f-mono); color: #E6E9F0; white-space: pre; overflow-x: auto; }
.fg-fileview span { display: inline-block; width: 42px; padding-right: 10px; text-align: right; color: #5C616B; user-select: none; }
.fg-sign { position: absolute; transform: translate(-50%, -50%); min-width: 26px; padding: 2px 5px; border-radius: 3px; background: #F4E3BF; box-shadow: 0 0 0 1.5px #8A5A34, 0 3px 6px rgb(0 0 0 / .3); color: #3B2A14; font: 700 12px/1.3 var(--f-mono); text-align: center; pointer-events: none; }
.fg-pop { left: 50%; top: 50%; transform: translate(-50%, -50%); width: min(460px, calc(100% - 32px)); max-height: calc(100% - 40px); z-index: 30; }
.fg-pop .fg-bar { cursor: default; }
.fg-lv { list-style: none; margin: 0; padding: 0; }
.fg-lv a, .fg-lv span.row { display: grid; grid-template-columns: 34px 1fr auto; align-items: center; gap: 10px; padding: 8px 6px; border-radius: 3px; color: #E8EAED; text-decoration: none; }
.fg-lv a:hover { background: #2E3035; text-decoration: none; }
.fg-lv a.cur { background: #3A4219; }
.fg-lv span.row { color: #7F858E; }
.fg-lv .n { display: grid; place-items: center; width: 30px; height: 30px; border-radius: 3px; background: #3C3F45; font: 600 13px var(--f-mono); }
.fg-lv a.done .n { background: #6B7B21; color: #fff; }
.fg-lv b { display: block; font-weight: 600; font-size: 14px; }
.fg-lv small { color: #9CA2AB; font-size: 12.5px; }
.fg-lv .st { display: flex; align-items: center; gap: 6px; color: #9CA2AB; font-size: 12.5px; font-variant-numeric: tabular-nums; }
.fg-lv .st svg { width: 16px; height: 16px; }
.fg-lv .st .ok { color: #A9D35A; } .fg-lv .st .star { color: #F3C431; }
.fg-note { margin: 0 0 10px; padding: 8px 10px; border-radius: 3px; background: #3D3520; color: #F5D46A; font-size: 13px; }
.fg-help ul { list-style: none; margin: 0 0 10px; padding: 0; display: grid; gap: 7px; font-size: 13.5px; color: #CDD2D8; }
.fg-help b { font: 600 12.5px var(--f-mono); color: #fff; }
.fg-help p { margin: 0 0 8px; font-size: 13.5px; color: #CDD2D8; }
.fg-done { position: absolute; left: 50%; top: 46%; transform: translate(-50%, -50%); z-index: 25; width: min(340px, calc(100% - 32px)); animation: fgIn .35s var(--ease); }
.fg-done .fg-body { text-align: center; }
.fg-done h3 { margin: 2px 0 6px; font: 650 22px/1.2 var(--f-display); color: #fff; }
.fg-done p { margin: 0 0 6px; color: #CDD2D8; }
.fg-done .stars { display: inline-flex; align-items: center; gap: 5px; color: #F3C431; font-weight: 600; }
.fg-done .stars svg { width: 18px; height: 18px; }
.fg-done .pts { color: #A9D35A; font-weight: 700; }
.fg-done .fg-nav { justify-content: center; }
.fg-fly { position: absolute; display: flex; align-items: center; gap: 3px; transform: translate(-50%, -100%); font: 800 15px/1 var(--f-body); color: #fff; text-shadow: 0 1px 3px rgb(0 0 0 / .55); white-space: nowrap; animation: fgFly 1s var(--ease) forwards; }
.fg-pet { position: absolute; transform: translate(-50%, -50%); padding: 1px 5px; border-radius: 3px; background: rgb(30 31 35 / .82); color: #F3C431; font: 700 11px/1.4 var(--f-mono); }
@keyframes fgFly { from { opacity: 0; margin-top: 6px; } 15% { opacity: 1; } to { opacity: 0; margin-top: -34px; } }
@keyframes fgIn { from { opacity: 0; transform: translate(-50%, -44%); } }
.fg-flat { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); display: grid; grid-template-columns: repeat(var(--w), 1fr); width: min(70%, calc(var(--w) * 80px)); aspect-ratio: var(--w) / var(--h); border-radius: 6px; overflow: hidden; background: #D88A40; box-shadow: 0 12px 0 #B86E2C; }
.fg-flat div { position: relative; background: #7E9C35; box-shadow: inset 0 0 0 2px #6C8A2B; }
.fg-flat div.soil { background: #AF5F2A repeating-linear-gradient(0deg, transparent 0 8px, #C77839 8px 12px); box-shadow: inset 0 0 0 2px #96501F; }
.fg-flat svg { position: absolute; inset: 10%; transform: scale(calc(.3 + .7 * var(--g, 1))); }
.fg-flat-drone { position: absolute; width: 26px; height: 26px; margin: -13px 0 0 -13px; border-radius: 50%; background: #E9A94C; box-shadow: 0 0 0 3px #5A5236, 0 6px 10px rgb(0 0 0 / .3); transition: left .15s, top .15s; }
.fg.narrow { height: auto !important; overflow: visible; box-shadow: none; border-radius: 0; }
.fg.narrow .fg-stage { position: relative; height: clamp(300px, 80vw, 500px); border-radius: 12px; }
.fg.narrow > .fg-win:not(.fg-pop):not(.fg-done) { position: static; width: auto !important; height: auto !important; margin-top: 12px; resize: none; }
.fg.narrow .fg-ed { min-height: 220px; max-height: 60vh; }
.fg.narrow .fg-pop { position: fixed; z-index: 200; }
.fg.narrow .fg-tb { width: 36px; height: 36px; }
@media (prefers-reduced-motion: reduce) { .fg-fly, .fg-done { animation: none; } }
`;
  function injectCSS() {
    let s = document.getElementById('fm-css');
    if (!s) { s = document.createElement('style'); s.id = 'fm-css'; document.head.appendChild(s); }
    s.textContent = CSS;
  }
  const unlocked = (lv, ctx) => ctx.all || lv.id === 1 || ctx.done[lv.id] != null || ctx.done[(lv.need || lv.id - 1)] != null;
  const hodov = n => `${n.toLocaleString('ru-RU')} ${plural(n, 'ход', 'хода', 'ходов')}`;
  const shortN = n => n >= 10000 ? Math.round(n / 1000) + 'k' : n >= 1000 ? (n / 1000).toFixed(1).replace('.0', '') + 'k' : String(n);

  function levelsHTML(ctx, cur, note) {
    const row = l => {
      const best = ctx.done[l.id], open = unlocked(l, ctx), done = best != null;
      const st = done ? `${l.par && best <= l.par ? `<span class="star" title="Уложились в норму">${ICON.star}</span>` : ''}${l.goal ? `<span>${hodov(best)}</span>` : ''}<span class="ok">${ICON.check}</span>`
        : open ? '' : `<span title="Откроется после уровня ${l.need}">${ICON.lock}</span>`;
      const inner = `<span class="n">${l.id}</span><span><b>${esc(l.title)}</b><small>${esc(l.concept)}${l.ege.length ? ` · ЕГЭ №${l.ege.join(', ')}` : ''}</small></span><span class="st">${st}</span>`;
      return `<li>${open ? `<a href="#farm-${l.id}" class="${done ? 'done' : ''} ${l === cur ? 'cur' : ''}">${inner}</a>` : `<span class="row">${inner}</span>`}</li>`;
    };
    return (note ? `<p class="fg-note">${note}</p>` : '') + CHAPTERS.map(c => `<h5 class="fg-chap"><span>Глава ${c.id}</span>${esc(c.title)}</h5><ul class="fg-lv">${c.levels.map(id => row(LEVELS.find(l => l.id === id))).join('')}</ul>`).join('');
  }

  function mount(box, ctx) {
    injectCSS();
    box.classList.add('fm-host');
    const ctl = { destroy() { } }, off = new AbortController();      // обработчики снимаются вместе с игрой
    const wanted = ctx.level ? LEVELS.find(l => l.id === ctx.level) : null;
    const firstOpen = ORDER.map(id => LEVELS.find(l => l.id === id)).find(l => (l.goal || l.answer) && ctx.done[l.id] == null && unlocked(l, ctx));
    const base = wanted && unlocked(wanted, ctx) ? wanted : firstOpen || LEVELS[LEVELS.length - 1];
    // своя ферма: амбар и купленные улучшения — из прогресса
    let save = base.sandbox ? JSON.parse(JSON.stringify((ctx.farmSave && ctx.farmSave()) || { t: 0, items: {}, up: {} })) : null;
    let lv = base.sandbox ? sandbox(save) : base;
    let note = '';
    if (wanted && !unlocked(wanted, ctx)) note = `Уровень ${wanted.id} откроется, когда вы пройдёте уровень ${wanted.need}.`;
    else if (ctx.level && !wanted) note = 'Такого уровня нет — выберите из списка.';
    const openLevels = !ctx.level || !!note;
    const hl = ctx.hl || esc;
    const codeKey = 'farm-code-' + lv.id;
    let code = ctx.store.get(codeKey, null) ?? lv.start;
    let speed = Math.min(lv.sandbox ? 2 : 3, Math.max(0, +ctx.store.get('farm-speed', 1) || 0));        // в своей ферме время идёт по-настоящему
    const oi = ORDER.indexOf(lv.id), prev = LEVELS.find(l => l.id === ORDER[oi - 1]), next = LEVELS.find(l => l.id === ORDER[oi + 1]);
    // уровень-задача: свои данные на каждый заход (таблички, строка, файлы, числа из условия)
    let data = null;
    const newData = () => { data = lv.gen ? lv.gen(rng32(Math.floor(Math.random() * 1e9))) : null; };
    newData();
    const showPet = !lv.api || lv.api.includes('measure');
    const helpHTML = () => `<ul>${(lv.api || Object.keys(DOC)).filter(n => DOC[n] && n !== 'get_pos_y').map(n => `<li><b>${esc(DOC[n][0])}</b> — ${DOC[n][1]}</li>`).join('')}</ul>
          <p>Каждая команда дрону — один ход. <code>get_pos_x()</code>, <code>get_world_size()</code> и <code>num_items()</code> бесплатны. Работает и обычный Python: <code>print()</code>, <code>range()</code>, <code>len()</code>, <code>min()</code>, <code>max()</code>, списки, словари, свои функции.</p>
          <p>В редакторе при наборе появляются подсказки: ↑ ↓ — выбрать, Tab или Enter — вставить, Esc — закрыть. Tab — отступ, Shift+Tab — убрать отступ, Ctrl+Enter — запуск, Esc и затем Tab — выйти из редактора. Окна можно перетаскивать за заголовок и сворачивать.</p>`;
    const goalItems = lv.goal ? Object.keys(lv.goal) : [];

    box.innerHTML = `<div class="fg" role="application" aria-label="Ферма: уровень ${lv.id}">
      <div class="fg-stage"><div class="fg-view"><div class="fg-loading">Загружаем ферму…</div></div>
      <div class="fg-labels"></div>
      <div class="fg-res" aria-label="Урожай"></div>
      <div class="fg-turn">Ход <b>0</b>${lv.goal ? ` / ${lv.limit.toLocaleString('ru-RU')}` : ''}${lv.answer ? ' · шагов программы <i>0</i>' : ''}</div>
      <div class="fg-tools">${lv.sandbox ? `<button type="button" class="fg-tb" data-fg="tree" title="Улучшения" aria-label="Улучшения">${ICON.plus}</button>` : ''}<button type="button" class="fg-tb" data-fg="levels" title="Уровни" aria-label="Уровни">${ICON.grid}</button><button type="button" class="fg-tb" data-fg="help" title="Команды дрона" aria-label="Команды дрона">${ICON.info}</button></div>
      <div class="fg-speed" role="group" aria-label="Скорость">${SPEEDS.map((s, i) => `<button type="button" data-speed="${i}" class="${i === speed ? 'on' : ''}" aria-pressed="${i === speed}" ${i === 3 && lv.sandbox ? 'disabled title="В своей ферме время идёт по-настоящему"' : ''}>${s[0]}</button>`).join('')}</div></div>
      <section class="fg-win fg-task" data-win="task" aria-label="Задание"><div class="fg-bar"><b>Уровень ${lv.id} · ${esc(lv.title)}</b><button type="button" class="fg-b" data-fg="min" aria-label="Свернуть">${ICON.min}</button></div>
        <div class="fg-body"><div class="fg-tags"><span class="fg-chip">${esc(lv.concept)}</span>${lv.ege.map(n => `<a class="fg-chip ege" href="#ege-${n}" title="${esc((ctx.egeTitle && ctx.egeTitle(n)) || 'Разбор задания в методичке')}">ЕГЭ №${n}</a>`).join('')}</div><h3>${esc(lv.title)}</h3><p class="fg-text"></p>
          ${lv.goal ? '<div class="fg-goal"></div>' : ''}
          ${lv.answer ? '<div class="fg-data"></div>' : ''}
          <div class="fg-learn"><h4>${esc(lv.learn[0])}</h4><pre>${hl(lv.learn[1])}</pre><p>${lv.learn[2]}</p></div>
          ${lv.py.length ? `<p class="fg-py">В учебнике: ${lv.py.map(id => `<a href="#py-${id}">${esc((ctx.topic && ctx.topic(id)) || 'тема ' + id)}</a>`).join(' · ')}</p>` : ''}
          <details><summary>Подсказка</summary><div>${lv.hint}</div></details>
          <div class="fg-nav">${prev ? `<a href="#farm-${prev.id}">${ICON.chevL}Уровень ${prev.id}</a>` : ''}${next && unlocked(next, ctx) ? `<a href="#farm-${next.id}">Уровень ${next.id}${ICON.chev}</a>` : ''}<button type="button" data-fg="restore">Начать код заново</button></div></div></section>
      <section class="fg-win fg-code" data-win="code" aria-label="Программа"><div class="fg-bar">
          <button type="button" class="fg-b go" data-fg="run" aria-label="Запустить" title="Запустить (Ctrl+Enter)">${ICON.play}</button>
          <button type="button" class="fg-b go" data-fg="step" aria-label="Шаг" title="Выполнить до следующей команды дрону">${ICON.step}</button>
          <button type="button" class="fg-b" data-fg="reset" aria-label="Заново" title="Вернуть поле в начало">${ICON.reset}</button>
          <b>уровень_${lv.id}.py</b><button type="button" class="fg-b" data-fg="min" aria-label="Свернуть">${ICON.min}</button></div>
        <div class="fg-ed"><div class="fg-ed-in"><div class="fg-gut" aria-hidden="true"></div><div class="fg-src"><div class="fg-hl"></div><pre aria-hidden="true"><code></code></pre>
          <textarea spellcheck="false" autocapitalize="off" autocomplete="off" autocorrect="off" wrap="off" aria-label="Программа на Python" aria-autocomplete="list"></textarea><span class="fg-cw" aria-hidden="true">xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx</span></div></div></div>
        <div class="fg-out" aria-live="polite"></div><div class="fg-ac" role="listbox" aria-label="Подсказки" hidden></div></section>
      ${lv.sandbox ? `<section class="fg-win fg-pop fg-tree" data-win="tree" aria-label="Улучшения" hidden><div class="fg-bar"><b>Улучшения</b><button type="button" class="fg-b" data-fg="tree" aria-label="Закрыть">${ICON.close}</button></div><div class="fg-body"></div></section>` : ''}
      <section class="fg-win fg-pop" data-win="levels" aria-label="Уровни" ${openLevels ? '' : 'hidden'}><div class="fg-bar"><b>Ферма · уровни</b><button type="button" class="fg-b" data-fg="levels" aria-label="Закрыть">${ICON.close}</button></div>
        <div class="fg-body">${levelsHTML(ctx, lv, note || `Дрон-фермер слушается только программы на Python. Каждый уровень учит одной вещи, за первое прохождение — ${ctx.points || 10} баллов.`)}</div></section>
      <section class="fg-win fg-pop fg-file" data-win="file" aria-label="Файл" hidden><div class="fg-bar"><b></b><button type="button" class="fg-b" data-fg="file" aria-label="Закрыть">${ICON.close}</button></div><div class="fg-body"></div></section>
      <section class="fg-win fg-pop fg-help" data-win="help" aria-label="Команды" hidden><div class="fg-bar"><b>Команды дрона</b><button type="button" class="fg-b" data-fg="help" aria-label="Закрыть">${ICON.close}</button></div>
        <div class="fg-body">${helpHTML()}</div></section>
    </div>`;
    const $ = s => box.querySelector(s);
    const fg = $('.fg'), stage = $('.fg-view'), labels = $('.fg-labels');
    const taskW = $('[data-win="task"]'), codeW = $('[data-win="code"]');
    const ta = $('textarea'), pre = $('.fg-src pre code'), gut = $('.fg-gut'), hlLine = $('.fg-hl'), out = $('.fg-out'), src = $('.fg-src');
    const runB = $('[data-fg="run"]'), stepB = $('[data-fg="step"]');
    ta.value = code;
    let run = null, world = new World(lv, 0, data), mode = 'idle', timer = 0, outN = 0, mark = null, saveT = 0, view = null, dead = false, narrow = false;

    function renderTask() {
      $('.fg-text').innerHTML = typeof lv.text === 'function' ? lv.text(data) : lv.text;
      const box = $('.fg-data'); if (!box || !data) return;
      const vars = Object.entries(data.vars || {}), files = Object.entries(data.files || {});
      box.innerHTML = `<p class="fg-ans">Ответ сдаётся командой <code>answer(…)</code>. Данные свои при каждом заходе — ответ нужно посчитать программой.</p>
        ${vars.length ? `<p>В программе уже есть: ${vars.map(([k, v]) => `<code>${esc(k)} = ${esc(repr(v))}</code>`).join(' ')}</p>` : ''}
        ${files.map(([n, t]) => `<button type="button" class="fg-file-b" data-file="${esc(n)}">${ICON.file}<b>${esc(n)}</b><small>${t.trimEnd().split('\n').length} ${plural(t.trimEnd().split('\n').length, 'строка', 'строки', 'строк')}</small></button>`).join('')}
        ${data.label ? `<p class="fg-labeltxt">Табличка на амбаре: <code>${esc(data.label.length > 90 ? data.label.slice(0, 90) + '…' : data.label)}</code></p>` : ''}
        <button type="button" class="fg-newdata" data-fg="newdata">${ICON.reset}Новые данные</button>`;
    }
    function showFile(name) {
      const t = (data.files || {})[name]; if (t === undefined) return;
      const lines = t.trimEnd().split('\n'), p = $('[data-win="file"]');
      p.querySelector('.fg-bar b').textContent = `${name} · ${lines.length} ${plural(lines.length, 'строка', 'строки', 'строк')}`;
      p.querySelector('.fg-body').innerHTML = `<pre class="fg-fileview">${lines.slice(0, 300).map((l, i) => `<span>${i + 1}</span>${esc(l.length > 200 ? l.slice(0, 200) + '…' : l)}`).join('\n')}</pre>${lines.length > 300 ? `<p class="fg-note">Показаны первые 300 строк из ${lines.length}. Программа читает файл целиком.</p>` : ''}`;
      box.querySelectorAll('.fg-pop').forEach(x => { x.hidden = x !== p; });
    }
    renderTask();

    /* окна: положение и размер помнятся в браузере */
    const ui = ctx.store.get('farm-ui', {}) || {};
    let zTop = 12;
    function place() {
      const W = fg.clientWidth, H = fg.clientHeight;
      const cw = Math.round(Math.min(500, Math.max(360, W * 0.38)));
      const def = { task: { x: 16, y: 108, w: Math.min(330, Math.max(270, W * 0.26)), h: 0 }, code: { x: W - cw - 16, y: 66, w: cw, h: H - 82 } };
      for (const [name, el] of [['task', taskW], ['code', codeW]]) {
        const s = { ...def[name], ...(ui[name] || {}) };
        s.w = Math.min(s.w, W - 24); s.x = Math.max(0, Math.min(s.x, W - Math.min(s.w, 160)));
        s.y = Math.max(0, Math.min(s.y, H - 40));
        el.style.left = s.x + 'px'; el.style.top = s.y + 'px'; el.style.width = s.w + 'px';
        if (name === 'code') el.style.height = Math.max(220, Math.min(s.h || def.code.h, H - s.y - 8)) + 'px';
        else el.style.maxHeight = (H - s.y - 70) + 'px';
        el.classList.toggle('min', !!s.min);
      }
    }
    function saveUI() {
      if (narrow) return;
      for (const [name, el] of [['task', taskW], ['code', codeW]]) {
        ui[name] = { x: el.offsetLeft, y: el.offsetTop, w: el.offsetWidth, min: el.classList.contains('min') ? 1 : 0 };
        if (name === 'code' && !el.classList.contains('min')) ui[name].h = el.offsetHeight;
      }
      ctx.store.set('farm-ui', ui);
    }
    function freeZone() {
      if (narrow) return null;
      const W = fg.clientWidth;
      let a = 0, b = W;
      if (!codeW.classList.contains('min') && codeW.offsetLeft > W * 0.45) b = codeW.offsetLeft;
      if (taskW.offsetLeft < W * 0.3) a = Math.max(a, taskW.offsetLeft + taskW.offsetWidth * (taskW.classList.contains('min') ? 0 : 0.85));
      if (b - a < 320) { a = 0; b = Math.max(b, 320); }
      return [a, b];
    }
    function layout() {
      if (dead) return;
      const wasNarrow = narrow;
      narrow = box.clientWidth < 860;
      fg.classList.toggle('narrow', narrow);
      if (!narrow) {
        const top = fg.getBoundingClientRect().top + scrollY, tb = document.getElementById('tabbar');
        const tbh = tb && tb.offsetParent ? tb.offsetHeight : 0;
        fg.style.height = Math.max(580, innerHeight - top - tbh - 16) + 'px';
        place();
      } else if (!wasNarrow) { fg.style.height = ''; }
      if (view) { view.fit(freeZone(), narrow); view.sync(world); petals(); }
      paint();
    }
    // перетаскивание за заголовок
    for (const win of [taskW, codeW]) {
      const bar = win.querySelector('.fg-bar');
      win.addEventListener('pointerdown', () => { if (!narrow) win.style.zIndex = ++zTop; });
      bar.addEventListener('pointerdown', e => {
        if (narrow || e.button !== 0 || e.target.closest('button')) return;
        const x0 = win.offsetLeft, y0 = win.offsetTop, sx = e.clientX, sy = e.clientY;
        bar.setPointerCapture(e.pointerId);
        const mv = ev => {
          win.style.left = Math.max(0, Math.min(x0 + ev.clientX - sx, fg.clientWidth - 80)) + 'px';
          win.style.top = Math.max(0, Math.min(y0 + ev.clientY - sy, fg.clientHeight - 36)) + 'px';
        };
        const up = () => { bar.removeEventListener('pointermove', mv); bar.removeEventListener('pointerup', up); bar.removeEventListener('pointercancel', up); saveUI(); if (view) { view.fit(freeZone()); petals(); } };
        bar.addEventListener('pointermove', mv); bar.addEventListener('pointerup', up); bar.addEventListener('pointercancel', up);
      });
    }
    const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(() => { clearTimeout(ro.t); ro.t = setTimeout(() => { if (!narrow) saveUI(); layout(); }, 80); }) : null;
    if (ro) { ro.observe(box); ro.observe(codeW); }
    const onResize = () => layout();
    addEventListener('resize', onResize, { signal: off.signal });

    /* сцена */
    function attach(make) {
      if (dead) return;
      stage.innerHTML = '';
      view = make();
      view.fit(freeZone(), narrow); view.sync(world); petals();
    }
    let THREE_ = null;
    // сцена пересоздаётся, когда поле выросло
    const build = () => { if (view) { view.dispose(); view = null; } if (THREE_) { try { attach(() => scene3d(THREE_, stage, lv)); return; } catch (e) { } } attach(() => sceneFlat(stage, lv)); };
    loadThree().then(T => { THREE_ = T; build(); }, build);
    // подписи над клетками: число на табличке и лепестки подсолнуха
    function petals() {
      labels.querySelectorAll('.fg-pet, .fg-sign').forEach(x => x.remove());
      if (!view) return;
      const tag = (x, y, hgt, cls, text) => { const p = view.project(x, y, hgt), d = document.createElement('span'); d.className = cls; d.textContent = text; d.style.left = p.x + 'px'; d.style.top = p.y + 'px'; labels.appendChild(d); };
      for (let y = 0; y < lv.h; y++) for (let x = 0; x < lv.w; x++) {
        const c = world.cell(x, y);
        if (c.sign !== undefined) tag(x, y, 0.3, 'fg-sign', c.sign);
        if (showPet && c.e && c.e.type === 'Sunflower') tag(x, y, 0.95, 'fg-pet', c.e.petals);
      }
    }

    /* редактор */
    function paint() {
      const v = ta.value;
      pre.innerHTML = hl(v) + '\n';
      const n = v.split('\n').length;
      if (gut.childElementCount !== n) gut.innerHTML = Array.from({ length: n }, (_, i) => `<span>${i + 1}</span>`).join('');
      ta.style.height = (n * 22 + 20) + 'px';
      ta.style.width = ''; ta.style.width = Math.max(src.clientWidth, pre.parentNode.scrollWidth) + 'px';
      showMark();
    }
    function showMark() {
      [...gut.children].forEach((s, i) => { s.className = mark && mark.line === i + 1 ? (mark.bad ? 'bad' : 'cur') : ''; });
      if (!mark) { hlLine.style.display = 'none'; return; }
      hlLine.style.display = 'block'; hlLine.style.top = (10 + (mark.line - 1) * 22) + 'px';
      hlLine.classList.toggle('bad', !!mark.bad);
    }
    function setMark(line, bad) { mark = line ? { line, bad } : null; showMark(); }
    function revealLine(line) {
      const ed = $('.fg-ed'), top = 10 + (line - 1) * 22;
      if (top < ed.scrollTop || top > ed.scrollTop + ed.clientHeight - 30) ed.scrollTop = top - 60;
    }
    ta.addEventListener('input', () => {
      code = ta.value; setMark(null); paint(); acUpdate(true);
      clearTimeout(saveT); saveT = setTimeout(() => ctx.store.set(codeKey, code), 400);
    });
    let tabOut = false;
    function edit(a, b, text) { ta.setRangeText(text, a, b, 'end'); ta.dispatchEvent(new Event('input')); }
    ta.addEventListener('keydown', e => {
      if (ac && !acEl.hidden) {
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); ac.sel = (ac.sel + (e.key === 'ArrowDown' ? 1 : ac.items.length - 1)) % ac.items.length; acShow(); return; }
        if ((e.key === 'Enter' || e.key === 'Tab') && !e.shiftKey && !e.ctrlKey && !e.metaKey) { e.preventDefault(); acAccept(ac.sel); return; }
        if (e.key === 'Escape') { e.preventDefault(); acHide(); return; }
      } else if (e.key === 'Escape' && !acEl.hidden) { e.preventDefault(); acHide(); return; }
      if (e.key === 'Escape') { tabOut = true; return; }
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); start(); return; }
      if (ta.readOnly) return;
      if (e.key === 'Tab' && !tabOut) {
        e.preventDefault();
        const v = ta.value, a = ta.selectionStart, b = ta.selectionEnd, ls = v.lastIndexOf('\n', a - 1) + 1;
        if (a === b && !e.shiftKey) { edit(a, b, '    '); return; }
        const le = v.indexOf('\n', b - (b > a && v[b - 1] === '\n' ? 1 : 0)), end = le < 0 ? v.length : le;
        const nl = v.slice(ls, end).split('\n').map(l => e.shiftKey ? l.replace(/^ {1,4}/, '') : '    ' + l).join('\n');
        ta.setRangeText(nl, ls, end, 'select'); ta.dispatchEvent(new Event('input'));
        return;
      }
      tabOut = false;
      if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        const v = ta.value, a = ta.selectionStart, line = v.slice(v.lastIndexOf('\n', a - 1) + 1, a);
        let ind = /^ */.exec(line)[0];
        if (/:\s*(#.*)?$/.test(line)) ind += '    ';
        else if (/^\s*(return|break|continue|pass)\b/.test(line)) ind = ind.slice(4);
        edit(a, ta.selectionEnd, '\n' + ind);
      } else if (e.key === 'Backspace' && ta.selectionStart === ta.selectionEnd) {
        const v = ta.value, a = ta.selectionStart, before = v.slice(v.lastIndexOf('\n', a - 1) + 1, a);
        if (before.length && /^ +$/.test(before)) { e.preventDefault(); edit(a - ((before.length - 1) % 4 + 1), a, ''); }
      }
    });

    /* поле и счётчики */
    function draw(ev) {
      const w = world;
      if (view) {
        view.sync(w, ev, speed === 3 ? 0 : Math.min(SPEEDS[speed][1], 260));
        if (ev && ev.got && speed < 3) fly(ev);
        if (ev && (ev.a === 'plant' || ev.a === 'harvest' || ev.a === 'till')) petals();
      }
      $('.fg-turn b').textContent = w.t.toLocaleString('ru-RU');
      opsShow();
      const items = [...new Set([...goalItems, ...Object.keys(w.items)])];
      $('.fg-res').innerHTML = items.map(k => `<div title="${ITEMS[k]}">${itemIcon(k, 34)}<span>${shortN(w.items[k] || 0)}</span></div>`).join('');
      if (lv.goal) $('.fg-goal').innerHTML = goalItems.map(k => {
        const n = lv.goal[k], h = Math.min(n, w.items[k] || 0);
        return `<div class="${h >= n ? 'ok' : ''}">${itemIcon(k, 20)}<i style="--p:${h / n}"></i><span>${h} / ${n}</span></div>`;
      }).join('');
    }
    function opsShow() { const i = $('.fg-turn i'); if (i) i.textContent = run ? run.ip.ops.toLocaleString('ru-RU') : '0'; }
    function fly(ev) {
      const p = view.project(ev.x, ev.y, 0.9), f = document.createElement('span');
      f.className = 'fg-fly'; f.innerHTML = `+${ev.got.n}${itemIcon(ev.got.item, 18)}`;
      f.style.left = p.x + 'px'; f.style.top = p.y + 'px';
      labels.appendChild(f); setTimeout(() => f.remove(), 1000);
    }

    /* журнал */
    function log(cls, html) {
      if (outN > 300) return;
      outN++;
      const d = document.createElement('div'); d.className = cls; d.innerHTML = html; out.appendChild(d); out.scrollTop = out.scrollHeight;
    }
    function flushOut() {
      if (!run) return;
      while (run.outI < run.out.length) { const o = run.out[run.outI++]; log(o.k === 'out' ? 'o' : 'n', esc(o.k === 'out' ? o.s.replace(/\n$/, '') : o.s)); }
    }

    /* запуск */
    function setMode(m) {
      mode = m;
      const on = m === 'run';
      runB.className = 'fg-b ' + (on ? 'stop' : 'go'); runB.innerHTML = on ? ICON.stop : ICON.play;
      runB.setAttribute('aria-label', on ? 'Остановить' : m === 'pause' ? 'Продолжить' : 'Запустить');
      runB.title = on ? 'Остановить' : m === 'pause' ? 'Продолжить' : 'Запустить (Ctrl+Enter)';
      stepB.className = 'fg-b ' + (on ? 'pause' : 'go'); stepB.innerHTML = on ? ICON.pause : ICON.step;
      stepB.setAttribute('aria-label', on ? 'Пауза' : 'Шаг'); stepB.title = on ? 'Пауза' : 'Выполнить до следующей команды дрону';
      ta.readOnly = m === 'run' || m === 'pause';
    }
    // амбар своей фермы: собранное сохраняется во время работы (в браузере) и после остановки (в аккаунте)
    let keptAt = 0;
    function keep(cloud) {
      if (!lv.sandbox || !run) return;
      save = { ...save, t: Date.now(), items: { ...run.world.items } };
      keptAt = NOW();
      if (ctx.onFarmSave) ctx.onFarmSave(save, cloud);
    }
    function fresh() {
      clearTimeout(timer); timer = 0;
      fg.querySelector('.fg-done')?.remove();
      out.innerHTML = ''; outN = 0;
      if (lv.sandbox) lv = sandbox(save);
      run = new Run(lv, ta.value, { data }); run.outI = 0;
      world = run.world; draw(); petals();
      if (run.state === 'error') { finish(); return false; }
      return true;
    }
    function start() {
      if (mode === 'run') { stop('Программа остановлена.'); return; }
      if (mode !== 'pause' && !fresh()) return;
      setMode('run'); loop();
    }
    function stop(msg) {
      clearTimeout(timer); timer = 0;
      if (mode !== 'idle') keep(true);
      if (msg) log('s', esc(msg));
      setMode('idle'); setMark(null);
    }
    function pause() { clearTimeout(timer); timer = 0; setMode('pause'); if (run) { setMark(run.ip.line); revealLine(run.ip.line); } }
    function stepOnce() {
      if (mode === 'run') return pause();
      if (mode !== 'pause') { if (!fresh()) return; setMode('pause'); }
      let ev; const t0 = NOW();
      do { ev = run.step(); } while (ev === IDLE && NOW() - t0 < 2000);
      draw(ev); flushOut();
      if (run.state !== 'run') return finish();
      setMark(run.ip.line); revealLine(run.ip.line);
    }
    function loop() {
      timer = 0;
      if (mode !== 'run' || !run || dead) return;
      const [, ms, batch] = SPEEDS[speed], t0 = NOW();
      let acts = 0, last = null;
      while (run.state === 'run') {
        const ev = run.step();
        if (ev && ev !== IDLE) { acts++; last = ev; if (speed < 3) draw(ev); if (acts >= batch) break; }
        if (NOW() - t0 > 14) break;
      }
      if (speed === 3) draw(last);
      flushOut(); opsShow();
      if (lv.sandbox && NOW() - keptAt > 3000) { keep(false); if (!$('[data-win="tree"]').hidden) treeRender(); }
      if (run.state !== 'run') return finish();
      if (speed < 3) setMark(run.ip.line);
      timer = setTimeout(loop, acts ? ms : 0);
    }
    function finish() {
      clearTimeout(timer); timer = 0;
      flushOut(); petals();
      const st = run.state, t = run.world.t;
      keep(true);
      setMode('idle');
      if (st === 'error') {
        const e = run.error;
        setMark(e.line, true); if (e.line) revealLine(e.line);
        if (codeW.classList.contains('min')) codeW.classList.remove('min');
        log('e', `${e.line ? `<button type="button" class="ln" data-line="${e.line}">Строка ${e.line}</button>: ` : ''}<b>${esc(e.type)}</b> — ${esc(e.message)}`);
        return;
      }
      setMark(null);
      if (st === 'win') return win(t);
      if (st === 'wrong') {
        const w = run.wrong;
        log('e', w.got !== w.n ? `answer() ждёт ${w.n} ${plural(w.n, 'значение', 'значения', 'значений')} через запятую, а получила ${w.got}.` : `Ответ <b>${esc(w.given)}</b> не подходит. Проверьте программу: выведите промежуточные значения через <code>print()</code>.`);
        return;
      }
      if (st === 'end' && lv.answer) { log('s', 'Программа закончилась, но ответ не сдан. В конце вызовите <code>answer(…)</code>.'); return; }
      if (st === 'limit') log('e', `Закончились ходы: на уровне их ${lv.limit.toLocaleString('ru-RU')}. Цель не выполнена — посмотрите, где дрон тратит ходы зря.`);
      else if (st === 'end') log('s', lv.goal ? (lv.id > 1 && !/while/.test(ta.value) ? 'Программа закончилась, а цель ещё не выполнена. Чтобы дрон работал, пока цель не выполнена, поместите команды в цикл <code>while True:</code>.' : 'Программа закончилась, а цель ещё не выполнена.') : `Программа закончилась за ${hodov(t)}.`);
    }
    function win(t) {
      const res = ctx.onWin ? ctx.onWin(lv.id, t) : { first: false, best: t };
      const star = lv.par && t <= lv.par;
      log('w', lv.answer ? 'Ответ верный.' : `Цель выполнена за ${hodov(t)}.`);
      const d = document.createElement('section'); d.className = 'fg-win fg-done'; d.setAttribute('aria-label', 'Уровень пройден');
      d.innerHTML = `<div class="fg-bar"><b>Уровень ${lv.id} пройден</b></div><div class="fg-body"><h3>${lv.answer ? 'Ответ верный!' : 'Урожай собран!'}</h3>
        <p>${lv.answer ? `Задача решена${lv.ege.length ? ` — так же решается задание ЕГЭ №${lv.ege.join(', ')}` : ''}. Нажмите «Ещё раз» — данные будут новые.` : `Цель выполнена за ${hodov(t)}.${res.best < t ? ` Ваш рекорд — ${hodov(res.best)}.` : ''}`}</p>
        ${lv.par ? (star ? `<p class="stars">${ICON.star}Уложились в норму: ${hodov(lv.par)}</p>` : `<p>Норма для звезды — ${hodov(lv.par)}. Можно короче!</p>`) : ''}
        ${res.points ? `<p class="pts">+${res.points} баллов</p>` : ''}
        <div class="fg-nav">${next ? `<a class="next" href="#farm-${next.id}">Следующий уровень${ICON.chev}</a>` : `<button type="button" data-fg="levels">Все уровни</button>`}<button type="button" data-fg="again">Ещё раз</button></div></div>`;
      fg.appendChild(d);
      $('[data-win="levels"] .fg-body').innerHTML = levelsHTML(ctx, lv, '');
    }
    function resetField() { stop(); fg.querySelector('.fg-done')?.remove(); out.innerHTML = ''; outN = 0; run = null; if (lv.sandbox) lv = sandbox(save); world = new World(lv, 0, data); draw(); petals(); opsShow(); }

    /* дерево улучшений */
    const UP_ICON = {
      size: '<rect x="4" y="4" width="16" height="16" rx="1.5"/><path d="M4 12h16M12 4v16"/>', count: '<path d="M5 19V9M10 19V5M15 19v-7M20 19H3"/>',
      pos: '<circle cx="12" cy="12" r="6"/><path d="M12 2v5M12 17v5M2 12h5M17 12h5"/>', grow: '<path d="M12 3c4 5 6 8 6 11a6 6 0 0 1-12 0c0-3 2-6 6-11z"/>',
      sense: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>', yield: '<path d="M5 7l5 5-5 5M12 7l5 5-5 5"/>',
    };
    const upIcon = u => ENT[u.icon] ? `<svg viewBox="0 0 40 40">${GL[u.icon]}</svg>` : `<svg viewBox="0 0 24 24" fill="none" stroke="#E6E9EC" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">${UP_ICON[u.icon]}</svg>`;
    function treeRender() {
      const p = $('[data-win="tree"] .fg-body'); if (!p) return;
      const depth = {}, dOf = u => depth[u.id] ?? (depth[u.id] = (u.need || []).length ? 1 + Math.max(...u.need.map(n => dOf(UPGRADES.find(x => x.id === n)))) : 0);
      UPGRADES.forEach(dOf);
      const tiers = [...new Set(Object.values(depth))].sort();
      const items = save.items || {};
      p.innerHTML = `<p class="fg-note">Амбар копится между запусками. Купленное улучшение действует со следующего запуска${mode !== 'idle' ? ' — сейчас программа работает, покупать можно после остановки' : ''}.</p>` + tiers.map(t => `<div class="fg-tier"><h5>Ступень ${t + 1}</h5><div class="fg-ups">${UPGRADES.filter(u => depth[u.id] === t).map(u => {
        const s = upState(save, u), multi = upMax(u) > 1, txt = typeof u.text === 'function' ? (s.cost ? u.text(s.have) : `поле ${SIZES[s.have]}×${SIZES[s.have]}`) : u.text;
        const cost = s.cost ? Object.entries(s.cost).map(([k, n]) => `<span class="${(items[k] || 0) >= n ? '' : 'no'}">${itemIcon(k, 16)}${n}</span>`).join('') : '';
        const need = s.st === 'locked' ? 'нужно: ' + u.need.map(n => '«' + UPGRADES.find(x => x.id === n).title + '»').join(', ') : '';
        return `<div class="fg-up ${s.st}"><div class="h"><i>${upIcon(u)}</i><b>${esc(u.title)}</b>${multi ? `<small>${s.have}/${upMax(u)}</small>` : ''}</div><p>${txt}</p>
          ${s.st === 'done' ? '<div class="got">' + ICON.check + 'куплено</div>' : `<div class="cost">${cost}</div>${need ? `<div class="need">${need}</div>` : `<button type="button" data-buy="${u.id}" ${s.st === 'ready' && mode === 'idle' ? '' : 'disabled'}>Купить</button>`}`}</div>`;
      }).join('')}</div></div>`).join('');
    }
    function buyUp(id) {
      if (mode !== 'idle') return;
      const ns = buy(save, id); if (!ns) return;
      const old = lv;
      save = ns; lv = sandbox(save);
      if (ctx.onFarmSave) ctx.onFarmSave(save, true);
      run = null; world = new World(lv, 0);
      if (old.w !== lv.w && view) build();
      $('[data-win="help"] .fg-body').innerHTML = helpHTML();
      treeRender(); draw(); petals();
      const u = UPGRADES.find(x => x.id === id);
      out.innerHTML = ''; outN = 0;
      log('w', `Куплено: «${esc(u.title)}». Действует со следующего запуска.`);
    }

    /* подсказки при наборе */
    const acEl = $('.fg-ac'), cwEl = $('.fg-cw'), edEl = $('.fg-ed');
    let ac = null;
    const avail = () => ({ api: lv.api || GAME, plants: lv.plants || null, vars: Object.keys((data && data.vars) || {}) });
    function acHide() { ac = null; acEl.hidden = true; }
    function acPlace(pos) {
      const cw = cwEl.offsetWidth / 40 || 8.1, v = ta.value.slice(0, pos), line = v.split('\n').length - 1, col = v.length - v.lastIndexOf('\n') - 1;
      const er = edEl.getBoundingClientRect(), wr = codeW.getBoundingClientRect();
      let x = er.left - wr.left + gut.offsetWidth + 14 + col * cw - edEl.scrollLeft, y = er.top - wr.top + 10 + (line + 1) * 22 - edEl.scrollTop + 2;
      acEl.hidden = false;
      x = Math.max(4, Math.min(x, wr.width - acEl.offsetWidth - 6));
      if (y + acEl.offsetHeight > wr.height - 4) y = y - 24 - acEl.offsetHeight;
      acEl.style.left = x + 'px'; acEl.style.top = Math.max(36, y) + 'px';
    }
    const docHTML = d => `<div class="dc"><code>${esc(d[0])}</code><span>${d[1]}</span></div>`;
    function acShow() {
      const it = ac.items[ac.sel];
      acEl.classList.remove('sig');
      acEl.innerHTML = `<ul>${ac.items.map((x, i) => `<li role="option" data-ac="${i}" class="${i === ac.sel ? 'on' : ''}" aria-selected="${i === ac.sel}"><span><b>${esc(x.name.slice(0, ac.pre.length))}</b>${esc(x.name.slice(ac.pre.length))}</span><small>${esc(x.kind)}</small></li>`).join('')}</ul>${it.doc ? docHTML(it.doc) : ''}`;
      acPlace(ac.from);
    }
    function acUpdate(typing) {
      if (ta.readOnly || document.activeElement !== ta || ta.selectionStart !== ta.selectionEnd) return acHide();
      const r = typing ? complete(ta.value, ta.selectionStart, avail()) : null;
      if (r) { ac = { ...r, sel: 0 }; acShow(); return; }
      ac = null;
      const sg = signature(ta.value, ta.selectionStart, avail());
      if (!sg) { acEl.hidden = true; return; }
      acEl.classList.add('sig'); acEl.innerHTML = docHTML(sg); acPlace(ta.selectionStart);
    }
    function acAccept(i) {
      const it = ac.items[i], ins = insertion(it), end = ta.selectionStart;
      ta.setRangeText(ins.text, ac.from, end, 'end');
      const c = ac.from + ins.text.length - ins.back;
      ta.setSelectionRange(c, c);
      ac = null;
      ta.dispatchEvent(new Event('input'));
    }
    acEl.addEventListener('mousedown', e => { const li = e.target.closest('[data-ac]'); e.preventDefault(); if (li && ac) acAccept(+li.dataset.ac); });
    ta.addEventListener('blur', () => setTimeout(() => { if (document.activeElement !== ta) acHide(); }, 100));
    ta.addEventListener('click', () => acUpdate(false));
    ta.addEventListener('keyup', e => { if (/^(Arrow(Left|Right)|Home|End)$/.test(e.key)) acUpdate(false); });
    edEl.addEventListener('scroll', () => { if (!acEl.hidden) acUpdate(!!ac); });

    box.addEventListener('click', e => {
      const b = e.target.closest('[data-fg],[data-speed],[data-line],[data-buy],[data-file]');
      if (!b) return;
      if (b.dataset.speed) {
        speed = +b.dataset.speed; ctx.store.set('farm-speed', speed);
        box.querySelectorAll('[data-speed]').forEach(x => { x.classList.toggle('on', x === b); x.setAttribute('aria-pressed', x === b); });
        return;
      }
      if (b.dataset.line) { setMark(+b.dataset.line, true); revealLine(+b.dataset.line); ta.focus(); return; }
      if (b.dataset.buy) { buyUp(b.dataset.buy); return; }
      if (b.dataset.file) { showFile(b.dataset.file); return; }
      const a = b.dataset.fg;
      if (a === 'run') { acHide(); start(); }
      else if (a === 'step') stepOnce();
      else if (a === 'reset') resetField();
      else if (a === 'again' || a === 'newdata') { if (lv.answer) { newData(); renderTask(); } resetField(); }
      else if (a === 'min') {
        const w = b.closest('.fg-win'); w.classList.toggle('min');
        b.innerHTML = w.classList.contains('min') ? ICON.plus : ICON.min; b.setAttribute('aria-label', w.classList.contains('min') ? 'Развернуть' : 'Свернуть');
        saveUI(); if (view) { view.fit(freeZone()); petals(); }
      }
      else if (a === 'levels' || a === 'help' || a === 'tree' || a === 'file') {
        const p = $(`[data-win="${a}"]`);
        p.hidden = !p.hidden;
        box.querySelectorAll('.fg-pop').forEach(x => { if (x !== p) x.hidden = true; });
        if (a === 'tree' && !p.hidden) treeRender();
        if (a === 'levels') fg.querySelector('.fg-done')?.remove();
        box.querySelectorAll('.fg-tb').forEach(t => t.classList.toggle('on', !$(`[data-win="${t.dataset.fg}"]`).hidden));
      }
      else if (a === 'restore') {
        if (ta.value !== lv.start && !b.dataset.sure) { b.dataset.sure = 1; b.textContent = 'Точно? Нажмите ещё раз'; setTimeout(() => { delete b.dataset.sure; b.textContent = 'Начать код заново'; }, 2500); return; }
        delete b.dataset.sure; b.textContent = 'Начать код заново';
        stop(); ta.value = lv.start; ta.dispatchEvent(new Event('input'));
      }
    }, { signal: off.signal });
    box.querySelectorAll('.fg-win:not(.fg-pop) [data-fg="min"]').forEach(b => { if (b.closest('.fg-win').classList.contains('min')) b.innerHTML = ICON.plus; });
    box.querySelectorAll('.fg-tb').forEach(t => t.classList.toggle('on', !$(`[data-win="${t.dataset.fg}"]`).hidden));
    setMode('idle');
    layout(); draw();
    requestAnimationFrame(layout);
    ctl.destroy = () => {
      if (mode !== 'idle') keep(true);
      dead = true; clearTimeout(timer); clearTimeout(saveT); ctx.store.set(codeKey, ta.value); mode = 'idle';
      off.abort(); if (ro) ro.disconnect();
      if (view) view.dispose();
    };
    return ctl;
  }

  root.StacklyFarm = { ...api, mount };
})(typeof window !== 'undefined' ? window : globalThis);
