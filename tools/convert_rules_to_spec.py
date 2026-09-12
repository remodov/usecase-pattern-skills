#!/usr/bin/env python3
"""Черновой конвертер старого rules-индекса в каркас openspec-требований.

Переносит механическое: разделы, коды, формулировки. Поля **Гейт**, **Покрытие**,
**Не ловит** и сценарии оставляет пустыми — их пишет человек, и spec_check.py
краснеет ровно по этому списку.

Запуск: python3 tools/convert_rules_to_spec.py .claude/docs/backend/pg-migrations/pg-migrations-rules.md pg-migrations
"""
import re
import sys
from dataclasses import dataclass

SECTION = re.compile(r"^##\s+\d+\.\s+(.+?)\s*$")
MUST_NOT = re.compile(r"^\*\*MUST NOT:\*\*\s*$")
MUST = re.compile(r"^\*\*MUST:\*\*\s*$")
RULE = re.compile(r"^-\s+\*\*([A-Z][A-Z0-9-]*)\.\*\*\s+(.+)$")

TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e",
    "ю": "yu", "я": "ya",
}
ID_WORDS = 5


@dataclass
class Rule:
    code: str
    section: str
    text: str
    is_antipattern: bool


def parse_rules(source):
    rules = []
    section = ""
    antipattern = False

    for raw in source.split("\n"):
        line = raw.strip()

        if line.startswith(">"):
            continue

        header = SECTION.match(line)

        if header:
            section = header.group(1)
            antipattern = False
            continue

        if MUST_NOT.match(line):
            antipattern = True
            continue

        if MUST.match(line):
            antipattern = False
            continue

        rule = RULE.match(line)

        if rule:
            rules.append(Rule(code=rule.group(1), section=section, text=rule.group(2), is_antipattern=antipattern))

    return rules


def make_id(area, text):
    plain = re.sub(r"`[^`]*`", " ", text).lower()
    letters = "".join(TRANSLIT.get(char, char) for char in plain)
    words = [word for word in re.findall(r"[a-z0-9]+", letters) if len(word) > 1]

    return f"{area}/{'-'.join(words[:ID_WORDS]) or 'untitled'}"


def render(rules, area):
    lines = [
        f"# {area}",
        "",
        "## Purpose",
        "",
        "TODO: одно-два предложения — про что этот домен.",
        "",
        "## Requirements",
        "",
    ]

    for rule in rules:
        modality = "SHALL NOT" if rule.is_antipattern else "SHALL"
        lines += [
            f"### Requirement: {rule.section} — {rule.code}",
            "",
            f"TODO переформулировать через {modality}: {rule.text}",
            "",
            f"**ID**: {make_id(area, rule.text)}",
            f"**Код**: {rule.code}",
            "**Гейт**:",
            "**Покрытие**:",
            "**Не ловит**:",
            "",
            "#### Scenario: TODO",
            "",
            "- **WHEN** TODO",
            "- **THEN** TODO",
            "",
        ]

    return "\n".join(lines)


if __name__ == "__main__":
    source = open(sys.argv[1], encoding="utf-8").read()
    print(render(parse_rules(source), sys.argv[2]))
