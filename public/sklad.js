/* stackly · Склад: робот-погрузчик под управлением Python раскладывает коробки с конвейера по стеллажам.
   Интерпретатор, редактор, окна и прогресс — общие с фермой (farm.js, StacklyFarm); здесь мир склада, команды робота,
   уровни и 3D-сцена. Логика работает и в node — её проверяет tests/sklad_check.js. */
(function (root, F) {
  'use strict';
  const { Const, NS, E, needArgs, rng32, Dirs, DIRS, outLines } = F;

  /* ═════════════ МИР СКЛАДА ═════════════
     Клетки ряда: I — конвейер (очередь коробок, берут первую), S — стеллаж (стопка, берут верхнюю), O — зона отгрузки,
     . — пол. Коробка: { id, n — число на ней, color }. Робот ездит по ряду и держит одну коробку */
  const COLORS = { Red: ['красная', '#D8483B', 'красную'], Blue: ['синяя', '#2F6FD6', 'синюю'], Green: ['зелёная', '#2E9E5B', 'зелёную'], Yellow: ['жёлтая', '#E8B322', 'жёлтую'] };
  const ColorC = Object.fromEntries(Object.keys(COLORS).map(k => [k, new Const('Colors', k, COLORS[k][0])]));
  const boxName = b => (b.color ? COLORS[b.color][0] + ' ' : '') + 'коробка «' + b.n + '»';
  const boxAcc = b => (b.color ? COLORS[b.color][2] + ' ' : '') + 'коробку «' + b.n + '»';

  class Sklad {
    constructor(lv, seed) {
      this.lv = lv; this.w = lv.layout.length; this.h = 1; this.t = 0; this.rng = rng32(seed);
      this.x = lv.robot || 0; this.y = 0; this.hold = null; this.items = {}; this.nextId = 1;
      this.cells = [...lv.layout].map(ch => ({ kind: { I: 'in', S: 'shelf', O: 'out' }[ch] || 'floor', stack: [], cap: ch === 'S' ? lv.cap || 6 : ch === 'O' ? 99 : 0 }));
      const r = rng32(seed * 31 + 7);
      if (lv.boxes) { const inC = this.cells.find(c => c.kind === 'in'); for (const b of lv.boxes(r)) inC.stack.push(this.box(b)); }
      if (lv.fill) lv.fill(this, r);
      this.initial = this.cells.map(c => c.stack.map(b => ({ ...b })));
    }
    box(b) { return { id: this.nextId++, n: b.n, color: b.color || null }; }
    cell(x = this.x) { return this.cells[x]; }
    left() { return this.cells.filter(c => c.kind === 'in').reduce((a, c) => a + c.stack.length, 0); }
    all() { return this.initial.flat(); }
    done() { return false; }                                   // склад проверяется, когда программа закончилась
  }

  /* ── команды робота: move, take, put — один ход; всё, что «посмотреть», — бесплатно ── */
  const CMDS = ['move', 'take', 'put', 'has_box', 'box_number', 'box_color', 'boxes_left', 'count', 'top_number', 'conveyor', 'get_pos_x', 'get_world_size'];
  function install(ip, w, lv, run) {
    for (const [k, v] of Object.entries(Dirs)) ip.builtins.set(k, v);
    ip.builtins.set('Colors', new NS('Colors', ColorC));
    const act = (a, extra) => { ip.lastAct = ip.ops; w.t++; return { a, x: w.x, y: 0, ...extra }; };
    const needHold = name => { if (!w.hold) throw E('RuntimeError', `${name}(): робот ничего не держит — сначала возьмите коробку: take()`); };
    const impl = {
      *move(args) {
        needArgs('move', args, 1);
        const d = args[0];
        if (!(d instanceof Const) || d.group !== 'Direction') throw E('TypeError', 'move() ждёт направление: East, West, North или South');
        const nx = w.x + DIRS[d.name][0];
        if (DIRS[d.name][1] !== 0 || nx < 0 || nx >= w.w) {
          run.note('wall', 'Робот упёрся в стену: склад — один ряд, ездить можно только вправо (East) и влево (West)');
          yield act('bump', { dir: d.name });
          return false;
        }
        w.x = nx;
        yield act('move', { dir: d.name });
        return true;
      },
      *take(args) {
        needArgs('take', args, 0);
        if (w.hold) throw E('RuntimeError', 'take(): робот уже держит коробку — сначала поставьте её: put()');
        const c = w.cell();
        if (c.kind === 'floor' || c.kind === 'out' || !c.stack.length) {
          run.note('empty', c.kind === 'out' ? 'Из зоны отгрузки коробки не забирают' : 'Здесь нечего брать: коробки ждут на конвейере и стоят на стеллажах');
          yield act('take', { ok: false });
          return false;
        }
        w.hold = c.kind === 'in' ? c.stack.shift() : c.stack.pop();
        yield act('take', { ok: true, box: w.hold.id });
        return true;
      },
      *put(args) {
        needArgs('put', args, 0);
        needHold('put');
        const c = w.cell();
        if (c.kind === 'floor') throw E('RuntimeError', `put(): здесь (x = ${w.x}) пустой пол — ставить можно только на стеллаж или в зону отгрузки`);
        if (c.kind === 'in') throw E('RuntimeError', 'put(): на конвейер коробки не возвращают');
        if (c.stack.length >= c.cap) throw E('RuntimeError', `put(): стеллаж x = ${w.x} заполнен — на нём уже ${c.cap} ${c.cap < 5 ? 'коробки' : 'коробок'}`);
        c.stack.push(w.hold); w.hold = null;
        yield act('put', { ok: true });
        return null;
      },
      has_box(args) { needArgs('has_box', args, 0); return !!w.hold; },
      box_number(args) { needArgs('box_number', args, 0); needHold('box_number'); return w.hold.n; },
      box_color(args) { needArgs('box_color', args, 0); needHold('box_color'); return w.hold.color ? ColorC[w.hold.color] : null; },
      boxes_left(args) { needArgs('boxes_left', args, 0); return w.left(); },
      count(args) { needArgs('count', args, 0); return w.cell().stack.length; },
      top_number(args) {
        needArgs('top_number', args, 0);
        const c = w.cell(), b = c.kind === 'in' ? c.stack[0] : c.stack[c.stack.length - 1];
        return b ? b.n : null;
      },
      conveyor(args) { needArgs('conveyor', args, 0); return w.cells.filter(c => c.kind === 'in').flatMap(c => c.stack.map(b => b.n)); },
      get_pos_x(args) { needArgs('get_pos_x', args, 0); return w.x; },
      get_world_size(args) { needArgs('get_world_size', args, 0); return w.w; },
    };
    const gen = new Set(['move', 'take', 'put']);
    for (const name of CMDS) {
      if (lv.api.includes(name)) { ip.def(name, impl[name], gen.has(name)); continue; }
      const at = ORDER.map(id => LEVELS.find(l => l.id === id)).find(l => l.api.includes(name));
      ip.def(name, () => { throw E('NameError', `команда ${name}() откроется ${at ? 'на уровне ' + at.num : 'позже'}`); });
    }
  }

  /* ── проверки: что не так на складе — понятными фразами ── */
  const where = (w, x) => { const c = w.cells[x]; return c.kind === 'out' ? 'в зоне отгрузки' : `на стеллаже x = ${x}`; };
  function common(w) {
    const m = [];
    if (w.hold) m.push(`Робот всё ещё держит ${boxAcc(w.hold)} — поставьте её.`);
    if (w.left()) { const n = w.left(); m.push(`На конвейере ${n % 10 === 1 && n % 100 !== 11 ? 'осталась' : 'осталось'} ${n} ${n % 10 === 1 && n % 100 !== 11 ? 'коробка' : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? 'коробки' : 'коробок'}.`); }
    return m;
  }
  // каждая коробка должна стоять там, куда её отправляет rule(b) (номер клетки)
  function placed(rule) {
    return run => {
      const w = run.world, m = common(w);
      if (m.length) return m;
      for (let x = 0; x < w.w; x++) for (const b of w.cells[x].stack) {
        const want = rule(b, w);
        if (want !== x) return [`${boxName(b)[0].toUpperCase() + boxName(b).slice(1)} стоит ${where(w, x)}, а должна — ${where(w, want)}.`];
      }
      return [];
    };
  }
  // стеллажи xs: по одной коробке, числа растут слева направо
  function sortedRow(xs) {
    return run => {
      const w = run.world, m = common(w);
      if (m.length) return m;
      const row = xs.map(x => w.cells[x].stack);
      if (row.some(s => s.length !== 1)) { const x = xs[row.findIndex(s => s.length !== 1)]; return [`На стеллаже x = ${x} должна стоять ровно одна коробка, а там ${w.cells[x].stack.length}.`]; }
      for (let i = 1; i < row.length; i++) if (row[i][0].n < row[i - 1][0].n) return [`Не по порядку: на x = ${xs[i - 1]} число ${row[i - 1][0].n}, а правее, на x = ${xs[i]}, — ${row[i][0].n}. Числа должны расти слева направо.`];
      return [];
    };
  }
  const ri = (r, a, b) => a + Math.floor(r() * (b - a + 1));
  const pickC = (r, cs) => cs[Math.floor(r() * cs.length)];
  const uniq = (r, k, a, b) => { const s = new Set(); while (s.size < k) s.add(ri(r, a, b)); return [...s]; };
  const GOTO = 'def go_to(x):\n    while get_pos_x() < x:\n        move(East)\n    while get_pos_x() > x:\n        move(West)\n';

  /* ═════════════ УРОВНИ ═════════════ id с 101: прогресс и баллы общие с фермой */
  const LEVELS = [
    {
      id: 101, title: 'Первая коробка', concept: 'команды робота', layout: 'I..S', cap: 4, limit: 50, par: 5, api: ['move', 'take', 'put'],
      boxes: r => [{ n: ri(r, 2, 9) }],
      check: placed(() => 3), goal: 'Коробка с конвейера — на стеллаже справа (x = 3).',
      text: 'Это склад. Робот-погрузчик стоит у конвейера (слева). Возьмите коробку командой <code>take()</code>, довезите её до стеллажа справа — три раза <code>move(East)</code> — и поставьте: <code>put()</code>.',
      learn: ['Команды робота', 'take()\nmove(East)\nput()', 'Робот выполняет команды по порядку, сверху вниз. <code>take()</code> — поднять коробку там, где он стоит; <code>put()</code> — поставить. Если брать нечего или ставить некуда, программа остановится и объяснит почему.'],
      start: 'take()\n# довезите коробку до стеллажа и поставьте\n',
      hint: 'Пять строк: <code>take()</code>, три раза <code>move(East)</code>, <code>put()</code>',
      solution: 'take()\nmove(East)\nmove(East)\nmove(East)\nput()\n',
    },
    {
      id: 102, title: 'Туда и обратно', concept: 'длинная последовательность', layout: 'I..S', cap: 4, limit: 80, par: 13, api: ['move', 'take', 'put'],
      boxes: r => [{ n: ri(r, 2, 9) }, { n: ri(r, 2, 9) }],
      check: placed(() => 3), goal: 'Обе коробки — на стеллаже x = 3.',
      text: 'Теперь коробок две. Отвезите первую, вернитесь к конвейеру — <code>move(West)</code> — и отвезите вторую. Программа выйдет длинной: скоро вы научитесь писать её короче.',
      learn: ['Направления', 'move(East)   # вправо\nmove(West)   # влево', '<code>East</code> — восток, вправо; <code>West</code> — запад, влево. Склад — один ряд, поэтому <code>North</code> и <code>South</code> упрутся в стену.'],
      start: 'take()\nmove(East)\nmove(East)\nmove(East)\nput()\n# вернитесь за второй коробкой\n',
      hint: 'После <code>put()</code>: три раза <code>move(West)</code>, затем повторите первые пять строк',
      solution: 'take()\nmove(East)\nmove(East)\nmove(East)\nput()\nmove(West)\nmove(West)\nmove(West)\ntake()\nmove(East)\nmove(East)\nmove(East)\nput()\n',
    },
    {
      id: 103, title: 'Пять коробок', concept: 'цикл for', layout: 'I..S', cap: 5, limit: 200, par: 40, api: ['move', 'take', 'put'],
      boxes: r => Array.from({ length: 5 }, () => ({ n: ri(r, 2, 9) })),
      check: placed(() => 3), codeHas: [[/\bfor\b/, 'Решите с циклом for — вручную вышло бы 40 строк.']], goal: 'Все пять коробок — на стеллаже x = 3.',
      text: 'Пять коробок. Повторять одно и то же умеет цикл: напишите команды для одной коробки один раз, а Python повторит их пять раз.',
      learn: ['Цикл for', 'for i in range(5):\n    take()\n    # туда\n    put()\n    # обратно', '<code>for i in range(5):</code> — «повтори 5 раз». Повторяемые команды пишут ниже с отступом в 4 пробела (клавиша Tab). Цикл можно вложить в цикл: <code>for j in range(3): move(East)</code> — три шага вправо.'],
      start: 'for i in range(5):\n    take()\n    for j in range(3):\n        move(East)\n    put()\n',
      hint: 'После <code>put()</code>, с тем же отступом: ещё один цикл <code>for j in range(3):</code> с <code>move(West)</code> — назад к конвейеру',
      solution: 'for i in range(5):\n    take()\n    for j in range(3):\n        move(East)\n    put()\n    for j in range(3):\n        move(West)\n',
    },
    {
      id: 104, title: 'Пока есть коробки', concept: 'while с условием', layout: 'I...S', cap: 9, limit: 300, api: ['move', 'take', 'put', 'boxes_left'],
      boxes: r => Array.from({ length: ri(r, 3, 8) }, () => ({ n: ri(r, 2, 9) })),
      check: placed(() => 4), codeHas: [[/\bwhile\b/, 'Нужен цикл while: сколько коробок придёт, заранее неизвестно.']], goal: 'Все коробки — на стеллаже x = 4. Сколько их будет, заранее неизвестно.',
      text: 'Сколько коробок придёт, заранее неизвестно — при каждом запуске по-разному. <code>boxes_left()</code> говорит, сколько ещё ждёт на конвейере. Работайте, пока они есть.',
      learn: ['while с условием', 'while boxes_left() > 0:\n    take()\n    # отвезти и вернуться', '<code>while условие:</code> — «повторяй, пока условие верно». Перед каждым повтором Python проверяет его заново; когда коробок не осталось, цикл заканчивается. <code>&gt;</code> — «больше».'],
      start: 'for i in range(5):\n    take()\n    for j in range(4):\n        move(East)\n    put()\n    for j in range(4):\n        move(West)\n',
      hint: 'Замените первую строку на <code>while boxes_left() &gt; 0:</code>',
      solution: 'while boxes_left() > 0:\n    take()\n    for j in range(4):\n        move(East)\n    put()\n    for j in range(4):\n        move(West)\n',
    },
    {
      id: 105, title: 'По цветам', concept: 'if / else и ==', layout: 'I.S.S', cap: 8, limit: 300, api: ['move', 'take', 'put', 'boxes_left', 'box_color'],
      shelfColor: { 2: 'Blue', 4: 'Red' },
      boxes: r => { const b = Array.from({ length: 6 }, () => ({ n: ri(r, 2, 9), color: pickC(r, ['Red', 'Blue']) })); b[0].color = 'Red'; b[1].color = 'Blue'; return b; },
      check: placed(b => b.color === 'Red' ? 4 : 2), goal: 'Красные коробки — на красный стеллаж (x = 4), синие — на синий (x = 2).',
      text: 'Коробки бывают красные и синие. <code>box_color()</code> говорит цвет коробки, которую держит робот. Красные везите на дальний красный стеллаж, синие — на ближний синий.',
      learn: ['if / else и ==', 'if box_color() == Colors.Red:\n    # к красному стеллажу\nelse:\n    # к синему', '<code>==</code> — «равно?» (два знака; один <code>=</code> кладёт значение в переменную). <code>Colors.Red</code> — красный, <code>Colors.Blue</code> — синий. Ветка <code>else</code> («иначе») выполняется, когда условие ложно.'],
      start: 'while boxes_left() > 0:\n    take()\n    if box_color() == Colors.Red:\n        pass   # к красному стеллажу (x = 4) и обратно\n    else:\n        pass   # к синему стеллажу (x = 2) и обратно\n',
      hint: 'Вместо первого <code>pass</code>: 4 шага вправо, <code>put()</code>, 4 шага влево. Вместо второго — то же, но по 2 шага',
      solution: 'while boxes_left() > 0:\n    take()\n    if box_color() == Colors.Red:\n        for j in range(4):\n            move(East)\n        put()\n        for j in range(4):\n            move(West)\n    else:\n        for j in range(2):\n            move(East)\n        put()\n        for j in range(2):\n            move(West)\n',
    },
    {
      id: 106, title: 'Тяжёлые и лёгкие', concept: 'сравнения < >', layout: 'IS.S', cap: 8, limit: 300, api: ['move', 'take', 'put', 'boxes_left', 'box_number'],
      captions: { 1: 'до 10 кг', 3: 'больше 10 кг' },
      boxes: r => { const b = Array.from({ length: 7 }, () => ({ n: ri(r, 1, 20) })); b[0].n = ri(r, 11, 20); b[1].n = ri(r, 1, 10); return b; },
      check: placed(b => b.n > 10 ? 3 : 1), goal: 'Коробки тяжелее 10 кг — на дальний стеллаж (x = 3), остальные — на ближний (x = 1).',
      text: 'Число на коробке — её вес в килограммах, <code>box_number()</code> его возвращает. Тяжёлые (больше 10 кг) везите на дальний стеллаж, лёгкие — на ближний.',
      learn: ['Сравнения', 'w = box_number()\nif w > 10:\n    # тяжёлая\nelse:\n    # лёгкая', 'Сравнения: <code>&gt;</code> больше, <code>&lt;</code> меньше, <code>&gt;=</code> больше или равно, <code>&lt;=</code> меньше или равно, <code>!=</code> не равно. Число удобно сначала положить в переменную: <code>w = box_number()</code>.'],
      start: 'while boxes_left() > 0:\n    take()\n    w = box_number()\n    # тяжёлая — на x = 3, лёгкая — на x = 1\n',
      hint: '<code>if w &gt; 10:</code> → 3 шага вправо, <code>put()</code>, 3 влево; <code>else:</code> → 1 шаг вправо, <code>put()</code>, 1 влево',
      solution: 'while boxes_left() > 0:\n    take()\n    w = box_number()\n    if w > 10:\n        for j in range(3):\n            move(East)\n        put()\n        for j in range(3):\n            move(West)\n    else:\n        move(East)\n        put()\n        move(West)\n',
    },
    {
      id: 107, title: 'Вес партии', concept: 'переменная-накопитель', layout: 'I..O', limit: 300, api: ['move', 'take', 'put', 'boxes_left', 'box_number'],
      boxes: r => Array.from({ length: ri(r, 4, 7) }, () => ({ n: ri(r, 3, 25) })),
      check: run => {
        const m = placed(() => 3)(run);
        if (m.length) return m;
        const total = String(run.world.all().reduce((a, b) => a + b.n, 0)), got = run.out.some(o => o.k === 'out') ? outLines(run.out) : [];
        return got.length === 1 && got[0].trim() === total ? [] : [`В журнале должен быть общий вес партии — одно число. А программа вывела: ${got.length ? got.map(x => '«' + x + '»').join(', ') : 'ничего'}.`];
      },
      goal: 'Все коробки — в зоне отгрузки (x = 3), а в журнале — общий вес партии.',
      text: 'Отгрузите всю партию в зону отгрузки справа и посчитайте её общий вес: перед отправкой каждой коробки прибавляйте её вес к переменной. В конце выведите его через <code>print()</code>.',
      learn: ['Переменная-накопитель', 'total = 0\ntotal = total + box_number()\nprint(total)', 'Переменная — коробка с именем. <code>total = total + box_number()</code>: Python берёт старое значение, прибавляет вес и кладёт обратно. Начинать нужно с <code>total = 0</code> — до цикла, иначе сумма будет обнуляться.'],
      start: 'total = 0\nwhile boxes_left() > 0:\n    take()\n    for j in range(3):\n        move(East)\n    put()\n    for j in range(3):\n        move(West)\n',
      hint: 'Сразу после <code>take()</code>: <code>total = total + box_number()</code>. После цикла, без отступа: <code>print(total)</code>',
      solution: 'total = 0\nwhile boxes_left() > 0:\n    take()\n    total = total + box_number()\n    for j in range(3):\n        move(East)\n    put()\n    for j in range(3):\n        move(West)\nprint(total)\n',
    },
    {
      id: 108, title: 'Адресная доставка', concept: 'своя функция с параметром', layout: 'ISSSSS', cap: 6, limit: 600, api: ['move', 'take', 'put', 'boxes_left', 'box_number', 'get_pos_x'],
      captions: { 1: '№1', 2: '№2', 3: '№3', 4: '№4', 5: '№5' },
      boxes: r => Array.from({ length: 7 }, () => ({ n: ri(r, 1, 5) })),
      check: placed(b => b.n), codeHas: [[/\bdef\b/, 'Опишите свою функцию def go_to(x) — так программа станет короче и понятнее.']], goal: 'Каждая коробка — на стеллаже со своим номером: коробка «3» — на x = 3.',
      text: 'Число на коробке — номер стеллажа, куда её везти. Двигаться «на сколько-то шагов» неудобно — напишите свою команду <code>go_to(x)</code>: «доехать до столбца x». Тогда доставка — это <code>go_to(box_number())</code>.',
      learn: ['Своя функция', GOTO + '\ngo_to(3)    # доехать до x = 3', '<code>def</code> создаёт новую команду. В скобках — параметр: значение, которое передают при вызове (<code>go_to(3)</code> — x будет 3). <code>get_pos_x()</code> — где сейчас робот. Тело функции пишут с отступом.'],
      start: GOTO + '\nwhile boxes_left() > 0:\n    go_to(0)\n    take()\n    # отвезите коробку на стеллаж с её номером\n',
      hint: 'После <code>take()</code>: <code>go_to(box_number())</code> и <code>put()</code>',
      solution: GOTO + '\nwhile boxes_left() > 0:\n    go_to(0)\n    take()\n    go_to(box_number())\n    put()\n',
    },
    {
      id: 109, title: 'По порядку', concept: 'списки: sorted, index', layout: 'ISSSSSS', cap: 1, limit: 600, api: ['move', 'take', 'put', 'boxes_left', 'box_number', 'get_pos_x', 'conveyor'],
      boxes: r => uniq(r, 6, 1, 60).map(n => ({ n })),
      check: sortedRow([1, 2, 3, 4, 5, 6]), goal: 'На стеллажах x = 1…6 по одной коробке, числа растут слева направо.',
      text: 'Шесть коробок с разными числами и шесть мест. Расставьте коробки так, чтобы числа росли слева направо. <code>conveyor()</code> возвращает список чисел всех коробок на конвейере — отсортируйте его, и место каждой коробки станет известно.',
      learn: ['Список', 'nums = conveyor()        # например [17, 4, 32]\norder = sorted(nums)     # [4, 17, 32]\nprint(order.index(17))   # 1 — место числа 17', 'Список хранит много значений по порядку: <code>[17, 4, 32]</code>. <code>sorted()</code> возвращает новый список, отсортированный по возрастанию. <code>order.index(x)</code> — номер места числа x, счёт с нуля.'],
      start: GOTO + '\norder = sorted(conveyor())\nprint(order)\nwhile boxes_left() > 0:\n    go_to(0)\n    take()\n    # на какое место везти эту коробку?\n',
      hint: 'Место коробки — <code>order.index(box_number()) + 1</code> (стеллажи начинаются с x = 1): <code>go_to(...)</code>, затем <code>put()</code>',
      solution: GOTO + '\norder = sorted(conveyor())\nwhile boxes_left() > 0:\n    go_to(0)\n    take()\n    go_to(order.index(box_number()) + 1)\n    put()\n',
    },
    {
      id: 110, title: 'Пузырёк', concept: 'вложенные циклы, сортировка обменом', layout: 'SSSSSS', cap: 1, robot: 0, limit: 3000, api: ['move', 'take', 'put', 'box_number', 'get_pos_x', 'top_number'],
      captions: { 0: 'буфер' },
      fill: (w, r) => { let ns; do ns = uniq(r, 5, 1, 60); while (ns.every((n, i) => !i || n > ns[i - 1])); ns.forEach((n, i) => w.cells[i + 1].stack.push(w.box({ n }))); },
      check: run => { const m = sortedRow([1, 2, 3, 4, 5])(run); if (m.length) return m; return run.world.cells[0].stack.length ? ['Буфер (x = 0) должен остаться пустым.'] : []; },
      goal: 'Числа на стеллажах x = 1…5 растут слева направо, буфер x = 0 пуст.',
      text: 'Коробки уже на стеллажах, но вперемешку. Отсортируйте их «пузырьком»: сравнивайте соседей и меняйте местами, если левая больше правой. Чтобы поменять две коробки, нужен пустой буфер (x = 0). <code>top_number()</code> — число коробки под роботом, брать её не нужно.',
      learn: ['Сортировка пузырьком', 'for k in range(4):\n    for i in range(1, 5 - k):\n        # сравнить коробки на i и i + 1,\n        # поменять, если левая больше', 'Каждый проход внешнего цикла «выталкивает» самую большую из оставшихся коробок вправо, как пузырёк. Поэтому внутренний цикл с каждым проходом короче. Обмен через буфер: левую — в буфер, правую — на место левой, из буфера — направо.'],
      start: GOTO + '\ndef swap(i, j):\n    go_to(i)\n    take()\n    go_to(0)\n    put()\n    # дальше: правую — на место левой, из буфера — на место правой\n\nfor k in range(4):\n    for i in range(1, 5 - k):\n        go_to(i)\n        a = top_number()\n        go_to(i + 1)\n        b = top_number()\n        if a > b:\n            swap(i, i + 1)\n',
      hint: 'В <code>swap</code> после первых четырёх строк: <code>go_to(j)</code>, <code>take()</code>, <code>go_to(i)</code>, <code>put()</code>, <code>go_to(0)</code>, <code>take()</code>, <code>go_to(j)</code>, <code>put()</code>',
      solution: GOTO + '\ndef swap(i, j):\n    go_to(i)\n    take()\n    go_to(0)\n    put()\n    go_to(j)\n    take()\n    go_to(i)\n    put()\n    go_to(0)\n    take()\n    go_to(j)\n    put()\n\nfor k in range(4):\n    for i in range(1, 5 - k):\n        go_to(i)\n        a = top_number()\n        go_to(i + 1)\n        b = top_number()\n        if a > b:\n            swap(i, i + 1)\n',
    },
  ];
  const CHAPTERS = [
    { id: 1, title: 'Первые команды', levels: [101, 102] },
    { id: 2, title: 'Циклы', levels: [103, 104] },
    { id: 3, title: 'Условия', levels: [105, 106] },
    { id: 4, title: 'Переменные и функции', levels: [107, 108] },
    { id: 5, title: 'Списки и сортировка', levels: [109, 110] },
  ];
  const ORDER = CHAPTERS.flatMap(c => c.levels);
  LEVELS.forEach(l => { const i = ORDER.indexOf(l.id); l.num = i + 1; l.need = i > 0 ? ORDER[i - 1] : 0; l.w = l.layout.length; l.h = 1; l.py = []; });
  const numOf = id => ORDER.indexOf(id) + 1;
  const CORE = { world: (lv, seed) => new Sklad(lv, seed), install, misses: () => [] };
  const DOC = {
    move: ['move(East)', 'проехать на соседнюю клетку: <code>East</code> — вправо, <code>West</code> — влево'],
    take: ['take()', 'взять коробку: с конвейера — первую, со стеллажа — верхнюю'],
    put: ['put()', 'поставить коробку на стеллаж или в зону отгрузки'],
    has_box: ['has_box()', '<code>True</code>, если робот держит коробку'],
    box_number: ['box_number()', 'число на коробке в руках робота'],
    box_color: ['box_color()', 'цвет коробки в руках: <code>Colors.Red</code>, <code>Colors.Blue</code>…'],
    boxes_left: ['boxes_left()', 'сколько коробок ещё ждёт на конвейере'],
    count: ['count()', 'сколько коробок на клетке под роботом'],
    top_number: ['top_number()', 'число верхней коробки на клетке под роботом или <code>None</code>'],
    conveyor: ['conveyor()', 'список чисел коробок на конвейере, по порядку'],
    get_pos_x: ['get_pos_x()', 'номер клетки, где стоит робот (слева 0)'],
    get_world_size: ['get_world_size()', 'длина склада в клетках'],
  };
  const CDOC = Object.fromEntries(Object.entries(DOC).map(([k, v]) => [k, [v[0].replace(/\(.+\)/, k === 'move' ? '(направление)' : '()'), v[1]]]));
  function simulate(lv, code, opt = {}) { return F.simulate(lv, code, { ...opt, game: CORE }); }
  const api = { LEVELS, CHAPTERS, ORDER, CORE, Sklad, simulate, COLORS };
  if (typeof module !== 'undefined' && module.exports) { module.exports = api; return; }

  /* ═════════════ 3D: цех, конвейер, стеллажи, робот-погрузчик ═════════════
     Состояние мира → цели для каждой вещи; меши догоняют цели плавно (экспоненциальное сглаживание
     со временем шага), поэтому любое действие выглядит как непрерывное движение */
  const UI = F.ui;
  function skladScene(THREE, host, lv) {
    const W = lv.w, S = 1.3, LANE = 0.5, RACK = -0.32;          // клетка, полоса робота и линия стеллажей по z
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.1;
    host.appendChild(renderer.domElement);
    const scene = new THREE.Scene(), cam = new THREE.PerspectiveCamera(30, 1, 0.1, 300);
    const geos = [], mats = [], texs = [];
    const G = g => (geos.push(g), g);
    const M = (o) => { const m = new THREE.MeshStandardMaterial({ roughness: 0.75, metalness: 0.05, ...o }); mats.push(m); return m; };
    const cache = new Map(), C = (color, o = {}) => { const k = color + JSON.stringify(o); if (!cache.has(k)) cache.set(k, M({ color, ...o })); return cache.get(k); };
    const mesh = (geo, mat, x = 0, y = 0, z = 0) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = m.receiveShadow = true; return m; };
    const box = (w, h, d) => G(new THREE.BoxGeometry(w, h, d));
    const tex = (w, h, draw) => { const c = document.createElement('canvas'); c.width = w; c.height = h; draw(c.getContext('2d'), w, h); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; texs.push(t); return t; };
    const cx = x => (x - (W - 1) / 2) * S;
    const FW = W * S + 1.8, FD = 4.4;                          // пол цеха

    // свет: мягкий общий, тёплый ключевой с тенями, холодный заполняющий и лампы на стене
    scene.add(new THREE.HemisphereLight(0xe3ebf5, 0x3b4048, 1.15));
    const key = new THREE.DirectionalLight(0xfff0dc, 2.3), R = FW * 0.7;
    key.position.set(-R * 0.6, R * 1.6, R * 1.1); key.castShadow = true; key.shadow.mapSize.set(2048, 2048);
    Object.assign(key.shadow.camera, { left: -R, right: R, top: R, bottom: -R, near: 0.5, far: R * 6 });
    key.shadow.bias = -0.0004; key.shadow.normalBias = 0.02; key.shadow.radius = 5;
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xb9d0ff, 0.55); fill.position.set(R, R * 0.6, R); scene.add(fill);

    // пол: светлый бетон плитками, жёлтая полоса проезда робота, разметка зон
    const floorTex = tex(1024, Math.round(1024 * FD / FW), (g, w, h) => {
      const u = w / FW;
      g.fillStyle = '#BFC4CB'; g.fillRect(0, 0, w, h);
      for (let i = 0; i < 1800; i++) { g.fillStyle = `rgba(${Math.random() < 0.5 ? '255,255,255' : '60,66,76'},${Math.random() * 0.05})`; g.fillRect(Math.random() * w, Math.random() * h, 2 + Math.random() * 5, 2 + Math.random() * 5); }
      g.strokeStyle = 'rgba(70,78,90,.18)'; g.lineWidth = 2;
      for (let x = 0; x <= FW; x += 1.2) { g.beginPath(); g.moveTo(x * u, 0); g.lineTo(x * u, h); g.stroke(); }
      for (let z = 0; z <= FD; z += 1.2) { g.beginPath(); g.moveTo(0, z * u); g.lineTo(w, z * u); g.stroke(); }
      const zc = z => (z + FD / 2) * u, xc = x => (x + FW / 2) * u;
      g.fillStyle = '#E8B322'; g.fillRect(xc(cx(0) - S / 2), zc(LANE) - 0.05 * u, (W * S) * u, 0.035 * u); g.fillRect(xc(cx(0) - S / 2), zc(LANE) + 0.36 * u, (W * S) * u, 0.035 * u);
      lv.layout.split('').forEach((ch, x) => {
        const x0 = xc(cx(x) - S / 2 + 0.06), wd = (S - 0.12) * u, z0 = zc(RACK - 0.55), dp = 1.0 * u;
        if (ch === 'O') {
          g.fillStyle = 'rgba(46,158,91,.35)'; g.fillRect(x0, z0, wd, dp);
          g.strokeStyle = '#2E9E5B'; g.lineWidth = 6; g.strokeRect(x0, z0, wd, dp);
          g.fillStyle = 'rgba(255,255,255,.75)';
          for (let k = 0; k < 3; k++) { const yy = z0 + dp * (0.25 + k * 0.25); g.beginPath(); g.moveTo(x0 + wd * 0.3, yy); g.lineTo(x0 + wd * 0.5, yy - dp * 0.12); g.lineTo(x0 + wd * 0.7, yy); g.lineTo(x0 + wd * 0.7, yy + dp * 0.06); g.lineTo(x0 + wd * 0.5, yy - dp * 0.06); g.lineTo(x0 + wd * 0.3, yy + dp * 0.06); g.fill(); }
        }
        if (ch === 'S') { g.strokeStyle = '#E8B322'; g.lineWidth = 5; const L = 0.18 * u; for (const [ax, az, sx, sz] of [[x0, z0, 1, 1], [x0 + wd, z0, -1, 1], [x0, z0 + dp, 1, -1], [x0 + wd, z0 + dp, -1, -1]]) { g.beginPath(); g.moveTo(ax + sx * L, az); g.lineTo(ax, az); g.lineTo(ax, az + sz * L); g.stroke(); } }
      });
    });
    const floorMat = M({ map: floorTex, roughness: 0.55, metalness: 0.05 }), sideMat = C(0x3B4049, { roughness: 0.9 });
    const floor = mesh(box(FW, 0.3, FD), [sideMat, sideMat, floorMat, sideMat, sideMat, sideMat], 0, -0.15, 0.25);
    scene.add(floor);
    // жёлто-чёрная кромка пола
    const stripe = tex(256, 32, (g, w, h) => { g.fillStyle = '#E8B322'; g.fillRect(0, 0, w, h); g.fillStyle = '#20232A'; for (let x = -h; x < w; x += 32) { g.beginPath(); g.moveTo(x, h); g.lineTo(x + 16, h); g.lineTo(x + 16 + h, 0); g.lineTo(x + h, 0); g.fill(); } });
    stripe.wrapS = THREE.RepeatWrapping; stripe.repeat.set(FW * 2, 1);
    const edge = mesh(box(FW + 0.02, 0.08, 0.06), M({ map: stripe, roughness: 0.6 }), 0, -0.02, 0.25 + FD / 2); scene.add(edge);

    // задняя стена: профлист, окна под потолком, вывеска, лампы
    const wallZ = 0.25 - FD / 2 - 0.06, WH = 2.7;
    const ribs = tex(256, 64, (g, w, h) => { const gr = g.createLinearGradient(0, 0, 32, 0); gr.addColorStop(0, '#7D8B99'); gr.addColorStop(0.5, '#93A1AF'); gr.addColorStop(1, '#6E7C8A'); g.fillStyle = gr; for (let x = 0; x < w; x += 32) { g.save(); g.translate(x, 0); g.fillRect(0, 0, 32, h); g.restore(); } });
    ribs.wrapS = THREE.RepeatWrapping; ribs.repeat.set(FW * 1.6, 1);
    scene.add(mesh(box(FW, WH, 0.12), [C(0x5C6976), C(0x5C6976), C(0x5C6976), C(0x5C6976), M({ map: ribs, roughness: 0.5, metalness: 0.35 }), C(0x5C6976)], 0, WH / 2 - 0.3, wallZ));
    scene.add(mesh(box(FW + 0.1, 0.12, 0.2), C(0x2B3038), 0, WH - 0.3, wallZ + 0.04));
    const winMat = M({ color: 0xBFE3FF, emissive: 0x9FD2FF, emissiveIntensity: 0.9, roughness: 0.2 });
    for (let i = 0; i < Math.max(2, Math.round(FW / 2.2)); i++) {
      const n = Math.max(2, Math.round(FW / 2.2)), x = (i + 0.5) / n * FW - FW / 2;
      scene.add(mesh(box(1.1, 0.42, 0.04), C(0x2B3038), x, WH - 0.72, wallZ + 0.07));
      scene.add(mesh(box(1.0, 0.34, 0.04), winMat, x, WH - 0.72, wallZ + 0.09));
    }
    const signTex = tex(512, 128, (g, w, h) => { g.fillStyle = '#1F5C3F'; g.fillRect(0, 0, w, h); g.strokeStyle = '#F4F1E8'; g.lineWidth = 6; g.strokeRect(10, 10, w - 20, h - 20); g.fillStyle = '#F4F1E8'; g.font = 'bold 64px "Golos Text", "Segoe UI", sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('СКЛАД № 1', w / 2, h / 2 + 4); });
    scene.add(mesh(box(1.9, 0.48, 0.05), [C(0x1F5C3F), C(0x1F5C3F), C(0x1F5C3F), C(0x1F5C3F), M({ map: signTex, roughness: 0.6 }), C(0x1F5C3F)], -FW / 2 + 1.5, WH - 1.35, wallZ + 0.09));
    const lamps = [];
    for (const lx of [-FW / 4, FW / 4]) {
      const lamp = mesh(box(0.42, 0.08, 0.2), M({ color: 0x2B3038, emissive: 0xFFD9A0, emissiveIntensity: 1.6 }), lx, WH - 1.05, wallZ + 0.16);
      scene.add(lamp); lamps.push(lamp);
      const pl = new THREE.PointLight(0xFFCF8F, 6, 6, 1.6); pl.position.set(lx, WH - 1.2, wallZ + 0.5); scene.add(pl);
    }
    // боковая стена слева и декор: поддоны, бочки, конус
    scene.add(mesh(box(0.12, WH, FD), C(0x6E7C8A, { roughness: 0.55, metalness: 0.3 }), -FW / 2 - 0.06, WH / 2 - 0.3, 0.25));
    const pallet = (x, z, y = 0) => { const p = new THREE.Group(); p.position.set(x, y, z); for (const dz of [-0.28, 0, 0.28]) p.add(mesh(box(0.8, 0.05, 0.14), C(0xB98A55), 0, 0.12, dz)); for (const dx of [-0.32, 0, 0.32]) p.add(mesh(box(0.1, 0.1, 0.72), C(0xA17444), dx, 0.05, 0)); scene.add(p); return p; };
    pallet(FW / 2 - 0.6, wallZ + 0.6); pallet(FW / 2 - 0.6, wallZ + 0.6, 0.15);
    const barrel = (x, z, col) => { const b = mesh(G(new THREE.CylinderGeometry(0.2, 0.2, 0.55, 18)), C(col, { roughness: 0.4, metalness: 0.3 }), x, 0.275, z); scene.add(b); for (const y of [0.1, 0.45]) scene.add(mesh(G(new THREE.TorusGeometry(0.2, 0.015, 6, 20).rotateX(Math.PI / 2)), C(0x2B3038), x, y, z)); };
    barrel(-FW / 2 + 0.45, wallZ + 0.45, 0x2F6FD6); barrel(-FW / 2 + 0.95, wallZ + 0.38, 0xD8483B);
    const cone = mesh(G(new THREE.ConeGeometry(0.13, 0.36, 16)), C(0xF0752B, { roughness: 0.5 }), -FW / 2 + 0.5, 0.18, 0.25 + FD / 2 - 0.45); scene.add(cone);
    scene.add(mesh(G(new THREE.CylinderGeometry(0.08, 0.1, 0.06, 16)), C(0xF4F1E8), -FW / 2 + 0.5, 0.2, 0.25 + FD / 2 - 0.45));
    scene.add(mesh(box(0.34, 0.03, 0.34), C(0xF0752B), -FW / 2 + 0.5, 0.015, 0.25 + FD / 2 - 0.45));

    // клетки ряда
    // стеллаж: до 4 коробок — одна стопка, больше — две стопки рядом (как ячейки настоящего стеллажа)
    const LVL = 0.38, BASE = 0.16, COLS = (lv.cap || 6) > 4 ? 2 : 1, rackH = LVL * Math.ceil((lv.cap || 6) / COLS) + 0.3;
    const slot = k => COLS === 2 ? { dx: k % 2 ? 0.2 : -0.2, lvl: Math.floor(k / 2) } : { dx: 0, lvl: k };
    const blue = C(0x2F5FA8, { roughness: 0.45, metalness: 0.45 }), orange = C(0xE8762B, { roughness: 0.5, metalness: 0.3 });
    let beltTex = null;
    const capTex = (text, col) => tex(256, 64, (g, w, h) => { g.fillStyle = col; g.fillRect(0, 0, w, h); g.fillStyle = '#fff'; g.font = 'bold 38px "Golos Text", "Segoe UI", sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(text, w / 2, h / 2 + 2); });
    lv.layout.split('').forEach((ch, x) => {
      const X = cx(x);
      if (ch === 'S') {
        const r = new THREE.Group(); r.position.set(X, 0, RACK); scene.add(r);
        for (const [dx, dz] of [[-0.42, -0.3], [0.42, -0.3], [-0.42, 0.3], [0.42, 0.3]]) r.add(mesh(box(0.06, rackH, 0.06), blue, dx, rackH / 2, dz));
        for (const y of [0.1, rackH - 0.04]) for (const dz of [-0.3, 0.3]) r.add(mesh(box(0.9, 0.06, 0.05), orange, 0, y, dz));
        for (const dz of [-0.2, 0, 0.2]) r.add(mesh(box(0.84, 0.03, 0.12), C(0xC79A63), 0, 0.12, dz));
        const sc = lv.shelfColor && lv.shelfColor[x];
        if (sc) r.add(mesh(box(0.5, 0.16, 0.03), M({ color: COLORS[sc][1], emissive: COLORS[sc][1], emissiveIntensity: 0.25 }), 0, rackH - 0.04, 0.33));
        r.add(mesh(box(0.22, 0.1, 0.02), M({ map: capTex('x = ' + x, '#20232A') }), 0.25, 0.25, 0.33));
      }
      if (ch === 'O') {
        const cart = new THREE.Group(); cart.position.set(X, 0, RACK); scene.add(cart);
        cart.add(mesh(box(0.86, 0.06, 0.78), C(0x2E9E5B, { roughness: 0.5, metalness: 0.2 }), 0, 0.12, 0));
        for (const [dx, dz] of [[-0.36, -0.32], [0.36, -0.32], [-0.36, 0.32], [0.36, 0.32]]) cart.add(mesh(G(new THREE.CylinderGeometry(0.05, 0.05, 0.05, 12).rotateZ(Math.PI / 2)), C(0x22252B), dx, 0.05, dz));
        cart.add(mesh(box(0.04, 0.5, 0.04), C(0x22252B), -0.43, 0.38, -0.36)); cart.add(mesh(box(0.04, 0.5, 0.04), C(0x22252B), -0.43, 0.38, 0.36)); cart.add(mesh(box(0.04, 0.04, 0.76), C(0x22252B), -0.43, 0.62, 0));
      }
      if (ch === 'I') {
        // конвейер выходит из стены к клетке: рама, бегущая лента, ролики, шторка в проёме
        const len = RACK + 0.42 - wallZ, mid = (RACK + 0.42 + wallZ) / 2;
        beltTex = tex(64, 256, (g, w, h) => { g.fillStyle = '#2B2F36'; g.fillRect(0, 0, w, h); g.fillStyle = '#3A3F48'; for (let y = 0; y < h; y += 32) g.fillRect(0, y, w, 12); });
        beltTex.wrapT = THREE.RepeatWrapping; beltTex.repeat.set(1, len * 2);
        scene.add(mesh(box(0.7, 0.03, len), M({ map: beltTex, roughness: 0.85 }), X, 0.3, mid));
        for (const dx of [-0.38, 0.38]) scene.add(mesh(box(0.06, 0.1, len + 0.04), C(0x8C96A3, { metalness: 0.6, roughness: 0.35 }), X + dx, 0.31, mid));
        for (let z = RACK + 0.38; z > wallZ; z -= 0.9) for (const dx of [-0.34, 0.34]) scene.add(mesh(box(0.05, 0.27, 0.05), C(0x5C6672, { metalness: 0.5 }), X + dx, 0.135, z));
        scene.add(mesh(G(new THREE.CylinderGeometry(0.06, 0.06, 0.72, 16).rotateZ(Math.PI / 2)), C(0x8C96A3, { metalness: 0.7, roughness: 0.3 }), X, 0.3, RACK + 0.42));
        for (let i = 0; i < 6; i++) scene.add(mesh(box(0.11, 0.6, 0.01), M({ color: 0x20262E, transparent: true, opacity: 0.55, roughness: 0.4 }), X - 0.3 + i * 0.12, 0.62, wallZ + 0.09));
        scene.add(mesh(box(0.86, 0.12, 0.08), C(0xE8B322), X, 0.98, wallZ + 0.09));
      }
    });
    const inX = lv.layout.indexOf('I');

    // коробки: картон, скотч сверху, цветная наклейка с числом спереди
    const boxG = box(0.36, 0.34, 0.36), tapeG = box(0.37, 0.012, 0.08);
    const kraft = tex(128, 128, (g, w, h) => { g.fillStyle = '#C8955A'; g.fillRect(0, 0, w, h); g.strokeStyle = 'rgba(120,80,40,.25)'; g.lineWidth = 2; g.strokeRect(6, 6, w - 12, h - 12); for (let i = 0; i < 40; i++) { g.fillStyle = `rgba(90,60,30,${Math.random() * 0.08})`; g.fillRect(Math.random() * w, Math.random() * h, 8, 2); } });
    const kraftMat = M({ map: kraft, roughness: 0.9 }), tapeMat = C(0xE2C48E, { roughness: 0.4 });
    const boxes = new Map();
    function makeBox(b) {
      const lbl = tex(128, 128, (g, w, h) => {
        g.drawImage(kraft.image, 0, 0, w, h);
        const col = b.color ? COLORS[b.color][1] : '#F4F1E8';
        g.fillStyle = col; g.beginPath(); g.roundRect(10, 16, w - 20, h - 32, 10); g.fill();
        g.fillStyle = b.color ? '#fff' : '#20232A'; g.font = `bold ${String(b.n).length > 1 ? 78 : 88}px "Golos Text", "Segoe UI", sans-serif`; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(b.n, w / 2, h / 2 + 3);
      });
      const front = M({ map: lbl, roughness: 0.85 });
      const grp = new THREE.Group();
      grp.add(mesh(boxG, [kraftMat, kraftMat, kraftMat, kraftMat, front, kraftMat]));
      grp.add(mesh(tapeG, tapeMat, 0, 0.175, 0));
      scene.add(grp);
      return { g: grp, front, mat: front };
    }

    // робот-погрузчик: жёлтый корпус, кабина с экраном-лицом, колёса, мачта с вилами, маячок
    const robot = new THREE.Group(); scene.add(robot);
    const body = new THREE.Group(); robot.add(body);
    const yellow = C(0xF2B12E, { roughness: 0.4, metalness: 0.15 }), dark = C(0x22252B, { roughness: 0.6 }), steel = C(0x3A3F47, { roughness: 0.35, metalness: 0.7 });
    body.add(mesh(box(0.66, 0.08, 0.6), dark, 0, 0.1, -0.04));
    body.add(mesh(box(0.62, 0.24, 0.56), yellow, 0, 0.26, -0.04));
    body.add(mesh(box(0.64, 0.05, 0.58), C(0xD99A1E, { roughness: 0.45 }), 0, 0.4, -0.04));
    const cab = mesh(box(0.44, 0.26, 0.34), yellow, 0, 0.55, -0.1); body.add(cab);
    body.add(mesh(box(0.36, 0.17, 0.02), C(0x14181F, { roughness: 0.15, metalness: 0.3 }), 0, 0.56, 0.075));
    const eyeMat = M({ color: 0x8FF3FF, emissive: 0x5FE8FF, emissiveIntensity: 2.2 });
    const eyes = [-0.075, 0.075].map(ex => { const e = mesh(box(0.06, 0.06, 0.01), eyeMat, ex, 0.57, 0.088); e.castShadow = false; body.add(e); return e; });
    const beaconMat = M({ color: 0xFF8A1F, emissive: 0xFF6A00, emissiveIntensity: 0.6, transparent: true, opacity: 0.9 });
    body.add(mesh(G(new THREE.CylinderGeometry(0.035, 0.035, 0.02, 12)), dark, 0.14, 0.69, -0.18));
    const beacon = mesh(G(new THREE.CylinderGeometry(0.03, 0.035, 0.06, 12)), beaconMat, 0.14, 0.73, -0.18); body.add(beacon);
    const wheels = [];
    for (const [wx, wz] of [[-0.31, 0.14], [0.31, 0.14], [-0.31, -0.24], [0.31, -0.24]]) {
      const wg = new THREE.Group(); wg.position.set(wx, 0.1, wz);
      wg.add(mesh(G(new THREE.CylinderGeometry(0.1, 0.1, 0.07, 18).rotateZ(Math.PI / 2)), dark));
      wg.add(mesh(G(new THREE.CylinderGeometry(0.045, 0.045, 0.075, 10).rotateZ(Math.PI / 2)), C(0xB8C0CA, { metalness: 0.6, roughness: 0.3 })));
      robot.add(wg); wheels.push(wg);
    }
    for (const mx of [-0.2, 0.2]) body.add(mesh(box(0.045, 1.0, 0.045), steel, mx, 0.6, 0.27));
    body.add(mesh(box(0.45, 0.045, 0.045), steel, 0, 1.08, 0.27));
    const carriage = new THREE.Group(); carriage.position.set(0, 0.12, 0.31); body.add(carriage);
    carriage.add(mesh(box(0.46, 0.14, 0.03), steel, 0, 0.07, 0));
    for (const fx of [-0.12, 0.12]) carriage.add(mesh(box(0.05, 0.025, 0.44), steel, fx, 0, 0.22));
    robot.scale.setScalar(1.05);

    // состояние анимации
    const st = { x: cx(lv.robot || 0), yaw: Math.PI / 2, yawT: Math.PI / 2, tau: 0.12, lift: 0.12, liftT: 0.12, act: null, bump: null, wx: lv.robot || 0, move: 0 };
    robot.position.set(st.x, 0, LANE); robot.rotation.y = st.yaw;
    let raf = 0, last = 0, size = { w: 1, h: 1 }, dur = 160, holdId = null, beltV = 0, world = null;
    const forkPos = new THREE.Vector3();
    function targets() {                                         // где должна быть каждая коробка
      const out = new Map();
      if (!world) return out;
      world.cells.forEach((c, x) => {
        c.stack.forEach((b, k) => {
          if (c.kind === 'in') out.set(b.id, new THREE.Vector3(cx(x), 0.32 + 0.17, RACK + 0.18 - k * 0.45));
          else { const sl = c.kind === 'out' ? { dx: k % 2 ? 0.2 : -0.2, lvl: Math.floor(k / 2) } : slot(k); out.set(b.id, new THREE.Vector3(cx(x) + sl.dx, BASE + 0.02 + 0.17 + sl.lvl * LVL, RACK)); }
        });
      });
      return out;
    }
    function frame() {
      raf = requestAnimationFrame(frame);
      const t = performance.now();                               // одно время с t0 событий: метка кадра бывает раньше
      const dt = Math.min(0.1, (t - last) / 1000 || 0); last = t;
      const calm = UI.reduceMotion();
      const a = st.tau > 0 && !calm ? 1 - Math.exp(-dt / st.tau) : 1;
      // едет и поворачивается
      const px = robot.position.x;
      robot.position.x += (st.x - robot.position.x) * a;
      const v = (robot.position.x - px) / (dt || 1);
      let dy = st.yawT - robot.rotation.y; dy = Math.atan2(Math.sin(dy), Math.cos(dy));
      robot.rotation.y += dy * (st.tau > 0 && !calm ? 1 - Math.exp(-dt / (st.tau * 0.7)) : 1);
      for (const w of wheels) w.rotation.x += (robot.position.x - px) / 0.1 * (Math.abs(Math.sin(robot.rotation.y)) > 0.5 ? Math.sign(Math.sin(robot.rotation.y)) : 0);
      body.rotation.x = calm ? 0 : -Math.max(-0.06, Math.min(0.06, (v - st.move) * 0.004));
      st.move = v;
      // упёрся в стену: короткий толчок вперёд и обратно
      let nudge = 0;
      if (st.bump && !calm) { const k = (t - st.bump.t0) / st.bump.d; if (k >= 1) st.bump = null; else nudge = Math.sin(k * Math.PI) * 0.12 * st.bump.s; }
      robot.position.x += nudge * a;
      // вилы: к нужной высоте, потом в положение «везу»
      if (st.act && !calm) {
        const k = (t - st.act.t0) / st.act.d;
        if (k >= 1) { st.act = null; }
        else st.liftT = k < 0.5 ? st.act.h : st.lift0;
      } else st.liftT = st.lift0 ?? 0.12;
      carriage.position.y += (st.liftT - carriage.position.y) * (calm ? 1 : 1 - Math.exp(-dt / Math.max(0.04, st.tau * 0.5)));
      // глаза моргают, маячок светится в движении
      const blink = (t % 3800) < 120;
      eyes.forEach(e => { e.scale.y = blink ? 0.15 : 1; });
      beaconMat.emissiveIntensity = Math.abs(v) > 0.05 ? 1.4 + Math.sin(t / 90) * 1.2 : 0.5;
      lamps.forEach((l, i) => { l.material.emissiveIntensity = 1.5 + Math.sin(t / 1700 + i) * 0.05; });
      // коробки догоняют свои места, коробка в руках — на вилах
      carriage.updateMatrixWorld(true);
      forkPos.set(0, 0.03 + 0.17, 0.24); carriage.localToWorld(forkPos);
      const tg = targets();
      for (const [id, bx] of boxes) {
        const goal = id === holdId ? forkPos : tg.get(id);
        if (!goal) continue;
        const k = id === holdId ? (calm ? 1 : 1 - Math.exp(-dt / Math.max(0.03, st.tau * 0.45))) : a;
        bx.g.position.lerp(goal, k);
        const yawGoal = id === holdId ? robot.rotation.y : 0;
        let dr = yawGoal - bx.g.rotation.y; dr = Math.atan2(Math.sin(dr), Math.cos(dr)); bx.g.rotation.y += dr * k;
      }
      // лента конвейера бежит, когда очередь сдвигается
      if (beltTex) { beltTex.offset.y -= beltV * dt; beltV *= Math.exp(-dt * 3); }
      renderer.render(scene, cam);
    }
    raf = requestAnimationFrame(frame);

    return {
      sync(w, ev, d) {
        world = w;
        dur = d || 0;
        st.tau = dur ? dur / 1000 / 3.2 : 0;
        // новые коробки — сразу на свои места
        const tg = targets();
        for (const b of w.cells.flatMap(c => c.stack).concat(w.hold ? [w.hold] : [])) if (!boxes.has(b.id)) { const m = makeBox(b); boxes.set(b.id, m); const p = tg.get(b.id); if (p) m.g.position.copy(p); }
        holdId = w.hold ? w.hold.id : null;
        st.lift0 = w.hold ? 0.36 : 0.12;
        if (w.x !== st.wx) { st.x = cx(w.x); st.wx = w.x; }
        if (ev && ev.a === 'move') st.yawT = ev.dir === 'West' ? -Math.PI / 2 : Math.PI / 2;
        if (ev && (ev.a === 'take' || ev.a === 'put')) {
          st.yawT = Math.PI;                                      // повернуться к стеллажу
          const c = w.cell(w.x), lvl = ev.a === 'take' ? (c.kind === 'in' ? 0.24 : BASE + slot(c.stack.length).lvl * LVL) : BASE + slot(c.stack.length - 1).lvl * LVL;
          if (dur) st.act = { t0: performance.now(), d: Math.max(140, dur), h: Math.max(0.12, lvl) };
          if (ev.a === 'take' && c.kind === 'in' && ev.ok) beltV = 1.2;
        }
        if (ev && ev.a === 'bump' && dur) st.bump = { t0: performance.now(), d: Math.max(140, dur * 0.8), s: ev.dir === 'West' ? -1 : 1 };
        if (!dur) {                                              // без анимации — всё сразу на месте
          robot.position.x = st.x; robot.rotation.y = st.yawT; carriage.position.y = st.lift0;
          for (const [id, bx] of boxes) { const p = tg.get(id); if (p) bx.g.position.copy(p); }
        }
      },
      fit(free, far) {
        const w = host.clientWidth || 1, h = host.clientHeight || 1;
        size = { w, h };
        renderer.setSize(w, h, false);
        cam.aspect = w / h;
        const fw = Math.max(200, free ? free[1] - free[0] : w), mid = free ? (free[0] + free[1]) / 2 : w / 2;
        const t = Math.tan(cam.fov * Math.PI / 360), span = Math.max(FW, 5);
        const d = Math.max(span * 0.62 / (2 * t), span * 0.92 / (2 * t * fw / h)) * (far ? 1.2 : 1), el = 0.55;
        cam.position.set(0, 0.6 + d * Math.sin(el), 0.4 + d * Math.cos(el));
        cam.lookAt(0, 0.55, -0.1);
        cam.setViewOffset(w, h, w / 2 - mid, far ? -h * 0.06 : 0, w, h);
        cam.updateProjectionMatrix();
      },
      project(x, y, hgt = 0.5) {
        const v = new THREE.Vector3(cx(x), hgt, RACK).project(cam);
        return { x: (v.x + 1) / 2 * size.w, y: (1 - v.y) / 2 * size.h };
      },
      dispose() {
        cancelAnimationFrame(raf);
        geos.forEach(g => g.dispose()); mats.forEach(m => m.dispose()); texs.forEach(t => t.dispose());
        renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove();
      },
    };
  }

  /* ── без WebGL: плоский ряд клеток ── */
  function skladFlat(host, lv) {
    const el = document.createElement('div'); el.className = 'sk-flat'; el.style.setProperty('--w', lv.w); host.appendChild(el);
    return {
      sync(w) {
        el.innerHTML = w.cells.map((c, x) => `<div class="${c.kind}">${c.stack.slice(-6).map(b => `<i style="--c:${b.color ? COLORS[b.color][1] : '#C8955A'}">${b.n}</i>`).join('')}${w.x === x ? `<b>${w.hold ? `<i style="--c:${w.hold.color ? COLORS[w.hold.color][1] : '#C8955A'}">${w.hold.n}</i>` : ''}</b>` : ''}</div>`).join('');
      },
      fit() { }, project(x) { const r = el.children[x] ? el.children[x].getBoundingClientRect() : { left: 0, top: 0, width: 0 }, p = host.getBoundingClientRect(); return { x: r.left - p.left + r.width / 2, y: r.top - p.top }; },
      dispose() { el.remove(); },
    };
  }

  /* ── описание игры для общего экрана (StacklyFarm.mount) ── */
  const HUD_ICON = {
    in: '<svg viewBox="0 0 24 24" width="32" height="32" aria-hidden="true"><rect x="2" y="15" width="20" height="3" rx="1.5" fill="#2B2F36"/><circle cx="6" cy="19.5" r="1.6" fill="#8C96A3"/><circle cx="18" cy="19.5" r="1.6" fill="#8C96A3"/><rect x="5" y="8" width="6" height="6.5" rx="1" fill="#C8955A"/><rect x="13" y="8" width="6" height="6.5" rx="1" fill="#C8955A"/></svg>',
    shelf: '<svg viewBox="0 0 24 24" width="32" height="32" aria-hidden="true"><path d="M4 3v18M20 3v18" stroke="#2F5FA8" stroke-width="2.4"/><path d="M4 12h16M4 20h16" stroke="#E8762B" stroke-width="2"/><rect x="6.5" y="6" width="5" height="5" rx=".8" fill="#C8955A"/><rect x="12.5" y="14" width="5" height="5" rx=".8" fill="#C8955A"/><rect x="6.5" y="14" width="5" height="5" rx=".8" fill="#C8955A"/></svg>',
    out: '<svg viewBox="0 0 24 24" width="32" height="32" aria-hidden="true"><rect x="1.5" y="7" width="13" height="9.5" rx="1" fill="#2E9E5B"/><path d="M14.5 10h4l3.5 3.5v3h-7.5z" fill="#24804A"/><circle cx="6" cy="18" r="2" fill="#22252B"/><circle cx="17.5" cy="18" r="2" fill="#22252B"/></svg>',
  };
  const ICON_BOX = '<svg viewBox="0 0 24 24" width="30" height="30" aria-hidden="true"><path d="M3 7.5 12 3l9 4.5v9L12 21l-9-4.5z" fill="#C8955A"/><path d="M3 7.5 12 12l9-4.5M12 12v9" stroke="#8E6234" stroke-width="1.3" fill="none"/><path d="M7.5 5.3 16.5 9.8" stroke="#E2C48E" stroke-width="2"/></svg>';
  const CSS = `
.fg-tag.sk-cap { position: absolute; transform: translate(-50%, -100%); padding: 2px 7px; border-radius: 3px; background: rgb(30 31 35 / .82); color: #fff; font: 600 11.5px/1.4 var(--f-body); white-space: nowrap; }
.sk-flat { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); display: grid; grid-template-columns: repeat(var(--w), 70px); gap: 6px; }
.sk-flat > div { position: relative; height: 200px; display: flex; flex-direction: column-reverse; align-items: center; gap: 3px; padding: 6px 0 40px; border-radius: 6px; background: #BFC4CB; }
.sk-flat > div.shelf { box-shadow: inset 0 0 0 3px #2F5FA8; } .sk-flat > div.out { box-shadow: inset 0 0 0 3px #2E9E5B; } .sk-flat > div.in { box-shadow: inset 0 0 0 3px #2B2F36; }
.sk-flat i { display: grid; place-items: center; width: 40px; height: 22px; border-radius: 3px; background: var(--c); color: #fff; font: 700 12px var(--f-mono); font-style: normal; }
.sk-flat b { position: absolute; bottom: 4px; width: 46px; height: 30px; border-radius: 6px; background: #F2B12E; display: grid; place-items: center; }
`;
  const UIX = {
    key: 'sklad', route: 'sklad', title: 'Склад', actor: 'робот', loading: 'Загружаем склад…', cmdTitle: 'Команды робота', winTitle: 'Склад в порядке!',
    stepTitle: 'Выполнить до следующей команды робота',
    levels: LEVELS, chapters: CHAPTERS, order: ORDER, numOf, core: CORE, scene: skladScene, flat: skladFlat,
    doc: DOC, cdoc: CDOC, cmds: CMDS, ns: { Colors: Object.fromEntries(Object.entries(COLORS).map(([k, v]) => [k, v[0]])) }, nsDoc: { Colors: 'цвета коробок' },
    seedFor: () => Math.floor(Math.random() * 1e9), newSeed: () => Math.floor(Math.random() * 1e9),
    helpNote: '<p><code>move</code>, <code>take</code> и <code>put</code> — один ход; посмотреть (<code>box_number()</code>, <code>boxes_left()</code>, <code>top_number()</code>…) можно бесплатно. Коробки при каждом запуске новые — программа должна работать для любых. Работает и обычный Python: <code>print()</code>, <code>range()</code>, списки, свои функции.</p>',
    intro: ctx => `Робот-погрузчик слушается программы на Python: возит коробки с конвейера по стеллажам. Каждый уровень объясняет одну новую вещь. За первое прохождение — ${ctx.points || 10} баллов.`,
    goalHTML: lv => `<div class="fg-want"><span>Цель:</span>${lv.goal}</div>`,
    hud(w) {
      const shelf = w.cells.filter(c => c.kind === 'shelf').reduce((a, c) => a + c.stack.length, 0), out = w.cells.filter(c => c.kind === 'out').reduce((a, c) => a + c.stack.length, 0);
      return [...(w.cells.some(c => c.kind === 'in') ? [['in', 'на конвейере', w.left()]] : []), ...(w.cells.some(c => c.kind === 'shelf') ? [['shelf', 'на стеллажах', shelf]] : []), ...(w.cells.some(c => c.kind === 'out') ? [['out', 'отгружено', out]] : [])]
        .map(([k, t, n]) => `<div title="Коробок ${t}: ${n}">${HUD_ICON[k]}<span>${n}</span></div>`).join('');
    },
    goalBars: null, fly: null,
    tags(w, lv) {
      const out = [];
      lv.layout.split('').forEach((ch, x) => {
        const cap = lv.captions && lv.captions[x];
        if (cap || ch === 'I' || ch === 'O') out.push({ x, y: 0, h: ch === 'S' ? 0.38 * Math.ceil(lv.cap / (lv.cap > 4 ? 2 : 1)) + 0.55 : 1.2, cls: 'sk-cap', text: cap || (ch === 'I' ? 'конвейер' : 'отгрузка') });
      });
      return out;
    },
    retag: () => false,
  };
  if (!document.getElementById('sk-css')) { const st = document.createElement('style'); st.id = 'sk-css'; st.textContent = CSS; document.head.appendChild(st); }
  root.StacklySklad = { ...api, game: UIX };
})(typeof window !== 'undefined' ? window : globalThis, typeof module !== 'undefined' && module.exports ? require('./farm.js') : window.StacklyFarm);
