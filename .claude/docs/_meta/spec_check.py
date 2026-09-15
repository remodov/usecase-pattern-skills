#!/usr/bin/env python3
"""Гейт корпуса: форма требований, адресация, гейты, синхронность сводных блоков
и согласованность с реестром мигрированных доменов.

Запуск: python3 .claude/docs/_meta/spec_check.py [docs_dir]
Exit 1 при находках.
"""
import pathlib
import re
import sys
from pathlib import Path

import spec_format

DOCS = Path(sys.argv[1] if len(sys.argv) > 1 else ".claude/docs")
REGISTRY = DOCS / "_meta" / "migrated-domains.md"
TRACKS = ("backend", "frontend", "e2e")


def _relative(path):
    return path.relative_to(DOCS).as_posix()


def check_registry(docs, migrated):
    problems = []
    declared = set(migrated)
    found = {_relative(path.parent) for path in sorted(docs.glob("**/spec.md"))}

    for domain in sorted(declared - found):
        problems.append(f"{domain}: в реестре есть, а spec.md нет — либо мигрируй домен, либо убери строку")

    for domain in sorted(found - declared):
        problems.append(f"{domain}/spec.md: домена нет в _meta/migrated-domains.md — гейт его не проверяет")

    for domain in sorted(declared & found):
        for leftover in sorted((docs / domain).glob("*-rules.md")):
            problems.append(
                f"{_relative(leftover)}: домен мигрирован, а старый rules-индекс остался — "
                "два источника правды в одном каталоге"
            )

    return problems


