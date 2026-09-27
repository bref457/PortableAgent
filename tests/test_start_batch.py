import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StartBatchTests(unittest.TestCase):
    def test_batch_uses_its_own_directory_and_prefers_portable_runtime(self):
        content = (ROOT / "start.bat").read_text(encoding="utf-8")

        self.assertIn('cd /d "%~dp0"', content)
        self.assertIn('set "PYTHONPATH=%PORTABLE_AGENT_ROOT%\\src"', content)
        self.assertIn(
            "%PORTABLE_AGENT_ROOT%\\runtime\\python\\python.exe",
            content,
        )
        self.assertNotIn("D:\\PortableAgent", content)
        self.assertNotIn("D:\\PortableLLM", content)
        self.assertNotIn("https://", content)
        self.assertNotIn("llama-server", content)
        self.assertIn("--start-detected-assets", content)
        self.assertIn("/api/shutdown", content)
        self.assertNotIn("Stop-Process", content)
        self.assertNotRegex(
            content,
            r"PortableAgent wurde beendet\.\s*\r?\npause",
        )
        self.assertIn("Mit dem aktuellen Projektstand neu starten?", content)
        self.assertIn("$health.service -ne 'portable-agent'", content)
        self.assertGreaterEqual(
            content.count("import sys, openpyxl, pypdf"),
            4,
            "Jeder Python-Kandidat muss vor seiner Auswahl geprueft werden.",
        )

    @unittest.skipUnless(sys.platform == "win32", "Windows-Batchdatei")
    def test_check_mode_validates_runtime_without_starting_server(self):
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", str(ROOT / "start.bat"), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Startpruefung erfolgreich", result.stdout)

    @unittest.skipUnless(sys.platform == "win32", "Windows-Batchdatei")
    def test_asset_list_mode_uses_selected_runtime_without_starting_server(self):
        result = subprocess.run(
            [
                "cmd.exe",
                "/d",
                "/c",
                str(ROOT / "start.bat"),
                "--list-local-assets",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Erkannte portable llama.cpp-Runtimes", result.stdout)
        self.assertIn("Erkannte lokale GGUF-Modelle", result.stdout)
        self.assertNotIn("PortableAgent startet", result.stdout)


if __name__ == "__main__":
    unittest.main()
