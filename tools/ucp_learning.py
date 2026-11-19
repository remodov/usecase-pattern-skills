#!/usr/bin/env python3
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

STORE_NAME = "candidates.json"
PLAYBOOK_NAME = "playbook.md"


def now():
    return datetime.now(timezone.utc).isoformat()


def clean(value):
    return " ".join(value.split()).strip()


def learning_dir(root):
    return Path(root).resolve() / ".ucp" / "learning"


def load_store(root):
    path = learning_dir(root) / STORE_NAME
    if not path.exists():
        return {"version": 1, "candidates": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("candidates"), dict):
        raise ValueError(f"Некорректный {path}")
    return data


def save_store(root, data):
    directory = learning_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    ignore = directory / ".gitignore"
    if not ignore.exists():
        ignore.write_text("candidates.json\n", encoding="utf-8")
    path = directory / STORE_NAME
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def candidate_id(category, lesson):
    return hashlib.sha256(f"{category}\n{lesson}".encode("utf-8")).hexdigest()[:12]


def record(root, category, lesson, evidence):
    category = clean(category)
    lesson = clean(lesson)
    evidence = clean(evidence)
    if not category or not lesson or not evidence:
        raise ValueError("category, lesson и evidence обязательны")
    data = load_store(root)
    candidate_id_value = candidate_id(category, lesson)
    candidates = data["candidates"]
    if candidate_id_value in candidates:
        candidate = candidates[candidate_id_value]
    else:
        timestamp = now()
        candidate = {
            "id": candidate_id_value,
            "category": category,
            "lesson": lesson,
            "scope": "project",
            "status": "collecting",
            "observations": 0,
            "evidence": [],
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    if candidate["status"] == "applied":
        raise ValueError(f"{candidate_id_value}: уже применён к playbook")
    if candidate["status"] == "rejected":
        raise ValueError(f"{candidate_id_value}: уже отклонён")
    if evidence not in candidate["evidence"]:
        candidate["evidence"].append(evidence)
        candidate["observations"] += 1
    if candidate["observations"] >= 2:
        candidate["status"] = "pending"
    candidate["updated_at"] = now()
    candidates[candidate_id_value] = candidate
    save_store(root, data)
    print(json.dumps(candidate, ensure_ascii=False))


def get_candidate(root, candidate_id_value):
    data = load_store(root)
    try:
        return data, data["candidates"][candidate_id_value]
    except KeyError as error:
        raise ValueError(f"Неизвестный candidate id: {candidate_id_value}") from error


def apply(root, candidate_id_value, confirmed):
    if not confirmed:
        raise ValueError("Применение требует подтверждения пользователя: --yes")
    data, candidate = get_candidate(root, candidate_id_value)
    if candidate["status"] != "pending" or candidate["observations"] < 2:
        raise ValueError("Нужны минимум два разных наблюдения и status=pending")
    if candidate["scope"] != "project":
        raise ValueError("Разрешено применение только с scope=project")
    directory = learning_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    playbook = directory / PLAYBOOK_NAME
    marker = f"<!-- BEGIN ucp-learning:{candidate_id_value} -->"
    if playbook.exists() and marker in playbook.read_text(encoding="utf-8"):
        raise ValueError(f"{candidate_id_value}: уже есть в playbook")
    block = (
        f"{marker}\n"
        f"## {candidate['category']}\n\n"
        f"- **Проектный нюанс:** {candidate['lesson']}\n"
        f"- **Подтверждение:** {'; '.join(candidate['evidence'])}\n"
        "- **Область:** только этот проект; в канонические скиллы и другие репозитории не переносить.\n"
        f"<!-- END ucp-learning:{candidate_id_value} -->\n"
    )
    with playbook.open("a", encoding="utf-8") as stream:
        if stream.tell() == 0:
            stream.write("# Проектный playbook\n\n")
        else:
            stream.write("\n")
        stream.write(block)
    candidate["status"] = "applied"
    candidate["applied_at"] = now()
    save_store(root, data)
    print(json.dumps(candidate, ensure_ascii=False))


def reject(root, candidate_id_value):
    data, candidate = get_candidate(root, candidate_id_value)
    if candidate["status"] != "pending":
        raise ValueError("Отклонить можно только candidate со status=pending")
    candidate["status"] = "rejected"
    candidate["updated_at"] = now()
    save_store(root, data)
    print(json.dumps(candidate, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Project-scoped learning с подтверждением перед применением")
    parser.add_argument("command", choices=["record", "apply", "reject", "list", "show"])
    parser.add_argument("--root", required=True)
    parser.add_argument("--category")
    parser.add_argument("--lesson")
    parser.add_argument("--evidence")
    parser.add_argument("--id", dest="candidate_id")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "record":
            record(args.root, args.category or "", args.lesson or "", args.evidence or "")
        elif args.command == "apply":
            apply(args.root, args.candidate_id or "", args.yes)
        elif args.command == "reject":
            reject(args.root, args.candidate_id or "")
        elif args.command == "list":
            print(json.dumps(load_store(args.root)["candidates"], ensure_ascii=False))
        elif args.command == "show":
            _, candidate = get_candidate(args.root, args.candidate_id or "")
            print(json.dumps(candidate, ensure_ascii=False))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