migrated = spec_format.parse_migrated(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else []
def check_changes(root, specs):
    """Каталог изменения: предложение, задачи и дельта — и все на месте.

    Дельта — это кусок будущей спеки, а не пересказ словами: при слиянии её
    переносят как есть. Поэтому проверяем не только наличие файлов, но и что
    дельта называет существующий spec.md и что раздел «Добавлено» написан
    в той же форме, что корпус.
    """
    problems = []
    changes = root / "openspec" / "changes"

    if not changes.is_dir():
        return problems

    # Каталоги изменений лежат вне .claude/docs, поэтому путь считаем от корня
    # репозитория: _relative умеет только «относительно корпуса».
    def откорня(path):
        try:
            return str(Path(path).resolve().relative_to(root.resolve()))
        except ValueError:
            return str(path)

    known = {str(Path(spec.file)) for spec in specs}
    known_ids = {
        requirement.meta["ID"]
        for spec in specs
        for requirement in spec.requirements
        if "ID" in requirement.meta
    }

    for change in sorted(p for p in changes.iterdir() if p.is_dir()):
        if change.name == "archive":
            continue

        for required in ("proposal.md", "tasks.md"):
            if not (change / required).exists():
                problems.append(f"{откорня(change)}: нет {required}")

        deltas = sorted(change.glob("delta*.md")) + sorted(change.glob("specs/**/*.md"))

        if not deltas:
            # Изменение без дельты бывает законным — правка инструментов, сборки,
            # документации. Но это должно быть сказано вслух и с причиной, иначе
            # забытая дельта не отличается от намеренно отсутствующей.
            proposal = change / "proposal.md"
            причина = ""

            if proposal.exists():
                for line in proposal.read_text(encoding="utf-8").splitlines():
                    if line.strip().startswith("Дельты нет:"):
                        причина = line.split(":", 1)[1].strip()

            if not причина:
                problems.append(
                    f"{откорня(change)}: нет дельты — изменение без неё нечего вливать в спеку. "
                    "Если требования не меняются, скажи это в proposal.md строкой "
                    "«Дельты нет: <причина>»"
                )

            continue

        for delta in deltas:
            source = delta.read_text(encoding="utf-8")
            targets = [line for line in source.splitlines() if "spec.md" in line]

            if not targets:
                problems.append(f"{откорня(delta)}: дельта не называет файл спеки")
            else:
                # В дельте путь пишут от корня репозитория или от каталога корпуса,
                # а spec.file — абсолютный. Сравниваем по хвосту, иначе честная
                # ссылка выглядит выдуманной.
                упомянуты = re.findall(r"[\w./-]*spec\.md", " ".join(targets))
                нашлось = any(
                    known_path.replace("\\", "/").endswith(упоминание.lstrip("./"))
                    for known_path in known
                    for упоминание in упомянуты
                )

                if not нашлось:
                    problems.append(f"{откорня(delta)}: названный файл спеки не найден в корпусе")

            if "## Добавлено" in source and "### Requirement:" not in source:
                problems.append(
                    f"{откорня(delta)}: раздел «Добавлено» без «### Requirement:» — "
                    "при слиянии такое переносят руками и теряют поля"
                )

            # «Изменено», «Удалено» и «Переименовано» правят то, что уже есть
            # в спеке. Если такого ID там нет, дельту некуда приложить — и
            # узнаётся это обычно при слиянии, когда автор уже забыл подробности.
            РАЗДЕЛЫ = ("## Добавлено", "## Изменено", "## Удалено", "## Переименовано")

            def кусок(раздел):
                if раздел not in source:
                    return ""

                хвост = source.split(раздел, 1)[1]

                for следующий in РАЗДЕЛЫ:
                    if следующий != раздел and следующий in хвост:
                        хвост = хвост.split(следующий, 1)[0]

                return хвост

            изменено = кусок("## Изменено")

            if изменено.strip():
                # Слияние — это замена блока целиком, а не наложение патча:
                # «было/стало» по одному полю руками не вливается.
                if "### Requirement:" not in изменено:
                    problems.append(
                        f"{откорня(delta)}: «Изменено» без «### Requirement:» — требование "
                        "переносится целиком, вместе с уцелевшими сценариями, а не кусками"
                    )

                for ident in re.findall(r"^\*\*ID\*\*:\s*(\S+)\s*$", изменено, re.MULTILINE):
                    if ident not in known_ids:
                        problems.append(
                            f"{откорня(delta)}: «{ident}» — такого требования нет в корпусе, "
                            "«Изменено» правит то, чего не существует"
                        )

            for header in re.findall(r"^###\s+([\w./-]+/[\w./-]+)\s*$", кусок("## Удалено"),
                                     re.MULTILINE):
                if header.startswith("<") or header not in known_ids:
                    problems.append(
                        f"{откорня(delta)}: «{header}» — такого требования нет в корпусе, "
                        "«Удалено» убирает то, чего не существует"
                    )

            # Переименование применяется первым: если источника уже нет, а цель
            # на месте — считаем слитым; если нет ни того, ни другого — поломка.
            переименовано = кусок("## Переименовано")
            froms = re.findall(r"^-\s*FROM:\s*`?([\w./-]+/[\w./-]+)`?\s*$", переименовано,
                               re.MULTILINE)
            tos = re.findall(r"^-\s*TO:\s*`?([\w./-]+/[\w./-]+)`?\s*$", переименовано,
                             re.MULTILINE)

            for источник, цель in zip(froms, tos):
                if источник not in known_ids and цель not in known_ids:
                    problems.append(
                        f"{откорня(delta)}: «{источник}» — переименовывать нечего, "
                        "такого требования в корпусе нет"
                    )

    archive = changes / "archive"

    if archive.is_dir():
        for change in sorted(p for p in archive.iterdir() if p.is_dir()):
            tasks = change / "tasks.md"

            if tasks.exists() and "- [ ]" in tasks.read_text(encoding="utf-8"):
                problems.append(
                    f"{откорня(change)}: в архиве неотмеченные задачи — "
                    "изменение закрыли, не доделав"
                )

    return problems


specs = spec_format.collect_specs(DOCS)
languages = spec_format.collect_languages(DOCS)

def check_dangling_references(docs, migrated, skills_dir):
    """Мигрированный домен потерял <domain>-rules.md и <domain>-style-guide.md —
    ссылки на них из других доменов и скиллов ведут в пустоту."""
    problems = []
    stale = {}

    for domain in migrated:
        name = domain.split("/")[-1]

        # Файл считается исчезнувшим, только если его действительно нет: пока домен
        # в реестре, но ещё не переехал, ссылки на него законны.
        for filename in (f"{name}-rules.md", f"{name}-style-guide.md"):
            if not any((docs / domain).glob(f"**/{filename}")):
                stale[filename] = domain

    if not stale:
        return problems

    files = sorted(docs.glob("**/*.md"))

    if skills_dir.is_dir():
        files += sorted(skills_dir.glob("**/*.md"))

    for path in files:
        text = path.read_text(encoding="utf-8")

        for filename, domain in stale.items():
            # Сравниваем по границе имени: «python-test-strategy-rules.md» содержит
            # «test-strategy-rules.md» подстрокой, но ссылкой на него не является.
            if re.search(rf"(?<![\w-]){re.escape(filename)}", text):
                problems.append(
                    f"{path}: ссылается на `{filename}`, которого больше нет — "
                    f"домен {domain} мигрирован, ссылку вести на `{domain}/spec.md`"
                )

    return problems


def check_domain_stats(specs):
    """Строка «Чем держится домен» пересчитывается генератором. Если она разошлась
    с требованиями, читателю обещают не ту долю ревью — а именно ради этой доли
    строку и завели."""
    problems = []

    for spec in specs:
        source = pathlib.Path(spec.file).read_text(encoding="utf-8")

        if spec_format.STATS_BLOCK_START not in source:
            problems.append(f"{spec.file}: нет блока «Чем держится домен» — заведи spec_sync.py")
            continue

        current = spec_format.extract_block(
            source, spec_format.STATS_BLOCK_START, spec_format.STATS_BLOCK_END
        )

        if current.strip() != spec_format.render_domain_stats(spec).strip():
            problems.append(
                f"{spec.file}: блок «Чем держится домен» разошёлся с требованиями — "
                "пересобери командой python3 .claude/docs/_meta/spec_sync.py"
            )

    return problems


WHY_MIN_LENGTH = 40


def check_why(specs):
    """Поле «Почему» обязательно: формулировка говорит, что обязано быть верно,
    а последствие — что случится, если этого не будет. Без него требование
    оспаривают на каждом ревью, потому что не видно, что стоит на кону."""
    problems = []

    for spec in specs:
        for requirement in spec.requirements:
            where = f"{spec.file}:{requirement.line} «{requirement.name}»"
            why = requirement.meta.get("Почему")

            if not why:
                problems.append(f"{where}: нет поля **Почему** — не сказано, что ломается без этого требования")
            elif len(why) < WHY_MIN_LENGTH:
                problems.append(
                    f"{where}: «Почему» короче {WHY_MIN_LENGTH} символов — "
                    "последствие названо формально"
                )

    return problems


def check_human_intro(specs):
    """Раздел Purpose обязан нести врезку «Что здесь главное» — три-пять фраз
    простым языком. Без неё домен читается как свод формулировок: чтобы понять,
    ради чего он, надо прочесть все требования подряд."""
    problems = []

    for spec in specs:
        source = pathlib.Path(spec.file).read_text(encoding="utf-8")
        head = source.split("## Requirements")[0]

        if "**Что здесь главное**" not in head:
            problems.append(
                f"{spec.file}: в Purpose нет врезки «Что здесь главное» — "
                "домен читается только целиком"
            )
            continue

        bullets = [
            line for line in head.split("**Что здесь главное**", 1)[1].split("\n")
            if line.startswith("- ")
        ]

        if len(bullets) < 3:
            problems.append(
                f"{spec.file}: во врезке «Что здесь главное» {len(bullets)} пункта — "
                "нужно хотя бы три, иначе это не вход, а заголовок"
            )

    return problems


def check_doc_links(docs, skills_dir):
    """Ссылка на файл корпуса ведёт в никуда. Ловит два случая: путь вида
    `.claude/docs/<...>.md`, которого нет, и обещанный требованием справочник
    `references/<...>.md`, которого нет рядом со спекой. Переименование файла
    без правки ссылок иначе замечает только читатель, открывший её."""
    problems = []
    existing = {str(f.relative_to(docs)) for f in docs.rglob("*.md")}

    files = sorted(docs.rglob("*.md"))

    if skills_dir.is_dir():
        files += sorted(skills_dir.rglob("*.md"))

    for f in files:
        text = f.read_text(encoding="utf-8")

        for match in re.finditer(r"\.claude/docs/([A-Za-z0-9/._-]+\.md)", text):
            if match.group(1) not in existing:
                problems.append(f"{f}: ссылка на `.claude/docs/{match.group(1)}` — файла нет")

        if f.name != "spec.md":
            continue

        for match in re.finditer(r"`(references/[A-Za-z0-9/._-]+\.md)`", text):
            if not (f.parent / match.group(1)).exists():
                problems.append(f"{f}: обещан справочник `{match.group(1)}` — файла нет")

    return problems


def check_empty_reference_dirs(docs):
    """Пустой `references/` — обещание без содержания: домен выглядит так, будто
    у него есть примеры, а открывать нечего."""
    return [
        f"{d.relative_to(docs)}: каталог `references/` пуст — либо наполнить, либо удалить"
        for d in docs.rglob("references")
        if d.is_dir() and not any(d.rglob("*.md"))
    ]


def check_gate_catalogue(docs, specs):
    """Собственные проверки методологии (script:*, archunit:* и аналоги) обязаны
    быть описаны в каталоге гейтов — иначе требование ссылается на проверку,
    которой никто не напишет."""
    catalogue_path = docs / "_meta" / "project-gates.md"

    if not catalogue_path.exists():
        return []

    catalogue = catalogue_path.read_text(encoding="utf-8")
    problems = []
    OWN_KINDS = ("script", "archunit", "import-linter", "dependency-cruiser")

    for spec in specs:
        for requirement in spec.requirements:
            where = f"{spec.file}:{requirement.line} «{requirement.name}»"

            for gates in spec_format.parse_gate(requirement.meta.get("Гейт", "нет")).values():
                for gate in gates:
                    kind = gate.split(":", 1)[0]

                    if kind in OWN_KINDS and gate not in catalogue:
                        problems.append(
                            f"{where}: гейта «{gate}» нет в каталоге _meta/project-gates.md — "
                            "проверка, которую никто не описал, гейтом не является"
                        )

    return problems


problems = check_registry(DOCS, migrated)
problems.extend(check_dangling_references(DOCS, migrated, DOCS.parent / "skills"))
problems.extend(check_changes(DOCS.parent.parent, specs))

for spec in specs:
    problems.extend(spec_format.check_structure(spec))

problems.extend(spec_format.check_addressing(specs))
problems.extend(spec_format.check_gates(specs, languages))
problems.extend(check_gate_catalogue(DOCS, specs))
problems.extend(check_doc_links(DOCS, DOCS.parent / "skills"))
problems.extend(check_empty_reference_dirs(DOCS))
problems.extend(check_domain_stats(specs))
problems.extend(check_human_intro(specs))
problems.extend(check_why(specs))

for track in TRACKS:
    index = DOCS / track / "_index.md"
    track_specs = spec_format.collect_specs(DOCS / track)

    if not track_specs or not index.exists():
        continue

    problems.extend(
        spec_format.check_block(
            index.read_text(encoding="utf-8"),
            spec_format.render_requirements(track_specs),
            spec_format.BLOCK_START,
            spec_format.BLOCK_END,
            f"пересобери командой python3 {REGISTRY.parent.as_posix()}/spec_sync.py",
        )
    )

if problems:
    print("spec_check — найдены проблемы:", file=sys.stderr)

    for problem in problems:
        print(f"  {problem}", file=sys.stderr)

    print(
        "\nТребование обещает гейт, которого нет, или корпус разошёлся с реестром. "
        "Поправь требование или заведи гейт.",
        file=sys.stderr,
    )
    sys.exit(1)

requirements = sum(len(spec.requirements) for spec in specs)
print(f"spec_check — спеки сходятся (доменов: {len(specs)}, требований: {requirements})")
