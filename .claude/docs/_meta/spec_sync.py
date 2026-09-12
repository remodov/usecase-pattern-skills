#!/usr/bin/env python3
"""Пересобирает сводные блоки корпуса: таблицу требований в docs/<track>/_index.md
и карту «код ↔ требование» в docs/_meta/rule-code-registry.md.

Запуск: python3 .claude/docs/_meta/spec_sync.py [docs_dir]
"""
import sys
from pathlib import Path

import spec_format

DOCS = Path(sys.argv[1] if len(sys.argv) > 1 else ".claude/docs")
TRACKS = ("backend", "frontend", "shared", "e2e")
REGISTRY = DOCS / "_meta" / "rule-code-registry.md"


def _write_block(path, block, start, end):
    if not path.exists():
        return f"✗ {path}: файла нет — блок собирать некуда"

    source = path.read_text(encoding="utf-8")

    try:
        updated = spec_format.replace_block(source, block, start, end)
    except ValueError as error:
        return f"✗ {path}: {error}"

    if updated == source:
        return f"= {path}: блок уже совпадает"

    path.write_text(updated, encoding="utf-8")

    return f"✓ {path}: блок пересобран"


messages = []
total = 0

for track in TRACKS:
    track_dir = DOCS / track

    if not track_dir.is_dir():
        continue

    specs = spec_format.collect_specs(track_dir)

    if not specs:
        continue

    total += sum(len(spec.requirements) for spec in specs)
    messages.append(
        _write_block(
            track_dir / "_index.md",
            spec_format.render_requirements(specs),
            spec_format.BLOCK_START,
            spec_format.BLOCK_END,
        )
    )

for spec in spec_format.collect_specs(DOCS):
    path = Path(spec.file)
    source = path.read_text(encoding="utf-8")
    block = spec_format.render_domain_stats(spec)

    if spec_format.STATS_BLOCK_START in source:
        messages.append(
            _write_block(path, block, spec_format.STATS_BLOCK_START, spec_format.STATS_BLOCK_END)
        )
    else:
        # Блока ещё нет — ставим его в конец Purpose, перед разделом требований.
        updated = source.replace("\n## Requirements", f"\n{block}\n\n## Requirements", 1)
        if updated != source:
            path.write_text(updated, encoding="utf-8")
            messages.append(f"+ {path}: блок статистики заведён")

all_specs = spec_format.collect_specs(DOCS)
messages.append(
    _write_block(
        REGISTRY,
        spec_format.render_code_map(all_specs),
        spec_format.CODE_BLOCK_START,
        spec_format.CODE_BLOCK_END,
    )
)

print("\n".join(messages))
print(f"spec_sync — требований в корпусе: {total}")
sys.exit(1 if any(message.startswith("✗") for message in messages) else 0)
