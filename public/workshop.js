/* stackly · Мастерская переменных: программа на Python, которую видно изнутри. Полка — память компьютера,
   переменная — ящик с именем, значение — жетон в ящике (число, строка, True/False, список). Робот Байт раскладывает
   жетоны по ящикам, лампа показывает ответ условия, счётчик — круг цикла, экран — print(), отдельный стол — вызов функции.
   Интерпретатор, редактор, окна и прогресс — общие с фермой (farm.js); игра смотрит на каждый шаг программы через ip.watch.
   Логика работает и в node — её проверяет tests/workshop_check.js. */
(function (root, F) {
  'use strict';
  const { Fn, Bi, NS, Const, Tup, E, tn, eq, repr, pystr, rng32, outLines } = F;

  /* ═════════════ ПАМЯТЬ ═════════════
     Ящик: { name, t — тип для показа (int, float, str, bool, list, none, other), s — подпись, items — отделения списка, rep — для сравнения } */
  const KIND = { int: 'int', float: 'float', str: 'str', bool: 'bool', list: 'list', tuple: 'list', NoneType: 'none' };
  const cut = (s, n) => s.length > n ? s.slice(0, n - 1) + '…' : s;
  const shown = v => !(v instanceof Fn || v instanceof Bi || v instanceof NS || v instanceof Const);
  function cell(name, v) {
    const t = KIND[tn(v)] || 'other', rep = cut(repr(v), 400);
    const c = { name, t, rep, s: cut(t === 'str' ? repr(v) : pystr(v), 24) };
    if (t === 'list') { const a = v instanceof Tup ? v.a : v; c.items = a.slice(0, 8).map(x => cut(repr(x), 6)); c.more = a.length > 8; c.n = a.length; }
    return c;
  }
  const snap = vars => [...vars].filter(([, v]) => shown(v)).map(([k, v]) => cell(k, v));
  const copy = v => Array.isArray(v) ? v.map(copy) : v;

  class Lab {
    constructor(lv, seed) {
      this.lv = lv; this.t = 0; this.rng = rng32(seed); this.w = 1; this.h = 1;
      this.given = lv.given ? lv.given(rng32(seed * 31 + 7)) : {};
      this.mem = Object.entries(this.given).map(([k, v]) => cell(k, v));
      this.frame = null;                                           // { name, depth, mem } — стол функции, которая сейчас работает
      this.stack = []; this.lamp = null; this.loop = null; this.screen = []; this.outN = 0;
    }
    done() { return false; }                                      // мастерская проверяется, когда программа закончилась
  }

  /* ── наблюдатель: после каждого шага программы — снимок памяти и событие для сцены ── */
  function install(ip, w, lv, run) {
    for (const [k, v] of Object.entries(w.given)) ip.globals.set(k, copy(v));
    let lines = null;                                            // run.code появляется после install
    const cond = () => ((lines = lines || run.code.split('\n'))[ip.line - 1] || '').trim().replace(/^(if|elif|while)\s+/, '').replace(/:\s*(#.*)?$/, '');
    ip.watch = (kind, s, sc, v, i) => {
      ip.lastAct = ip.ops;
      if (kind === 'call') w.stack.push({ name: s.name, sc });
      if (kind === 'ret') w.stack.pop();
      const top = w.stack[w.stack.length - 1];
      const g = snap(ip.globals), f = top ? { name: top.name, depth: w.stack.length, mem: snap(top.sc.vars) } : null;
      const diff = (now, was) => now.filter(c => { const o = was && was.find(x => x.name === c.name); return !o || o.rep !== c.rep; }).map(c => c.name);
      const cg = diff(g, w.mem), cl = f ? diff(f.mem, w.frame && w.frame.depth === f.depth && w.frame.name === f.name ? w.frame.mem : null) : [];
      let printed = false;
      for (; w.outN < run.out.length; w.outN++) if (run.out[w.outN].k === 'out') printed = true;
      let ev;
      if (kind === 'set' || kind === 'expr') { if (!cg.length && !cl.length && !printed) return null; ev = { a: cg.length || cl.length ? 'set' : 'print' }; }
      else if (kind === 'if' || kind === 'while') { ev = { a: 'test', kind, ok: v, src: cond() }; w.lamp = { ok: v, kind, src: ev.src }; if (kind === 'while' && v) w.loop = { kind, n: i + 1 }; }
      else if (kind === 'for') { ev = { a: 'loop', n: i + 1, name: s.target.k === 'name' ? s.target.id : null }; w.loop = { kind, n: i + 1, name: ev.name }; }
      else if (kind === 'call') ev = { a: 'call', fn: s.name };
      else ev = { a: 'ret', fn: s.name, v: cut(repr(v), 14) };
      Object.assign(ev, { g: cg, l: cl, out: printed });
      w.mem = g; w.frame = f; w.t++;
      if (printed) w.screen = outLines(run.out).slice(-6);
      return ev;
    };
  }

  /* ── проверки: что лежит в ящиках после программы — понятными фразами ── */
  const RU = { int: 'число', float: 'дробное число', str: 'строка', bool: 'логическое значение', list: 'список', NoneType: 'None' };
  const show = v => v === null || v === undefined ? 'None' : typeof v === 'boolean' ? (v ? 'True' : 'False') : `${RU[tn(v)] || tn(v)} ${cut(repr(v), 60)}`;
  function same(a, b) { return tn(a) === tn(b) && eq(a, b); }
  // в ящиках должны лежать значения want(given, run): { имя: значение }
  function want(fn) {
    return run => {
      const vals = fn(run.world.given, run), G = run.ip.globals;
      for (const [k, v] of Object.entries(vals)) {
        if (!G.has(k) || !shown(G.get(k))) return [`Ящика «${k}» на полке нет. Создайте его: ${k} = …`];
        const got = G.get(k);
        if (same(got, v)) continue;
        let tip = '';
        if (tn(v) === 'int' && tn(got) === 'float') tip = ' Получилось дробное число — для деления нацело есть //.';
        else if (tn(v) === 'int' && tn(got) === 'str') tip = ' Это строка, а нужно число: превратите строку в число с помощью int().';
        else if (tn(v) === 'str' && tn(got) === 'str' && got.trim() === v.trim()) tip = ' Проверьте пробелы.';
        return [`В ящике «${k}» должно лежать ${show(v)}, а лежит ${show(got)}.${tip}`];
      }
      return [];
    };
  }
  // на экране должны быть строки lines(given)
  function says(fn) {
    return run => {
      const need = fn(run.world.given), got = run.out.some(o => o.k === 'out') ? outLines(run.out) : [];
      if (got.length === need.length && got.every((l, i) => l.trimEnd() === need[i])) return [];
      const q = a => a.length ? a.slice(0, 6).map(x => `«${x}»`).join(', ') + (a.length > 6 ? ' …' : '') : 'ничего';
      return [`На экране должно быть: ${q(need)}. А программа вывела: ${q(got)}.`];
    };
  }
  const all = (...cs) => run => { for (const c of cs) { const m = c(run); if (m.length) return m; } return []; };
  const without = (name, msg) => run => new RegExp('\\b' + name + '\\s*\\(').test(run.code.replace(/#.*$/gm, '')) ? [msg] : [];
  const isFn = name => run => run.ip.globals.get(name) instanceof Fn ? [] : [`Опишите функцию ${name}: def ${name}(…):`];

  const ri = (r, a, b) => a + Math.floor(r() * (b - a + 1));
  const list = (r, n, a, b) => Array.from({ length: n }, () => ri(r, a, b));
  const NAMES = ['Аня', 'Тимур', 'Лиза', 'Марк', 'Ева', 'Саша', 'Даня', 'Мира'];

  /* ═════════════ УРОВНИ ═════════════ id с 201: прогресс и баллы общие с фермой и складом */
  const LEVELS = [
    {
      id: 201, title: 'Первый ящик', concept: 'переменная и знак =', adds: ['='],
      check: want(() => ({ x: 5 })), task: 'В ящике <code>x</code> — число 5.',
      text: 'Это мастерская, а полка — память компьютера. Переменная — ящик с именем: в него кладут значение, а потом достают по имени. Создайте ящик <code>x</code> и положите в него число 5. Нажмите ▶ и посмотрите, что сделает робот.',
      learn: ['Переменная', 'x = 5', 'Знак <code>=</code> в Python — не «равно», а «положи»: возьми значение справа и положи в ящик с именем слева. Если ящика ещё нет, Python его создаст. Имя пишут латинскими буквами без пробелов; большие и маленькие буквы различаются.'],
      start: '# положите в ящик x число 5\n',
      hint: 'Одна строка: <code>x = 5</code>',
      solution: 'x = 5\n',
    },
    {
      id: 202, title: 'Ящик из ящиков', concept: 'вычисления с переменными', adds: ['math'],
      check: want(() => ({ width: 4, height: 3, area: 12 })),
      codeHas: [[/area\s*=\s*(width\s*\*\s*height|height\s*\*\s*width)/, 'Вычислите площадь из ящиков: area = width * height — не пишите 12 вручную.']],
      task: 'В <code>width</code> — 4, в <code>height</code> — 3, в <code>area</code> — их произведение.',
      text: 'Значение можно не только написать, но и вычислить — в том числе из других ящиков. Ящики <code>width</code> (ширина) и <code>height</code> (высота) уже есть в программе. Положите в ящик <code>area</code> площадь — их произведение. Умножение в Python — звёздочка <code>*</code>.',
      learn: ['Значения из ящиков', 'width = 4\nheight = 3\narea = width * height', 'Когда Python видит имя ящика справа от <code>=</code>, он заглядывает в ящик и берёт оттуда значение. Сначала вычисляется всё, что справа, потом результат кладётся в ящик слева. Арифметика: <code>+</code> <code>-</code> <code>*</code> <code>/</code>.'],
      start: 'width = 4\nheight = 3\n# положите в area произведение width и height\n',
      hint: 'Третья строка: <code>area = width * height</code>',
      solution: 'width = 4\nheight = 3\narea = width * height\n',
    },
    {
      id: 203, title: 'Ящики уже на полке', concept: 'данные в переменных', adds: [],
      given: r => ({ a: ri(r, 10, 99), b: ri(r, 10, 99) }),
      check: want(g => ({ total: g.a + g.b })), task: 'В ящике <code>total</code> — сумма <code>a</code> и <code>b</code>.',
      text: 'На полке уже стоят ящики <code>a</code> и <code>b</code> с числами. При каждом запуске числа новые, поэтому написать ответ вручную не выйдет. Положите в ящик <code>total</code> их сумму, обращаясь к ящикам по именам.',
      learn: ['Переменные хранят данные', 'total = a + b', 'Программа почти никогда не знает заранее, какие числа ей дадут: их вводит человек, присылает сайт, измеряет датчик. Поэтому программы пишут через имена переменных — и одна программа работает для любых чисел.'],
      start: '# в ящиках a и b — числа; положите в total их сумму\n',
      hint: '<code>total = a + b</code>',
      solution: 'total = a + b\n',
    },
    {
      id: 204, title: 'Новое значение', concept: 'x = x + 10', adds: [],
      given: r => ({ coins: ri(r, 3, 20) }),
      check: want(g => ({ coins: (g.coins + 10) * 2 })), task: 'В копилке <code>coins</code> — (старое число + 10) × 2.',
      text: 'В копилке <code>coins</code> лежат монеты. Добавьте в неё 10 монет, а потом удвойте то, что получилось. Посмотрите, что происходит со старым значением, когда в ящик кладут новое.',
      learn: ['Изменить переменную', 'coins = coins + 10\ncoins = coins * 2', 'В ящике помещается только одно значение. <code>coins = coins + 10</code>: Python достаёт из ящика старое число, прибавляет 10 и кладёт результат обратно — старое значение исчезает. Короче то же самое пишут так: <code>coins += 10</code>.'],
      start: '# добавьте 10 монет, потом удвойте\n',
      hint: 'Две строки: <code>coins = coins + 10</code>, затем <code>coins = coins * 2</code>',
      solution: 'coins = coins + 10\ncoins = coins * 2\n',
    },
    {
      id: 205, title: 'Поменять местами', concept: 'временная переменная', adds: [],
      given: r => { const a = ri(r, 10, 99); let b; do b = ri(r, 10, 99); while (b === a); return { left: a, right: b }; },
      check: want(g => ({ left: g.right, right: g.left })), task: 'Числа в <code>left</code> и <code>right</code> поменялись местами.',
      text: 'В ящиках <code>left</code> и <code>right</code> лежат числа. Поменяйте их местами: что было в left, должно оказаться в right, и наоборот. Запустите стартовый код и посмотрите, куда пропало одно из чисел.',
      learn: ['Обмен через третий ящик', 'tmp = left\nleft = right\nright = tmp', '<code>left = right</code> сразу стирает старое значение left. Как поменять содержимое двух стаканов? Нужен третий, пустой. Так и здесь: <code>tmp</code> временно хранит значение. В Python есть и короткая запись: <code>left, right = right, left</code>.'],
      start: 'left = right\nright = left\n',
      hint: 'Сначала сохраните left: <code>tmp = left</code>. Затем <code>left = right</code> и <code>right = tmp</code>',
      solution: 'tmp = left\nleft = right\nright = tmp\n',
    },
    {
      id: 206, title: 'Строки', concept: 'строки и склейка', adds: ['str'],
      given: r => ({ name: NAMES[ri(r, 0, NAMES.length - 1)] }),
      check: want(g => ({ greeting: 'Привет, ' + g.name + '!' })), task: 'В <code>greeting</code> — строка вида <code>Привет, Аня!</code> с именем из <code>name</code>.',
      text: 'Значения бывают разных типов. Числа вы уже видели, а текст в Python называется строкой и пишется в кавычках: <code>"Привет"</code>. В ящике <code>name</code> лежит имя. Положите в <code>greeting</code> приветствие: «Привет, », потом имя, потом «!» — например, <code>Привет, Аня!</code>',
      learn: ['Строка', 'greeting = "Привет, " + name + "!"', 'Строка — любой текст в кавычках: <code>"кот"</code>, <code>"42"</code>, <code>""</code>. Знак <code>+</code> строки не складывает, а склеивает: <code>"ко" + "т"</code> — это <code>"кот"</code>. Пробел внутри кавычек — тоже символ. В мастерской числа — синие жетоны, строки — жёлтые карточки.'],
      start: '# положите в greeting строку «Привет, <имя>!»\ngreeting = "Привет"\n',
      hint: '<code>greeting = "Привет, " + name + "!"</code> — пробел после запятой внутри кавычек',
      solution: 'greeting = "Привет, " + name + "!"\n',
    },
    {
      id: 207, title: 'Строка или число?', concept: 'int() и str()', adds: ['int'],
      given: r => ({ text: String(ri(r, 12, 49)) }),
      check: want(g => ({ n: +g.text * 2 })), task: 'В <code>n</code> — число из строки <code>text</code>, умноженное на 2.',
      text: 'В ящике <code>text</code> лежит число, записанное строкой — например, <code>"25"</code>: так приходят данные, которые ввёл человек. Положите в <code>n</code> это число, умноженное на 2. Запустите стартовый код и посмотрите, что получается, если умножать строку.',
      learn: ['Превращение типов', 'n = int(text) * 2\ns = str(n)', '<code>"25" * 2</code> — это <code>"2525"</code>: строку Python просто повторяет. <code>int("25")</code> превращает строку в целое число 25, <code>str(25)</code> — число в строку <code>"25"</code>. Сложить строку и число нельзя: <code>"5" + 5</code> — ошибка TypeError.'],
      start: 'n = text * 2\n',
      hint: 'Сначала превратите строку в число: <code>n = int(text) * 2</code>',
      solution: 'n = int(text) * 2\n',
    },
    {
      id: 208, title: 'Поделить поровну', concept: 'деление // и %', adds: ['divmod'],
      given: r => { let c, k; do { c = ri(r, 20, 60); k = ri(r, 3, 7); } while (c % k === 0); return { candies: c, kids: k }; },
      check: want(g => ({ each: Math.floor(g.candies / g.kids), rest: g.candies % g.kids })), task: 'В <code>each</code> — сколько конфет получит каждый, в <code>rest</code> — сколько останется.',
      text: 'Конфеты <code>candies</code> делят поровну между детьми, их <code>kids</code>. Положите в <code>each</code>, сколько конфет достанется каждому, а в <code>rest</code> — сколько останется. Конфеты не режут, поэтому нужно деление нацело.',
      learn: ['Целое деление и остаток', 'each = candies // kids\nrest = candies % kids', '<code>/</code> — обычное деление, ответ дробный: <code>17 / 5</code> — <code>3.4</code>. <code>//</code> — нацело: <code>17 // 5</code> — <code>3</code>. <code>%</code> — остаток: <code>17 % 5</code> — <code>2</code>. Дробные числа в мастерской — фиолетовые жетоны.'],
      start: 'each = candies / kids\n',
      hint: '<code>each = candies // kids</code> и <code>rest = candies % kids</code>',
      solution: 'each = candies // kids\nrest = candies % kids\n',
    },
    {
      id: 209, title: 'Вывод на экран', concept: 'print()', adds: ['print'],
      given: r => ({ a: ri(r, 2, 12), b: ri(r, 2, 12) }),
      check: says(g => ['Сумма: ' + (g.a + g.b), 'Произведение: ' + g.a * g.b]), task: 'На экране две строки: <code>Сумма: …</code> и <code>Произведение: …</code>',
      text: 'Ящики видны только в мастерской, а человеку программа сообщает результат через экран. Выведите две строки: <code>Сумма: …</code> и <code>Произведение: …</code> — с суммой и произведением чисел из ящиков <code>a</code> и <code>b</code>.',
      learn: ['print()', 'print("Сумма:", a + b)', '<code>print()</code> выводит на экран то, что в скобках. Значения можно перечислить через запятую — print поставит между ними пробел. Каждый print — новая строка. Кавычки у строк на экран не выводятся.'],
      start: 'print("Сумма:", a + b)\n',
      hint: 'Вторая строка: <code>print("Произведение:", a * b)</code>',
      solution: 'print("Сумма:", a + b)\nprint("Произведение:", a * b)\n',
    },
    {
      id: 210, title: 'Правда или ложь', concept: 'сравнения, True и False', adds: ['cmp'],
      given: r => ({ age: r() < 0.5 ? ri(r, 7, 17) : ri(r, 18, 30) }),
      check: want(g => ({ adult: g.age >= 18 })), task: 'В <code>adult</code> — <code>True</code>, если <code>age</code> не меньше 18, иначе <code>False</code>.',
      text: 'Сравнение — это вопрос, на который Python отвечает <code>True</code> («правда») или <code>False</code> («ложь»). Такой ответ — тоже значение, его можно положить в ящик. В <code>age</code> — возраст. Положите в <code>adult</code> ответ на вопрос «age больше или равно 18?».',
      learn: ['Логические значения', 'adult = age >= 18', 'Сравнения: <code>&gt;</code> <code>&lt;</code> <code>&gt;=</code> <code>&lt;=</code>, <code>==</code> — «равно?», <code>!=</code> — «не равно?». Не путайте: <code>=</code> кладёт в ящик, <code>==</code> сравнивает. В мастерской True — зелёная табличка, False — красная.'],
      start: '# adult — True, если age больше или равно 18\n',
      hint: '<code>adult = age &gt;= 18</code>',
      solution: 'adult = age >= 18\n',
    },
    {
      id: 211, title: 'Если холодно', concept: 'if / else', adds: ['if'],
      given: r => ({ temp: r() < 0.5 ? ri(r, -15, -1) : ri(r, 1, 25) }),
      check: want(g => ({ clothes: g.temp < 0 ? 'куртка' : 'футболка' })), task: 'В <code>clothes</code> — <code>"куртка"</code>, если <code>temp</code> ниже нуля, иначе <code>"футболка"</code>.',
      text: 'В <code>temp</code> — температура на улице. Если она ниже нуля, положите в <code>clothes</code> строку <code>"куртка"</code>, иначе — <code>"футболка"</code>. Следите за лампой условия на стене: она показывает, что ответил Python.',
      learn: ['if / else', 'if temp < 0:\n    clothes = "куртка"\nelse:\n    clothes = "футболка"', '<code>if</code> — «если». После условия ставят двоеточие, а команды ветки пишут ниже с отступом в 4 пробела (Tab). Условие True — выполняется первая ветка, False — ветка <code>else</code> («иначе»). Выполнится ровно одна из двух.'],
      start: 'clothes = "куртка"\n# если temp ниже нуля — куртка, иначе — футболка\n',
      hint: 'Строка <code>if temp &lt; 0:</code>, под ней с отступом <code>clothes = "куртка"</code>, затем <code>else:</code> и с отступом <code>clothes = "футболка"</code>',
      solution: 'if temp < 0:\n    clothes = "куртка"\nelse:\n    clothes = "футболка"\n',
    },
    {
      id: 212, title: 'Больший из двух', concept: 'сравнение переменных', adds: [],
      given: r => { const a = ri(r, 1, 99); let b; do b = ri(r, 1, 99); while (b === a); return { a, b }; },
      check: all(without('max', 'Решите без max() — через if и сравнение.'), want(g => ({ biggest: Math.max(g.a, g.b) }))),
      codeHas: [[/\bif\b/, 'Нужно условие if: какое из чисел больше, заранее неизвестно.']], task: 'В <code>biggest</code> — большее из чисел <code>a</code> и <code>b</code>.',
      text: 'Положите в <code>biggest</code> большее из чисел <code>a</code> и <code>b</code>. Решите через <code>if</code>, без готовой функции <code>max()</code>: так вы поймёте, как она устроена.',
      learn: ['Сравнить два ящика', 'if a > b:\n    biggest = a\nelse:\n    biggest = b', 'В условии можно сравнивать ящики между собой. Python достаёт оба значения, сравнивает и решает, какую ветку выполнить.'],
      start: 'biggest = a\n',
      hint: '<code>if a &gt; b:</code> → <code>biggest = a</code>, <code>else:</code> → <code>biggest = b</code>',
      solution: 'if a > b:\n    biggest = a\nelse:\n    biggest = b\n',
    },
    {
      id: 213, title: 'Оценка', concept: 'цепочка elif', adds: [],
      given: r => { const t = ri(r, 0, 3); return { points: [ri(r, 85, 100), ri(r, 70, 84), ri(r, 50, 69), ri(r, 0, 49)][t] }; },
      check: want(g => ({ grade: g.points >= 85 ? 5 : g.points >= 70 ? 4 : g.points >= 50 ? 3 : 2 })), task: 'В <code>grade</code> — оценка за <code>points</code> баллов.',
      text: 'В <code>points</code> — баллы за контрольную, от 0 до 100. Положите в <code>grade</code> оценку: 85 и больше — 5, от 70 — 4, от 50 — 3, меньше 50 — 2. В стартовом коде одной ветки не хватает.',
      learn: ['Цепочка elif', 'if points >= 85:\n    grade = 5\nelif points >= 70:\n    grade = 4\nelse:\n    grade = 2', '<code>elif</code> — «а иначе, если». Python проверяет условия сверху вниз и выполняет первую ветку, где ответ True; остальные пропускает. Поэтому при 90 баллах <code>grade</code> станет 5, а до проверки <code>&gt;= 70</code> дело не дойдёт.'],
      start: 'if points >= 85:\n    grade = 5\nelif points >= 70:\n    grade = 4\nelse:\n    grade = 2\n',
      hint: 'Перед <code>else:</code> добавьте ещё одну ветку: <code>elif points &gt;= 50:</code> → <code>grade = 3</code>',
      solution: 'if points >= 85:\n    grade = 5\nelif points >= 70:\n    grade = 4\nelif points >= 50:\n    grade = 3\nelse:\n    grade = 2\n',
    },
    {
      id: 214, title: 'Повтори n раз', concept: 'цикл for и range()', adds: ['for'],
      given: r => ({ n: ri(r, 3, 7) }),
      check: says(g => Array(g.n).fill('Ура!')), codeHas: [[/\bfor\b/, 'Нужен цикл for: сколько раз повторять, записано в n.']], task: 'На экране <code>Ура!</code> — ровно <code>n</code> раз.',
      text: 'Выведите на экран слово <code>Ура!</code> столько раз, сколько записано в ящике <code>n</code>. Написать print несколько раз не выйдет: n каждый запуск новое. Повторять умеет цикл.',
      learn: ['Цикл for', 'for i in range(n):\n    print("Ура!")', '<code>for i in range(n):</code> — «повтори n раз». Команды, которые нужно повторять, пишут ниже с отступом. Счётчик на стене показывает, какой идёт круг.'],
      start: 'print("Ура!")\n',
      hint: 'Две строки: <code>for i in range(n):</code> и под ней с отступом <code>print("Ура!")</code>',
      solution: 'for i in range(n):\n    print("Ура!")\n',
    },
    {
      id: 215, title: 'Счёт до n', concept: 'переменная цикла', adds: [],
      given: r => ({ n: ri(r, 4, 9) }),
      check: says(g => Array.from({ length: g.n }, (_, i) => String(i + 1))), codeHas: [[/\bfor\b/, 'Нужен цикл for.']], task: 'На экране числа от 1 до <code>n</code>, каждое на своей строке.',
      text: 'Выведите числа от 1 до <code>n</code>, каждое на своей строке. Цикл сам кладёт номер круга в ящик <code>i</code> — посмотрите на полку во время работы. Стартовый код почти верный: запустите его и сравните.',
      learn: ['range(начало, конец)', 'for i in range(1, 4):\n    print(i)   # 1, 2, 3', '<code>range(5)</code> — числа 0, 1, 2, 3, 4: от нуля, а 5 уже не входит. <code>range(1, 4)</code> — 1, 2, 3: от первого числа до второго, не включая его. На каждом круге цикл кладёт следующее число в ящик <code>i</code>.'],
      start: 'for i in range(n):\n    print(i)\n',
      hint: '<code>for i in range(1, n + 1):</code> — последнее число в range не входит, поэтому n + 1',
      solution: 'for i in range(1, n + 1):\n    print(i)\n',
    },
    {
      id: 216, title: 'Копилка', concept: 'переменная-накопитель', adds: [],
      given: r => ({ n: ri(r, 5, 12) }),
      check: all(without('sum', 'Решите без sum() — копилкой в цикле.'), want(g => ({ total: g.n * (g.n + 1) / 2 }))), codeHas: [[/\bfor\b/, 'Нужен цикл for.']],
      task: 'В <code>total</code> — сумма чисел от 1 до <code>n</code>.',
      text: 'Положите в <code>total</code> сумму всех чисел от 1 до <code>n</code>. Для этого нужен ящик-копилка: до цикла в нём 0, а на каждом круге к нему добавляется очередное число. В стартовом коде копилка стоит не на своём месте — запустите и посмотрите, что с ней происходит.',
      learn: ['Переменная-накопитель', 'total = 0\nfor i in range(1, n + 1):\n    total = total + i', 'Это один из главных приёмов программирования. Важно, где стоит <code>total = 0</code>: до цикла — копилка заводится один раз. Внутри цикла она обнулялась бы на каждом круге.'],
      start: 'for i in range(1, n + 1):\n    total = 0\n    total = total + i\n',
      hint: 'Перенесите <code>total = 0</code> выше цикла, без отступа',
      solution: 'total = 0\nfor i in range(1, n + 1):\n    total = total + i\n',
    },
    {
      id: 217, title: 'Пока мало', concept: 'цикл while', adds: ['while'],
      given: r => ({ goal: ri(r, 50, 500) }),
      check: want(g => { let x = 1, k = 0; while (x < g.goal) { x *= 2; k++; } return { x, steps: k }; }), codeHas: [[/\bwhile\b/, 'Нужен цикл while: сколько раз удваивать, заранее неизвестно.']],
      task: 'В <code>x</code> — первое удвоенное число, не меньшее <code>goal</code>; в <code>steps</code> — сколько раз удвоили.',
      text: 'Число <code>x</code> начинается с 1 и удваивается: 1, 2, 4, 8… Удваивайте, пока x меньше <code>goal</code>, и считайте в <code>steps</code>, сколько раз удвоили. Сколько понадобится кругов, заранее неизвестно — для этого есть while.',
      learn: ['Цикл while', 'while x < goal:\n    x = x * 2\n    steps = steps + 1', '<code>while условие:</code> — «повторяй, пока условие True». Перед каждым кругом Python проверяет условие заново — смотрите на лампу. Когда ответ станет False, цикл закончится. Если он никогда не станет False, цикл будет бесконечным.'],
      start: 'x = 1\nsteps = 0\nwhile x < goal:\n    x = x * 2\n',
      hint: 'В цикл, с тем же отступом: <code>steps = steps + 1</code>',
      solution: 'x = 1\nsteps = 0\nwhile x < goal:\n    x = x * 2\n    steps = steps + 1\n',
    },
    {
      id: 218, title: 'Стоп!', concept: 'break', adds: ['break'],
      given: r => ({ start: ri(r, 20, 80) }),
      check: want(g => ({ n: Math.ceil(g.start / 7) * 7 })), codeHas: [[/\bbreak\b/, 'Остановите цикл командой break.']],
      task: 'В <code>n</code> — первое число не меньше <code>start</code>, которое делится на 7.',
      text: 'Найдите первое число, не меньшее <code>start</code>, которое делится на 7 без остатка, и оставьте его в ящике <code>n</code>. Перебирайте числа по одному и остановите цикл командой <code>break</code>, как только нашли. Стартовый код без break никогда не остановится — запустите и проверьте.',
      learn: ['break', 'n = start\nwhile True:\n    if n % 7 == 0:\n        break\n    n = n + 1', '<code>while True:</code> — цикл без конца: условие всегда True. Выйти из него можно командой <code>break</code> — она сразу прерывает цикл. <code>n % 7 == 0</code> значит «делится на 7»: остаток от деления равен нулю.'],
      start: 'n = start\nwhile True:\n    # если n делится на 7 — break\n    n = n + 1\n',
      hint: 'Перед <code>n = n + 1</code>: <code>if n % 7 == 0:</code> и глубже <code>break</code>',
      solution: 'n = start\nwhile True:\n    if n % 7 == 0:\n        break\n    n = n + 1\n',
    },
    {
      id: 219, title: 'Ящик с отделениями', concept: 'список и индексы', adds: ['list'],
      given: r => ({ nums: list(r, ri(r, 4, 7), 1, 50) }),
      check: want(g => ({ first: g.nums[0], last: g.nums[g.nums.length - 1], count: g.nums.length })),
      task: 'В <code>first</code> — первое число списка <code>nums</code>, в <code>last</code> — последнее, в <code>count</code> — сколько их.',
      text: 'Список — ящик с пронумерованными отделениями. В <code>nums</code> лежит список чисел, и длина у него каждый раз разная. Положите в <code>first</code> первое число, в <code>last</code> — последнее, а в <code>count</code> — сколько всего чисел.',
      learn: ['Список', 'first = nums[0]\ncount = len(nums)\nlast = nums[count - 1]', 'Список пишут в квадратных скобках: <code>[4, 8, 15]</code>. Номер отделения — индекс — считают с нуля: <code>nums[0]</code> — первое число. <code>len(nums)</code> — длина списка, поэтому последнее — <code>nums[len(nums) - 1]</code>, или короче: <code>nums[-1]</code>.'],
      start: 'first = nums[1]\n',
      hint: 'Индексы с нуля: <code>first = nums[0]</code>. Затем <code>count = len(nums)</code> и <code>last = nums[count - 1]</code>',
      solution: 'first = nums[0]\ncount = len(nums)\nlast = nums[count - 1]\n',
    },
    {
      id: 220, title: 'Сумма покупок', concept: 'цикл по списку', adds: [],
      given: r => ({ prices: list(r, ri(r, 4, 7), 10, 300) }),
      check: all(without('sum', 'Решите без sum() — циклом по списку.'), want(g => ({ total: g.prices.reduce((a, b) => a + b, 0) }))), codeHas: [[/\bfor\b/, 'Пройдите по списку циклом for.']],
      task: 'В <code>total</code> — сумма всех цен из <code>prices</code>.',
      text: 'В <code>prices</code> — цены покупок. Посчитайте в <code>total</code> общую сумму: пройдите по списку циклом и складывайте цены в копилку. Без готовой <code>sum()</code>.',
      learn: ['for по списку', 'for p in prices:\n    total = total + p', '<code>for p in prices:</code> — «для каждого p из списка». На каждом круге цикл кладёт в ящик <code>p</code> следующее значение из списка, и кругов столько, сколько в списке элементов.'],
      start: 'total = 0\n',
      hint: '<code>for p in prices:</code> и с отступом <code>total = total + p</code>',
      solution: 'total = 0\nfor p in prices:\n    total = total + p\n',
    },
    {
      id: 221, title: 'Самое большое', concept: 'поиск максимума', adds: [],
      given: r => { const a = list(r, ri(r, 5, 8), 1, 99), k = a.indexOf(Math.max(...a)); if (k === 0) [a[0], a[a.length - 1]] = [a[a.length - 1], a[0]]; return { nums: a }; },
      check: all(without('max', 'Решите без max() — циклом и сравнением.'), want(g => ({ biggest: Math.max(...g.nums) }))), codeHas: [[/\bfor\b/, 'Пройдите по списку циклом for.'], [/\bif\b/, 'Нужно условие: больше ли число найденного?']],
      task: 'В <code>biggest</code> — самое большое число из <code>nums</code>.',
      text: 'Найдите в списке <code>nums</code> самое большое число и положите его в <code>biggest</code> — без <code>max()</code>. Идея: держите в ящике лучшее найденное и сравнивайте с ним каждое следующее.',
      learn: ['Поиск максимума', 'biggest = nums[0]\nfor x in nums:\n    if x > biggest:\n        biggest = x', 'Начинаем с первого числа: пока это лучшее, что мы видели. Дальше каждое число сравниваем с <code>biggest</code>; если оно больше — оно становится новым лучшим. Так устроена и встроенная <code>max()</code>.'],
      start: 'biggest = nums[0]\nfor x in nums:\n    pass   # сравните x с biggest\n',
      hint: 'Вместо <code>pass</code>: <code>if x &gt; biggest:</code> и глубже <code>biggest = x</code>',
      solution: 'biggest = nums[0]\nfor x in nums:\n    if x > biggest:\n        biggest = x\n',
    },
    {
      id: 222, title: 'Только чётные', concept: 'новый список и append()', adds: ['append'],
      given: r => { let a; do a = list(r, ri(r, 6, 8), 1, 50); while (!a.some(x => x % 2) || !a.some(x => !(x % 2))); return { nums: a }; },
      check: want(g => ({ evens: g.nums.filter(x => x % 2 === 0) })), task: 'В <code>evens</code> — все чётные числа из <code>nums</code>, по порядку.',
      text: 'Соберите в новый список <code>evens</code> все чётные числа из <code>nums</code> — в том же порядке. Начните с пустого списка <code>[]</code> и добавляйте в него подходящие числа. Стартовый код добавляет все подряд.',
      learn: ['append()', 'evens = []\nevens.append(8)   # [8]', '<code>[]</code> — пустой список. <code>evens.append(x)</code> добавляет x в конец списка — у ящика появляется новое отделение. Число чётное, если делится на 2 без остатка: <code>x % 2 == 0</code>.'],
      start: 'evens = []\nfor x in nums:\n    evens.append(x)\n',
      hint: 'Перед <code>append</code>: <code>if x % 2 == 0:</code>, а <code>evens.append(x)</code> — ещё глубже',
      solution: 'evens = []\nfor x in nums:\n    if x % 2 == 0:\n        evens.append(x)\n',
    },
    {
      id: 223, title: 'Своя команда', concept: 'функция def', adds: ['def'],
      check: all(says(() => ['Ура!', 'Мы справились!', 'Ура!', 'Мы справились!', 'Ура!', 'Мы справились!']), isFn('cheer'),
        run => (run.code.replace(/#.*$/gm, '').match(/\bprint\s*\(/g) || []).length > 2 ? ['print должен встречаться только внутри функции — вызывайте cheer().'] : []),
      task: 'Функция <code>cheer()</code> выводит две строки; программа вызывает её 3 раза.',
      text: 'Функция — своя команда из нескольких строк. Её описывают один раз через <code>def</code>, а вызывают сколько угодно раз. Функция <code>cheer()</code> уже описана — вызовите её три раза. Посмотрите, что делает программа, когда функцию только описали.',
      learn: ['def', 'def cheer():\n    print("Ура!")\n\ncheer()', '<code>def имя():</code> создаёт функцию, её тело пишут с отступом. Само описание ничего не выполняет — команды сработают, когда функцию вызовут: <code>cheer()</code>. В мастерской на время вызова загорается стол функции справа.'],
      start: 'def cheer():\n    print("Ура!")\n    print("Мы справились!")\n',
      hint: 'После функции, без отступа, три строки <code>cheer()</code>',
      solution: 'def cheer():\n    print("Ура!")\n    print("Мы справились!")\n\ncheer()\ncheer()\ncheer()\n',
    },
    {
      id: 224, title: 'Квадрат', concept: 'параметр и return', adds: ['return'],
      given: r => ({ a: ri(r, 2, 12), b: ri(r, 2, 12) }),
      check: all(isFn('square'), want(g => ({ result: g.a * g.a + g.b * g.b }))), codeHas: [[/\breturn\b/, 'Функция должна вернуть результат: return x * x.']],
      task: 'Функция <code>square(x)</code> возвращает x · x; в <code>result</code> — <code>square(a) + square(b)</code>.',
      text: 'Функция <code>square(x)</code> должна вернуть квадрат числа — x, умноженное на x. Тогда в <code>result</code> можно положить сумму квадратов <code>a</code> и <code>b</code>. Сейчас функция печатает ответ, но не возвращает его — запустите и прочитайте ошибку.',
      learn: ['Параметр и return', 'def square(x):\n    return x * x\n\ns = square(5)   # 25', 'В скобках у def — параметр: ящик на столе функции, куда при вызове попадёт значение. <code>square(5)</code> — внутри функции x будет 5. <code>return</code> отдаёт результат туда, где функцию вызвали, и сразу её заканчивает. Без return функция возвращает <code>None</code> — «ничего».'],
      start: 'def square(x):\n    print(x * x)\n\nresult = square(a) + square(b)\n',
      hint: 'Замените <code>print(x * x)</code> на <code>return x * x</code>',
      solution: 'def square(x):\n    return x * x\n\nresult = square(a) + square(b)\n',
    },
    {
      id: 225, title: 'Стол функции', concept: 'локальные переменные', adds: [],
      given: r => ({ apples: ri(r, 2, 9), pears: ri(r, 2, 9) }),
      check: all(isFn('price'), want(g => ({ bill: g.apples * 30 + g.pears * 45 }))), codeHas: [[/price\s*\(\s*pears/, 'Посчитайте и груши: price(pears, 45).']],
      task: 'В <code>bill</code> — стоимость <code>apples</code> яблок по 30 ₽ и <code>pears</code> груш по 45 ₽.',
      text: 'Яблоко стоит 30 рублей, груша — 45. Функция <code>price(count, cost)</code> считает стоимость покупки. Положите в <code>bill</code> стоимость <code>apples</code> яблок и <code>pears</code> груш. Посмотрите на стол функции: ящики count, cost и total живут только там и исчезают после return.',
      learn: ['Локальные переменные', 'def price(count, cost):\n    total = count * cost\n    return total', 'Ящики, созданные внутри функции, — её собственные, локальные: они стоят на столе функции, снаружи их не видно, а после return они исчезают. Поэтому одинаковые имена внутри и снаружи функции друг другу не мешают.'],
      start: 'def price(count, cost):\n    total = count * cost\n    return total\n\nbill = price(apples, 30)\n',
      hint: '<code>bill = price(apples, 30) + price(pears, 45)</code>',
      solution: 'def price(count, cost):\n    total = count * cost\n    return total\n\nbill = price(apples, 30) + price(pears, 45)\n',
    },
  ];
  const CHAPTERS = [
    { id: 1, title: 'Переменные', levels: [201, 202, 203, 204, 205] },
    { id: 2, title: 'Типы значений', levels: [206, 207, 208, 209] },
    { id: 3, title: 'Условия', levels: [210, 211, 212, 213] },
    { id: 4, title: 'Циклы', levels: [214, 215, 216, 217, 218] },
    { id: 5, title: 'Списки', levels: [219, 220, 221, 222] },
    { id: 6, title: 'Функции', levels: [223, 224, 225] },
  ];
  const ORDER = CHAPTERS.flatMap(c => c.levels);
  const learned = [];
  ORDER.forEach((id, i) => {
    const l = LEVELS.find(x => x.id === id);
    learned.push(...l.adds);
    Object.assign(l, { num: i + 1, need: i > 0 ? ORDER[i - 1] : 0, w: 1, h: 1, py: [], api: [...learned], limit: l.limit || 600 });
    const src = l.solution + l.start;                          // что из мастерской нужно на уровне
    l.parts = { lamp: /\b(if|while)\b/.test(src), loop: /\b(for|while)\b/.test(src), screen: /\bprint\s*\(/.test(src), fn: /\bdef\b/.test(src) };
  });
  const numOf = id => ORDER.indexOf(id) + 1;
  const CORE = { world: (lv, seed) => new Lab(lv, seed), install, misses: () => [] };
  // справка «Что уже умеете»: открывается по мере прохождения
  const DOC = {
    '=': ['x = 5', 'положить значение в ящик x; старое значение исчезает'],
    math: ['+  -  *  /', 'сложить, вычесть, умножить, разделить'],
    str: ['"текст"', 'строка; <code>+</code> склеивает строки'],
    int: ['int(s)  str(x)', 'строку — в целое число; число — в строку'],
    divmod: ['//  %', 'деление нацело и остаток от деления'],
    print: ['print(a, b)', 'вывести значения на экран через пробел'],
    cmp: ['==  !=  <  >  <=  >=', 'сравнить; ответ — <code>True</code> или <code>False</code>'],
    if: ['if / elif / else', 'выполнить ветку, условие которой True'],
    for: ['for i in range(n):', 'повторить n раз; в i — номер круга, с нуля'],
    while: ['while условие:', 'повторять, пока условие True'],
    break: ['break', 'сразу выйти из цикла'],
    list: ['nums[0]  len(nums)', 'отделение списка по номеру (с нуля) и длина списка'],
    append: ['nums.append(x)', 'добавить x в конец списка'],
    def: ['def f(x):', 'описать свою функцию с параметром x'],
    return: ['return x', 'вернуть результат из функции'],
  };
  function simulate(lv, code, opt = {}) { return F.simulate(lv, code, { ...opt, game: CORE }); }
  const api = { LEVELS, CHAPTERS, ORDER, CORE, Lab, simulate, cell };
  if (typeof module !== 'undefined' && module.exports) { module.exports = api; return; }

  /* ═════════════ 3D: мастерская — верстак с ящиками, робот Байт, лампа, счётчик, экран, стол функции ═════════════
     Как и на складе: состояние мира → цели для каждой вещи, меши догоняют цели плавно */
  const UI = F.ui;
  const MONO = '600 {s}px ui-monospace, "Cascadia Mono", "JetBrains Mono", Consolas, monospace';
  const font = s => MONO.replace('{s}', s);
  const TOK = { int: ['#2F6FD6', '#fff'], float: ['#7A4FD0', '#fff'], str: ['#F2C14E', '#3A2A05'], none: ['#8C96A3', '#fff'], other: ['#8C96A3', '#fff'], list: ['#F4F1E8', '#20232A'] };
  function labScene(THREE, host, lv) {
    const P = lv.parts, FN = P.fn;
    const B0 = -3.3, B1 = FN ? 0.9 : 3.3, F0 = 1.35, F1 = 4.05;    // верстак с ящиками и стол функции по x
    const TOP = 0.78, TOP2 = 1.66, ZB = -0.55, WALL = -1.05;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
    host.appendChild(renderer.domElement);
    const scene = new THREE.Scene(), cam = new THREE.PerspectiveCamera(30, 1, 0.1, 300);
    const geos = [], mats = [], texs = [];
    const G = g => (geos.push(g), g);
    const M = o => { const m = new THREE.MeshStandardMaterial({ roughness: 0.75, metalness: 0.05, ...o }); mats.push(m); return m; };
    const cache = new Map(), C = (color, o = {}) => { const k = color + JSON.stringify(o); if (!cache.has(k)) cache.set(k, M({ color, ...o })); return cache.get(k); };
    const mesh = (geo, mat, x = 0, y = 0, z = 0) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = m.receiveShadow = true; return m; };
    const box = (w, h, d) => G(new THREE.BoxGeometry(w, h, d));
    const canvasTex = (w, h, draw) => { const c = document.createElement('canvas'); c.width = w; c.height = h; draw(c.getContext('2d'), w, h); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t; };
    const tex = (w, h, draw) => { const t = canvasTex(w, h, draw); texs.push(t); return t; };
    const fitText = (g, text, maxW, size) => { let s = size; g.font = font(s); while (s > 10 && g.measureText(text).width > maxW) { s -= 2; g.font = font(s); } return s; };
    const RW = 24, RD = 10;                                     // пол комнаты

    // свет: тёплый ключевой с тенями, мягкий общий, лампа над верстаком
    scene.add(new THREE.HemisphereLight(0xfff4e6, 0x4a3f36, 1.1));
    const key = new THREE.DirectionalLight(0xfff0dc, 2.1), R = 6;
    key.position.set(-R * 0.5, R * 1.3, R); key.castShadow = true; key.shadow.mapSize.set(2048, 2048);
    Object.assign(key.shadow.camera, { left: -R, right: R, top: R, bottom: -R, near: 0.5, far: R * 5 });
    key.shadow.bias = -0.0004; key.shadow.normalBias = 0.02; key.shadow.radius = 5;
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xc9dcff, 0.5); fill.position.set(R, R * 0.5, R); scene.add(fill);

    // пол — доски, стена — светлая штукатурка с перфопанелью над верстаком
    const floorTex = tex(1024, 512, (g, w, h) => {
      const rows = 9, rh = h / rows;
      for (let i = 0; i < rows; i++) {
        let x = -Math.random() * 200;
        while (x < w) {
          const len = 180 + Math.random() * 260, l = 52 + Math.random() * 10;
          g.fillStyle = `hsl(${28 + Math.random() * 6}, ${38 + Math.random() * 10}%, ${l}%)`; g.fillRect(x, i * rh, len, rh);
          for (let k = 0; k < 6; k++) { g.fillStyle = `rgba(80,50,25,${Math.random() * 0.08})`; g.fillRect(x, i * rh + Math.random() * rh, len, 1.5); }
          g.fillStyle = 'rgba(60,38,20,.45)'; g.fillRect(x, i * rh, 2, rh);
          x += len;
        }
        g.fillStyle = 'rgba(60,38,20,.5)'; g.fillRect(0, i * rh, w, 2);
      }
    });
    const floor = mesh(box(RW, 0.2, RD), [C(0x6B4A30), C(0x6B4A30), M({ map: floorTex, roughness: 0.7 }), C(0x6B4A30), C(0x6B4A30), C(0x6B4A30)], 0, -0.1, WALL + RD / 2);
    scene.add(floor);
    const wallTex = tex(1024, 384, (g, w, h) => {
      g.fillStyle = '#E9E1D3'; g.fillRect(0, 0, w, h);
      for (let i = 0; i < 2500; i++) { g.fillStyle = `rgba(${Math.random() < 0.5 ? '255,255,255' : '120,100,80'},${Math.random() * 0.05})`; g.fillRect(Math.random() * w, Math.random() * h, 3, 3); }
      g.fillStyle = '#B9A58C'; g.fillRect(0, h - 40, w, 40);                    // плинтус-панель
    });
    const WH = 9;
    scene.add(mesh(box(RW, WH, 0.12), [C(0xD9CFBF), C(0xD9CFBF), C(0xD9CFBF), C(0xD9CFBF), M({ map: wallTex, roughness: 0.9 }), C(0xD9CFBF)], 0, WH / 2 - 0.2, WALL - 0.06));
    const peg = tex(512, 256, (g, w, h) => { g.fillStyle = '#C79A63'; g.fillRect(0, 0, w, h); g.fillStyle = 'rgba(70,45,20,.55)'; for (let y = 12; y < h; y += 22) for (let x = 12; x < w; x += 22) { g.beginPath(); g.arc(x, y, 3.2, 0, 7); g.fill(); } });
    peg.wrapS = peg.wrapT = THREE.RepeatWrapping; peg.repeat.set((B1 - B0) / 2.2, 1);
    scene.add(mesh(box(B1 - B0 + 0.3, 1.0, 0.03), M({ map: peg, roughness: 0.8 }), (B0 + B1) / 2, TOP + 0.62, WALL + 0.02));

    // верстак: толстая столешница, ноги, нижняя полка; над ним — полка для лишних ящиков
    const wood = C(0xA9774A, { roughness: 0.6 }), woodD = C(0x7A5232, { roughness: 0.7 }), metal = C(0x3A3F47, { roughness: 0.35, metalness: 0.7 });
    const bench = (x0, x1, top, felt) => {
      const w = x1 - x0, cx = (x0 + x1) / 2;
      scene.add(mesh(box(w, 0.08, 0.9), wood, cx, top - 0.04, ZB));
      if (felt) scene.add(mesh(box(w - 0.1, 0.012, 0.8), C(felt, { roughness: 0.95 }), cx, top + 0.006, ZB));
      for (const lx of [x0 + 0.08, x1 - 0.08]) for (const lz of [ZB - 0.36, ZB + 0.36]) scene.add(mesh(box(0.08, top - 0.08, 0.08), woodD, lx, (top - 0.08) / 2, lz));
      scene.add(mesh(box(w - 0.2, 0.04, 0.7), woodD, cx, 0.22, ZB));
    };
    bench(B0, B1, TOP);
    scene.add(mesh(box(B1 - B0, 0.05, 0.42), wood, (B0 + B1) / 2, TOP2 - 0.025, WALL + 0.21));
    for (const bx of [B0 + 0.3, (B0 + B1) / 2, B1 - 0.3]) scene.add(mesh(box(0.05, 0.22, 0.3), metal, bx, TOP2 - 0.14, WALL + 0.16));
    // декор на нижней полке верстака: банки с болтами, ящик с инструментом
    for (const [dx, col] of [[0.35, 0x6FA8DC], [0.62, 0xE8B322]]) { scene.add(mesh(G(new THREE.CylinderGeometry(0.1, 0.1, 0.2, 16)), C(col, { roughness: 0.3, transparent: true, opacity: 0.85 }), B0 + dx, 0.34, ZB - 0.1)); }
    scene.add(mesh(box(0.6, 0.2, 0.3), C(0xC8483B, { roughness: 0.4, metalness: 0.3 }), B1 - 0.6, 0.34, ZB - 0.05));

    // стол функции: зелёное сукно и вывеска с именем функции
    let fnSign = null, fnSignTex = null, fnLamp = null;
    const drawSign = (g, w, h, name) => {
      g.fillStyle = name ? '#1F5C3F' : '#40514A'; g.fillRect(0, 0, w, h);
      g.strokeStyle = '#F4F1E8'; g.lineWidth = 6; g.strokeRect(8, 8, w - 16, h - 16);
      g.fillStyle = name ? '#F4F1E8' : 'rgba(244,241,232,.55)'; g.textAlign = 'center'; g.textBaseline = 'middle';
      const t = name ? `внутри ${name}()` : 'стол функции'; fitText(g, t, w - 40, 54); g.fillText(t, w / 2, h / 2 + 2);
    };
    if (FN) {
      bench(F0, F1, TOP, 0x2E7D52);
      fnSignTex = tex(512, 128, (g, w, h) => drawSign(g, w, h, null));
      fnSign = mesh(box(2.0, 0.5, 0.05), [C(0x1F5C3F), C(0x1F5C3F), C(0x1F5C3F), C(0x1F5C3F), M({ map: fnSignTex, roughness: 0.6 }), C(0x1F5C3F)], (F0 + F1) / 2, TOP + 0.95, WALL + 0.06);
      scene.add(fnSign);
      fnLamp = new THREE.PointLight(0x9CFFC8, 0, 3.5, 1.6); fnLamp.position.set((F0 + F1) / 2, TOP + 1.2, ZB + 0.4); scene.add(fnLamp);
    }

    // табло на стене: лампа условия, счётчик кругов, экран print
    const boards = [];
    if (P.lamp) boards.push('lamp');
    if (P.loop) boards.push('loop');
    if (P.screen) boards.push('screen');
    const BY = 2.5, bw = { lamp: 1.5, loop: 1.1, screen: 2.2 };
    let bx = (B0 + (FN ? F1 : B1)) / 2 - (boards.reduce((a, b) => a + bw[b], 0) + (boards.length - 1) * 0.3) / 2;
    const at = {};
    for (const b of boards) { at[b] = bx + bw[b] / 2; bx += bw[b] + 0.3; }
    const plate = (w, h, draw) => {
      const t = tex(Math.round(w * 256), Math.round(h * 256), draw);
      return { t, draw };
    };
    let lampBulb = null, lampMat = null, lampTex = null, loopTex = null, scrTex = null;
    const redraw = (t, draw) => { const c = t.image, g = c.getContext('2d'); g.clearRect(0, 0, c.width, c.height); draw(g, c.width, c.height); t.needsUpdate = true; };
    const drawLamp = (g, w, h, l) => {
      g.fillStyle = '#20232A'; g.fillRect(0, 0, w, h);
      g.fillStyle = 'rgba(255,255,255,.55)'; g.font = font(30); g.textAlign = 'center'; g.textBaseline = 'middle';
      g.fillText(l ? (l.kind === 'while' ? 'while: пока…' : 'if: если…') : 'условие', w / 2, 34);
      if (l) {
        g.fillStyle = '#fff'; fitText(g, l.src, w - 30, 34); g.fillText(l.src, w / 2, h / 2 + 4);
        g.fillStyle = l.ok ? '#5BE08F' : '#FF6B5E'; g.font = font(44); g.fillText(l.ok ? 'True' : 'False', w / 2, h - 44);
      }
    };
    const drawLoop = (g, w, h, lp) => {
      g.fillStyle = '#20232A'; g.fillRect(0, 0, w, h);
      g.fillStyle = 'rgba(255,255,255,.55)'; g.font = font(30); g.textAlign = 'center'; g.textBaseline = 'middle';
      g.fillText(lp ? (lp.kind === 'for' ? 'цикл for' : 'цикл while') : 'цикл', w / 2, 34);
      g.fillStyle = '#FFD166'; g.font = font(lp && lp.n > 99 ? 72 : 96); g.fillText(lp ? String(lp.n) : '–', w / 2, h / 2 + 10);
      g.fillStyle = 'rgba(255,255,255,.55)'; g.font = font(28); g.fillText('круг', w / 2, h - 30);
    };
    const drawScreen = (g, w, h, lines) => {
      g.fillStyle = '#0E1A14'; g.fillRect(0, 0, w, h);
      g.fillStyle = 'rgba(120,255,170,.12)'; for (let y = 0; y < h; y += 6) g.fillRect(0, y, w, 2);
      g.fillStyle = 'rgba(160,255,200,.5)'; g.font = font(26); g.textAlign = 'left'; g.textBaseline = 'top'; g.fillText('экран', 18, 12);
      g.fillStyle = '#8CFFB4'; const ls = lines.slice(-5);
      ls.forEach((l, i) => { fitText(g, l || ' ', w - 40, 38); g.fillText(l, 22, 52 + i * 40); });
    };
    const frameBoard = (x, w, h) => { scene.add(mesh(box(w + 0.1, h + 0.1, 0.06), C(0x2B3038, { roughness: 0.4, metalness: 0.4 }), x, BY, WALL + 0.04)); };
    if (at.lamp !== undefined) {
      frameBoard(at.lamp, 1.5, 0.9);
      lampTex = plate(1.5, 0.9, () => { }).t; redraw(lampTex, (g, w, h) => drawLamp(g, w, h, null));
      scene.add(mesh(G(new THREE.PlaneGeometry(1.5, 0.9)), M({ map: lampTex, roughness: 0.5 }), at.lamp, BY, WALL + 0.08));
      lampMat = M({ color: 0x555a60, emissive: 0x000000, emissiveIntensity: 1, roughness: 0.2 });
      scene.add(mesh(box(0.3, 0.08, 0.2), metal, at.lamp, BY + 0.52, WALL + 0.12));
      lampBulb = mesh(G(new THREE.SphereGeometry(0.13, 24, 16)), lampMat, at.lamp, BY + 0.66, WALL + 0.14); scene.add(lampBulb);
    }
    if (at.loop !== undefined) {
      frameBoard(at.loop, 1.1, 0.9);
      loopTex = plate(1.1, 0.9, () => { }).t; redraw(loopTex, (g, w, h) => drawLoop(g, w, h, null));
      scene.add(mesh(G(new THREE.PlaneGeometry(1.1, 0.9)), M({ map: loopTex, roughness: 0.5 }), at.loop, BY, WALL + 0.08));
    }
    let loopRing = null;
    if (at.loop !== undefined) {                                    // колесо-карусель над счётчиком: поворачивается на каждом круге
      loopRing = new THREE.Group(); loopRing.position.set(at.loop, BY + 0.62, WALL + 0.14); scene.add(loopRing);
      loopRing.add(mesh(G(new THREE.TorusGeometry(0.17, 0.03, 8, 28)), C(0xFFD166, { roughness: 0.4, metalness: 0.3 })));
      for (let k = 0; k < 6; k++) { const a = k / 6 * Math.PI * 2; loopRing.add(mesh(G(new THREE.SphereGeometry(0.035, 10, 8)), C(0xE8762B), Math.cos(a) * 0.17, Math.sin(a) * 0.17, 0)); }
    }
    let scrMat = null;
    if (at.screen !== undefined) {
      frameBoard(at.screen, 2.2, 0.9);
      scrTex = plate(2.2, 0.9, () => { }).t; redraw(scrTex, (g, w, h) => drawScreen(g, w, h, []));
      scrMat = M({ map: scrTex, emissive: 0xffffff, emissiveMap: scrTex, emissiveIntensity: 0.35, roughness: 0.3 });
      scene.add(mesh(G(new THREE.PlaneGeometry(2.2, 0.9)), scrMat, at.screen, BY, WALL + 0.08));
    }

    // ящики и жетоны
    const crateMat = C(0xC79A63, { roughness: 0.8 }), crateD = C(0x9E7448, { roughness: 0.8 });
    const crates = new Map(), dying = [];
    const crateW = (c, local) => c.t === 'list' ? Math.max(0.8, 0.3 * Math.max(1, c.items.length + (c.more ? 1 : 0)) + 0.24) : local ? 0.68 : 0.8;
    function makeCrate(name, w, local) {
      const g = new THREE.Group(), own = [];
      const B = (bw, bh, bd, m, x, y, z) => { const gg = new THREE.BoxGeometry(bw, bh, bd); own.push(gg); g.add(mesh(gg, m, x, y, z)); };
      B(w, 0.04, 0.5, crateD, 0, 0.02, 0);
      B(w, 0.34, 0.04, crateMat, 0, 0.17, -0.23);
      B(0.04, 0.3, 0.5, crateMat, -w / 2 + 0.02, 0.15, 0); B(0.04, 0.3, 0.5, crateMat, w / 2 - 0.02, 0.15, 0);
      B(w, 0.2, 0.04, crateMat, 0, 0.1, 0.23);
      const t = canvasTex(Math.round(w * 400), 80, (gc, cw, ch) => {
        gc.fillStyle = local ? '#DFF3E6' : '#F7F3EA'; gc.beginPath(); gc.roundRect(2, 2, cw - 4, ch - 4, 10); gc.fill();
        gc.fillStyle = '#20232A'; gc.textAlign = 'center'; gc.textBaseline = 'middle'; fitText(gc, name, cw - 16, 58); gc.fillText(name, cw / 2, ch / 2 + 2);
      });
      const pm = new THREE.MeshStandardMaterial({ map: t, roughness: 0.6 }), pg = new THREE.PlaneGeometry(w - 0.08, 0.16);
      own.push(pg); const p = new THREE.Mesh(pg, pm); p.position.set(0, 0.1, 0.252); g.add(p);
      g.scale.setScalar(0.01); scene.add(g);
      return { g, w, own, mats: [pm], texs: [t], tok: null, pos: new THREE.Vector3(), alive: true, local };
    }
    function makeToken(c, w) {
      const g = new THREE.Group(), own = [], ms = [], ts = [];
      const [bg, fg] = TOK[c.t] || TOK.other;
      const body = (geo, m) => { own.push(geo); ms.push(m); const x = new THREE.Mesh(geo, m); x.castShadow = true; g.add(x); return x; };
      const face = (fw, fh, draw) => {
        const t = canvasTex(Math.round(fw * 400), Math.round(fh * 400), draw); ts.push(t);
        const m = new THREE.MeshStandardMaterial({ map: t, transparent: true, roughness: 0.5 }), pg = new THREE.PlaneGeometry(fw, fh);
        ms.push(m); own.push(pg); const p = new THREE.Mesh(pg, m); g.add(p); return p;
      };
      const text = (txt, col, max) => (gc, cw, ch) => { gc.fillStyle = col; gc.textAlign = 'center'; gc.textBaseline = 'middle'; fitText(gc, txt, cw * 0.86, max); gc.fillText(txt, cw / 2, ch / 2 + 3); };
      if (c.t === 'int' || c.t === 'float' || c.t === 'none') {
        const r = c.t === 'none' ? 0.18 : 0.24;
        body(new THREE.CylinderGeometry(r, r, 0.07, 40).rotateX(Math.PI / 2), new THREE.MeshStandardMaterial({ color: bg, roughness: 0.35, metalness: 0.25 }));
        const rim = body(new THREE.TorusGeometry(r - 0.02, 0.012, 6, 40), new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.4, transparent: true, opacity: 0.5 })); rim.position.z = 0.037;
        face(r * 1.7, r * 1.1, text(c.s, fg, 120)).position.z = 0.04;
      } else if (c.t === 'bool') {
        const on = c.s === 'True';
        body(new THREE.BoxGeometry(0.56, 0.3, 0.06), new THREE.MeshStandardMaterial({ color: on ? 0x2E9E5B : 0xC8483B, emissive: on ? 0x2E9E5B : 0xC8483B, emissiveIntensity: 0.35, roughness: 0.35 }));
        face(0.52, 0.26, text(c.s, '#fff', 110)).position.z = 0.032;
      } else if (c.t === 'list') {
        const n = c.items.length + (c.more ? 1 : 0), tw = w - 0.12;
        body(new THREE.BoxGeometry(tw, 0.42, 0.05), new THREE.MeshStandardMaterial({ color: 0xF4F1E8, roughness: 0.5 }));
        face(tw, 0.42, (gc, cw, ch) => {
          const cell = cw / Math.max(1, n);
          if (!n) { gc.fillStyle = '#8C96A3'; gc.font = font(60); gc.textAlign = 'center'; gc.textBaseline = 'middle'; gc.fillText('[ ]', cw / 2, ch / 2); return; }
          for (let i = 0; i < n; i++) {
            const x = i * cell;
            gc.fillStyle = i % 2 ? '#E6EEF9' : '#DCE7F7'; gc.fillRect(x + 4, 6, cell - 8, ch * 0.62);
            gc.fillStyle = '#20232A'; gc.textAlign = 'center'; gc.textBaseline = 'middle';
            const v = i < c.items.length ? c.items[i] : '…';
            fitText(gc, v, cell - 16, 64); gc.fillText(v, x + cell / 2, 6 + ch * 0.31);
            gc.fillStyle = '#6B7380'; gc.font = font(34); gc.fillText(i < c.items.length ? String(i) : '', x + cell / 2, ch * 0.84);
          }
        }).position.z = 0.027;
      } else {
        const tw = c.t === 'str' ? Math.min(0.9, Math.max(0.5, 0.06 * c.s.length + 0.2)) : 0.6;
        body(new THREE.BoxGeometry(tw, 0.32, 0.03), new THREE.MeshStandardMaterial({ color: bg, roughness: 0.6 }));
        face(tw - 0.04, 0.28, text(c.s, fg, 90)).position.z = 0.017;
      }
      scene.add(g);
      return { g, own, ms, ts, rep: c.rep, s: 1 };
    }
    const disposeObj = o => { scene.remove(o.g); o.own.forEach(x => x.dispose()); (o.ms || o.mats).forEach(x => x.dispose()); (o.ts || o.texs).forEach(x => x.dispose()); };

    // робот Байт: оранжевый шар с экраном-лицом, антенной и пропеллером, парит перед верстаком
    const robot = new THREE.Group(); scene.add(robot);
    const rb = new THREE.Group(); robot.add(rb);
    const orange = C(0xF08A3C, { roughness: 0.35, metalness: 0.1 }), dark = C(0x22252B, { roughness: 0.5 });
    rb.add(mesh(G(new THREE.SphereGeometry(0.2, 32, 24)), orange));
    const faceM = mesh(G(new THREE.SphereGeometry(0.155, 32, 16, -Math.PI * 0.32, Math.PI * 0.64, Math.PI * 0.3, Math.PI * 0.42)), C(0x14181F, { roughness: 0.15, metalness: 0.3 }), 0, 0, 0.06);
    rb.add(faceM);
    const eyeMat = M({ color: 0x8FF3FF, emissive: 0x5FE8FF, emissiveIntensity: 2.2 });
    const eyes = [-0.055, 0.055].map(ex => { const e = mesh(G(new THREE.SphereGeometry(0.026, 12, 8)), eyeMat, ex, 0.02, 0.2); e.castShadow = false; rb.add(e); return e; });
    rb.add(mesh(G(new THREE.CylinderGeometry(0.008, 0.008, 0.14, 8)), dark, 0, 0.26, 0));
    const tipMat = M({ color: 0xFFD166, emissive: 0xFFB000, emissiveIntensity: 0.8 });
    rb.add(mesh(G(new THREE.SphereGeometry(0.03, 12, 8)), tipMat, 0, 0.34, 0));
    for (const sx of [-1, 1]) {                                    // ручки-манипуляторы
      const arm = mesh(G(new THREE.CapsuleGeometry(0.025, 0.12, 4, 8)), dark, sx * 0.2, -0.08, 0.06); arm.rotation.z = sx * 0.5; rb.add(arm);
    }
    rb.add(mesh(G(new THREE.TorusGeometry(0.2, 0.018, 8, 36).rotateX(Math.PI / 2)), C(0x3A3F47, { metalness: 0.6, roughness: 0.3 }), 0, -0.02, 0));
    const HOME = new THREE.Vector3((B0 + B1) / 2 - 0.4, TOP + 1.15, ZB + 0.6);
    robot.position.copy(HOME);

    const st = { tau: 0.12, goal: HOME.clone(), look: 0, ring: 0, ringT: 0, flash: 0 };
    let raf = 0, last = 0, size = { w: 1, h: 1 }, dur = 160, world = null, fnName = null, fnGlow = 0;
    const hand = () => robot.position.clone().add(new THREE.Vector3(0, -0.25, 0.1));
    // где стоит каждый ящик: глобальные — на верстаке (лишние — на полке выше), локальные — на столе функции
    function layout(mem, x0, x1, local) {
      const out = new Map(); let x = x0 + 0.1, row = 0;
      for (const c of mem) {
        const w = crateW(c, local);
        if (x + w > x1 - 0.05 && x > x0 + 0.1) { x = x0 + 0.1; row++; }
        const y = row === 0 ? TOP : TOP2 + (row - 1) * 0.9, z = row === 0 ? ZB + 0.05 : WALL + 0.24;
        out.set(c.name, { c, w, p: new THREE.Vector3(x + w / 2, y, z) });
        x += w + 0.08;
      }
      return out;
    }
    function frame() {
      raf = requestAnimationFrame(frame);
      const t = performance.now(), dt = Math.min(0.1, (t - last) / 1000 || 0); last = t;
      const calm = UI.reduceMotion();
      const a = st.tau > 0 && !calm ? 1 - Math.exp(-dt / st.tau) : 1;
      // робот летит к цели, покачивается и наклоняется в полёте
      const px = robot.position.x;
      robot.position.lerp(st.goal, a);
      const v = (robot.position.x - px) / (dt || 1);
      rb.position.y = calm ? 0 : Math.sin(t / 420) * 0.025;
      rb.rotation.z += ((calm ? 0 : -Math.max(-0.35, Math.min(0.35, v * 0.08))) - rb.rotation.z) * Math.min(1, dt * 8);
      rb.rotation.y += (st.look - rb.rotation.y) * Math.min(1, dt * 6);
      const blink = (t % 3600) < 110; eyes.forEach(e => { e.scale.y = blink ? 0.2 : 1; });
      tipMat.emissiveIntensity = 0.6 + Math.sin(t / 300) * 0.4;
      // ящики и жетоны догоняют свои места
      for (const [k, cr] of crates) {
        const sGoal = cr.alive ? 1 : 0;
        const s = cr.g.scale.x + (sGoal - cr.g.scale.x) * (calm ? 1 : Math.min(1, a * 1.4 + 0.02));
        cr.g.scale.setScalar(Math.max(0.001, s));
        cr.g.position.lerp(cr.pos, a);
        if (cr.tok) {
          const tg = cr.pos.clone().add(new THREE.Vector3(0, 0.36, 0.02));
          if (cr.alive) cr.tok.g.position.lerp(tg, Math.min(1, a * 1.15)); else cr.tok.g.position.lerp(tg, a);
          cr.tok.s += (1 - cr.tok.s) * a; cr.tok.g.scale.setScalar(Math.max(0.001, cr.tok.s * cr.g.scale.x));
        }
        if (!cr.alive && cr.g.scale.x < 0.03) { if (cr.tok) disposeObj(cr.tok); disposeObj(cr); crates.delete(k); }
      }
      // старые значения: взлетают и тают
      for (let i = dying.length - 1; i >= 0; i--) {
        const d = dying[i], k = calm ? 1 : Math.min(1, dt / Math.max(0.12, st.tau * 2.2));
        d.g.position.y += (calm ? 1 : dt * 1.6); d.s -= k; d.g.rotation.z += dt * 2;
        d.g.scale.setScalar(Math.max(0.001, d.s));
        if (d.s <= 0.02) { disposeObj(d); dying.splice(i, 1); }
      }
      // лампа, карусель, стол функции
      if (lampMat) {
        const l = world && world.lamp, col = !l ? 0x000000 : l.ok ? 0x2EE06F : 0xFF3B2E;
        lampMat.emissive.setHex(col); lampMat.color.setHex(!l ? 0x555a60 : l.ok ? 0x6BF0A0 : 0xFF7A6E);
        st.flash = Math.max(0, st.flash - dt * 2.5); lampMat.emissiveIntensity = 1.2 + st.flash * 2;
      }
      if (loopRing) { loopRing.rotation.z += (st.ringT - loopRing.rotation.z) * a; }
      if (fnLamp) { fnGlow += ((fnName ? 2.2 : 0) - fnGlow) * Math.min(1, dt * 5); fnLamp.intensity = fnGlow; }
      renderer.render(scene, cam);
    }
    raf = requestAnimationFrame(frame);

    return {
      sync(w, ev, d) {
        const fresh = w !== world;                                 // новый запуск или сброс; без события sync зовут и при перекладке окон
        world = w; dur = d || 0;
        st.tau = dur ? dur / 1000 / 3.2 : 0;
        const spots = new Map([...layout(w.mem, B0, B1, false)].map(([k, v]) => ['g:' + k, v]));
        if (FN && w.frame) for (const [k, v] of layout(w.frame.mem, F0, F1, true)) spots.set(`l${w.frame.depth}:${k}`, v);
        const moved = [];
        for (const [k, cr] of crates) if (!spots.has(k)) cr.alive = false;
        for (const [k, sp] of spots) {
          let cr = crates.get(k);
          if (cr && Math.abs(cr.w - sp.w) > 0.001) {                 // список вырос — ящик пошире
            const old = cr; cr = makeCrate(sp.c.name, sp.w, old.local); cr.g.position.copy(old.g.position); cr.g.scale.setScalar(1); cr.tok = old.tok; cr.tok && (cr.tok.rep = null);
            old.tok = null; disposeObj(old); crates.set(k, cr);
          }
          if (!cr) { cr = makeCrate(sp.c.name, sp.w, k[0] === 'l'); cr.g.position.copy(sp.p); crates.set(k, cr); }
          cr.alive = true; cr.pos.copy(sp.p);
          if (!cr.tok || cr.tok.rep !== sp.c.rep) {
            if (cr.tok) { if (dur) dying.push(cr.tok); else disposeObj(cr.tok); }
            cr.tok = makeToken(sp.c, sp.w);
            if (dur && ev) { cr.tok.g.position.copy(hand()); cr.tok.s = 0.35; moved.push(cr); }
            else cr.tok.g.position.copy(sp.p).add(new THREE.Vector3(0, 0.36, 0.02));
          }
        }
        // куда смотреть роботу: на ящик, который меняется, на лампу, экран или стол функции
        let goal = null; st.look = 0;
        if (ev) {
          const name = ev.l && ev.l.length ? `l${w.frame ? w.frame.depth : 0}:${ev.l[ev.l.length - 1]}` : ev.g && ev.g.length ? 'g:' + ev.g[ev.g.length - 1] : null;
          const cr = name && crates.get(name);
          if (cr && cr.alive) goal = new THREE.Vector3(cr.pos.x + 0.1, cr.pos.y + 1.15, ZB + 0.6);
          else if (ev.a === 'test' && at.lamp !== undefined) { goal = new THREE.Vector3(at.lamp + 0.9, 1.9, 0.2); st.look = 0.35; }
          else if (ev.a === 'print' && at.screen !== undefined) { goal = new THREE.Vector3(at.screen - 1.3, 1.9, 0.2); st.look = -0.3; }
          else if ((ev.a === 'call' || ev.a === 'ret') && FN) goal = new THREE.Vector3((F0 + F1) / 2, TOP + 1.0, ZB + 0.8);
          if (ev.a === 'test') st.flash = 1;
          if (ev.a === 'loop' || (ev.a === 'test' && ev.kind === 'while' && ev.ok)) st.ringT -= Math.PI / 3;
        }
        if (goal) st.goal.copy(goal); else if (!ev && fresh) st.goal.copy(HOME);
        if (lampTex) redraw(lampTex, (g, cw, ch) => drawLamp(g, cw, ch, w.lamp));
        if (loopTex) redraw(loopTex, (g, cw, ch) => drawLoop(g, cw, ch, w.loop));
        if (scrTex && (!ev || ev.out)) redraw(scrTex, (g, cw, ch) => drawScreen(g, cw, ch, w.screen));
        const nm = w.frame ? w.frame.name : null;
        if (fnSignTex && nm !== fnName) redraw(fnSignTex, (g, cw, ch) => drawSign(g, cw, ch, nm));
        fnName = nm;
        if (!dur) {                                              // без анимации — всё сразу на месте
          robot.position.copy(st.goal);
          for (const [, cr] of crates) { cr.g.position.copy(cr.pos); cr.g.scale.setScalar(cr.alive ? 1 : 0.001); if (cr.tok) { cr.tok.s = 1; cr.tok.g.position.copy(cr.pos).add(new THREE.Vector3(0, 0.36, 0.02)); } }
          dying.splice(0).forEach(disposeObj);
          if (loopRing) loopRing.rotation.z = st.ringT;
        }
      },
      fit(free, far) {
        const w = host.clientWidth || 1, h = host.clientHeight || 1;
        size = { w, h };
        renderer.setSize(w, h, false);
        cam.aspect = w / h;
        const fw = Math.max(200, free ? free[1] - free[0] : w), mid = free ? (free[0] + free[1]) / 2 : w / 2;
        const t = Math.tan(cam.fov * Math.PI / 360), spanX = (FN ? F1 : B1) - B0 + 0.6, spanY = boards.length ? 3.0 : 2.3;
        const d = Math.max(spanY / (2 * t), spanX / (2 * t * fw / h)) * (far ? 1.15 : 1.02), el = 0.2;
        const lx = (B0 + (FN ? F1 : B1)) / 2, ly = boards.length ? 1.55 : 1.15;
        cam.position.set(lx, ly + d * Math.sin(el), ZB + d * Math.cos(el));
        cam.lookAt(lx, ly, ZB);
        cam.setViewOffset(w, h, w / 2 - mid, far ? -h * 0.05 : 0, w, h);
        cam.updateProjectionMatrix();
      },
      project(x, y, hgt = 0.5) {
        const p = x === 'fn' ? new THREE.Vector3((F0 + F1) / 2, TOP + 1.1, ZB) : new THREE.Vector3(x, hgt, y);
        const v = p.project(cam);
        return { x: (v.x + 1) / 2 * size.w, y: (1 - v.y) / 2 * size.h };
      },
      dispose() {
        cancelAnimationFrame(raf);
        for (const [, cr] of crates) { if (cr.tok) disposeObj(cr.tok); disposeObj(cr); }
        dying.forEach(disposeObj);
        geos.forEach(g => g.dispose()); mats.forEach(m => m.dispose()); texs.forEach(t => t.dispose());
        renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove();
      },
    };
  }

  /* ── без WebGL: полка из карточек ── */
  function labFlat(host, lv) {
    const el = document.createElement('div'); el.className = 'ws-flat'; host.appendChild(el);
    const esc = UI.esc;
    const card = c => `<div class="ws-box"><span class="v ${c.t}">${c.t === 'list' ? c.items.map((x, i) => `<i>${esc(x)}<small>${i}</small></i>`).join('') + (c.more ? '<i>…</i>' : '') : esc(c.s)}</span><b>${esc(c.name)}</b></div>`;
    return {
      sync(w) {
        el.innerHTML = `<div class="ws-shelf">${w.mem.map(card).join('') || '<p>Полка пуста</p>'}</div>`
          + (w.frame ? `<div class="ws-shelf fn"><h5>внутри ${esc(w.frame.name)}()</h5>${w.frame.mem.map(card).join('')}</div>` : '')
          + `<div class="ws-side">${w.lamp ? `<div class="ws-lamp ${w.lamp.ok ? 'on' : 'off'}">${esc(w.lamp.src)} → ${w.lamp.ok ? 'True' : 'False'}</div>` : ''}${w.loop ? `<div class="ws-loop">круг ${w.loop.n}</div>` : ''}${w.screen.length ? `<pre class="ws-scr">${esc(w.screen.join('\n'))}</pre>` : ''}</div>`;
      },
      fit() { }, project() { const r = el.getBoundingClientRect(), p = host.getBoundingClientRect(); return { x: r.left - p.left + r.width / 2, y: r.top - p.top }; },
      dispose() { el.remove(); },
    };
  }

  /* ── описание игры для общего экрана (StacklyFarm.mount) ── */
  const HUD_ICON = {
    box: '<svg viewBox="0 0 24 24" width="32" height="32" aria-hidden="true"><path d="M3 9h18v11H3z" fill="#C79A63"/><path d="M3 9h18v3H3z" fill="#9E7448"/><rect x="7" y="14" width="10" height="3.5" rx="1" fill="#F7F3EA"/><circle cx="12" cy="7" r="4.5" fill="#2F6FD6"/></svg>',
    loop: '<svg viewBox="0 0 24 24" width="32" height="32" aria-hidden="true"><circle cx="12" cy="12" r="7.5" fill="none" stroke="#FFD166" stroke-width="2.6"/><path d="m16.5 3.5 3 3.2-4 1.3z" fill="#E8762B"/><circle cx="12" cy="4.5" r="1.8" fill="#E8762B"/><circle cx="12" cy="19.5" r="1.8" fill="#E8762B"/></svg>',
    fn: '<svg viewBox="0 0 24 24" width="32" height="32" aria-hidden="true"><rect x="2" y="9" width="20" height="4" rx="1" fill="#2E7D52"/><path d="M4 13v8M20 13v8" stroke="#7A5232" stroke-width="2.4"/><rect x="5" y="2.5" width="14" height="5" rx="1" fill="#1F5C3F"/></svg>',
  };
  const CSS = `
.ws-flat { position: absolute; inset: 60px 16px 16px; display: flex; flex-wrap: wrap; align-content: center; justify-content: center; gap: 14px; font: 600 13px/1.4 var(--f-body); }
.ws-shelf { display: flex; flex-wrap: wrap; gap: 8px; padding: 12px; border-radius: 8px; background: #A9774A; }
.ws-shelf.fn { background: #2E7D52; } .ws-shelf h5 { flex-basis: 100%; margin: 0; color: #fff; font: inherit; } .ws-shelf p { margin: 0; color: #fff; }
.ws-box { display: grid; justify-items: center; gap: 4px; min-width: 64px; padding: 8px; border-radius: 6px; background: #C79A63; }
.ws-box b { padding: 1px 8px; border-radius: 4px; background: #F7F3EA; color: #20232A; font: 600 12px var(--f-mono); }
.ws-box .v { display: flex; min-width: 40px; min-height: 30px; align-items: center; justify-content: center; padding: 2px 8px; border-radius: 15px; background: #8C96A3; color: #fff; font: 700 13px var(--f-mono); }
.ws-box .v.int { background: #2F6FD6; } .ws-box .v.float { background: #7A4FD0; } .ws-box .v.str { border-radius: 3px; background: #F2C14E; color: #3A2A05; }
.ws-box .v.bool { border-radius: 3px; background: #2E9E5B; } .ws-box .v.list { gap: 3px; border-radius: 3px; background: #F4F1E8; color: #20232A; }
.ws-box .v.list i { display: grid; justify-items: center; min-width: 22px; font-style: normal; } .ws-box .v.list small { color: #6B7380; font-size: 10px; }
.ws-side { display: grid; gap: 8px; } .ws-lamp, .ws-loop, .ws-scr { margin: 0; padding: 6px 10px; border-radius: 6px; background: #20232A; color: #fff; font: 600 13px var(--f-mono); }
.ws-lamp.on { box-shadow: inset 4px 0 #2EE06F; } .ws-lamp.off { box-shadow: inset 4px 0 #FF3B2E; } .ws-scr { color: #8CFFB4; background: #0E1A14; }
`;
  const UIX = {
    key: 'vars', route: 'vars', title: 'Мастерская переменных', actor: 'робот', loading: 'Открываем мастерскую…', cmdTitle: 'Что вы уже знаете', winTitle: 'Всё разложено по ящикам!',
    stepTitle: 'Выполнить один шаг программы', turn: 'Шаг', unit: ['шаг', 'шага', 'шагов'], speed: 0,
    limitMsg: lv => `Программа сделала уже ${lv.limit} шагов и не закончилась. Похоже, цикл никогда не останавливается: проверьте, что условие while когда-нибудь станет False или что в цикле есть break.`,
    levels: LEVELS, chapters: CHAPTERS, order: ORDER, numOf, core: CORE, scene: labScene, flat: labFlat,
    doc: DOC, cdoc: {}, cmds: [], ns: {}, nsDoc: {},
    seedFor: () => Math.floor(Math.random() * 1e9), newSeed: () => Math.floor(Math.random() * 1e9),
    helpNote: '<p>Каждая строка программы — один шаг: робот кладёт значения в ящики, лампа показывает ответ условия, счётчик — круг цикла. Кнопка «шаг» выполняет программу по одной строке — так удобнее всего разбираться. Данные в ящиках при каждом запуске новые: программа должна работать для любых.</p>',
    intro: ctx => `Мастерская показывает программу изнутри: переменные — ящики на полке, значения — жетоны в них. Для тех, кто начинает с нуля: переменные, типы, условия, циклы, списки и функции. За первое прохождение уровня — ${ctx.points || 10} баллов.`,
    goalHTML: lv => `<div class="fg-want"><span>Цель:</span>${lv.task}</div>`,
    hud(w) {
      const out = [['box', `Ящиков на полке: ${w.mem.length}`, w.mem.length]];
      if (w.loop) out.push(['loop', `Круг цикла: ${w.loop.n}`, w.loop.n]);
      if (w.frame) out.push(['fn', `Работает функция ${w.frame.name}()`, w.frame.name + '()']);
      return out.map(([k, t, n]) => `<div title="${UI.esc(t)}">${HUD_ICON[k]}<span>${UI.esc(String(n))}</span></div>`).join('');
    },
    goalBars: null,
    fly: ev => ev.a === 'ret' ? { x: 'fn', y: 0, h: 0, html: `вернула <b>${UI.esc(ev.v)}</b>` } : null,
    tags: () => [], retag: () => false,
  };
  if (!document.getElementById('ws-css')) { const st = document.createElement('style'); st.id = 'ws-css'; st.textContent = CSS; document.head.appendChild(st); }
  root.StacklyWorkshop = { ...api, game: UIX };
})(typeof window !== 'undefined' ? window : globalThis, typeof module !== 'undefined' && module.exports ? require('./farm.js') : window.StacklyFarm);
