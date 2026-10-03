"""Проверки закрытых материалов: в public/ нет методички и банка, карточки заданий совпадают с content/ege.js.

Запуск:  python3 -m unittest discover -s tests -v
"""
import json, os, re, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STR = r"'((?:\\.|[^'\\])*)'"
FIELDS = ('n', 'title', 'short', 'sect', 'level', 'time', 'tool', 'isNew', 'lead')


def read(*path):
    with open(os.path.join(ROOT, *path), encoding='utf-8') as f:
        return f.read()


def js_str(s):
    return re.sub(r'\\(.)', lambda m: {'n': '\n', 't': '\t'}.get(m.group(1), m.group(1)), s)


def content_cards(src):
    """Поля карточек из заголовков E({...}) в content/ege.js."""
    cards = []
    for block in re.split(r'\nE\(\{', src)[1:]:
        head = block.split('\n  theory:')[0].split('\n  types:')[0]
        o = {}
        for key in FIELDS:
            m = re.search(r'(?:^|[\s,{])' + key + r': (?:' + STR + r'|(\d+)|(true))', head)
            if m:
                o[key] = js_str(m.group(1)) if m.group(1) is not None else int(m.group(2)) if m.group(2) else True
        cards.append(o)
    return cards


class ContentSplitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = read('content', 'ege.js')
        cls.public = ''.join(read('public', f) for f in os.listdir(os.path.join(ROOT, 'public'))
                             if f.endswith(('.html', '.js', '.json')))
        m = re.search(r'^window\.BANK = (\[.*\]);$', cls.content, re.M)
        cls.bank = json.loads(m.group(1))

    def test_public_has_no_bank(self):
        self.assertNotIn('STACKLY_CONTENT = true', self.public)
        for p in self.bank:
            self.assertNotIn(p['code'].strip()[:80], self.public, p['id'])
            self.assertNotIn(p['text'].strip()[:80], self.public, p['id'])

    def test_public_has_no_methodology(self):
        # 24 разбора со своей теорией и общая GAME_THEORY для заданий 19–21
        theories = re.findall(r'\n  theory: R`([^`]{40,})', self.content) + re.findall(r'GAME_THEORY = R`([^`]{40,})', self.content)
        self.assertEqual(len(theories), 25)
        for t in theories:
            self.assertNotIn(t[:80], self.public)

    def test_cards_match_content(self):
        m = re.search(r'^window\.EGE = \[\n(.*?)\n\];$', self.public, re.M | re.S)
        public = [json.loads(line.strip().rstrip(',')) for line in m.group(1).split('\n')]
        self.assertEqual(public, content_cards(self.content),
                         'карточки заданий в public/index.html разошлись с content/ege.js')
        total = int(re.search(r'^window\.BANK_TOTAL = (\d+);$', self.public, re.M).group(1))
        self.assertEqual(total, len(self.bank))


if __name__ == '__main__':
    unittest.main()
