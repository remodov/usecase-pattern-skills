import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import skill_harness


class SkillHarnessTest(unittest.TestCase):
    def test_load_scenario_rejects_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            scenario = Path(tmp) / "scenario.json"
            scenario.write_text(json.dumps({
                "skill": "ucp-test",
                "title": "unsafe",
                "prompt": "test",
                "forbidden_files": ["../outside"],
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Небезопасный путь"):
                skill_harness.load_scenario(scenario)

    def test_evaluate_checks_files_globs_and_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            scenario = {
                "required_files": ["docs/spec/service-spec.md"],
                "forbidden_files": ["src/Main.java"],
                "required_globs": ["docs/spec/aggregates/*.md"],
                "forbidden_globs": ["src/**/*"],
                "output_patterns": ["подтверд"],
            }
            self.assertEqual(len(skill_harness.evaluate(scenario, project, "нет")), 3)
            (project / "docs/spec/aggregates").mkdir(parents=True)
            (project / "docs/spec/service-spec.md").write_text("spec", encoding="utf-8")
            (project / "docs/spec/aggregates/note.md").write_text("aggregate", encoding="utf-8")
            self.assertEqual(skill_harness.evaluate(scenario, project, "подтверди"), [])

    def test_kimi_uses_canonical_skills_directory(self):
        command, env = skill_harness.build_command("kimi", Path("/tmp/project"), "prompt", Path("/repo/.claude/skills"))
        self.assertIn("--skills-dir", command)
        self.assertIn("/repo/.claude/skills", command)
        self.assertEqual(env, {})

    def test_dry_run_does_not_call_model(self):
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "skill_harness.py"),
                "--scenario", str(ROOT / "tools" / "evals" / "ucp-new-service-missing-input.json"),
                "--agent", "kimi",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ucp-new-service", result.stdout)

    def test_run_scenario_uses_isolated_project_and_returns_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            scenario = Path(tmp) / "scenario.json"
            scenario.write_text(json.dumps({
                "skill": "ucp-test",
                "title": "fake model",
                "prompt": "test",
                "required_globs": ["docs/spec/*-spec.md"],
                "output_patterns": ["готов"],
            }), encoding="utf-8")
            script = (
                "from pathlib import Path; "
                "p=Path('docs/spec'); p.mkdir(parents=True, exist_ok=True); "
                "(p/'service-spec.md').write_text('spec'); "
                "print('готов')"
            )
            with mock.patch.object(skill_harness, "build_command", return_value=([sys.executable, "-c", script], {})):
                result = skill_harness.run_scenario(scenario, "kimi", ROOT)
            self.assertEqual(result, 0)

    def test_timeout_bytes_become_a_failed_report_not_an_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            scenario = Path(tmp) / "scenario.json"
            scenario.write_text(json.dumps({
                "skill": "ucp-test",
                "title": "timeout",
                "prompt": "test",
            }), encoding="utf-8")
            with mock.patch.object(skill_harness, "build_command", return_value=(["ignored"], {})):
                with mock.patch.object(skill_harness.subprocess, "run") as run:
                    run.side_effect = [
                        subprocess.CompletedProcess(args=[], returncode=0),
                        subprocess.TimeoutExpired(cmd="kimi", timeout=1, output=b"partial", stderr=b"timeout"),
                    ]
                    result = skill_harness.run_scenario(scenario, "kimi", ROOT, timeout=1)
            self.assertEqual(result, 1)

    def test_file_patterns_validate_generated_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            scenario = {"file_patterns": {"src/**/*.java": ["record", "UseCaseCommand"]}}
            self.assertEqual(len(skill_harness.evaluate(scenario, project, "")), 1)
            source = project / "src/main/java/example/CreateNoteCommand.java"
            source.parent.mkdir(parents=True)
            source.write_text("record CreateNoteCommand() implements UseCaseCommand {}", encoding="utf-8")
            self.assertEqual(skill_harness.evaluate(scenario, project, ""), [])
            source.write_text("class CreateNoteCommand {}", encoding="utf-8")
            self.assertEqual(len(skill_harness.evaluate(scenario, project, "")), 2)


if __name__ == "__main__":
    unittest.main()
