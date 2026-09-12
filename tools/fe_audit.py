#!/usr/bin/env python3
"""Сверяет frontend-скиллы с эталонным репозиторием шаблонов.

Правила фронта живут не здесь, а в `<репозиторий шаблонов фронтенда>`. Наши скиллы
только ведут по ним — и потому обязаны совпадать: выдуманный идентификатор
требования отправляет читателя в никуда, а незакрытая область означает, что
часть требований шаблона не ведёт ни один скилл. Обе ошибки бесшумны.

Запуск:  python3 tools/fe_audit.py <путь-к-клону-frontend-templates>
"""
import pathlib
import re
import sys

SKILLS = pathlib.Path(".claude/skills")
SPEC_GLOB = "templates/next-ssr/openspec/specs/*/spec.md"
ID = re.compile(r"^\*\*ID\*\*:\s*(\S+)", re.M)
CITED = re.compile(r"`([a-z][a-z0-9-]*/[a-z0-9-]+)`")


def template_requirements(repo):
    found = {}

    for spec in sorted(repo.glob(SPEC_GLOB)):
        for match in ID.finditer(spec.read_text(encoding="utf-8")):
            found[match.group(1)] = spec.parent.name

    return found


def cited_requirements(areas):
    cited = {}

    for skill in sorted(SKILLS.glob("ucp-fe-*/SKILL.md")):
        for match in CITED.finditer(skill.read_text(encoding="utf-8")):
            requirement = match.group(1)

            if requirement.split("/")[0] in areas:
                cited.setdefault(requirement, set()).add(skill.parent.name)

    return cited


def audit(repo):
    real = template_requirements(repo)

    if not real:
        return [f"{repo}: требований не найдено — путь не похож на клон frontend-templates"]

    cited = cited_requirements({area for area in (r.split("/")[0] for r in real)})
    problems = []

    for requirement, skills in sorted(cited.items()):
        if requirement not in real:
            problems.append(
                f"{', '.join(sorted(skills))}: требования «{requirement}» в шаблоне нет — "
                "ссылка ведёт в никуда"
            )

    for requirement in sorted(set(real) - set(cited)):
        problems.append(
            f"требование «{requirement}» ({real[requirement]}) не ведёт ни один скилл ucp-fe-*"
        )

    return problems


def main():
    if len(sys.argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2

    problems = audit(pathlib.Path(sys.argv[1]))

    if problems:
        print("fe_audit — расхождение с эталонным репозиторием:", file=sys.stderr)

        for problem in problems:
            print(f"  {problem}", file=sys.stderr)

        return 1

    real = template_requirements(pathlib.Path(sys.argv[1]))
    print(f"fe_audit — скиллы совпадают с шаблоном (требований: {len(real)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
