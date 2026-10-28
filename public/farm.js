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
  class Ret { constructor(v) { this.v = v; } }
  const BREAK = { brk: 1 }, CONT = { cont: 1 }, IDLE = { idle: 1 };

  const isBool = x => typeof x === 'boolean';
  const isInt = x => typeof x === 'number' || isBool(x);
  const isNum = x => isInt(x) || x instanceof F;
  const nv = x => x instanceof F ? x.v : +x;
  function tn(x) {
    if (x === null || x === undefined) return 'NoneType';
    if (isBool(x)) return 'bool';
    if (typeof x === 'number') return 'int';
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
    if (isNum(k)) return 'n' + nv(k);
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
    return pystr(x);
  }
  function pystr(x) {
    if (x === null || x === undefined) return 'None';
    if (isBool(x)) return x ? 'True' : 'False';
    if (typeof x === 'number') return String(x);
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
    if (x instanceof F) return x.v !== 0;
    if (typeof x === 'string' || Array.isArray(x)) return x.length > 0;
    if (x instanceof Tup) return x.a.length > 0;
    if (x instanceof Dict) return x.m.size > 0;
    if (x instanceof Range) return x.n > 0;
    return true;
  }
  function eq(a, b) {
    if (isNum(a) && isNum(b)) return nv(a) === nv(b);
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
    if (isNum(a) && isNum(b)) { const x = nv(a), y = nv(b); return x < y ? -1 : x > y ? 1 : 0; }
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
    if (c instanceof Range) { if (!isInt(x)) return false; const v = +x; return c.s > 0 ? v >= c.a && v < c.b && (v - c.a) % c.s === 0 : v <= c.a && v > c.b && (c.a - v) % -c.s === 0; }
    throw E('TypeError', `у значения типа ${tn(c)} нельзя проверить «in»`);
  }
  function arith(op, a, b) {
    const fl = a instanceof F || b instanceof F, x = nv(a), y = nv(b);
    let r;
    switch (op) {
      case '+': r = x + y; break;
      case '-': r = x - y; break;
      case '*': r = x * y; break;
      case '/': if (y === 0) throw E('ZeroDivisionError', 'деление на ноль'); return new F(x / y);
      case '//': if (y === 0) throw E('ZeroDivisionError', 'целочисленное деление на ноль'); r = Math.floor(x / y); break;
      case '%': if (y === 0) throw E('ZeroDivisionError', 'остаток от деления на ноль'); r = x - y * Math.floor(x / y); break;
      case '**': r = Math.pow(x, y); if (!fl && y < 0) return new F(r); break;
    }
    return fl ? new F(r) : r;
  }
  function binop(op, a, b) {
    if (isNum(a) && isNum(b)) return arith(op, a, b);
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
    throw E('TypeError', `нельзя ${NAMES[op]} значения типов ${tn(a)} и ${tn(b)} (операция «${op}»)`);
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
    throw E('TypeError', `значение типа ${tn(v)} нельзя перебрать в цикле for`);
  }
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
  const OPS2 = ['**=', '//=', '**', '//', '==', '!=', '<=', '>=', '+=', '-=', '*=', '/=', '%=', '->'];
  const OPS1 = '+-*/%<>=()[]{}:,.;';
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
  const UNSUPPORTED = { class: 'классы', try: 'try/except', except: 'try/except', finally: 'try/finally', with: 'with', lambda: 'lambda', yield: 'yield', del: 'del', assert: 'assert', raise: 'raise', nonlocal: 'nonlocal', async: 'async', await: 'await' };
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
      if (c.t === 'NAME') {
        switch (c.v) {
          case 'if': return [this.ifStmt()];
          case 'while': return [this.whileStmt()];
          case 'for': return [this.forStmt()];
          case 'def': return [this.defStmt()];
          case 'elif': case 'else': throw this.fail(`«${c.v}» без «if»: проверьте, что отступ у ${c.v} такой же, как у своего if`);
          case 'import': case 'from': throw this.fail('import в игре не нужен: все команды дрона уже доступны');
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
      if (c2.t === 'OP' && /^(\+|-|\*|\/|\/\/|%|\*\*)=$/.test(c2.v)) {
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
    endsList() { const c = this.cur; return c.t === 'NL' || c.t === 'EOF' || c.t === 'OP' && (['=', ')', ']', ':', ';'].includes(c.v) || /^(\+|-|\*|\/|\/\/|%|\*\*)=$/.test(c.v)); }
    expr() {
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
      const line = this.cur.line, items = [this.arith()], ops = [];
      for (;;) {
        const c = this.cur;
        if (c.t === 'OP' && ['<', '>', '==', '!=', '<=', '>='].includes(c.v)) { this.i++; ops.push(c.v); }
        else if (this.kw('in')) { this.i++; ops.push('in'); }
        else if (this.kw('not') && this.t[this.i + 1].t === 'NAME' && this.t[this.i + 1].v === 'in') { this.i += 2; ops.push('not in'); }
        else if (this.kw('is')) { this.i++; if (this.kw('not')) { this.i++; ops.push('is not'); } else ops.push('is'); }
        else break;
        items.push(this.arith());
      }
      return ops.length ? { k: 'cmp', ops, items, line } : items[0];
    }
    arith() { let e = this.term(); while (this.op('+') || this.op('-')) { const t = this.next(); e = { k: 'bin', op: t.v, a: e, b: this.term(), line: t.line }; } return e; }
    term() { let e = this.factor(); while (this.op('*') || this.op('/') || this.op('//') || this.op('%')) { const t = this.next(); e = { k: 'bin', op: t.v, a: e, b: this.factor(), line: t.line }; } return e; }
    factor() {
      if (this.op('-') || this.op('+')) { const t = this.next(); return { k: 'un', op: t.v, a: this.factor(), line: t.line }; }
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
          const pairs = [];
          while (!this.op('}')) {
            const k = this.expr();
            this.want(':', 'в словаре пары пишутся через двоеточие: {"a": 1}');
            pairs.push([k, this.expr()]);
            if (!this.eatOp(',')) break;
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
      const m = /^(.*?):(\.\d+f|d|\d+)$/.exec(inner);
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
      this.ops = 0; this.lastAct = 0; this.idleOps = opt.idleOps || 1500000; this.depth = 0; this.line = 0;
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
        case 'def': this.assign(s.name, new Fn(s, sc.isGlobal ? null : sc), sc); return;
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
            if (/^\.\d+f$/.test(p.spec)) { if (!isNum(v)) throw E('ValueError', `формат ${p.spec} подходит только для чисел`); s += nv(v).toFixed(+p.spec.slice(1, -1)); }
            else if (/^\d+$/.test(p.spec)) s += pystr(v).padStart(+p.spec, ' ');
            else s += pystr(v);
          }
          return s;
        }
        case 'list': { const a = []; for (const x of e.items) a.push(yield* this.ev(x, sc)); return a; }
        case 'tuple': { const a = []; for (const x of e.items) a.push(yield* this.ev(x, sc)); return new Tup(a); }
        case 'dict': { const d = new Dict(); for (const [k, v] of e.pairs) { const kk = yield* this.ev(k, sc); d.set(kk, yield* this.ev(v, sc)); } return d; }
        case 'comp': {
          const out = [], inner = { vars: new Map(), locals: new Set(), globalNames: new Set(), parent: sc.isGlobal ? null : sc, isGlobal: false };
          yield* this.compLoop(e, 0, inner, out);
          return out;
        }
        case 'bool': {
          const a = yield* this.ev(e.a, sc);
          if (e.op === 'and') return truthy(a) ? yield* this.ev(e.b, sc) : a;
          return truthy(a) ? a : yield* this.ev(e.b, sc);
        }
        case 'not': return !truthy(yield* this.ev(e.a, sc));
        case 'un': {
          const v = yield* this.ev(e.a, sc);
          if (!isNum(v)) throw E('TypeError', `знак «${e.op}» нельзя поставить перед значением типа ${tn(v)}`, e.line);
          return e.op === '-' ? (v instanceof F ? new F(-v.v) : -v) : (v instanceof F ? v : +v);
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
          for (const a of e.args) args.push(yield* this.ev(a, sc));
          for (const [k, v] of e.kw) kw[k] = yield* this.ev(v, sc);
          this.line = e.line;
          return yield* this.call(fn, args, kw, e.fn);
        }
      }
      throw E('SyntaxError', 'неизвестное выражение', e.line);
    }
    *compLoop(e, i, sc, out) {
      if (i === e.fors.length) { out.push(yield* this.ev(e.elt, sc)); return; }
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
      if (fn instanceof Fn) {
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
        if (++this.depth > 150) { this.depth = 0; throw E('RecursionError', 'слишком глубокая рекурсия: функция вызывает себя слишком много раз'); }
        try { yield* this.run(d.body, sc); return null; }
        catch (e) {
          if (e instanceof Ret) return e.v;
          if (e instanceof PyError && e.line == null) e.line = this.line;
          throw e;
        }
        finally { this.depth = Math.max(0, this.depth - 1); this.line = line; }
      }
      const what = node && node.k === 'name' ? `«${node.id}» — это ${tn(fn)}, а не функция` : `значение типа ${tn(fn)} нельзя вызвать как функцию`;
      throw E('TypeError', what + (fn instanceof Const ? '. Скобки () не нужны' : ''));
    }
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
      return parseInt(s, b);
    }
    if (isNum(x)) return Math.trunc(nv(x));
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
      throw E('TypeError', `у значения типа ${tn(x)} нет длины`);
    });
    ip.def('abs', args => { needArgs('abs', args, 1); if (!isNum(args[0])) throw E('TypeError', `abs() ждёт число, а не ${tn(args[0])}`); return args[0] instanceof F ? new F(Math.abs(args[0].v)) : Math.abs(args[0]); });
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
    ip.def('input', () => { throw E('RuntimeError', 'input() в игре не работает: дрону некого спрашивать. Задайте значение в программе: n = 5'); });
  }
  const bm = (name, fn, gen) => new Bi(name, fn, gen);
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
      case 'strip': return bm(name, () => o.trim());
      case 'split': return bm(name, a => a.length && a[0] !== null ? o.split(pystr(a[0])) : o.split(/\s+/).filter(Boolean));
      case 'join': return bm(name, a => { needArgs('join', a, 1); const xs = [...iter(a[0])]; xs.forEach(x => { if (typeof x !== 'string') throw E('TypeError', `join() склеивает только строки, а встретилось значение типа ${tn(x)}`); }); return xs.join(o); });
      case 'replace': return bm(name, a => (needArgs('replace', a, 2), o.split(pystr(a[0])).join(pystr(a[1]))));
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
  class World {
    constructor(lv, seed) {
      this.lv = lv; this.w = lv.w; this.h = lv.h; this.t = 0; this.x = 0; this.y = 0;
      this.items = {}; this.rng = rng32(seed);
      this.cells = Array.from({ length: this.w * this.h }, () => ({ g: 'grass', e: { type: 'Grass', at: -1e6 } }));
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
    add(item, n) { this.items[item] = (this.items[item] || 0) + n; }
    done() { const g = this.lv.goal; return !!g && Object.keys(g).every(k => (this.items[k] || 0) >= g[k]); }
  }

  /* ── команды дрону: каждая — один ход ── */
  const GAME = ['harvest', 'can_harvest', 'move', 'get_world_size', 'plant', 'till', 'get_ground_type', 'get_pos_x', 'get_pos_y', 'get_entity_type', 'num_items', 'measure'];
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
      *measure(args) { needArgs('measure', args, 0); const e = w.cell().e; yield act('look'); return e && e.type === 'Sunflower' ? e.petals : null; },
    };
    for (const name of GAME) {
      const open = !lv.api || lv.api.includes(name);
      if (!open) {
        const at = LEVELS.find(l => l.api && l.api.includes(name));
        ip.builtins.set(name, new Bi(name, () => { throw E('NameError', `команда ${name}() откроется ${at ? `на уровне ${at.id}` : 'позже'}`); }));
      } else ip.builtins.set(name, new Bi(name, impl[name], impl[name].constructor.name === 'GeneratorFunction'));
    }
  }

  /* ── запуск программы на уровне: step() — до следующего хода дрона ── */
  class Run {
    constructor(lv, code, opt = {}) {
      this.lv = lv; this.out = []; this.notes = new Set();
      this.world = new World(lv, opt.seed ?? lv.id * 7919 + 13);
      this.ip = new Interp({ print: s => this.print(s), rng: this.world.rng });
      installGame(this.ip, this.world, lv, this);
      this.state = 'run';
      try { this.gen = this.ip.run(parse(code), this.ip.top); }
      catch (e) { this.fail(e); }
    }
    print(s) { if (this.out.length < 400) this.out.push({ k: 'out', s }); }
    note(key, s) { if (!this.notes.has(key)) { this.notes.add(key); this.out.push({ k: 'note', s }); } }
    fail(e) {
      this.state = 'error';
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
    return { state: r.state, t: r.world.t, items: r.world.items, error: r.error && `${r.error.type} (строка ${r.error.line}): ${r.error.message}`, out: r.out };
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
      id: 12, title: 'Своя ферма', concept: 'свободная игра', w: 6, h: 6, goal: null, limit: 20000, par: 0, need: 6,
      text: 'Цели нет: все команды открыты, поле 6×6. Попробуйте собрать как можно больше за 20 000 ходов или придумайте свою задачу.',
      learn: ['Всё вместе', 'while True:\n    print(num_items(Items.Wood))', '<code>num_items(Items.Hay)</code> — сколько собрано: <code>Hay</code>, <code>Wood</code>, <code>Carrot</code>, <code>Pumpkin</code>, <code>Power</code>. <code>print()</code> выводит значения в журнал под полем.'],
      start: '# Свободная ферма: все команды открыты\n',
      hint: 'Начните с программы из «Свои функции» и добавьте тыквы и подсолнухи',
      solution: null,
    },
  ];
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
  };
  // ход уровня со своим решением — норма для звезды; посчитана прогоном решений (tests/farm_check.js)
  const PAR = { 3: 23, 4: 22, 5: 128, 6: 167, 7: 239, 8: 235, 9: 717, 10: 934, 11: 498 };
  LEVELS.forEach(l => { if (!l.par && PAR[l.id]) l.par = PAR[l.id]; });

  const api = { PyError, parse, tokenize, Interp, Run, World, simulate, LEVELS, pystr, repr };
  if (typeof module !== 'undefined' && module.exports) { module.exports = api; return; }

  /* ═════════════ ЭКРАН ИГРЫ ═════════════ */
  const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const GL = {
    Grass: '<path d="M12 33c1-6 0-11-3-15M20 33c0-7 1-13 4-18M28 33c-1-5 1-9 4-12" stroke="#4E9A3A" stroke-width="3" fill="none" stroke-linecap="round"/>',
    Bush: '<circle cx="13.5" cy="25" r="8" fill="#3D8A47"/><circle cx="26.5" cy="25" r="8" fill="#3D8A47"/><circle cx="20" cy="18" r="9.5" fill="#4FA65A"/><circle cx="16.5" cy="15.5" r="2.5" fill="#6DBE73"/>',
    Tree: '<rect x="17.5" y="23" width="5" height="12" rx="1.5" fill="#8A5A34"/><circle cx="20" cy="17" r="11.5" fill="#2F7D46"/><circle cx="15.5" cy="13" r="4" fill="#45985C"/>',
    Carrot: '<path d="M20 12c-2-4-5-5-8-5M20 12c0-4 1-6 3-8M20 12c2-3 5-4 8-3" stroke="#3E9A45" stroke-width="2.6" fill="none" stroke-linecap="round"/><path d="M13.5 13.5h13L20 35z" fill="#F08A24" stroke="#F08A24" stroke-width="2" stroke-linejoin="round"/><path d="M17 19h3M18 24h2.5" stroke="#C86A10" stroke-width="1.6" stroke-linecap="round"/>',
    Pumpkin: '<path d="M20 15c0-3 1-5 3-6.5" stroke="#4F7F2C" stroke-width="2.6" stroke-linecap="round" fill="none"/><ellipse cx="20" cy="25" rx="14" ry="10" fill="#F0902A"/><path d="M20 15.5v19M13 16.5c-3.5 5-3.5 12 0 17M27 16.5c3.5 5 3.5 12 0 17" stroke="#C96A12" stroke-width="1.6" fill="none"/>',
    Dead_Pumpkin: '<ellipse cx="20" cy="27" rx="13" ry="8" fill="#8C7B66"/><path d="M20 19.5v15M13.5 20.5c-3 4-3 9 0 13M26.5 20.5c3 4 3 9 0 13" stroke="#6B5C4A" stroke-width="1.6" fill="none"/><path d="M15 25l3 2M25 25l-3 2" stroke="#4A3F33" stroke-width="1.6" stroke-linecap="round"/>',
    Sunflower: '<path d="M20 22v13M20 30c-3-3-6-3-8-2" stroke="#3E8A3E" stroke-width="2.6" stroke-linecap="round" fill="none"/>' + Array.from({ length: 10 }, (_, i) => `<ellipse cx="20" cy="7.5" rx="3" ry="5.5" fill="#F5C518" transform="rotate(${i * 36} 20 16)"/>`).join('') + '<circle cx="20" cy="16" r="5" fill="#7A4B1E"/>',
  };
  const SPEEDS = [['Медленно', 420, 1], ['Обычно', 160, 1], ['Быстро', 45, 1], ['Мгновенно', 0, 400]];
  const ICON = {
    play: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5.5v13l11-6.5z" fill="currentColor"/></svg>',
    stop: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6.5" y="6.5" width="11" height="11" rx="1.5" fill="currentColor"/></svg>',
    step: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 6l7 6-7 6M17 6v12"/></svg>',
    reset: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3"/><path d="M4.5 4.5v4h4"/></svg>',
    lock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><rect x="5.5" y="10.5" width="13" height="9.5" rx="2"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5"/></svg>',
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 5 5 9-10"/></svg>',
    star: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3.5 2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z" fill="currentColor"/></svg>',
    chevL: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m14.5 6-6 6 6 6"/></svg>',
    chev: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9.5 6 6 6-6 6"/></svg>',
  };
  const CSS = `
.fm-page { --fm-grass: #DCEFD2; --fm-grass-2: #D2E9C6; --fm-soil: #E7D3BC; --fm-soil-line: rgb(120 80 40 / .16); --fm-cline: rgb(40 70 30 / .12); }
:root[data-theme="dark"] .fm-page { --fm-grass: #1D2E1F; --fm-grass-2: #1A2A1C; --fm-soil: #33281E; --fm-soil-line: rgb(255 210 160 / .08); --fm-cline: rgb(200 255 200 / .06); }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) .fm-page { --fm-grass: #1D2E1F; --fm-grass-2: #1A2A1C; --fm-soil: #33281E; --fm-soil-line: rgb(255 210 160 / .08); --fm-cline: rgb(200 255 200 / .06); } }
.fm-list { list-style: none; margin: 22px 0 0; padding: 0; background: var(--paper); border-radius: var(--r); box-shadow: inset 0 0 0 1px var(--line); overflow: hidden; }
.fm-list li + li { border-top: 1px solid var(--line); }
.fm-lv { display: flex; align-items: center; gap: 16px; padding: 14px 18px 14px 0; color: var(--ink); text-decoration: none; transition: background-color .15s; }
a.fm-lv:hover { background: var(--paper-2); text-decoration: none; }
.fm-lv .fm-n { flex: none; width: 56px; text-align: right; padding-right: 14px; border-right: 1.5px solid var(--margin); font: 600 19px/1.6 var(--f-mono); letter-spacing: -.03em; color: var(--ink-2); }
.fm-lv .fm-lt { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.fm-lv .fm-lt b { font: 600 16px/1.3 var(--f-body); }
.fm-lv .fm-lt span { color: var(--mute); font-size: 14px; }
.fm-lv .fm-st { flex: none; display: flex; align-items: center; gap: 8px; color: var(--mute); font-size: 13.5px; font-variant-numeric: tabular-nums; }
.fm-lv .fm-st svg { width: 18px; height: 18px; }
.fm-lv.done .fm-st .ok { color: var(--ok); }
.fm-lv .fm-star { color: #E0A800; }
.fm-lv.locked { color: var(--mute); }
.fm-lv.locked .fm-lt b { color: var(--mute); font-weight: 500; }
.fm-lv.fm-next .fm-n { color: var(--blue-fg); }
.fm-tag { display: inline-flex; align-items: center; height: 24px; padding: 0 9px; border-radius: 5px; background: var(--blue-soft); color: var(--blue-ink); font: 500 13px/1 var(--f-body); }
.fm-intro { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 22px; }
.fm-intro div { padding: 14px 16px; border-radius: var(--r); background: var(--paper); box-shadow: inset 0 0 0 1px var(--line); color: var(--ink-2); font-size: 14.5px; line-height: 1.5; }
.fm-intro b { display: block; color: var(--ink); font-weight: 600; margin-bottom: 2px; }

.fm-top { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 12px 24px; }
.fm-top h1 { font: 650 clamp(24px, 2.8vw, 32px)/1.15 var(--f-display); letter-spacing: -.025em; margin: 6px 0 0; }
.fm-back { display: inline-flex; align-items: center; gap: 4px; color: var(--mute); font-size: 14px; text-decoration: none; }
.fm-back svg { width: 16px; height: 16px; }
.fm-pn { display: flex; gap: 8px; }
.fm-pn a, .fm-pn span { display: inline-grid; place-items: center; width: 38px; height: 38px; border-radius: var(--r-s); box-shadow: inset 0 0 0 1px var(--line-2); color: var(--ink); background: var(--paper); }
.fm-pn span { opacity: .4; }
.fm-pn svg { width: 18px; height: 18px; }
.fm-wrap { display: grid; grid-template-columns: minmax(0, 1fr) minmax(300px, .9fr); grid-template-areas: "task board" "code board" "code out"; gap: 18px 22px; align-items: start; margin-top: 18px; }
.fm-task { grid-area: task; } .fm-codebox { grid-area: code; } .fm-side { grid-area: board; position: sticky; top: 76px; } .fm-outbox { grid-area: out; }
@media (max-width: 960px) { .fm-wrap { grid-template-columns: minmax(0, 1fr); grid-template-areas: "task" "board" "code" "out"; } .fm-side { position: static; } }
.fm-card { background: var(--paper); border-radius: var(--r); box-shadow: inset 0 0 0 1px var(--line); padding: 16px 18px; }
.fm-task p { margin: 0; color: var(--ink-2); line-height: 1.55; }
.fm-task code, .fm-out code, .fm-api code { font: 500 .92em var(--f-mono); background: var(--paper-2); border-radius: 4px; padding: 1px 4px; }
.fm-goal { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.fm-goal span { display: inline-flex; align-items: center; gap: 6px; height: 28px; padding: 0 10px; border-radius: 6px; background: var(--lime-soft); color: var(--on-lime); font: 500 13.5px/1 var(--f-body); font-variant-numeric: tabular-nums; }
.fm-goal span.ok { background: var(--ok-soft); color: var(--ok); }
.fm-learn { margin-top: 14px; border-top: 1px dashed var(--line-2); padding-top: 12px; }
.fm-learn h3 { font: 600 14px/1.3 var(--f-body); margin: 0 0 8px; color: var(--ink); }
.fm-learn pre { margin: 0 0 8px; padding: 10px 12px; border-radius: var(--r-s); background: var(--code-bg); color: var(--code-fg); font: 13px/1.6 var(--f-mono); overflow-x: auto; tab-size: 4; }
.fm-learn p { font-size: 14.5px; }
.fm-more { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px 18px; }
.fm-more details { font-size: 14px; color: var(--ink-2); }
.fm-more summary { cursor: pointer; color: var(--blue-fg); font-weight: 500; }
.fm-more details[open] { flex-basis: 100%; }
.fm-more details > div { margin-top: 8px; line-height: 1.5; }
.fm-api { list-style: none; margin: 8px 0 0; padding: 0; display: grid; gap: 6px; }
.fm-api li { line-height: 1.45; }
.fm-api b { font: 600 13px var(--f-mono); color: var(--ink); }
.fm-ed { position: relative; display: flex; border-radius: var(--r); background: var(--code-bg); border: 1px solid var(--code-line); overflow: hidden; min-height: 260px; }
.fm-ed:focus-within { border-color: var(--blue); box-shadow: 0 0 0 3px color-mix(in srgb, var(--blue) 25%, transparent); }
.fm-gut { flex: none; padding: 12px 10px 12px 12px; color: #5B6272; font: 13.5px/22px var(--f-mono); text-align: right; user-select: none; border-right: 1px solid var(--code-line); min-width: 40px; box-sizing: border-box; }
.fm-gut span { display: block; }
.fm-gut span.cur { color: var(--code-fg); }
.fm-gut span.bad { color: #FF7C72; }
.fm-in { position: relative; flex: 1; min-width: 0; overflow: auto; }
.fm-in pre, .fm-in textarea { margin: 0; padding: 12px 14px; font: 13.5px/22px var(--f-mono); tab-size: 4; white-space: pre; border: 0; box-sizing: border-box; min-width: 100%; letter-spacing: 0; }
.fm-in pre { position: absolute; inset: 0 auto auto 0; pointer-events: none; color: var(--code-fg); background: none; }
.fm-in pre, .fm-in textarea, .fm-learn pre { font-variant-ligatures: none; font-feature-settings: "liga" 0, "calt" 0; }
.fm-in pre code { background: none; border: 0; border-radius: 0; padding: 0; color: inherit; font: inherit; }
.fm-in textarea { position: relative; display: block; width: 100%; resize: none; overflow: hidden; background: transparent; color: transparent; caret-color: #fff; outline: 0; }
.fm-in textarea::selection { background: rgb(120 150 255 / .35); color: transparent; }
.fm-hlline { position: absolute; left: 0; right: 0; height: 22px; background: rgb(255 235 138 / .12); box-shadow: inset 3px 0 0 #FFD84A; pointer-events: none; display: none; }
.fm-hlline.bad { background: rgb(255 124 114 / .14); box-shadow: inset 3px 0 0 #FF7C72; }
.fm-codebar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; margin-top: 10px; color: var(--mute); font-size: 13px; }
.fm-codebar button { background: none; border: 0; padding: 4px 0; color: var(--blue-fg); font: 500 13.5px var(--f-body); cursor: pointer; }
.fm-stage { position: relative; }
.fm-stats { display: flex; flex-wrap: wrap; gap: 6px 14px; align-items: baseline; justify-content: space-between; margin-bottom: 10px; font-size: 14px; color: var(--ink-2); font-variant-numeric: tabular-nums; }
.fm-stats b { font: 650 20px/1 var(--f-display); color: var(--ink); letter-spacing: -.02em; }
.fm-inv { display: flex; flex-wrap: wrap; gap: 6px; }
.fm-inv span { padding: 3px 8px; border-radius: 5px; background: var(--paper-2); font-size: 13px; }
.fm-board { position: relative; display: grid; grid-template-columns: repeat(var(--w), 1fr); width: 100%; max-width: calc(var(--w) * 92px); aspect-ratio: var(--w) / var(--h); margin: 0 auto; border-radius: var(--r); overflow: hidden; box-shadow: inset 0 0 0 1px var(--line-2), var(--shadow-card); background: var(--fm-grass); }
.fm-c { position: relative; box-shadow: inset 0 0 0 .5px var(--fm-cline); background: var(--fm-grass); }
.fm-c:nth-child(odd) { background: var(--fm-grass-2); }
.fm-c.soil { background: var(--fm-soil) repeating-linear-gradient(0deg, transparent 0 7px, var(--fm-soil-line) 7px 9px); }
.fm-c svg { position: absolute; inset: 9%; width: 82%; height: 82%; transform: scale(calc(.3 + .7 * var(--g, 1))); transform-origin: 50% 85%; transition: transform .25s var(--ease); }
.fm-c.dry svg { opacity: .78; filter: saturate(.7); }
.fm-pet { position: absolute; right: 4px; top: 3px; font: 600 11px/1 var(--f-mono); color: #7A4B1E; background: rgb(255 255 255 / .75); border-radius: 3px; padding: 2px 3px; }
.fm-drone { position: absolute; left: 0; top: 0; width: calc(100% / var(--w)); height: calc(100% / var(--h)); display: grid; place-items: center; transform: translate(calc(var(--x) * 100%), calc(var(--y) * 100%)); transition: transform var(--dur, .16s) var(--ease); pointer-events: none; z-index: 2; }
.fm-drone i { position: relative; width: 38%; height: 38%; max-width: 30px; max-height: 30px; border-radius: 50%; background: #FFD84A; box-shadow: inset 0 0 0 2px #141820, 0 6px 10px -4px rgb(20 24 32 / .5); }
.fm-drone i::after { content: ""; position: absolute; width: 36%; height: 36%; border-radius: 50%; background: #fff; top: 18%; right: 16%; }
.fm-drone.act i { animation: fmBob .3s var(--ease); }
@keyframes fmBob { 40% { transform: translateY(-14%) scale(1.08); } }
.fm-fly { position: absolute; z-index: 3; transform: translate(-50%, -50%); font: 700 13px/1 var(--f-body); color: var(--ok); background: var(--paper); padding: 3px 6px; border-radius: 5px; box-shadow: var(--shadow-lift); pointer-events: none; animation: fmFly .9s var(--ease) forwards; white-space: nowrap; }
@keyframes fmFly { from { opacity: 0; margin-top: 4px; } 20% { opacity: 1; } to { opacity: 0; margin-top: -26px; } }
.fm-ctl { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; align-items: center; }
.fm-ctl .btn svg { width: 16px; height: 16px; }
.fm-ctl .btn.ghost { padding: 0 14px; }
.fm-speed { display: flex; gap: 2px; padding: 3px; border-radius: var(--r-s); background: var(--sunken); margin-left: auto; }
.fm-speed button { border: 0; background: none; height: 34px; padding: 0 10px; border-radius: 6px; color: var(--ink-2); font: 500 13px var(--f-body); cursor: pointer; }
.fm-speed button.on { background: var(--paper); color: var(--ink); box-shadow: var(--shadow-card), 0 0 0 1px var(--line); }
@media (max-width: 520px) { .fm-speed { margin-left: 0; width: 100%; } .fm-speed button { flex: 1; padding: 0 4px; } }
.fm-out { margin-top: 0; max-height: 260px; overflow: auto; padding: 12px 14px; border-radius: var(--r); background: var(--paper); box-shadow: inset 0 0 0 1px var(--line); font-size: 14px; line-height: 1.5; }
.fm-out:empty::before { content: "Журнал: здесь появятся сообщения программы и print()"; color: var(--mute); }
.fm-out .o { font: 13px/1.55 var(--f-mono); color: var(--ink); white-space: pre-wrap; overflow-wrap: anywhere; }
.fm-out .n { color: var(--on-lime); background: var(--lime-soft); border-radius: 6px; padding: 6px 10px; margin: 4px 0; }
.fm-out .e { color: var(--bad); background: var(--bad-soft); border-radius: 6px; padding: 8px 10px; margin: 4px 0; }
.fm-out .e b { font-family: var(--f-mono); font-weight: 600; }
.fm-out .s { color: var(--ink-2); background: var(--paper-2); border-radius: 6px; padding: 8px 10px; margin: 4px 0; }
.fm-out .w { color: var(--ok); background: var(--ok-soft); border-radius: 6px; padding: 8px 10px; margin: 4px 0; font-weight: 500; }
.fm-out button.ln { border: 0; background: none; padding: 0; color: inherit; font: inherit; text-decoration: underline; cursor: pointer; }
.fm-win { position: absolute; inset: 0; z-index: 4; display: grid; place-items: center; padding: 16px; background: color-mix(in srgb, var(--paper) 72%, transparent); backdrop-filter: blur(2px); border-radius: var(--r); animation: fmIn .3s var(--ease); }
.fm-win > div { max-width: 320px; text-align: center; background: var(--paper); padding: 20px 22px; border-radius: var(--r-xl); box-shadow: var(--shadow-pop), inset 0 0 0 1px var(--line); }
.fm-win h3 { font: 650 22px/1.2 var(--f-display); margin: 0 0 6px; letter-spacing: -.02em; }
.fm-win p { margin: 0 0 6px; color: var(--ink-2); font-size: 14.5px; }
.fm-win .fm-stars { color: #E0A800; font-weight: 600; display: inline-flex; gap: 4px; align-items: center; }
.fm-win .fm-stars svg { width: 18px; height: 18px; }
.fm-win .pts { color: var(--ok); font-weight: 600; }
.fm-win .row { display: flex; gap: 8px; justify-content: center; margin-top: 14px; flex-wrap: wrap; }
@keyframes fmIn { from { opacity: 0; } }
@media (prefers-reduced-motion: reduce) { .fm-drone, .fm-c svg { transition: none; } .fm-fly, .fm-drone.act i, .fm-win { animation: none; } }
`;
  function injectCSS() {
    if (document.getElementById('fm-css')) return;
    const s = document.createElement('style'); s.id = 'fm-css'; s.textContent = CSS; document.head.appendChild(s);
  }
  const unlocked = (lv, ctx) => ctx.all || lv.id === 1 || ctx.done[lv.id] != null || ctx.done[(lv.need || lv.id - 1)] != null;
  const goalText = g => Object.entries(g).map(([k, n]) => `${ITEMS[k].toLowerCase()} ${n}`).join(', ');
  const hodov = n => `${n} ${plural(n, 'ход', 'хода', 'ходов')}`;

  function listHTML(ctx) {
    const firstOpen = LEVELS.find(l => ctx.done[l.id] == null && l.goal && unlocked(l, ctx));
    const done = LEVELS.filter(l => ctx.done[l.id] != null).length;
    return `<div class="fm-top"><div><span class="eyebrow">Python в игре</span><h1>Ферма</h1></div></div>
      <p style="margin:10px 0 0;color:var(--ink-2);max-width:64ch">Дрон-фермер слушается только программы. Каждый уровень учит одной вещи из Python: вызов функции, циклы, условия, свои функции, списки. За пройденный уровень — ${ctx.points || 10} баллов.</p>
      <div class="fm-intro"><div><b>Пишете код</b>Настоящий Python: отступы, циклы, функции. Ошибки объясняются по-русски.</div>
        <div><b>Смотрите на поле</b>Дрон выполняет команды по одной, строка программы подсвечивается.</div>
        <div><b>Ищете решение короче</b>Каждая команда — ход. Уложитесь в норму — получите звезду.</div></div>
      <ol class="fm-list">${LEVELS.map(l => {
        const best = ctx.done[l.id], open = unlocked(l, ctx), isDone = best != null;
        const st = isDone ? `${l.par && best <= l.par ? `<span class="fm-star" title="Уложились в норму">${ICON.star}</span>` : ''}<span>${l.goal ? hodov(best) : ''}</span><span class="ok">${ICON.check}</span>`
          : open ? (l === firstOpen ? '<span class="fm-tag">дальше</span>' : '') : `<span title="Откроется после уровня ${l.need || l.id - 1}">${ICON.lock}</span>`;
        const inner = `<span class="fm-n">${l.id}</span><span class="fm-lt"><b>${esc(l.title)}</b><span>${esc(l.concept)}${l.goal ? ` · поле ${l.w}×${l.h}` : ''}</span></span><span class="fm-st">${st}</span>`;
        return `<li>${open ? `<a class="fm-lv ${isDone ? 'done' : ''} ${l === firstOpen ? 'fm-next' : ''}" href="#farm-${l.id}">${inner}</a>` : `<div class="fm-lv locked">${inner}</div>`}</li>`;
      }).join('')}</ol>
      <p class="muted" style="margin-top:14px;font-size:14px">Пройдено ${done} из ${LEVELS.filter(l => l.goal).length}. Код каждого уровня сохраняется в этом браузере.</p>`;
  }

  function mount(box, ctx) {
    injectCSS();
    box.classList.add('fm-page');
    const ctl = { destroy() { } };
    const lv = ctx.level ? LEVELS.find(l => l.id === ctx.level) : null;
    if (!ctx.level) { box.innerHTML = listHTML(ctx); return ctl; }
    if (!lv || !unlocked(lv, ctx)) {
      box.innerHTML = `<a class="fm-back" href="#farm">${ICON.chevL}Все уровни</a><div class="t-empty" style="margin-top:16px"><b>${lv ? 'Уровень пока закрыт' : 'Такого уровня нет'}</b>${lv ? `Он откроется, когда вы пройдёте уровень ${lv.need || lv.id - 1}.` : 'Выберите уровень из списка.'}<div class="cta-row"><a class="btn small" href="#farm">К уровням</a></div></div>`;
      return ctl;
    }
    const hl = ctx.hl || esc;
    const codeKey = 'farm-code-' + lv.id;
    let code = ctx.store.get(codeKey, null) ?? lv.start;
    let speed = Math.min(3, Math.max(0, +ctx.store.get('farm-speed', 1) || 0));
    const prev = LEVELS.find(l => l.id === lv.id - 1), next = LEVELS.find(l => l.id === lv.id + 1);
    const showPet = !lv.api || lv.api.includes('measure');
    const D = DOC, apiList = (lv.api || Object.keys(D)).filter(n => D[n] && n !== 'get_pos_y');
    box.innerHTML = `<div class="fm-top"><div><a class="fm-back" href="#farm">${ICON.chevL}Ферма · уровень ${lv.id} из ${LEVELS.length}</a><h1>${esc(lv.title)}</h1></div>
        <div class="fm-pn">${prev ? `<a href="#farm-${prev.id}" aria-label="Предыдущий уровень">${ICON.chevL}</a>` : `<span>${ICON.chevL}</span>`}${next && unlocked(next, ctx) ? `<a href="#farm-${next.id}" aria-label="Следующий уровень">${ICON.chev}</a>` : `<span>${ICON.chev}</span>`}</div></div>
      <div class="fm-wrap">
        <section class="fm-task fm-card"><p>${lv.text}</p>
          ${lv.goal ? `<div class="fm-goal" id="fmgoal"></div>` : ''}
          <div class="fm-learn"><h3>${esc(lv.learn[0])}</h3><pre>${hl(lv.learn[1])}</pre><p>${lv.learn[2]}</p></div>
          <div class="fm-more"><details><summary>Команды дрона</summary><div><ul class="fm-api">${apiList.map(n => `<li><b>${esc(D[n][0])}</b> — ${D[n][1]}</li>`).join('')}</ul>
            <p style="margin-top:8px">Каждая команда дрону — один ход. <code>get_pos_x()</code>, <code>get_world_size()</code> и <code>num_items()</code> бесплатны. Работают и обычные функции Python: <code>print()</code>, <code>range()</code>, <code>len()</code>, <code>min()</code>, <code>max()</code>…</p></div></details>
            <details><summary>Подсказка</summary><div>${lv.hint}</div></details></div>
        </section>
        <section class="fm-codebox"><div class="fm-ed"><div class="fm-gut" aria-hidden="true"></div><div class="fm-in"><div class="fm-hlline"></div><pre aria-hidden="true"><code></code></pre><textarea spellcheck="false" autocapitalize="off" autocomplete="off" autocorrect="off" wrap="off" aria-label="Программа на Python"></textarea></div></div>
          <div class="fm-codebar"><span>Tab — отступ · Ctrl+Enter — запуск · Esc, затем Tab — выйти из редактора</span><button type="button" data-fm="restore">Вернуть исходный код</button></div></section>
        <section class="fm-side"><div class="fm-stage fm-card">
          <div class="fm-stats"><span><b id="fmt">0</b> ${lv.goal ? `из ${lv.limit} ходов` : 'ходов'}</span><span class="fm-inv" id="fminv"></span></div>
          <div class="fm-board" id="fmboard" role="img" style="--w:${lv.w};--h:${lv.h}"></div>
          <div class="fm-ctl"><button type="button" class="btn" data-fm="run">${ICON.play}<span>Запустить</span></button>
            <button type="button" class="btn ghost" data-fm="step" title="Выполнить до следующей команды дрону">${ICON.step}<span>Шаг</span></button>
            <button type="button" class="btn ghost" data-fm="reset" title="Вернуть поле в начало" aria-label="Заново">${ICON.reset}</button>
            <div class="fm-speed" role="group" aria-label="Скорость">${SPEEDS.map((s, i) => `<button type="button" data-speed="${i}" class="${i === speed ? 'on' : ''}" aria-pressed="${i === speed}">${s[0]}</button>`).join('')}</div></div>
        </div></section>
        <section class="fm-outbox"><div class="fm-out" id="fmout" aria-live="polite"></div></section>
      </div>`;
    const $ = s => box.querySelector(s);
    const ta = $('textarea'), pre = $('.fm-in pre code'), gut = $('.fm-gut'), hlLine = $('.fm-hlline'), board = $('#fmboard'), out = $('#fmout');
    const runBtn = $('[data-fm="run"]');
    ta.value = code;
    let run = null, world = new World(lv, 0), mode = 'idle', timer = 0, outN = 0, mark = null, saveT = 0;

    /* редактор */
    function paint() {
      const v = ta.value;
      pre.innerHTML = hl(v) + '\n';
      const n = v.split('\n').length;
      if (gut.childElementCount !== n) gut.innerHTML = Array.from({ length: n }, (_, i) => `<span>${i + 1}</span>`).join('');
      ta.style.height = (n * 22 + 24) + 'px';
      ta.style.width = ''; ta.style.width = Math.max(ta.parentNode.clientWidth, pre.parentNode.scrollWidth) + 'px';
      showMark();
    }
    function showMark() {
      [...gut.children].forEach((s, i) => { s.className = mark && mark.line === i + 1 ? (mark.bad ? 'bad' : 'cur') : ''; });
      if (!mark) { hlLine.style.display = 'none'; return; }
      hlLine.style.display = 'block'; hlLine.style.top = (12 + (mark.line - 1) * 22) + 'px';
      hlLine.classList.toggle('bad', !!mark.bad);
    }
    function setMark(line, bad) { mark = line ? { line, bad } : null; showMark(); }
    function revealLine(line) {
      const sc = $('.fm-in'), top = 12 + (line - 1) * 22;
      if (top < sc.scrollTop || top > sc.scrollTop + sc.clientHeight - 30) sc.scrollTop = top - 60;
      const r = $('.fm-ed').getBoundingClientRect();
      if (r.bottom < 80 || r.top > innerHeight) $('.fm-ed').scrollIntoView({ block: 'nearest' });
    }
    ta.addEventListener('input', () => {
      code = ta.value; setMark(null); paint();
      clearTimeout(saveT); saveT = setTimeout(() => ctx.store.set(codeKey, code), 400);
    });
    let tabOut = false;
    ta.addEventListener('keydown', e => {
      if (e.key === 'Escape') { tabOut = true; return; }
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); start(); return; }
      if (e.key === 'Tab' && !tabOut) {
        e.preventDefault();
        const v = ta.value, a = ta.selectionStart, b = ta.selectionEnd;
        const ls = v.lastIndexOf('\n', a - 1) + 1;
        if (a === b && !e.shiftKey) { edit(a, b, '    '); return; }
        const le = v.indexOf('\n', b - (b > a && v[b - 1] === '\n' ? 1 : 0)), end = le < 0 ? v.length : le;
        const lines = v.slice(ls, end).split('\n');
        const nl = lines.map(l => e.shiftKey ? l.replace(/^ {1,4}/, '') : '    ' + l).join('\n');
        ta.setRangeText(nl, ls, end, 'select'); ta.dispatchEvent(new Event('input'));
        return;
      }
      tabOut = false;
      if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        const v = ta.value, a = ta.selectionStart, ls = v.lastIndexOf('\n', a - 1) + 1, line = v.slice(ls, a);
        let ind = /^ */.exec(line)[0];
        if (/:\s*(#.*)?$/.test(line)) ind += '    ';
        else if (/^\s*(return|break|continue|pass)\b/.test(line)) ind = ind.slice(4);
        edit(a, ta.selectionEnd, '\n' + ind);
      } else if (e.key === 'Backspace' && ta.selectionStart === ta.selectionEnd) {
        const v = ta.value, a = ta.selectionStart, ls = v.lastIndexOf('\n', a - 1) + 1, before = v.slice(ls, a);
        if (before.length && /^ +$/.test(before)) { e.preventDefault(); edit(a - ((before.length - 1) % 4 + 1), a, ''); }
      }
    });
    function edit(a, b, text) { ta.setRangeText(text, a, b, 'end'); ta.dispatchEvent(new Event('input')); }

    /* поле */
    const cellEls = [];
    let sig = [];
    function buildBoard() {
      board.innerHTML = '';
      cellEls.length = 0;
      for (let row = lv.h - 1; row >= 0; row--) for (let x = 0; x < lv.w; x++) {
        const d = document.createElement('div'); d.className = 'fm-c'; board.appendChild(d); cellEls[row * lv.w + x] = d;
      }
      const dr = document.createElement('div'); dr.className = 'fm-drone'; dr.innerHTML = '<i></i>'; board.appendChild(dr);
      sig = [];
    }
    function draw(ev) {
      const w = world, sp = SPEEDS[speed];
      for (let y = 0; y < w.h; y++) for (let x = 0; x < w.w; x++) {
        const i = y * w.w + x, c = w.cells[i], k = w.kind(x, y), g = k === 'Dead_Pumpkin' ? 1 : w.progress(x, y);
        const s = c.g + (k || '') + (k === 'Sunflower' && showPet ? c.e.petals : '');
        const el = cellEls[i];
        if (sig[i] !== s) {
          sig[i] = s;
          el.className = 'fm-c' + (c.g === 'soil' ? ' soil' : '');
          el.innerHTML = k ? `<svg viewBox="0 0 40 40" aria-hidden="true">${GL[k]}</svg>${k === 'Sunflower' && showPet ? `<span class="fm-pet">${c.e.petals}</span>` : ''}` : '';
        }
        el.style.setProperty('--g', (Math.round(g * 20) / 20).toFixed(2));
        el.classList.toggle('dry', k && k !== 'Dead_Pumpkin' && g < 1);
      }
      const dr = board.lastChild;
      dr.style.setProperty('--dur', ev && ev.wrap || speed === 3 ? '0s' : Math.min(sp[1], 220) / 1000 + 's');
      dr.style.setProperty('--x', w.x); dr.style.setProperty('--y', w.h - 1 - w.y);
      if (ev && ev.a !== 'move' && ev.a !== 'look' && speed < 3) { dr.classList.remove('act'); void dr.offsetWidth; dr.classList.add('act'); }
      if (ev && ev.got && speed < 3) fly(ev);
      board.setAttribute('aria-label', `Поле ${w.w}×${w.h}, дрон в клетке (${w.x}, ${w.y})`);
      $('#fmt').textContent = w.t.toLocaleString('ru-RU');
      const inv = Object.entries(w.items).filter(([k]) => !lv.goal || !(k in lv.goal));
      $('#fminv').innerHTML = inv.map(([k, n]) => `<span>${ITEMS[k]} ${n}</span>`).join('');
      if (lv.goal) $('#fmgoal').innerHTML = Object.entries(lv.goal).map(([k, n]) => { const h = Math.min(n, w.items[k] || 0); return `<span class="${h >= n ? 'ok' : ''}">${h >= n ? ICON.check.replace('<svg', '<svg width="14" height="14"') : ''}${ITEMS[k]}: ${h} / ${n}</span>`; }).join('');
    }
    function fly(ev) {
      const f = document.createElement('span'); f.className = 'fm-fly';
      f.textContent = `+${ev.got.n} ${ITEMS[ev.got.item].toLowerCase()}`;
      f.style.left = ((ev.x + .5) / lv.w * 100) + '%'; f.style.top = ((lv.h - ev.y - .5) / lv.h * 100) + '%';
      board.appendChild(f); setTimeout(() => f.remove(), 900);
    }

    /* журнал */
    function log(cls, html) {
      if (outN > 300) return;
      outN++;
      const d = document.createElement('div'); d.className = cls; d.innerHTML = html; out.appendChild(d); out.scrollTop = out.scrollHeight;
    }
    function flushOut() {
      if (!run) return;
      while (run.outI < run.out.length) {
        const o = run.out[run.outI++];
        if (o.k === 'out') log('o', esc(o.s.replace(/\n$/, '')));
        else log('n', esc(o.s));
      }
    }

    /* запуск */
    function setMode(m) {
      mode = m;
      const on = m === 'run';
      runBtn.innerHTML = on ? `${ICON.stop}<span>Стоп</span>` : `${ICON.play}<span>${m === 'pause' ? 'Дальше' : 'Запустить'}</span>`;
      runBtn.classList.toggle('ghost', false);
      ta.readOnly = m === 'run' || m === 'pause';
    }
    function fresh() {
      clearTimeout(timer); timer = 0;
      $('.fm-win')?.remove();
      out.innerHTML = ''; outN = 0;
      run = new Run(lv, ta.value); run.outI = 0;
      world = run.world; buildBoard(); draw();
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
      if (msg) log('s', esc(msg));
      setMode('idle'); setMark(null);
    }
    function stepOnce() {
      if (mode === 'run') return;
      if (mode !== 'pause') { if (!fresh()) return; setMode('pause'); }
      let ev;
      const t0 = NOW();
      do { ev = run.step(); } while (ev === IDLE && NOW() - t0 < 2000);
      draw(ev); flushOut();
      if (run.state !== 'run') return finish();
      setMark(run.ip.line); revealLine(run.ip.line);
    }
    function loop() {
      timer = 0;
      if (mode !== 'run' || !run) return;
      const [, ms, batch] = SPEEDS[speed], t0 = NOW();
      let acts = 0, last = null;
      while (run.state === 'run') {
        const ev = run.step();
        if (ev && ev !== IDLE) { acts++; last = ev; if (speed < 3) draw(ev); if (acts >= batch) break; }
        if (NOW() - t0 > 14) break;
      }
      if (speed === 3) draw(last);
      flushOut();
      if (run.state !== 'run') return finish();
      if (speed < 3) setMark(run.ip.line);
      timer = setTimeout(loop, acts ? ms : 0);
    }
    function finish() {
      clearTimeout(timer); timer = 0;
      flushOut();
      const st = run.state, t = run.world.t;
      setMode('idle');
      if (st === 'error') {
        const e = run.error;
        setMark(e.line, true); if (e.line) revealLine(e.line);
        log('e', `${e.line ? `<button type="button" class="ln" data-line="${e.line}">Строка ${e.line}</button>: ` : ''}<b>${esc(e.type)}</b> — ${esc(e.message)}`);
        return;
      }
      setMark(null);
      if (st === 'win') return win(t);
      if (st === 'limit') log('e', `Закончились ходы: на уровне их ${lv.limit.toLocaleString('ru-RU')}. Цель не выполнена — посмотрите, где дрон тратит ходы зря.`);
      else if (st === 'end') log('s', lv.goal ? (lv.id > 1 && !/while/.test(ta.value) ? 'Программа закончилась, а цель ещё не выполнена. Чтобы дрон работал, пока цель не выполнена, поместите команды в цикл <code>while True:</code>.' : 'Программа закончилась, а цель ещё не выполнена.') : `Программа закончилась за ${hodov(t)}.`);
    }
    function win(t) {
      const res = ctx.onWin ? ctx.onWin(lv.id, t) : { first: false, best: t };
      const star = lv.par && t <= lv.par;
      log('w', `Цель выполнена за ${hodov(t)}.`);
      const d = document.createElement('div'); d.className = 'fm-win';
      d.innerHTML = `<div><h3>Урожай собран</h3><p>Цель выполнена за ${hodov(t)}.${res.best < t ? ` Ваш рекорд — ${hodov(res.best)}.` : ''}</p>
        ${lv.par ? (star ? `<p class="fm-stars">${ICON.star}Уложились в норму: ${hodov(lv.par)}</p>` : `<p>Норма для звезды — ${hodov(lv.par)}. Можно короче!</p>`) : ''}
        ${res.points ? `<p class="pts">+${res.points} баллов</p>` : ''}
        <div class="row">${next ? `<a class="btn" href="#farm-${next.id}">Следующий уровень</a>` : `<a class="btn" href="#farm">Все уровни</a>`}<button type="button" class="btn ghost" data-fm="again">Ещё раз</button></div></div>`;
      $('.fm-stage').appendChild(d);
      const nx = $('.fm-pn span:last-child');
      if (next && nx) nx.outerHTML = `<a href="#farm-${next.id}" aria-label="Следующий уровень">${ICON.chev}</a>`;
    }
    box.addEventListener('click', e => {
      const b = e.target.closest('[data-fm],[data-speed],[data-line]');
      if (!b) return;
      if (b.dataset.speed) {
        speed = +b.dataset.speed; ctx.store.set('farm-speed', speed);
        box.querySelectorAll('[data-speed]').forEach(x => { x.classList.toggle('on', x === b); x.setAttribute('aria-pressed', x === b); });
        return;
      }
      if (b.dataset.line) { setMark(+b.dataset.line, true); revealLine(+b.dataset.line); ta.focus(); return; }
      const a = b.dataset.fm;
      if (a === 'run') start();
      else if (a === 'step') stepOnce();
      else if (a === 'reset' || a === 'again') { stop(); $('.fm-win')?.remove(); out.innerHTML = ''; outN = 0; run = null; world = new World(lv, 0); buildBoard(); draw(); }
      else if (a === 'restore') {
        if (ta.value !== lv.start && !ctx.confirmRestore) { ctx.confirmRestore = true; b.textContent = 'Точно? Нажмите ещё раз'; setTimeout(() => { ctx.confirmRestore = false; b.textContent = 'Вернуть исходный код'; }, 2500); return; }
        ctx.confirmRestore = false; b.textContent = 'Вернуть исходный код';
        stop(); ta.value = lv.start; ta.dispatchEvent(new Event('input'));
      }
    });
    buildBoard(); draw(); paint(); setMode('idle');
    ctl.destroy = () => { clearTimeout(timer); clearTimeout(saveT); ctx.store.set(codeKey, ta.value); mode = 'idle'; };
    return ctl;
  }

  root.StacklyFarm = { ...api, mount };
})(typeof window !== 'undefined' ? window : globalThis);
