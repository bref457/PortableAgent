import builtins
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from portable_agent.runtime import discover_local_assets
from portable_agent.runtime.discovery import LocalAssetDiscoveryError


class RuntimeDiscoveryTests(unittest.TestCase):
    def test_missing_fixed_directories_produce_empty_inventory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            inventory = discover_local_assets(temporary_directory)

        self.assertEqual(inventory.llama_runtimes, ())
        self.assertEqual(inventory.gguf_models, ())

    def test_discovers_only_allowlisted_runtime_paths_and_direct_gguf_models(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            runtime_directory = root / "runtime" / "llama.cpp" / "bin"
            model_directory = root / "models"
            nested_directory = model_directory / "nested"
            runtime_directory.mkdir(parents=True)
            nested_directory.mkdir(parents=True)

            (runtime_directory / "llama-server.exe").write_bytes(b"runtime")
            (runtime_directory / "unrelated.exe").write_bytes(b"ignored")
            (model_directory / "Zulu.GGUF").write_bytes(b"model-z")
            (model_directory / "alpha.gguf").write_bytes(b"model-a")
            (model_directory / "notes.txt").write_text("ignored", encoding="utf-8")
            (nested_directory / "hidden.gguf").write_bytes(b"ignored")

            inventory = discover_local_assets(root)

        self.assertEqual(
            [runtime.relative_path for runtime in inventory.llama_runtimes],
            ["runtime/llama.cpp/bin/llama-server.exe"],
        )
        self.assertEqual(inventory.llama_runtimes[0].size_bytes, len(b"runtime"))
        self.assertEqual(
            [model.name for model in inventory.gguf_models],
            ["alpha.gguf", "Zulu.GGUF"],
        )
        self.assertEqual(
            [model.relative_path for model in inventory.gguf_models],
            ["models/alpha.gguf", "models/Zulu.GGUF"],
        )

    def test_discovery_does_not_open_detected_assets(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            runtime_directory = root / "runtime" / "llama.cpp"
            model_directory = root / "models"
            runtime_directory.mkdir(parents=True)
            model_directory.mkdir()
            (runtime_directory / "llama-server.exe").write_bytes(b"runtime")
            (model_directory / "synthetic.gguf").write_bytes(b"model")

            with patch.object(
                builtins,
                "open",
                side_effect=AssertionError("Asset-Inhalte duerfen nicht geoeffnet werden."),
            ):
                inventory = discover_local_assets(root)

        self.assertEqual(len(inventory.llama_runtimes), 1)
        self.assertEqual(len(inventory.gguf_models), 1)

    def test_rejects_non_directory_project_root(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root_file = Path(temporary_directory) / "root.txt"
            root_file.write_text("synthetic", encoding="utf-8")

            with self.assertRaises(LocalAssetDiscoveryError):
                discover_local_assets(root_file)


if __name__ == "__main__":
    unittest.main()
