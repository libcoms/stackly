/* stackly — формулы в тексте: маленькое подмножество TeX → HTML, без внешних библиотек и шрифтов.
   $\frac{3}{4}$, $\sqrt{x+1}$, $\sqrt[3]{8}$, $x^{2}$, $\log_{2} 8$, $\vec{a}$, $\overline{AB}$, $30^\circ$,
   $\alpha$, $\pi$, $\sin x$, $\le$, $\cdot$ … Неизвестная команда — ошибка: texify() оставляет исходник в <code>,
   а tests/tex_check.js проверяет, что формулы банка разбираются без ошибок.
   В браузере — window.StacklyTex, в node — module.exports. */
(function (root) {
  'use strict';
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
  const SYM = {
    alpha: 'α', beta: 'β', gamma: 'γ', delta: 'δ', epsilon: 'ε', varepsilon: 'ε', theta: 'θ', lambda: 'λ', mu: 'μ',
    pi: 'π', rho: 'ρ', sigma: 'σ', tau: 'τ', phi: 'φ', varphi: 'φ', omega: 'ω', Delta: 'Δ', Omega: 'Ω',
    nu: 'ν', eta: 'η', kappa: 'κ', xi: 'ξ', psi: 'ψ', chi: 'χ', zeta: 'ζ',
    cdot: '·', times: '×', le: '≤', leqslant: '≤', ge: '≥', geqslant: '≥', ne: '≠', neq: '≠', approx: '≈', pm: '±', mp: '∓',
    infty: '∞', in: '∈', notin: '∉', cup: '∪', cap: '∩', angle: '∠', triangle: '△', parallel: '∥', perp: '⊥', to: '→',
    Rightarrow: '⇒', Leftrightarrow: '⇔', ldots: '…', cdots: '⋯', circ: '∘', prime: '′', emptyset: '∅', varnothing: '∅',
    lt: '<', gt: '>', '%': '%', '{': '{', '}': '}', '|': '‖', ',': ' ', ';': ' ', ':': ' ', '!': '', ' ': ' ',
    quad: ' ', qquad: '  ',
  };
  const FN = new Set(['sin', 'cos', 'tg', 'ctg', 'tan', 'cot', 'log', 'ln', 'lg', 'exp', 'arcsin', 'arccos', 'arctg', 'arcctg', 'min', 'max', 'sgn']);
  const REL = new Set(['=', '<', '>', '≤', '≥', '≠', '≈', '∈', '⇒', '⇔', '→']);
  const BIN = new Set(['+', '−', '±', '∓', '·', '×']);

  function parse(src) {
    const s = String(src);
    let i = 0;
    const fail = m => { throw new Error(`${m} в «${s}»`); };
    // группа {…} или один знак/команда — аргумент \frac, ^, _
    function arg() {
      while (s[i] === ' ') i++;
      if (s[i] === '{') { i++; const h = seq('}'); if (s[i++] !== '}') fail('нет }'); return h; }
      if (i >= s.length) fail('нет аргумента');
      return atom();
    }
    function cmd() {
      const m = /^\\([A-Za-z]+|.)/.exec(s.slice(i));
      if (!m) fail('обрывок команды');
      i += m[0].length;
      const c = m[1];
      if (c === 'frac' || c === 'dfrac' || c === 'tfrac') { const a = arg(), b = arg(); return `<span class="fr"><span>${a}</span><span>${b}</span></span>`; }
      if (c === 'sqrt') {
        let n = '';
        if (s[i] === '[') { const j = s.indexOf(']', i); if (j < 0) fail('нет ]'); n = esc(s.slice(i + 1, j)); i = j + 1; }
        return `<span class="sq">${n ? `<sup class="ri">${n}</sup>` : ''}<span class="rad">√</span><span class="ra">${arg()}</span></span>`;
      }
      if (c === 'vec') return `<span class="vec">${arg()}</span>`;
      if (c === 'overline' || c === 'bar') return `<span class="ovl">${arg()}</span>`;
      if (c === 'text' || c === 'mathrm') { while (s[i] === ' ') i++; if (s[i] !== '{') fail('\\text без {'); const j = s.indexOf('}', i); if (j < 0) fail('нет }'); const t = esc(s.slice(i + 1, j)); i = j + 1; return `<span class="tt">${t}</span>`; }
      if (c === 'left' || c === 'right') {                // \left( … \right) — скобки выше обычных, по росту дроби
        const d = s[i++];
        const ch = d === '.' ? '' : d === '\\' ? (i++, s[i - 1] === '{' ? '{' : s[i - 1] === '}' ? '}' : '|') : d;
        return ch ? `<span class="dl">${esc(ch)}</span>` : '';
      }
      if (FN.has(c)) return `<span class="fn">${c}</span>`;
      if (c in SYM) { const v = SYM[c]; return REL.has(v) ? `<span class="rel">${v}</span>` : BIN.has(v) ? `<span class="bin">${v}</span>` : esc(v); }
      return fail(`неизвестная команда \\${c}`);
    }
    function atom() {
      const ch = s[i];
      if (ch === '\\') return cmd();
      if (ch === '{') { i++; const h = seq('}'); if (s[i++] !== '}') fail('нет }'); return h; }
      if (/[0-9]/.test(ch)) { const m = /^\d+(?:,\d+)?/.exec(s.slice(i)); i += m[0].length; return m[0]; }
      if (/[A-Za-z]/.test(ch)) { i++; return `<i>${ch}</i>`; }
      i++;
      if (ch === '-' || ch === '−') return '<span class="bin">−</span>';
      if (ch === '+' || ch === '*') return `<span class="bin">${ch === '*' ? '·' : '+'}</span>`;
      if (ch === '=' || ch === '<' || ch === '>') return `<span class="rel">${esc(ch)}</span>`;
      if (ch === '}' ) fail('лишняя }');
      if (ch === '^' || ch === '_') fail('индекс без основания');
      if (ch === "'") return '′';
      return esc(ch);
    }
    function seq(stop) {
      let h = '';
      while (i < s.length && s[i] !== stop) {
        if (s[i] === ' ') { i++; continue; }                // пробелы в TeX не значат ничего — отступы дают знаки
        let a = atom();
        // степени и индексы: x^2, x_{n}, x_1^{2}, 30^\circ → 30°
        for (;;) {
          if (s[i] === '^') {
            i++;
            if (s.startsWith('\\circ', i)) { i += 5; a += '°'; continue; }
            if (s.startsWith('{\\circ}', i)) { i += 7; a += '°'; continue; }
            a = `${a}<sup>${arg()}</sup>`;
          } else if (s[i] === '_') { i++; a = `${a}<sub>${arg()}</sub>`; }
          else break;
        }
        if (a.startsWith('<span class="fn">') && i < s.length && s[i] !== stop && !/^\s*[()[\]]/.test(s.slice(i))) a += ' ';   // log₂ 8, sin x
        h += a;
      }
      return h;
    }
    const out = seq(null);
    if (i < s.length) fail('лишняя }');
    return out;
  }

  // формула → <span class="tx">…</span>
  function tex(src) { return `<span class="tx">${parse(src)}</span>`; }

  // $…$ внутри HTML-строки → формулы; при ошибке — исходник в <code>, чтобы задача не ломалась целиком
  function texify(html, strict) {
    return String(html).replace(/\$([^$]+)\$/g, (m, src) => {
      try { return tex(src); }
      catch (e) { if (strict) throw e; if (root.console) console.warn('формула:', e.message); return `<code class="txerr">${esc(src)}</code>`; }
    });
  }

  const api = { tex, texify, parse };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.StacklyTex = api;
})(typeof window !== 'undefined' ? window : globalThis);
