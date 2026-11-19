#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
AGENTS = {"kimi", "opencode", "codex", "claude"}


def safe_relative(value):
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Небезопасный путь: {value}")
    return str(path)


def load_scenario(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for field in ("skill", "title", "prompt"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise ValueError(f"Сценарий требует {field}")
    for field in ("required_files", "forbidden_files", "required_globs", "forbidden_globs", "unchanged_files"):
        for value in data.get(field, []):
            safe_relative(value)
    for field in ("output_patterns",):
        for value in data.get(field, []):
            re.compile(value)
    for field in ("file_patterns", "file_forbidden_patterns"):
        for glob, patterns in data.get(field, {}).items():
            safe_relative(glob)
            for value in patterns:
                re.compile(value)
    for path_value in data.get("initial_files", {}):
        safe_relative(path_value)
    return data


def build_command(agent, project, prompt, skills):
    if agent == "kimi":
        return ["kimi", "--skills-dir", str(skills), "-p", prompt], {}
    if agent == "opencode":
        config_home = project / ".harness" / "config"
        destination = config_home / "opencode" / "skills"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(skills, target_is_directory=True)
        return ["opencode", "run", "--standalone", "--format", "json", prompt], {
            "XDG_CONFIG_HOME": str(config_home)
        }
    if agent == "codex":
        destination = project / ".agents" / "skills"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(skills, target_is_directory=True)
        return ["codex", "exec", "--sandbox", "workspace-write", "-C", str(project), prompt], {}
    if agent == "claude":
        destination = project / ".claude" / "skills"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(skills, target_is_directory=True)
        return [
            "claude", "-p", "--permission-mode", "acceptEdits",
            "--setting-sources", "project", prompt,
        ], {}
    raise ValueError(f"Неподдерживаемый agent: {agent}")


def evaluate(scenario, project, output):
    failures = []
    for relative in scenario.get("required_files", []):
        if not (project / relative).is_file():
            failures.append(f"Нет файла: {relative}")
    for relative in scenario.get("forbidden_files", []):
        if (project / relative).exists():
            failures.append(f"Запрещённый файл появился: {relative}")
    for relative in scenario.get("unchanged_files", []):
        expected = scenario.get("initial_files", {}).get(relative)
        if expected is None:
            failures.append(f"unchanged_file без initial content: {relative}")
        elif not (project / relative).is_file() or (project / relative).read_text(encoding="utf-8") != expected:
            failures.append(f"Файл был изменён: {relative}")
    for pattern in scenario.get("required_globs", []):
        if not list(project.glob(pattern)):
            failures.append(f"Нет совпадений glob: {pattern}")
    for pattern in scenario.get("forbidden_globs", []):
        matches = list(project.glob(pattern))
        if matches:
            failures.append(f"Запрещённый glob {pattern}: {[str(path.relative_to(project)) for path in matches]}")
    for glob, patterns in scenario.get("file_patterns", {}).items():
        files = list(project.glob(glob))
        if not files:
            failures.append(f"Нет файлов для content glob: {glob}")
        for path in files:
            if not path.is_file():
                continue
            content = path.read_text(encoding="utf-8")
            for pattern in patterns:
                if not re.search(pattern, content, re.MULTILINE):
                    failures.append(f"{path.relative_to(project)}: нет content pattern {pattern}")
    for glob, patterns in scenario.get("file_forbidden_patterns", {}).items():
        for path in project.glob(glob):
            if not path.is_file():
                continue
            content = path.read_text(encoding="utf-8")
            for pattern in patterns:
                if re.search(pattern, content, re.MULTILINE):
                    failures.append(f"{path.relative_to(project)}: запрещённый content pattern {pattern}")
    for pattern in scenario.get("output_patterns", []):
        if not re.search(pattern, output, re.MULTILINE):
            failures.append(f"В ответе нет pattern: {pattern}")
    return failures


def run_scenario(scenario, agent, repo, keep=False, timeout=180):
    scenario = load_scenario(scenario)
    project = Path(tempfile.mkdtemp(prefix=f"ucp-eval-{scenario['skill']}-"))
    started = time.monotonic()
    try:
        subprocess.run(["git", "-C", str(project), "init", "-q"], check=True)
        for relative, content in scenario.get("initial_files", {}).items():
            target = project / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        skills = repo / ".claude" / "skills"
        command, extra_env = build_command(agent, project, scenario["prompt"], skills)
        try:
            process = subprocess.run(
                command,
                cwd=project,
                env={**os.environ, **extra_env},
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = process.stdout + process.stderr
            command_error = None if process.returncode == 0 else f"CLI exit {process.returncode}"
        except subprocess.TimeoutExpired as error:
            output = (error.stdout or "") + (error.stderr or "")
            command_error = f"Тайм-аут {timeout}s"
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        failures = evaluate(scenario, project, output)
        if command_error:
            failures.insert(0, command_error)
        report = {
            "skill": scenario["skill"],
            "title": scenario["title"],
            "agent": agent,
            "passed": not failures,
            "failures": failures,
            "duration_seconds": round(time.monotonic() - started, 2),
            "output_tail": output[-12000:],
            "project": str(project),
            "files": sorted(str(path.relative_to(project)) for path in project.rglob("*") if path.is_file()),
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if not failures else 1
    finally:
        if keep:
            print(f"Project сохранён: {project}", file=sys.stderr)
        else:
            shutil.rmtree(project)


def main():
    parser = argparse.ArgumentParser(description="Поведенческий harness для одного скилла")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--agent", choices=sorted(AGENTS), required=True)
    parser.add_argument("--repo", default=str(ROOT))
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        scenario = load_scenario(args.scenario)
        if args.dry_run:
            print(json.dumps({"skill": scenario["skill"], "title": scenario["title"], "agent": args.agent}, ensure_ascii=False))
            return 0
        return run_scenario(args.scenario, args.agent, Path(args.repo).resolve(), args.keep, args.timeout)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
