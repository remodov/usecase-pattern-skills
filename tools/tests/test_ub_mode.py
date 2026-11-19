import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from agent_targets import split_frontmatter
from sync_platforms import SKILL_LINKS


class UbModeTest(unittest.TestCase):
    def test_metadata_and_mit_notice(self):
        skill = ROOT / ".claude" / "skills" / "ub-mode" / "SKILL.md"
        metadata, body = split_frontmatter(skill)
        self.assertEqual(metadata["name"], "ub-mode")
        self.assertEqual(metadata["lang"], "any")
        self.assertEqual(metadata["track"], "any")
        self.assertIn("https://github.com/unclebob/ub-mode", body)
        self.assertIn("не выдумывай CRAP score", body)
        license_text = (skill.parent / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("Copyright (c) 2026 Robert C. Martin", license_text)
        self.assertIn("MIT License", license_text)

    def test_every_native_catalog_exposes_ub_mode(self):
        targets = {target for paths in SKILL_LINKS.values() for target in paths}
        for target in targets:
            with self.subTest(target=target):
                self.assertTrue((ROOT / target / "ub-mode" / "SKILL.md").is_file())

    def test_every_install_target_can_select_ub_mode(self):
        registry = json.loads((ROOT / "tools" / "agent-targets.json").read_text(encoding="utf-8"))["targets"]
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            home = Path(tmp) / "home"
            project.mkdir()
            home.mkdir()
            for target in registry:
                with self.subTest(target=target["id"]):
                    env = os.environ.copy()
                    env.update({
                        "UCP_SKILLS": "ub-mode",
                        "UCP_HOME": str(home),
                        "GITLAB_TOKEN_FILE": str(home / "no-token"),
                    })
                    result = subprocess.run(
                        [str(ROOT / "install.sh"), "--target", target["id"], "--dry-run", str(project)],
                        cwd=ROOT,
                        env=env,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("ub-mode →", result.stdout)


if __name__ == "__main__":
    unittest.main()
