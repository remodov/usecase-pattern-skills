#!/usr/bin/env python3
"""Парсер и проверки openspec-требований корпуса методологии.

Библиотека без побочных эффектов: читают файлы и печатают вызывающие скрипты
(spec_check.py, spec_sync.py). Формат требования — authoring-contract.md §3.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

FENCE = re.compile(r"^(```|~~~)")
PURPOSE = re.compile(r"^##\s+Purpose\s*$", re.IGNORECASE)
REQUIREMENTS = re.compile(r"^##\s+Requirements\s*$", re.IGNORECASE)
REQUIREMENT = re.compile(r"^###\s+Requirement:\s*(.+?)\s*$", re.IGNORECASE)
SCENARIO = re.compile(r"^####\s+(.+?)\s*$")
META = re.compile(r"^\*\*([^*]+)\*\*:\s*(.*)$")
SHALL = re.compile(r"\b(SHALL|MUST)\b")


@dataclass
class Scenario:
    name: str
    steps: list = field(default_factory=list)


@dataclass
class Requirement:
    name: str
    line: int
    body: str = ""
    meta: dict = field(default_factory=dict)
    scenarios: list = field(default_factory=list)


@dataclass
class ParsedSpec:
    file: str
    has_purpose: bool = False
    has_requirements: bool = False
    unbalanced_fence: bool = False
    requirements: list = field(default_factory=list)


def strip_fences(source):
    """Гасит строки внутри блоков кода: пример требования в справочнике не должен
    попадать в разбор. Второе значение — признак незакрытого блока."""
    inside = False
    lines = []

    for raw in source.lstrip("﻿").replace("\r\n", "\n").split("\n"):
        if FENCE.match(raw.strip()):
            inside = not inside
            lines.append("")
            continue

        lines.append("" if inside else raw)

    return lines, inside


def parse_spec(file, source):
    spec = ParsedSpec(file=file)
    lines, spec.unbalanced_fence = strip_fences(source)
    current = None
    scenario = None

    for index, raw in enumerate(lines, start=1):
        line = raw.strip()

        if PURPOSE.match(line):
            spec.has_purpose = True
            continue

        if REQUIREMENTS.match(line):
            spec.has_requirements = True
            continue

        header = REQUIREMENT.match(line)

        if header:
            current = Requirement(name=header.group(1), line=index)
            spec.requirements.append(current)
            scenario = None
            continue

        if current is None or not line:
            continue

        scenario_header = SCENARIO.match(line)

        if scenario_header:
            scenario = Scenario(name=scenario_header.group(1))
            current.scenarios.append(scenario)
            continue

        if scenario is not None:
            scenario.steps.append(line)
            continue

        meta = META.match(line)

        if meta:
            current.meta[meta.group(1).strip()] = meta.group(2).strip()
            continue

        current.body = f"{current.body} {line}".strip()

    return spec


def check_structure(spec):
    problems = []

    if not spec.has_purpose:
        problems.append(f"{spec.file}: нет раздела «## Purpose»")

    if not spec.has_requirements:
        problems.append(f"{spec.file}: нет раздела «## Requirements»")

    if not spec.requirements:
        problems.append(f"{spec.file}: нет ни одного «### Requirement:»")

    if spec.unbalanced_fence:
        problems.append(
            f"{spec.file}: незакрытый блок кода — всё после него парсер не читает, "
            "и требования из хвоста файла молча исчезают из сводной таблицы"
        )

    for requirement in spec.requirements:
        where = f"{spec.file}:{requirement.line} «{requirement.name}»"

        if not SHALL.search(requirement.body):
            problems.append(f"{where}: в теле требования нет SHALL или MUST — в заголовке они не считаются")

        if not requirement.scenarios:
            problems.append(f"{where}: нет ни одного «#### Scenario:»")

        for scenario in requirement.scenarios:
            has_when = any("**WHEN**" in step for step in scenario.steps)
            has_then = any("**THEN**" in step for step in scenario.steps)

            if not has_when or not has_then:
                problems.append(f"{where}, сценарий «{scenario.name}»: нужны и **WHEN**, и **THEN**")

    return problems


ID_SHAPE = re.compile(r"^[a-z0-9-]+/[a-z0-9-]+$")
# Точки в номере — форма кодов стиля (JS-2.6.1), а не опечатка.
CODE_SHAPE = re.compile(r"^[A-Z][A-Z0-9]*(-[A-Z0-9]+[a-z]?(\.[A-Z0-9]+)*)+$")


def _area(file):
    """Область требования — имя каталога, в котором лежит spec.md."""
    parts = file.split("/")

    return parts[-2] if len(parts) > 1 else ""


def _codes(requirement):
    """Поле **Код** — один код или список через запятую: антипаттерн и его
    положительная формулировка сливаются в одно требование, но оба старых кода
    обязаны находиться грепом."""
    raw = requirement.meta.get("Код", "")

    return [code.strip() for code in raw.split(",") if code.strip()]


def check_addressing(specs):
    problems = []
    seen_ids = {}
    seen_codes = {}

    for spec in specs:
        area = _area(spec.file)

        for requirement in spec.requirements:
            where = f"{spec.file}:{requirement.line} «{requirement.name}»"
            ident = requirement.meta.get("ID")

            if ident is None:
                problems.append(f"{where}: нет поля **ID**")
                continue

            if not ID_SHAPE.match(ident):
                problems.append(
                    f"{where}: **ID** «{ident}» не в форме <область>/<имя> "
                    "строчными латинскими буквами через дефис"
                )
                continue

            if not ident.startswith(f"{area}/"):
                problems.append(
                    f"{where}: **ID** «{ident}» не начинается с области «{area}», в каталоге которой лежит файл"
                )

            if ident in seen_ids:
                problems.append(f"{where}: **ID** «{ident}» уже занят в {seen_ids[ident]}")

            seen_ids[ident] = spec.file

            for code in _codes(requirement):
                if not CODE_SHAPE.match(code):
                    problems.append(f"{where}: **Код** «{code}» не в форме <PREFIX>-<N> заглавными латинскими")
                    continue

                if code in seen_codes:
                    problems.append(f"{where}: **Код** «{code}» уже занят требованием {seen_codes[code]}")

                seen_codes[code] = ident

    return problems


def collect_ids(specs):
    return [
        requirement.meta["ID"]
        for spec in specs
        for requirement in spec.requirements
        if "ID" in requirement.meta
    ]


def collect_codes(specs):
    return {
        code: requirement.meta["ID"]
        for spec in specs
        for requirement in spec.requirements
        if "ID" in requirement.meta
        for code in _codes(requirement)
    }


GATE_KINDS = frozenset({
    "checkstyle", "archunit", "errorprone", "spotbugs", "ruff", "mypy",
    "golangci-lint", "eslint", "import-linter", "dependency-cruiser",
    "squawk", "gitleaks", "trivy", "dependency-check",
    "gradle", "script", "test", "ci", "ревью",
})
LANGS = ("java", "python", "go", "node")
COVERAGE = ("полное", "частичное", "нет")
GAP_MIN_LENGTH = 20
NO_GATE = "нет"
REVIEW_GATE = "ревью"
LANG_CLAUSE = re.compile(r"^(java|python|go|node):\s*(.+)$")


def parse_gate(value):
    """Поле **Гейт** → карта «язык → гейты». Ключ «*» — форма без языковой оси."""
    if value.strip() == NO_GATE:
        return {}

    gates = {}

    for clause in (item.strip() for item in value.split("·")):
        if not clause:
            continue

        match = LANG_CLAUSE.match(clause)
        lang = match.group(1) if match else "*"
        body = match.group(2) if match else clause
        gates.setdefault(lang, []).extend(item.strip() for item in body.split(",") if item.strip())

    return gates


def _check_gate_value(where, gate):
    kind, separator, value = gate.partition(":")

    if kind == "ревью" and not separator:
        return []

    if not separator or not value.strip():
        return [
            f"{where}: гейт «{gate}» без значения — нужен вид "
            f"{', '.join(sorted(GATE_KINDS))} с двоеточием и значением"
        ]

    if kind not in GATE_KINDS:
        return [f"{where}: неизвестный вид гейта «{kind}»"]

    return []


def check_gates(specs, languages):
    problems = []

    for spec in specs:
        area = _area(spec.file)
        area_langs = languages.get(area, [])

        for requirement in spec.requirements:
            where = f"{spec.file}:{requirement.line} «{requirement.name}»"
            coverage = requirement.meta.get("Покрытие")
            gap = requirement.meta.get("Не ловит", "")
            raw = requirement.meta.get("Гейт")

            if coverage not in COVERAGE:
                problems.append(f"{where}: поле **Покрытие** обязано быть одним из: {', '.join(COVERAGE)}")

            if coverage != "полное" and len(gap) < GAP_MIN_LENGTH:
                problems.append(
                    f"{where}: покрытие не полное — поле **Не ловит** обязано назвать нарушение, "
                    f"проходящее гейт. Прочерк и строка короче {GAP_MIN_LENGTH} символов описанием "
                    "дыры не считаются; на большее проверка не смотрит, конкретность держится ревью"
                )

            if raw is None:
                problems.append(f"{where}: нет поля **Гейт**")
                continue

            gates = parse_gate(raw)

            if not gates:
                if coverage != "нет":
                    problems.append(f"{where}: гейта нет, значит **Покрытие** обязано быть «нет»")

                continue

            machine = {
                lang: [gate for gate in lang_gates if gate != REVIEW_GATE]
                for lang, lang_gates in gates.items()
            }
            has_machine = any(lang_gates for lang_gates in machine.values())

            if not has_machine:
                if coverage != "нет":
                    problems.append(
                        f"{where}: машинного гейта нет — «{REVIEW_GATE}» его не заменяет, "
                        "**Покрытие** обязано быть «нет»"
                    )

                continue

            if coverage == "нет":
                problems.append(
                    f"{where}: **Покрытие** «нет» при названном гейте «{raw}» — либо гейт что-то "
                    "ловит и покрытие «частичное», либо он не ловит ничего и в поле **Гейт** пишется «нет»"
                )

            unnamed = [lang for lang in area_langs if lang not in gates] if "*" not in gates else []

            for lang in unnamed:
                problems.append(
                    f"{where}: язык «{lang}» области есть в references/, но в поле **Гейт** не назван — "
                    "покрытие считается по худшему языку, умолчание его завышает"
                )

            # Про языки, которые не названы вовсе, уже сказано выше — не дублируем
            # менее точной формулировкой про ревью.
            # Гейт, объявленный без языковой оси, применяется ко всем языкам:
            # проверка конфигурации или манифеста не зависит от языка сервиса.
            neutral = bool(machine.get("*"))

            if not unnamed and not neutral and coverage == "полное" and not all(
                machine.get(lang) for lang in (area_langs or ["*"])
            ):
                problems.append(
                    f"{where}: часть языков держится ревью, поэтому покрытие не может быть «полное» — "
                    "оно считается по худшему языку"
                )

            for lang_gates in gates.values():
                for gate in lang_gates:
                    problems.extend(_check_gate_value(where, gate))

    return problems



STATS_BLOCK_START = "<!-- BEGIN:ucp-domain-stats -->"
STATS_BLOCK_END = "<!-- END:ucp-domain-stats -->"


def render_domain_stats(spec):
    """Строка «чем держится домен» — считается по требованиям, руками не пишется.

    Читателю она отвечает на вопрос, который иначе требует прочесть весь файл:
    сколько здесь правил и какая доля из них не проверяется ничем, кроме
    внимательности."""
    total = len(spec.requirements)
    review = sum(1 for r in spec.requirements if r.meta.get("Покрытие") == "нет")
    machine = total - review
    share = round(review / total * 100) if total else 0

    return "\n".join([
        STATS_BLOCK_START,
        f"**Чем держится домен.** Требований — {total}; проверкой закрыто {machine}, "
        f"держится ревью {review} ({share} %).",
        STATS_BLOCK_END,
    ])


BLOCK_START = "<!-- BEGIN:ucp-requirements -->"
BLOCK_END = "<!-- END:ucp-requirements -->"
CODE_BLOCK_START = "<!-- BEGIN:ucp-code-map -->"
CODE_BLOCK_END = "<!-- END:ucp-code-map -->"


def render_requirements(specs):
    rows = sorted(
        (
            requirement.meta.get("ID", ""),
            f"| [{requirement.meta.get('ID', '—')}]({spec.file}) — {requirement.name} "
            f"| {requirement.meta.get('Гейт', 'нет')} | {requirement.meta.get('Покрытие', '—')} |",
        )
        for spec in specs
        for requirement in spec.requirements
    )

    return "\n".join([
        BLOCK_START,
        "",
        "| Требование | Гейт | Покрытие |",
        "| --- | --- | --- |",
        *[row for _, row in rows],
        "",
        BLOCK_END,
    ])


def render_code_map(specs):
    rows = sorted(
        (code, f"| `{code}` | `{requirement.meta['ID']}` | {_area(spec.file)} |")
        for spec in specs
        for requirement in spec.requirements
        if "ID" in requirement.meta
        for code in _codes(requirement)
    )

    return "\n".join([
        CODE_BLOCK_START,
        "",
        "| Код | Требование | Область |",
        "| --- | --- | --- |",
        *[row for _, row in rows],
        "",
        CODE_BLOCK_END,
    ])


def extract_block(source, start, end):
    first = source.find(start)
    last = source.find(end)

    if first == -1 or last == -1 or last < first:
        return None

    return source[first:last + len(end)]


def replace_block(source, block, start, end):
    first = source.find(start)
    last = source.find(end)

    if first == -1 or last == -1 or last < first:
        raise ValueError(f"нет маркеров {start} … {end}")

    return f"{source[:first]}{block}{source[last + len(end):]}"


def normalize(block):
    lines = []

    for raw in block.split("\n"):
        line = re.sub(r"\s+", " ", raw.strip())
        line = re.sub(r"\s*\|\s*", "|", line)

        if line:
            lines.append(line)

    return "\n".join(lines)


def check_block(source, expected, start, end, hint):
    block = extract_block(source, start, end)

    if block is None:
        return [f"нет маркеров {start} … {end}"]

    if normalize(block) != normalize(expected):
        return [f"блок разошёлся с требованиями — {hint}"]

    return []


MIGRATED_ITEM = re.compile(r"^-\s+`([^`]+)`\s*$")


def parse_migrated(source):
    return [
        match.group(1)
        for match in (MIGRATED_ITEM.match(line.strip()) for line in source.split("\n"))
        if match
    ]


def collect_specs(docs_dir):
    return [
        parse_spec(path.as_posix(), path.read_text(encoding="utf-8"))
        for path in sorted(Path(docs_dir).glob("**/spec.md"))
    ]


def collect_languages(docs_dir):
    languages = {}

    for references in sorted(Path(docs_dir).glob("**/references")):
        area = references.parent.name
        languages[area] = [
            entry.name for entry in sorted(references.iterdir()) if entry.is_dir() and entry.name in LANGS
        ]

    return languages
