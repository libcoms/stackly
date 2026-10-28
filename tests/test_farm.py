"""Игры на Python: «Ферма» (public/farm.js — интерпретатор, движок, уровни) проверяет tests/farm_check.js,
«Склад» (public/sklad.js) — tests/sklad_check.js, «Мастерскую переменных» (public/workshop.js) — tests/workshop_check.js; все в node."""
import os, shutil, subprocess, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@unittest.skipUnless(shutil.which('node'), 'нет node')
class FarmTest(unittest.TestCase):
    def test_farm(self):
        r = subprocess.run(['node', os.path.join(ROOT, 'tests', 'farm_check.js')], capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_sklad(self):
        r = subprocess.run(['node', os.path.join(ROOT, 'tests', 'sklad_check.js')], capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_workshop(self):
        r = subprocess.run(['node', os.path.join(ROOT, 'tests', 'workshop_check.js')], capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == '__main__':
    unittest.main()
