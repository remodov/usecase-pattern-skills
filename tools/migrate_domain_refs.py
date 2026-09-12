#!/usr/bin/env python3
"""Механическая часть переезда домена: заменить старые коды правил на ID
требований по всему корпусу и починить пути на rules-индекс и style-guide.

Запуск: python3 tools/migrate_domain_refs.py <domain-dir> <code-regex> [--refs-langs]

  domain-dir   путь до каталога домена, например .claude/docs/backend/pg-types
  code-regex   как выглядит старый код, например 'PG-T-\\d+X?'
  --refs-langs у домена справочники разложены по языкам (references/<lang>/)

Содержательное — поля «Гейт», «Покрытие», «Не ловит» и сценарии — скрипт
не трогает: их пишет человек.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, ".claude/docs/_meta")
import spec_format

domain_dir = Path(sys.argv[1])
code_pattern = sys.argv[2]
per_lang = "--refs-langs" in sys.argv

domain = domain_dir.name
spec_path = domain_dir / "spec.md"

if not spec_path.exists():
    sys.exit(f"нет {spec_path} — сначала напиши требования, потом чини ссылки")

# Карта строится по всему корпусу: код мигрированного домена мог переехать
# в требование соседнего (так PG-I-019 живёт в pg-migrations/index-concurrently).
code_to_id = spec_format.collect_codes(spec_format.collect_specs(Path(".claude/docs")))

if not code_to_id:
    sys.exit("в корпусе нет ни одного поля **Код** — нечего перепривязывать")

CODE = re.compile(rf"`({code_pattern})`")
LIST_ITEM = re.compile(rf"^- `({code_pattern})`(?: / `({code_pattern})`)? ", re.MULTILINE)
FINDING = re.compile(rf"^(\[(?:критично|важно|замечание)\]) ({code_pattern}) ", re.MULTILINE)

targets = sorted(set(Path(".claude/docs").glob("**/*.md")) | set(Path(".claude/skills").glob("**/*.md")))
changed = []
unknown = set()


def to_id(code):
    if code not in code_to_id:
        unknown.add(code)

    return code_to_id.get(code, code)


for path in targets:
    text = path.read_text(encoding="utf-8")
    updated = LIST_ITEM.sub(
        lambda m: "- `{}` (`{}`) ".format(
            to_id(m.group(1)),
            "`, `".join(code for code in (m.group(1), m.group(2)) if code),
        ),
        text,
    )
    updated = CODE.sub(lambda m: f"`{to_id(m.group(1))}`", updated)
    updated = FINDING.sub(lambda m: f"{m.group(1)} {to_id(m.group(2))} ({m.group(2)}) ", updated)

    updated = (updated
               .replace(f"{domain}/{domain}-rules.md", f"{domain}/spec.md")
               .replace(f"`{domain}-rules.md`", f"`{domain}/spec.md`")
               .replace(f"../{domain}-rules.md", "../spec.md"))

    if per_lang:
        for lang in spec_format.LANGS:
            updated = updated.replace(
                f"{domain}/{lang}/{domain}-style-guide.md",
                f"{domain}/references/{lang}/{domain}-style-guide.md",
            )
    else:
        updated = updated.replace(
            f"{domain}/{domain}-style-guide.md",
            f"{domain}/references/{domain}-style-guide.md",
        )

    if updated != text:
        path.write_text(updated, encoding="utf-8")
        changed.append(path.as_posix())

print(f"{domain}: кодов в карте {len(code_to_id)}, файлов изменено {len(changed)}")

if unknown:
    print(f"  ⚠ коды без требования (проверь поле **Код**): {', '.join(sorted(unknown))}")
