#!/usr/bin/env python3
"""Собирает банк профильной математики в content/ege.js: запускает генераторы tools/gen_math*.py и заменяет
в window.BANK все встроенные задачи математики (id «m<номер>-g…») свежими. Остальной банк не трогается.

    python3 tools/build_math_bank.py            # все номера
    python3 tools/build_math_bank.py 7 8        # только указанные номера
"""
import glob, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, 'content', 'ege.js')


def main(nums):
    gens = sorted(glob.glob(os.path.join(ROOT, 'tools', 'gen_math*.py')), key=lambda p: int(re.search(r'(\d+)\.py$', p).group(1)))
    if nums:
        gens = [g for g in gens if int(re.search(r'(\d+)\.py$', g).group(1)) in nums]
    fresh = {}
    for g in gens:
        num = int(re.search(r'(\d+)\.py$', g).group(1))
        r = subprocess.run([sys.executable, g], capture_output=True, text=True, encoding='utf-8',
                           env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        if r.returncode:
            raise SystemExit(f'{os.path.basename(g)}:\n{r.stderr}')
        fresh[num] = json.loads(r.stdout)
        print(f'№{num}: {len(fresh[num])} задач {r.stderr.strip()}', file=sys.stderr)
    s = open(PATH, encoding='utf-8').read()
    a = s.index('window.BANK = ') + len('window.BANK = ')
    b = s.index(';\n', a)
    bank = json.loads(s[a:b])
    # сквозные номера задач (#1234) — это позиции в банке: блок номера заменяется на месте, новые номера — в конец
    out, done = [], set()
    for p in bank:
        k = p.get('snum') if p.get('subject') == 'Математика' and p['id'].startswith('m') else None
        if k in fresh:
            if k not in done:
                out += fresh[k]
                done.add(k)
            continue
        out.append(p)
    for k in sorted(fresh):
        if k not in done:
            out += fresh[k]
    bank = out
    math = [p for p in bank if p.get('subject') == 'Математика']
    s = s[:a] + json.dumps(bank, ensure_ascii=False) + s[b:]
    open(PATH, 'w', encoding='utf-8', newline='').write(s)
    print(f'в банке {len(bank)} задач, из них по математике {len(math)}', file=sys.stderr)


if __name__ == '__main__':
    main({int(x) for x in sys.argv[1:]})
