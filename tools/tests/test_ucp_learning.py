import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
TOOL = ROOT / "tools" / "ucp_learning.py"


class ProjectLearningTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self, command, *args):
        return subprocess.run(
            [sys.executable, str(TOOL), command, "--root", str(self.root), *args],
            capture_output=True,
            text=True,
        )

    def record(self, evidence="Первый тест не прошёл, исправление подтверждено"):
        return self.run_tool(
            "record",
            "--category", "tests",
            "--lesson", "Использовать реальный PostgreSQL вместо SQLite",
            "--evidence", evidence,
        )

    def test_first_observation_stays_collecting(self):
        result = self.record()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        candidate = json.loads(result.stdout)
        self.assertEqual(candidate["status"], "collecting")
        self.assertEqual(candidate["observations"], 1)
        self.assertFalse((self.root / ".ucp" / "learning" / "playbook.md").exists())

    def test_second_distinct_observation_opens_question_but_not_apply(self):
        self.record()
        result = self.record("Второй сценарий также потребовал PostgreSQL")
        candidate = json.loads(result.stdout)
        self.assertEqual(candidate["status"], "pending")
        self.assertEqual(candidate["observations"], 2)
        self.assertFalse((self.root / ".ucp" / "learning" / "playbook.md").exists())

    def test_duplicate_evidence_does_not_inflate_count(self):
        self.record()
        result = self.record()
        candidate = json.loads(result.stdout)
        self.assertEqual(candidate["observations"], 1)
        self.assertEqual(candidate["status"], "collecting")

    def test_apply_requires_confirmation_and_two_observations(self):
        candidate_id = json.loads(self.record().stdout)["id"]
        missing_yes = self.run_tool("apply", "--id", candidate_id)
        self.assertEqual(missing_yes.returncode, 1)
        self.record("Второе независимое подтверждение")
        not_yes = self.run_tool("apply", "--id", candidate_id)
        self.assertEqual(not_yes.returncode, 1)
        applied = self.run_tool("apply", "--id", candidate_id, "--yes")
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        playbook = (self.root / ".ucp" / "learning" / "playbook.md").read_text(encoding="utf-8")
        self.assertIn("реальный PostgreSQL", playbook)
        self.assertIn("только этот проект", playbook)
        again = self.run_tool("apply", "--id", candidate_id, "--yes")
        self.assertEqual(again.returncode, 1)

    def test_rejected_candidate_never_reaches_playbook(self):
        candidate_id = json.loads(self.record().stdout)["id"]
        self.record("Второе подтверждение")
        result = self.run_tool("reject", "--id", candidate_id)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "rejected")
        self.assertFalse((self.root / ".ucp" / "learning" / "playbook.md").exists())
        applied = self.run_tool("apply", "--id", candidate_id, "--yes")
        self.assertEqual(applied.returncode, 1)

    def test_raw_candidates_are_gitignored_and_scope_is_project(self):
        candidate = json.loads(self.record().stdout)
        self.assertEqual(candidate["scope"], "project")
        ignore = (self.root / ".ucp" / "learning" / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("candidates.json", ignore)
    def test_skill_is_language_neutral_and_available_everywhere(self):
        from agent_targets import split_frontmatter
        from sync_platforms import SKILL_LINKS

        skill = ROOT / ".claude" / "skills" / "ucp-learn" / "SKILL.md"
        metadata, _ = split_frontmatter(skill)
        self.assertEqual(metadata["lang"], "any")
        self.assertEqual(metadata["track"], "any")
        for target in {target for paths in SKILL_LINKS.values() for target in paths}:
            with self.subTest(target=target):
                self.assertTrue((ROOT / target / "ucp-learn" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
