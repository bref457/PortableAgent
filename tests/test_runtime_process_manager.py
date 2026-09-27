import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from portable_agent.runtime import (
    LocalLlamaProcessError,
    LocalLlamaProcessManager,
    LocalLlamaProcessStateError,
    build_local_llama_launch_plan,
    discover_local_assets,
)


class FakeProcess:
    def __init__(self, *, time_out_once: bool = False):
        self.returncode = None
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_calls = []
        self.time_out_once = time_out_once

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminate_calls += 1

    def kill(self):
        self.kill_calls += 1
        self.returncode = -9

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        if self.time_out_once:
            self.time_out_once = False
            raise subprocess.TimeoutExpired("synthetic", timeout)
        self.returncode = 0 if self.returncode is None else self.returncode
        return self.returncode


class RecordingFactory:
    def __init__(self, process):
        self.process = process
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        return self.process


class RuntimeProcessManagerTests(unittest.TestCase):
    def make_project(self, root: Path):
        runtime = root / "runtime" / "llama.cpp" / "llama-server.exe"
        model = root / "models" / "synthetic.gguf"
        runtime.parent.mkdir(parents=True)
        model.parent.mkdir()
        runtime.write_bytes(b"synthetic runtime")
        model.write_bytes(b"synthetic model")
        inventory = discover_local_assets(root)
        return build_local_llama_launch_plan(
            inventory,
            runtime_path="runtime/llama.cpp/llama-server.exe",
            model_path="models/synthetic.gguf",
        )

    def test_construction_and_plan_creation_never_start_a_process(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            plan = self.make_project(root)
            with patch.object(subprocess, "Popen") as popen:
                manager = LocalLlamaProcessManager(root)

        self.assertFalse(manager.is_running)
        self.assertEqual(plan.model_path, "models/synthetic.gguf")
        popen.assert_not_called()

    def test_start_uses_exact_vector_without_shell_and_stop_owns_child(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            plan = self.make_project(root)
            process = FakeProcess()
            factory = RecordingFactory(process)
            manager = LocalLlamaProcessManager(root, process_factory=factory)

            manager.start(plan)
            self.assertTrue(manager.is_running)
            self.assertEqual(len(factory.calls), 1)
            command, options = factory.calls[0]
            self.assertEqual(command, plan.command)
            self.assertEqual(options["cwd"], str(root.resolve()))
            self.assertIs(options["shell"], False)
            self.assertIs(options["stdin"], subprocess.DEVNULL)
            self.assertIs(options["stdout"], subprocess.DEVNULL)
            self.assertIs(options["stderr"], subprocess.DEVNULL)

            self.assertTrue(manager.stop())

        self.assertEqual(process.terminate_calls, 1)
        self.assertEqual(process.kill_calls, 0)
        self.assertFalse(manager.is_running)

    def test_second_start_is_rejected_while_owned_process_runs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            plan = self.make_project(root)
            process = FakeProcess()
            factory = RecordingFactory(process)
            manager = LocalLlamaProcessManager(root, process_factory=factory)
            manager.start(plan)

            with self.assertRaises(LocalLlamaProcessStateError):
                manager.start(plan)
            manager.stop()

        self.assertEqual(len(factory.calls), 1)

    def test_start_revalidates_assets_immediately_before_process_creation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            plan = self.make_project(root)
            (root / plan.model_path).unlink()
            factory = RecordingFactory(FakeProcess())
            manager = LocalLlamaProcessManager(root, process_factory=factory)

            with self.assertRaises(LocalLlamaProcessError):
                manager.start(plan)

        self.assertEqual(factory.calls, [])

    def test_stop_escalates_only_its_child_after_timeout(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            plan = self.make_project(root)
            process = FakeProcess(time_out_once=True)
            manager = LocalLlamaProcessManager(
                root,
                stop_timeout_seconds=0.25,
                process_factory=RecordingFactory(process),
            )
            manager.start(plan)

            self.assertTrue(manager.stop())

        self.assertEqual(process.terminate_calls, 1)
        self.assertEqual(process.kill_calls, 1)
        self.assertEqual(process.wait_calls, [0.25, 0.25])


if __name__ == "__main__":
    unittest.main()
