import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GIT = shutil.which("git")


@unittest.skipUnless(GIT, "Git wird nur fuer die Release-Pruefung benoetigt")
class ReleaseHygieneTests(unittest.TestCase):
    def test_gitignore_excludes_local_assets_and_keeps_project_sources(self):
        ignored_paths = (
            "runtime/python/python.exe",
            "runtime/llama.cpp/llama-server.exe",
            "models/synthetic-model.gguf",
            "data/memory.sqlite3",
            "data/memory.sqlite3-shm",
            "data/memory.sqlite3-wal",
            "sessions/synthetic-session.json",
            "user_data/synthetic-table.csv",
            "src/portable_agent/__pycache__/module.pyc",
            ".env",
            "settings.local.json",
        )
        tracked_paths = (
            "src/portable_agent/sessions/manager.py",
            "config/semantic_catalog.json",
            "examples/synthetic/einsaetze.csv",
            "examples/synthetic/projektinfo.txt",
            "tests/golden_questions.json",
            "README.md",
            "LICENSE",
            "SECURITY.md",
            "THIRD_PARTY_ASSETS.md",
            "CONTRIBUTING.md",
            ".github/workflows/tests.yml",
            ".github/dependabot.yml",
            ".github/ISSUE_TEMPLATE/bug_report.yml",
            ".github/ISSUE_TEMPLATE/feature_request.yml",
            ".github/ISSUE_TEMPLATE/config.yml",
            ".github/pull_request_template.md",
            ".env.example",
        )

        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            shutil.copyfile(ROOT / ".gitignore", repository / ".gitignore")
            for relative_path in (*ignored_paths, *tracked_paths):
                path = repository / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetischer Testinhalt\n", encoding="utf-8")

            initialized = subprocess.run(
                [GIT, "init", "--quiet"],
                cwd=repository,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            self.assertEqual(
                initialized.returncode,
                0,
                initialized.stdout + initialized.stderr,
            )

            for relative_path in ignored_paths:
                with self.subTest(path=relative_path, expected="ignored"):
                    result = self._check_ignore(repository, relative_path)
                    self.assertEqual(
                        result.returncode,
                        0,
                        f"Muss ignoriert sein: {relative_path}\n{result.stderr}",
                    )

            for relative_path in tracked_paths:
                with self.subTest(path=relative_path, expected="tracked"):
                    result = self._check_ignore(repository, relative_path)
                    self.assertEqual(
                        result.returncode,
                        1,
                        f"Darf nicht ignoriert sein: {relative_path}\n{result.stdout}",
                    )

    @staticmethod
    def _check_ignore(repository, relative_path):
        return subprocess.run(
            [
                GIT,
                "-c",
                f"core.excludesFile={os.devnull}",
                "check-ignore",
                "--no-index",
                "--quiet",
                "--",
                relative_path,
            ],
            cwd=repository,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )


if __name__ == "__main__":
    unittest.main()

