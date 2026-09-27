import io
import sys
import unittest
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.cli import build_parser, main


class FakeApplication:
    def __init__(self, *, interrupt=False):
        self.address = ("127.0.0.1", 9001)
        self.interrupt = interrupt
        self.serve_calls = 0
        self.shutdown_calls = 0

    def serve_forever(self):
        self.serve_calls += 1
        if self.interrupt:
            raise KeyboardInterrupt

    def shutdown(self):
        self.shutdown_calls += 1


class RecordingFactory:
    def __init__(self, application=None, error=None):
        self.application = application
        self.error = error
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.application


class FakeProcessManager:
    def __init__(self):
        self.started_plans = []
        self.stop_calls = 0

    def start(self, plan):
        self.started_plans.append(plan)

    def stop(self):
        self.stop_calls += 1
        return True


class RecordingManagerFactory:
    def __init__(self, manager):
        self.manager = manager
        self.calls = []

    def __call__(self, project_root):
        self.calls.append(Path(project_root))
        return self.manager


class CliTests(unittest.TestCase):
    def test_arguments_are_forwarded_without_starting_other_processes(self):
        app = FakeApplication()
        factory = RecordingFactory(app)
        output = io.StringIO()

        with redirect_stdout(output):
            result = main(
                [
                    "--port", "9001",
                    "--llama-endpoint", "http://127.0.0.1:9090/v1/chat/completions",
                    "--llama-timeout", "30",
                ],
                application_factory=factory,
            )

        self.assertEqual(result, 0)
        self.assertEqual(factory.calls, [{
            "endpoint": "http://127.0.0.1:9090/v1/chat/completions",
            "llama_timeout_seconds": 30.0,
            "port": 9001,
        }])
        self.assertEqual(app.serve_calls, 1)
        self.assertEqual(app.shutdown_calls, 1)
        self.assertIn("http://127.0.0.1:9001", output.getvalue())

    def test_keyboard_interrupt_performs_clean_shutdown(self):
        app = FakeApplication(interrupt=True)
        output = io.StringIO()

        with redirect_stdout(output):
            result = main([], application_factory=RecordingFactory(app))

        self.assertEqual(result, 0)
        self.assertEqual(app.shutdown_calls, 1)
        self.assertIn("wird beendet", output.getvalue())

    def test_configuration_error_is_reported_without_traceback(self):
        error = ValueError("synthetisch ungueltige lokale Konfiguration")
        factory = RecordingFactory(error=error)
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            result = main([], application_factory=factory)

        self.assertEqual(result, 2)
        self.assertIn("konnte nicht gestartet werden", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_parser_rejects_invalid_port_timeout_and_unknown_options(self):
        parser = build_parser()
        cases = (
            ["--port", "0"],
            ["--port", "65536"],
            ["--llama-timeout", "nan"],
            ["--llama-timeout", "0"],
            ["--host", "0.0.0.0"],
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        parser.parse_args(arguments)

    def test_local_runtime_and_model_must_be_supplied_together(self):
        for arguments in (
            ["--local-runtime", "runtime/llama.cpp/llama-server.exe"],
            ["--local-model", "models/synthetic.gguf"],
        ):
            with self.subTest(arguments=arguments):
                stderr = io.StringIO()
                factory = RecordingFactory(FakeApplication())
                with redirect_stderr(stderr):
                    result = main(arguments, application_factory=factory)

                self.assertEqual(result, 2)
                self.assertEqual(factory.calls, [])
                self.assertIn("gemeinsam", stderr.getvalue())

    def test_explicit_local_assets_start_manager_and_are_forwarded_to_app(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / "runtime" / "llama.cpp" / "llama-server.exe"
            model = root / "models" / "synthetic.gguf"
            runtime.parent.mkdir(parents=True)
            model.parent.mkdir()
            runtime.write_bytes(b"synthetic runtime")
            model.write_bytes(b"synthetic model")
            manager = FakeProcessManager()
            manager_factory = RecordingManagerFactory(manager)
            application = FakeApplication()
            application_factory = RecordingFactory(application)

            result = main(
                [
                    "--local-runtime",
                    "runtime/llama.cpp/llama-server.exe",
                    "--local-model",
                    "models/synthetic.gguf",
                ],
                application_factory=application_factory,
                process_manager_factory=manager_factory,
                project_root=root,
            )

        self.assertEqual(result, 0)
        self.assertEqual(manager_factory.calls, [root.resolve()])
        self.assertEqual(len(manager.started_plans), 1)
        self.assertEqual(
            manager.started_plans[0].model_path,
            "models/synthetic.gguf",
        )
        self.assertIs(
            application_factory.calls[0]["model_process_manager"],
            manager,
        )
        self.assertEqual(manager.stop_calls, 1)

    def test_detected_asset_start_requires_and_selects_exactly_one_pair(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / "runtime" / "llama.cpp" / "llama-server.exe"
            model = root / "models" / "synthetic.gguf"
            runtime.parent.mkdir(parents=True)
            model.parent.mkdir()
            runtime.write_bytes(b"synthetic runtime")
            model.write_bytes(b"synthetic model")
            manager = FakeProcessManager()
            application = FakeApplication()
            application_factory = RecordingFactory(application)

            result = main(
                ["--start-detected-assets"],
                application_factory=application_factory,
                process_manager_factory=RecordingManagerFactory(manager),
                project_root=root,
            )

        self.assertEqual(result, 0)
        self.assertEqual(len(manager.started_plans), 1)
        self.assertEqual(
            manager.started_plans[0].executable,
            "runtime/llama.cpp/llama-server.exe",
        )
        self.assertEqual(
            manager.started_plans[0].model_path,
            "models/synthetic.gguf",
        )
        self.assertIs(
            application_factory.calls[0]["model_process_manager"],
            manager,
        )

    def test_detected_asset_start_rejects_missing_or_ambiguous_assets(self):
        cases = (0, 2)
        for model_count in cases:
            with self.subTest(model_count=model_count):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    runtime = root / "runtime" / "llama.cpp" / "llama-server.exe"
                    runtime.parent.mkdir(parents=True)
                    runtime.write_bytes(b"runtime")
                    models = root / "models"
                    models.mkdir()
                    for index in range(model_count):
                        (models / f"model-{index}.gguf").write_bytes(b"model")
                    application_factory = RecordingFactory(FakeApplication())
                    stderr = io.StringIO()

                    with redirect_stderr(stderr):
                        result = main(
                            ["--start-detected-assets"],
                            application_factory=application_factory,
                            project_root=root,
                        )

                self.assertEqual(result, 2)
                self.assertEqual(application_factory.calls, [])
                self.assertIn("genau ein erkanntes GGUF-Modell", stderr.getvalue())

    def test_application_failure_stops_new_managed_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / "runtime" / "llama.cpp" / "llama-server.exe"
            model = root / "models" / "synthetic.gguf"
            runtime.parent.mkdir(parents=True)
            model.parent.mkdir()
            runtime.write_bytes(b"synthetic runtime")
            model.write_bytes(b"synthetic model")
            manager = FakeProcessManager()
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                result = main(
                    [
                        "--local-runtime",
                        "runtime/llama.cpp/llama-server.exe",
                        "--local-model",
                        "models/synthetic.gguf",
                    ],
                    application_factory=RecordingFactory(
                        error=OSError("synthetic bind failure")
                    ),
                    process_manager_factory=RecordingManagerFactory(manager),
                    project_root=root,
                )

        self.assertEqual(result, 2)
        self.assertEqual(len(manager.started_plans), 1)
        self.assertEqual(manager.stop_calls, 1)
        self.assertIn("konnte nicht gestartet werden", stderr.getvalue())

    def test_managed_start_rejects_custom_llama_endpoint(self):
        stderr = io.StringIO()
        manager = FakeProcessManager()
        with redirect_stderr(stderr):
            result = main(
                [
                    "--local-runtime",
                    "runtime/llama.cpp/llama-server.exe",
                    "--local-model",
                    "models/synthetic.gguf",
                    "--llama-endpoint",
                    "http://127.0.0.1:9090/v1/chat/completions",
                ],
                application_factory=RecordingFactory(FakeApplication()),
                process_manager_factory=RecordingManagerFactory(manager),
            )

        self.assertEqual(result, 2)
        self.assertEqual(manager.started_plans, [])
        self.assertIn("festen Endpunkt", stderr.getvalue())

    def test_list_local_assets_prints_only_relative_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / "runtime" / "llama.cpp" / "llama-server.exe"
            model = root / "models" / "synthetic.gguf"
            runtime.parent.mkdir(parents=True)
            model.parent.mkdir()
            runtime.write_bytes(b"runtime")
            model.write_bytes(b"model")
            application_factory = RecordingFactory(FakeApplication())
            manager = FakeProcessManager()
            manager_factory = RecordingManagerFactory(manager)
            output = io.StringIO()

            with redirect_stdout(output):
                result = main(
                    ["--list-local-assets"],
                    application_factory=application_factory,
                    process_manager_factory=manager_factory,
                    project_root=root,
                )

        rendered = output.getvalue()
        self.assertEqual(result, 0)
        self.assertIn("runtime/llama.cpp/llama-server.exe (7 Bytes)", rendered)
        self.assertIn("models/synthetic.gguf (5 Bytes)", rendered)
        self.assertNotIn(str(root), rendered)
        self.assertEqual(application_factory.calls, [])
        self.assertEqual(manager_factory.calls, [])
        self.assertEqual(manager.started_plans, [])

    def test_list_local_assets_reports_empty_inventory_without_starting(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = io.StringIO()
            application_factory = RecordingFactory(FakeApplication())
            with redirect_stdout(output):
                result = main(
                    ["--list-local-assets"],
                    application_factory=application_factory,
                    project_root=temporary,
                )

        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue().count("- keine"), 2)
        self.assertEqual(application_factory.calls, [])

    def test_list_local_assets_rejects_combined_model_start(self):
        stderr = io.StringIO()
        application_factory = RecordingFactory(FakeApplication())
        with redirect_stderr(stderr):
            result = main(
                [
                    "--list-local-assets",
                    "--local-runtime",
                    "runtime/llama.cpp/llama-server.exe",
                    "--local-model",
                    "models/synthetic.gguf",
                ],
                application_factory=application_factory,
            )

        self.assertEqual(result, 2)
        self.assertEqual(application_factory.calls, [])
        self.assertIn("nicht mit einem Modellstart", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
