#!/usr/bin/env python3
import argparse
import json
import re
import shlex
import sys
from pathlib import Path, PurePosixPath

REGISTRY = Path(__file__).with_name("agent-targets.json")
SUPPORT_LEVELS = {"native", "compatible", "skill-only"}
AGENT_FORMATS = {"markdown", "codex-toml"}
CODEX_MARKER = "# Managed by usecase-pattern-skills install.sh"


def load_registry(path=REGISTRY):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    targets = data.get("targets")
    if data.get("version") != 1 or not isinstance(targets, list):
        raise ValueError("Ожидался registry version 1 со списком targets")
    by_id = {}
    for target in targets:
        target_id = target.get("id")
        if not isinstance(target_id, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", target_id):
            raise ValueError(f"Некорректный target id: {target_id!r}")
        if target_id in by_id:
            raise ValueError(f"Дубликат target id: {target_id}")
        by_id[target_id] = target
        validate_target(target)
    return data


def validate_relative_path(value, field, allow_empty=False):
    if value is None and allow_empty:
        return
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field}: ожидался непустой относительный путь")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{field}: небезопасный путь {value!r}")


def validate_target(target):
    required = ["label", "support", "scope", "skills", "instructions", "template", "agents", "agent_format", "rules", "hooks", "mcp", "invocation"]
    missing = [field for field in required if field not in target]
    if missing:
        raise ValueError(f"{target['id']}: отсутствуют поля {', '.join(missing)}")
    if target["support"] not in SUPPORT_LEVELS:
        raise ValueError(f"{target['id']}: неизвестный support={target['support']!r}")
    if target["scope"] not in {"project", "home"}:
        raise ValueError(f"{target['id']}: неизвестный scope={target['scope']!r}")
    for field in ("skills", "agents", "rules", "instructions", "manifest"):
        if field in target:
            validate_relative_path(target[field], f"{target['id']}.{field}", allow_empty=field != "skills")
    if bool(target["instructions"]) != bool(target["template"]):
        raise ValueError(f"{target['id']}: instructions и template должны быть заданы вместе")
    if target["agent_format"] not in AGENT_FORMATS and target["agent_format"] is not None:
        raise ValueError(f"{target['id']}: неизвестный agent_format")
    if bool(target["agents"]) != bool(target["agent_format"]):
        raise ValueError(f"{target['id']}: agents и agent_format должны быть заданы вместе")
    for field in ("hooks", "mcp"):
        if not isinstance(target[field], bool):
            raise ValueError(f"{target['id']}.{field}: ожидался boolean")


def get_target(target_id, path=REGISTRY):
    registry = load_registry(path)
    for target in registry["targets"]:
        if target["id"] == target_id:
            return target
    known = ", ".join(target["id"] for target in registry["targets"])
    raise ValueError(f"Неизвестный target {target_id!r}. Доступно: {known}")


def resolve(base, relative):
    return str((Path(base) / PurePosixPath(relative)).resolve()) if relative else ""


def shell_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def print_target(target, project, home):
    asset_base = Path(home) if target["scope"] == "home" else Path(project)
    values = {
        "TARGET_ID": target["id"],
        "TARGET_LABEL": target["label"],
        "TARGET_SUPPORT": target["support"],
        "TARGET_SCOPE": target["scope"],
        "TARGET_SKILLS_DIR": resolve(asset_base, target["skills"]),
        "TARGET_AGENTS_DIR": resolve(asset_base, target["agents"]),
        "TARGET_AGENT_FORMAT": target["agent_format"] or "",
        "TARGET_RULES_DIR": resolve(project, target["rules"]),
        "TARGET_INSTRUCTION_FILE": resolve(project, target["instructions"]),
        "TARGET_TEMPLATE": target["template"] or "",
        "TARGET_HOOKS": target["hooks"],
        "TARGET_MCP": target["mcp"],
        "TARGET_MANIFEST": resolve(asset_base, target.get("manifest")),
        "TARGET_INVOCATION": target["invocation"],
    }
    for key, value in values.items():
        print(f"{key}={shlex.quote(shell_value(value))}")


def split_frontmatter(source):
    text = Path(source).read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n?(.*)\Z", text, re.DOTALL)
    if not match:
        raise ValueError(f"{source}: отсутствует YAML frontmatter")
    metadata = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.startswith((" ", "\t")):
            continue
        key, separator, value = line.partition(":")
        if separator:
            metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata, match.group(2).strip() + "\n"


def toml_string(value):
    return json.dumps(value, ensure_ascii=False)


def toml_multiline(value):
    return '"""\n' + value.replace("\\", "\\\\").replace('"""', '\\"\\"\\"') + '"""'


def emit_codex_agent(source, destination):
    metadata, body = split_frontmatter(source)
    name = metadata.get("name") or Path(source).stem
    description = metadata.get("description")
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", name):
        raise ValueError(f"{source}: некорректное имя агента {name!r}")
    if not description:
        raise ValueError(f"{source}: у Codex-агента обязательно поле description")
    content = (
        f"{CODEX_MARKER}\n"
        f"name = {toml_string(name)}\n"
        f"description = {toml_string(description)}\n"
        f"developer_instructions = {toml_multiline(body)}\n"
    )
    Path(destination).write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Реестр адаптеров coding-агентов UCP")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    subparsers.add_parser("list")
    target_parser = subparsers.add_parser("target")
    target_parser.add_argument("id")
    target_parser.add_argument("--project", required=True)
    target_parser.add_argument("--home", required=True)
    codex_parser = subparsers.add_parser("emit-codex-agent")
    codex_parser.add_argument("source")
    codex_parser.add_argument("destination")
    args = parser.parse_args()
    try:
        if args.command == "validate":
            registry = load_registry()
            print(f"OK: {len(registry['targets'])} targets")
        elif args.command == "list":
            registry = load_registry()
            for target in registry["targets"]:
                print(f"{target['id']}\t{target['label']}\t{target['support']}")
        elif args.command == "target":
            print_target(get_target(args.id), args.project, args.home)
        elif args.command == "emit-codex-agent":
            emit_codex_agent(args.source, args.destination)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
