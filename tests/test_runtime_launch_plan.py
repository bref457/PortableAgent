import subprocess
import unittest
from unittest.mock import patch

from portable_agent.runtime import (
    LocalAssetInventory,
    LocalGgufModel,
    LocalLaunchPlanError,
    LocalLlamaRuntime,
    build_local_llama_launch_plan,
)


def synthetic_inventory() -> LocalAssetInventory:
    return LocalAssetInventory(
        llama_runtimes=(
            LocalLlamaRuntime(
                relative_path="runtime/llama.cpp/llama-server.exe",
                size_bytes=100,
            ),
        ),
        gguf_models=(
            LocalGgufModel(
                name="synthetic.gguf",
                relative_path="models/synthetic.gguf",
                size_bytes=200,
            ),
        ),
    )


class RuntimeLaunchPlanTests(unittest.TestCase):
    def test_builds_fixed_loopback_argument_vector_from_explicit_assets(self):
        plan = build_local_llama_launch_plan(
            synthetic_inventory(),
            runtime_path="runtime/llama.cpp/llama-server.exe",
            model_path="models/synthetic.gguf",
            port=8081,
            context_size=8192,
        )

        self.assertEqual(plan.executable, "runtime/llama.cpp/llama-server.exe")
        self.assertEqual(
            plan.arguments,
            (
                "--model",
                "models/synthetic.gguf",
                "--host",
                "127.0.0.1",
                "--port",
                "8081",
                "--ctx-size",
                "8192",
            ),
        )
        self.assertEqual(plan.command, (plan.executable, *plan.arguments))

    def test_rejects_assets_that_are_not_in_inventory(self):
        for runtime_path, model_path in (
            ("runtime/llama.cpp/bin/llama-server.exe", "models/synthetic.gguf"),
            ("runtime/llama.cpp/llama-server.exe", "models/other.gguf"),
        ):
            with self.subTest(runtime_path=runtime_path, model_path=model_path):
                with self.assertRaises(LocalLaunchPlanError):
                    build_local_llama_launch_plan(
                        synthetic_inventory(),
                        runtime_path=runtime_path,
                        model_path=model_path,
                    )

    def test_rejects_nonportable_paths_and_uncontrolled_limits(self):
        invalid_cases = (
            {"runtime_path": "../llama-server.exe"},
            {"model_path": "D:/models/synthetic.gguf"},
            {"model_path": "models\\synthetic.gguf"},
            {"model_path": "models/synthetic.gguf\n"},
            {"port": True},
            {"port": 0},
            {"context_size": 511},
            {"context_size": 131_073},
        )
        base = {
            "runtime_path": "runtime/llama.cpp/llama-server.exe",
            "model_path": "models/synthetic.gguf",
        }
        for overrides in invalid_cases:
            with self.subTest(overrides=overrides):
                with self.assertRaises(LocalLaunchPlanError):
                    build_local_llama_launch_plan(
                        synthetic_inventory(),
                        **(base | overrides),
                    )

    def test_inventory_cannot_broaden_fixed_path_allowlists(self):
        broadened_inventory = LocalAssetInventory(
            llama_runtimes=(
                LocalLlamaRuntime(
                    relative_path="runtime/other.exe",
                    size_bytes=100,
                ),
            ),
            gguf_models=(
                LocalGgufModel(
                    name="hidden.gguf",
                    relative_path="models/nested/hidden.gguf",
                    size_bytes=200,
                ),
            ),
        )
        with self.assertRaises(LocalLaunchPlanError):
            build_local_llama_launch_plan(
                broadened_inventory,
                runtime_path="runtime/other.exe",
                model_path="models/nested/hidden.gguf",
            )

    def test_building_plan_never_starts_a_process(self):
        with (
            patch.object(subprocess, "Popen") as popen,
            patch.object(subprocess, "run") as run,
        ):
            build_local_llama_launch_plan(
                synthetic_inventory(),
                runtime_path="runtime/llama.cpp/llama-server.exe",
                model_path="models/synthetic.gguf",
            )

        popen.assert_not_called()
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
