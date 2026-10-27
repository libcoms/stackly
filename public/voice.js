/* Голоса эфира — общие для сайта (выбор и «Прослушать») и оверлея live.html.
   Голоса берутся из браузера (Web Speech API), поэтому набор зависит от устройства: естественно звучат нейросетевые
   «Microsoft … Online (Natural)» в Edge и «Google русский» в Chrome.
   Стиль голоса — код, а не имя: ученик выбирает его на своём устройстве, а звучит он на компьютере учителя.
   Армянский акцент: русский текст переписывается армянскими буквами и читается армянским голосом (в Edge — Анаит, Айк). */
(() => {
  const STYLES = [
    ['', 'Как настроил учитель'],
    ['ru-f', 'Женский'],
    ['ru-m', 'Мужской'],
    ['hy-f', 'Женский с армянским акцентом'],
    ['hy-m', 'Мужской с армянским акцентом'],
  ];
  const FEMALE = /svetlana|irina|ekaterina|daria|dariya|milena|alena|anna|katya|google/i;
  const MALE = /dmitry|pavel|maxim|yuri|denis|artem/i;
  const rank = v => /natural|online/i.test(v.name) ? 3 : /google/i.test(v.name) ? 2 : 1;
  const all = () => window.speechSynthesis ? speechSynthesis.getVoices() : [];
  const byLang = re => all().filter(v => re.test(v.lang)).sort((a, b) => rank(b) - rank(a) || a.name.localeCompare(b.name));
  const ru = () => byLang(/^ru/i), hy = () => byLang(/^hy/i);

  // код стиля или имя голоса → { voice, hy: читать ли армянскими буквами }; null — такого голоса на устройстве нет
  function pick(code) {
    if (!code) return null;
    if (code === 'ru-f') { const v = ru().find(x => FEMALE.test(x.name)); return v ? { voice: v } : null; }
    if (code === 'ru-m') { const v = ru().find(x => MALE.test(x.name)); return v ? { voice: v } : null; }
    if (code === 'hy-f' || code === 'hy-m') {
      const list = hy(), v = list.find(x => (code === 'hy-f' ? /anahit/i : /hayk/i).test(x.name)) || list[0];
      return v ? { voice: v, hy: true } : null;
    }
    const v = all().find(x => x.name === code);
    return v ? { voice: v, hy: /^hy/i.test(v.lang) } : null;
  }
  // стиль ученика → голос учителя по умолчанию → лучший русский
  const resolve = (code, fallback) => pick(code) || pick(fallback) || (ru()[0] ? { voice: ru()[0] } : null);

  /* ── русский текст армянскими буквами ── */
  const ONES = ['ноль', 'один', 'два', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять', 'десять', 'одиннадцать', 'двенадцать', 'тринадцать',
    'четырнадцать', 'пятнадцать', 'шестнадцать', 'семнадцать', 'восемнадцать', 'девятнадцать'];
  const TENS = ['', '', 'двадцать', 'тридцать', 'сорок', 'пятьдесят', 'шестьдесят', 'семьдесят', 'восемьдесят', 'девяносто'];
  const HUND = ['', 'сто', 'двести', 'триста', 'четыреста', 'пятьсот', 'шестьсот', 'семьсот', 'восемьсот', 'девятьсот'];
  function words(n) {
    if (n < 20) return ONES[n];
    if (n < 100) return TENS[Math.floor(n / 10)] + (n % 10 ? ' ' + ONES[n % 10] : '');
    if (n < 1000) return HUND[Math.floor(n / 100)] + (n % 100 ? ' ' + words(n % 100) : '');
    if (n < 1e6) {
      const t = Math.floor(n / 1000), r = n % 1000, m10 = t % 10, m100 = t % 100;
      const head = t % 10 === 1 && m100 !== 11 ? (t > 1 ? words(t - 1) + ' ' : '') + 'одна' : t % 10 === 2 && m100 !== 12 ? (t > 2 ? words(t - 2) + ' ' : '') + 'две' : words(t);
      const unit = m10 === 1 && m100 !== 11 ? 'тысяча' : m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20) ? 'тысячи' : 'тысяч';
      return head + ' ' + unit + (r ? ' ' + words(r) : '');
    }
    return String(n);
  }
  const HY = { а: 'ա', б: 'բ', в: 'վ', г: 'գ', д: 'դ', ж: 'ժ', з: 'զ', и: 'ի', й: 'յ', к: 'կ', л: 'լ', м: 'մ', н: 'ն', п: 'պ', р: 'ր', с: 'ս', т: 'տ',
    у: 'ու', ф: 'ֆ', х: 'խ', ц: 'ց', ч: 'չ', ш: 'շ', щ: 'շչ', ъ: '', ы: 'ը', ь: '', э: 'է', ю: 'յու', я: 'յա', ё: 'յո' };
  const VOWEL = /[аеёиоуыэюяъь]/;
  function toArmenian(text) {
    const t = text.toLowerCase().replace(/\d+/g, d => words(+d));
    let out = '';
    for (let i = 0; i < t.length; i++) {
      const c = t[i], prev = i ? t[i - 1] : ' ', start = !/[а-яё]/.test(prev);
      if (c === 'е') out += start || VOWEL.test(prev) ? 'յե' : 'ե';
      else if (c === 'о') out += start ? 'օ' : 'ո';
      else out += c in HY ? HY[c] : c;
    }
    return out;
  }

  function speak(text, code, rate, fallback) {
    return new Promise(done => {
      if (!window.speechSynthesis) return setTimeout(done, 4000);
      const r = resolve(code, fallback);
      const u = new SpeechSynthesisUtterance(r && r.hy ? toArmenian(text) : text);
      u.lang = r ? r.voice.lang : 'ru-RU'; u.rate = rate || 1; if (r) u.voice = r.voice;
      let fin = false; const end = () => { if (!fin) { fin = true; done(); } };
      u.onend = end; u.onerror = end;
      setTimeout(end, 4000 + text.length * 130);          // если голос не ответил — не зависаем
      speechSynthesis.cancel(); speechSynthesis.speak(u);
    });
  }
  // голоса приходят не сразу — подписчики перерисуют списки, когда браузер их отдаст
  const onReady = fn => { if (window.speechSynthesis) { speechSynthesis.getVoices(); speechSynthesis.addEventListener('voiceschanged', fn); } };

  window.StacklyVoice = { STYLES, rank, ru, hy, pick, resolve, speak, toArmenian, onReady };
})();
