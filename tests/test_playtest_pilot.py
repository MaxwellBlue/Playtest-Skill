import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill" / "playtest-pilot" / "scripts" / "playtest_pilot.py"
SPEC = importlib.util.spec_from_file_location("playtest_pilot", SCRIPT)
pilot = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(pilot)


class PlaytestPilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="playtest-pilot-test-")
        self.project = Path(self.temp.name) / "Game"
        self.project.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def write_config(self, checks):
        path = self.project / ".playtest-pilot.json"
        path.write_text(json.dumps({"checks": checks}), encoding="utf-8")
        return path

    def test_detects_unity_project_and_version(self):
        (self.project / "Assets").mkdir()
        settings = self.project / "ProjectSettings"
        settings.mkdir()
        (settings / "ProjectVersion.txt").write_text("m_EditorVersion: 6000.0.1f1\n", encoding="utf-8")

        result = pilot.detect_project(self.project)

        self.assertEqual(result["engine"], "unity")
        self.assertEqual(result["engineVersion"], "6000.0.1f1")

    def test_detects_unreal_project_file(self):
        uproject = self.project / "Game.uproject"
        uproject.write_text("{}", encoding="utf-8")

        result = pilot.detect_project(self.project)

        self.assertEqual(result["engine"], "unreal")
        self.assertEqual(result["projectFile"], str(uproject))

    def test_passing_check_saves_log_report_and_evidence(self):
        self.write_config(
            [
                {
                    "name": "Smoke Test",
                    "command": [
                        sys.executable,
                        "-c",
                        "from pathlib import Path; Path(r\"{output}/result.txt\").write_text('ok'); print('passed')",
                    ],
                    "evidence": ["{output}/result.txt"],
                    "requiredEvidence": True,
                }
            ]
        )

        exit_code = pilot.main(["run", "--project", str(self.project)])

        self.assertEqual(exit_code, 0)
        report_path = next(self.project.glob(".playtest-pilot/*/report.json"))
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["checks"][0]["evidence"][0]["exists"])
        self.assertIn("passed", Path(report["checks"][0]["log"]).read_text(encoding="utf-8"))
        self.assertTrue((report_path.parent / "report.md").is_file())

    def test_failed_exit_code_is_not_a_pass(self):
        self.write_config(
            [
                {
                    "name": "broken",
                    "command": [sys.executable, "-c", "print('failure detail'); raise SystemExit(3)"],
                }
            ]
        )

        exit_code = pilot.main(["run", "--project", str(self.project)])

        self.assertEqual(exit_code, 1)
        report_path = next(self.project.glob(".playtest-pilot/*/report.json"))
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["checks"][0]["exitCode"], 3)
        self.assertIn("failure detail", Path(report["checks"][0]["log"]).read_text(encoding="utf-8"))

    def test_missing_required_evidence_fails_even_with_zero_exit(self):
        self.write_config(
            [
                {
                    "name": "empty evidence",
                    "command": [sys.executable, "-c", "print('done')"],
                    "evidence": ["{output}/missing.xml"],
                    "requiredEvidence": True,
                }
            ]
        )

        exit_code = pilot.main(["run", "--project", str(self.project)])

        self.assertEqual(exit_code, 1)
        report_path = next(self.project.glob(".playtest-pilot/*/report.json"))
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertIn("Required evidence is missing", report["checks"][0]["reasons"])

    def test_rejects_shell_command_strings(self):
        path = self.write_config([{"name": "unsafe", "command": "echo nope"}])

        with self.assertRaises(pilot.PilotError):
            pilot.load_config(path)

    def test_generic_project_inspection_still_works(self):
        exit_code = pilot.main(["inspect", "--project", str(self.project), "--json"])
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
