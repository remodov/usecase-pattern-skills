import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALL = ROOT / "install.sh"
REGISTRY = json.loads((ROOT / "tools" / "agent-targets.json").read_text(encoding="utf-8"))["targets"]


class InstallTargetsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.project = self.base / "project"
        self.home = self.base / "home"
        self.project.mkdir()
        self.home.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def run_install(self, target, *args, skills="ucp-pattern-*", check=False):
        env = os.environ.copy()
        env.update({
            "UCP_SKILLS": skills,
            "UCP_HOME": str(self.home),
            "GITLAB_TOKEN_FILE": str(self.home / "no-token"),
        })
        env.pop("GITLAB_PERSONAL_ACCESS_TOKEN", None)
        command = [str(INSTALL), "--target", target]
        if check:
            command.append("--check")
        command.extend(args)
        command.append(str(self.project))
        return subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)

    def assert_project_writes_are_scoped(self, target):
        expected = {".claude", ".gitignore"}
        for field in ("skills", "instructions", "agents", "rules"):
            value = target.get(field)
            if value and (field in {"instructions", "rules"} or target["scope"] == "project"):
                expected.add(Path(value).parts[0])
        actual = {path.name for path in self.project.iterdir()}
        self.assertEqual(actual, expected)

    def test_every_target_installs_checks_and_reinstalls(self):
        for target in REGISTRY:
            with self.subTest(target=target["id"]):
                self.project = self.base / f"{target['id']}-project"
                self.home = self.base / f"{target['id']}-home"
                self.project.mkdir()
                self.home.mkdir()
                result = self.run_install(target["id"])
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assert_project_writes_are_scoped(target)
                check = self.run_install(target["id"], check=True)
                self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
                again = self.run_install(target["id"])
                self.assertEqual(again.returncode, 0, again.stdout + again.stderr)

    def test_dry_run_does_not_write(self):
        result = self.run_install("kimi", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Dry run: Kimi Code", result.stdout)
        self.assertIn("hooks не настраиваются", result.stdout)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_target_switch_removes_previous_managed_links(self):
        first = self.run_install("claude")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertTrue((self.project / ".claude" / "skills" / "ucp-pattern-review").is_symlink())
        second = self.run_install("kimi")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertFalse((self.project / ".claude" / "skills" / "ucp-pattern-review").exists())
        self.assertTrue((self.project / ".kimi-code" / "skills" / "ucp-pattern-review").is_symlink())
        settings = json.loads((self.project / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings.get("hooks", {}), {})

    def test_language_filter_is_independent_of_target(self):
        result = self.run_install("generic", skills="ucp-*pattern-*")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        env_result = subprocess.run(
            [str(INSTALL), "--target", "generic", "--check", str(self.project)],
            cwd=ROOT,
            env={**os.environ, "UCP_SKILLS": "ucp-*pattern-*", "UCP_LANG": "java"},
            capture_output=True,
            text=True,
        )
        self.assertEqual(env_result.returncode, 0, env_result.stdout + env_result.stderr)
        result = subprocess.run(
            [str(INSTALL), "--target", "generic", str(self.project)],
            cwd=ROOT,
            env={
                **os.environ,
                "UCP_SKILLS": "ucp-*pattern-*",
                "UCP_LANG": "python",
                "UCP_HOME": str(self.home),
                "GITLAB_TOKEN_FILE": str(self.home / "no-token"),
            },
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        skills = self.project / ".agents" / "skills"
        self.assertTrue((skills / "ucp-py-pattern-design").is_symlink())
        self.assertFalse((skills / "ucp-pattern-design").exists())

    def test_user_content_survives_managed_updates(self):
        (self.project / "AGENTS.md").write_text("Мои правила\n", encoding="utf-8")
        (self.project / ".gitignore").write_text("my-output/\n", encoding="utf-8")
        result = self.run_install("codex")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Мои правила", (self.project / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertIn("my-output/", (self.project / ".gitignore").read_text(encoding="utf-8"))
        again = self.run_install("codex")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual((self.project / "AGENTS.md").read_text(encoding="utf-8").count("<!-- BEGIN ucp-skills"), 1)

    def test_claude_hooks_use_project_root_and_preserve_custom_hook(self):
        settings_dir = self.project / ".claude"
        settings_dir.mkdir()
        (settings_dir / "settings.json").write_text(json.dumps({
            "hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "my-hook"}]}]}
        }), encoding="utf-8")
        result = self.run_install("claude")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        settings = json.loads((settings_dir / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"], "my-hook")
        commands = [
            hook["command"]
            for groups in settings["hooks"].values()
            for group in groups
            for hook in group["hooks"]
            if "ucp-" in hook["command"] or "impl-task-detect" in hook["command"]
        ]
        self.assertEqual(len(commands), 4)
        for command in commands:
            self.assertIn('"$CLAUDE_PROJECT_DIR"/.claude/hooks/', command)


if __name__ == "__main__":
    unittest.main()
