import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from agent_targets import render_codex_agent
from sync_platforms import AGENT_LINKS, SKILL_LINKS, Sync


class PlatformEntrypointsTest(unittest.TestCase):
    def test_sync_check_is_green(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "sync_platforms.py"), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_ecc_style_directories_are_physical_repository_entries(self):
        expected = {
            ".adal", ".agents", ".codebuddy", ".codex", ".cursor", ".gemini",
            ".github", ".grok-plugin", ".hermes", ".joycode", ".kimi-code",
            ".openclaw", ".opencode", ".qwen", ".vibe", ".zed",
        }
        for directory in expected:
            with self.subTest(directory=directory):
                self.assertTrue((ROOT / directory).exists(), directory)

    def test_skill_and_agent_links_are_relative_and_resolve(self):
        targets = {target for paths in SKILL_LINKS.values() for target in paths} | set(AGENT_LINKS)
        for target in targets:
            with self.subTest(target=target):
                link = ROOT / target
                self.assertTrue(link.is_symlink())
                self.assertFalse(os.path.isabs(os.readlink(link)))
                self.assertTrue(link.resolve().is_dir())

    def test_generic_catalog_contains_every_canonical_skill(self):
        canonical = list((ROOT / ".claude" / "skills").glob("*/SKILL.md"))
        generic = list((ROOT / ".agents" / "skills").glob("*/SKILL.md"))
        self.assertEqual(len(generic), len(canonical))
        self.assertGreater(len(canonical), 0)

    def test_instruction_files_match_templates(self):
        neutral = (ROOT / "templates" / "agents-block.md").read_text(encoding="utf-8")
        for target in ("AGENTS.md", ".kimi-code/AGENTS.md", ".github/copilot-instructions.md", "GEMINI.md", "QWEN.md"):
            with self.subTest(target=target):
                self.assertEqual((ROOT / target).read_text(encoding="utf-8"), neutral)
        self.assertEqual(
            (ROOT / "CLAUDE.md").read_text(encoding="utf-8"),
            (ROOT / "templates" / "claude-block.md").read_text(encoding="utf-8"),
        )

    def test_native_configs_and_codex_agents_are_valid(self):
        json.loads((ROOT / ".opencode" / "opencode.json").read_text(encoding="utf-8"))
        json.loads((ROOT / ".grok-plugin" / "plugin.json").read_text(encoding="utf-8"))
        with (ROOT / ".codex" / "config.toml").open("rb") as stream:
            tomllib.load(stream)
        for source in (ROOT / ".claude" / "agents").glob("*.md"):
            generated = ROOT / ".codex" / "agents" / f"{source.stem}.toml"
            self.assertEqual(generated.read_text(encoding="utf-8"), render_codex_agent(source))
            with generated.open("rb") as stream:
                tomllib.load(stream)

    def test_sync_is_idempotent_in_a_clean_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_fixture(tmp)
            first = Sync(root)
            self.assertEqual(first.run(), 0, first.errors)
            second = Sync(root, check=True)
            self.assertEqual(second.run(), 0, second.errors)

    def test_sync_refuses_to_replace_unmanaged_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_fixture(tmp)
            (root / ".agents" / "skills").mkdir(parents=True)
            sync = Sync(root)
            self.assertEqual(sync.run(), 1)
            self.assertTrue((root / ".agents" / "skills").is_dir())
            self.assertTrue(any("не является managed symlink" in error for error in sync.errors))

    def make_fixture(self, tmp):
        root = Path(tmp)
        skill = root / ".claude" / "skills" / "ucp-example"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: ucp-example\ndescription: Example\n---\nBody\n", encoding="utf-8")
        agents = root / ".claude" / "agents"
        agents.mkdir(parents=True)
        (agents / "ucp-test.md").write_text(
            "---\nname: ucp-test\ndescription: Test agent\n---\nDo not edit.\n",
            encoding="utf-8",
        )
        templates = root / "templates"
        templates.mkdir()
        for name in ("agents-block.md", "claude-block.md"):
            (templates / name).write_text((ROOT / "templates" / name).read_text(encoding="utf-8"), encoding="utf-8")
        return root


if __name__ == "__main__":
    unittest.main()
