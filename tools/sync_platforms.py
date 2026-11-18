#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path

from agent_targets import CODEX_MARKER, load_registry, render_codex_agent

ROOT = Path(__file__).resolve().parents[1]
MANAGED_PREFIX = "Managed by usecase-pattern-skills sync_platforms.py"

SKILL_LINKS = {
    "kimi": [".kimi-code/skills"],
    "codex": [".agents/skills"],
    "cursor": [".cursor/skills"],
    "copilot": [".github/skills"],
    "gemini": [".gemini/skills"],
    "opencode": [".opencode/skills"],
    "qwen": [".qwen/skills"],
    "zed": [".zed/skills"],
    "antigravity": [".agents/skills"],
    "codebuddy": [".codebuddy/skills"],
    "joycode": [".joycode/skills"],
    "hermes": [".hermes/skills"],
    "openclaw": [".openclaw/skills"],
    "adal": [".adal/skills"],
    "mistral-vibe": [".vibe/skills"],
    "generic": [".agents/skills"],
}

AGENT_LINKS = [
    ".kimi-code/agents",
    ".cursor/agents",
    ".github/agents",
    ".opencode/agents",
    ".qwen/agents",
    ".agents/agents",
    ".codebuddy/agents",
]


class Sync:
    def __init__(self, root, check=False):
        self.root = Path(root).resolve()
        self.check = check
        self.changes = []
        self.errors = []

    def relative(self, path):
        return str(path.relative_to(self.root))

    def link(self, target_relative, source_relative):
        target = self.root / target_relative
        source = self.root / source_relative
        expected = os.path.relpath(source, target.parent)
        if target.is_symlink():
            if os.readlink(target) != expected:
                self.errors.append(f"{target_relative}: symlink указывает не на {expected}")
            return
        if target.exists():
            self.errors.append(f"{target_relative}: существует и не является managed symlink")
            return
        if self.check:
            self.errors.append(f"{target_relative}: отсутствует symlink на {expected}")
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(expected, target_is_directory=True)
        self.changes.append(target_relative)

    def file(self, target_relative, content, marker=None):
        target = self.root / target_relative
        if target.exists():
            current = target.read_text(encoding="utf-8")
            if current == content:
                return
            if marker is None or marker not in current:
                self.errors.append(f"{target_relative}: содержимое отличается и файл не managed")
                return
        elif self.check:
            self.errors.append(f"{target_relative}: файл отсутствует")
            return
        if self.check:
            self.errors.append(f"{target_relative}: generated content устарел")
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.changes.append(target_relative)

    def run(self):
        registry = load_registry()
        target_ids = {target["id"] for target in registry["targets"]}
        mapped_ids = set(SKILL_LINKS) | {"claude", "grok"}
        if mapped_ids != target_ids:
            self.errors.append(
                "Platform mapping не совпадает с registry: "
                f"нет {sorted(target_ids - mapped_ids)}, лишние {sorted(mapped_ids - target_ids)}"
            )
            return self.finish()

        skill_targets = {target for paths in SKILL_LINKS.values() for target in paths}
        for target in sorted(skill_targets):
            self.link(target, ".claude/skills")
        for target in AGENT_LINKS:
            self.link(target, ".claude/agents")

        neutral = (self.root / "templates" / "agents-block.md").read_text(encoding="utf-8")
        claude = (self.root / "templates" / "claude-block.md").read_text(encoding="utf-8")
        for target in (
            "AGENTS.md",
            ".kimi-code/AGENTS.md",
            ".github/copilot-instructions.md",
            "GEMINI.md",
            "QWEN.md",
        ):
            self.file(target, neutral, "<!-- BEGIN ucp-skills")
        self.file("CLAUDE.md", claude, "<!-- BEGIN ucp-skills")

        codex_config = (
            f"# {MANAGED_PREFIX}\n"
            "#:schema https://developers.openai.com/codex/config-schema.json\n\n"
            "[features]\n"
            "multi_agent = true\n"
        )
        self.file(".codex/config.toml", codex_config, MANAGED_PREFIX)
        for source in sorted((self.root / ".claude" / "agents").glob("*.md")):
            self.file(
                f".codex/agents/{source.stem}.toml",
                render_codex_agent(source),
                CODEX_MARKER,
            )
        expected_agents = {f"{source.stem}.toml" for source in (self.root / ".claude" / "agents").glob("*.md")}
        codex_dir = self.root / ".codex" / "agents"
        if codex_dir.exists():
            for generated in codex_dir.glob("ucp-*.toml"):
                if generated.name in expected_agents:
                    continue
                if CODEX_MARKER not in generated.read_text(encoding="utf-8"):
                    continue
                if self.check:
                    self.errors.append(f"{self.relative(generated)}: устаревший managed agent")
                else:
                    generated.unlink()
                    self.changes.append(self.relative(generated))

        opencode = {
            "$schema": "https://opencode.ai/config.json",
            "instructions": ["AGENTS.md"],
            "skills": {"paths": ["../.claude/skills"]},
        }
        self.file(".opencode/opencode.json", json.dumps(opencode, indent=2, ensure_ascii=False) + "\n")
        grok = {
            "name": "ucp",
            "description": "Use Case Pattern Agent Skills",
            "skills": ".claude/skills/",
        }
        self.file(".grok-plugin/plugin.json", json.dumps(grok, indent=2, ensure_ascii=False) + "\n")
        return self.finish()

    def finish(self):
        for error in self.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        if self.check:
            if not self.errors:
                print("platform sync — все native entry points совпадают")
        elif not self.errors:
            for change in self.changes:
                print(f"✓ {change}")
            print(f"platform sync — обновлено {len(self.changes)} entry points")
        return 1 if self.errors else 0


def main():
    parser = argparse.ArgumentParser(description="Синхронизация ECC-style native platform entry points")
    parser.add_argument("--check", action="store_true", help="только проверить, ничего не менять")
    parser.add_argument("--root", default=str(ROOT), help="корень репозитория скиллов")
    args = parser.parse_args()
    try:
        return Sync(args.root, args.check).run()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
