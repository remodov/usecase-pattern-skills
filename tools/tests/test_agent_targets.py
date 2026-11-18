import json
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import agent_targets


EXPECTED_TARGETS = {
    "claude", "kimi", "codex", "cursor", "copilot", "gemini", "opencode",
    "qwen", "zed", "antigravity", "codebuddy", "joycode", "hermes",
    "openclaw", "adal", "grok", "mistral-vibe", "generic",
}


class AgentTargetRegistryTest(unittest.TestCase):
    def test_registry_is_valid_and_covers_ecc_catalog(self):
        registry = agent_targets.load_registry()
        self.assertEqual({target["id"] for target in registry["targets"]}, EXPECTED_TARGETS)

    def test_native_destinations(self):
        expected = {
            "claude": ".claude/skills",
            "kimi": ".kimi-code/skills",
            "codex": ".agents/skills",
            "copilot": ".github/skills",
            "mistral-vibe": ".vibe/skills",
        }
        for target_id, destination in expected.items():
            with self.subTest(target=target_id):
                self.assertEqual(agent_targets.get_target(target_id)["skills"], destination)

    def test_unknown_target_fails_with_catalog(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "agent_targets.py"), "target", "unknown", "--project", "/tmp/project", "--home", "/tmp/home"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Доступно:", result.stderr)

    def test_registry_rejects_unsafe_path(self):
        target = agent_targets.get_target("kimi").copy()
        target["skills"] = "../outside"
        with self.assertRaisesRegex(ValueError, "небезопасный путь"):
            agent_targets.validate_target(target)

    def test_every_skill_has_portable_standard_frontmatter(self):
        for skill in sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md")):
            with self.subTest(skill=skill.parent.name):
                metadata, body = agent_targets.split_frontmatter(skill)
                self.assertEqual(metadata.get("name"), skill.parent.name)
                self.assertTrue(metadata.get("description"))
                self.assertLessEqual(len(skill.parent.name), 64)
                self.assertRegex(skill.parent.name, r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
                self.assertNotIn('Skill("', body)
                self.assertNotIn("${CLAUDE_SKILL_DIR}", body)
                self.assertNotRegex(body, r"`/ucp-[a-z]")
                if skill.parent.name != "ucp-meta-review":
                    self.assertNotIn("TodoWrite", body)

    def test_codex_agent_emitter(self):
        with tempfile.TemporaryDirectory() as tmp:
            for source in sorted((ROOT / ".claude" / "agents").glob("*.md")):
                with self.subTest(agent=source.name):
                    destination = Path(tmp) / f"{source.stem}.toml"
                    agent_targets.emit_codex_agent(source, destination)
                    with destination.open("rb") as stream:
                        data = tomllib.load(stream)
                    self.assertEqual(data["name"], source.stem)
                    self.assertTrue(data["description"])
                    self.assertIn("developer_instructions", data)
                    self.assertNotIn("model", data)
                    self.assertIn(agent_targets.CODEX_MARKER, destination.read_text(encoding="utf-8"))

    def test_codex_agent_requires_description(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "broken.md"
            source.write_text("---\nname: broken\n---\nBody\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "description"):
                agent_targets.emit_codex_agent(source, Path(tmp) / "broken.toml")


if __name__ == "__main__":
    unittest.main()
