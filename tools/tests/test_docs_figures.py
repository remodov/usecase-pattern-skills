"""Числа в README и шаблоне блока обязаны сходиться с корпусом.

Проза устаревает молча: требований стало больше, а «57 % держится ревью»
осталось. Тест считает по спекам и сверяет.
"""

import collections
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
DOCS = ROOT / ".claude" / "docs"
README = ROOT / "README.md"
BLOCK = ROOT / "templates" / "claude-block.md"


def coverage():
    counts = collections.Counter()

    for spec in DOCS.rglob("spec.md"):
        for match in re.finditer(r"^\*\*Покрытие\*\*:\s*(\S+)", spec.read_text(encoding="utf-8"), re.M):
            counts[match.group(1)] += 1

    return counts


class ReadmeFigures(unittest.TestCase):
    def setUp(self):
        self.counts = coverage()
        self.total = sum(self.counts.values())
        self.readme = README.read_text(encoding="utf-8")

    def test_таблица_покрытия_сходится(self):
        for level in ("полное", "частичное", "нет"):
            match = re.search(rf"^\| {level} \| (\d+) \|$", self.readme, re.M)
            self.assertIsNotNone(match, f"в README нет строки покрытия «{level}»")
            self.assertEqual(
                int(match.group(1)),
                self.counts[level],
                f"README обещает {match.group(1)} требований с покрытием «{level}», в корпусе {self.counts[level]}",
            )

    def test_доля_ревью_сходится(self):
        expected = round(self.counts["нет"] / self.total * 100)

        for path, text in ((README, self.readme), (BLOCK, BLOCK.read_text(encoding="utf-8"))):
            match = re.search(r"(\d+) % (?:требований )?корпуса? держ", text)
            self.assertIsNotNone(match, f"{path.name}: не нашлась доля требований на ревью")
            self.assertEqual(
                int(match.group(1)),
                expected,
                f"{path.name} обещает {match.group(1)} %, в корпусе {expected} %",
            )

    def test_число_доменов_сходится(self):
        backend = len(list((DOCS / "backend").rglob("spec.md")))
        shared = len(list((DOCS / "shared").rglob("spec.md")))

        match = re.search(r"backend — (\d+) домена?, общий слой — (\d+)", self.readme)
        self.assertIsNotNone(match, "в README нет строки о числе доменов")
        self.assertEqual((int(match.group(1)), int(match.group(2))), (backend, shared))


if __name__ == "__main__":
    unittest.main()
