import http.client
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.application import (
    LocalApplicationStateError,
    create_local_document_application,
)
from portable_agent.sessions import DocumentSessionManager
from portable_agent.memory import SqliteMemoryRepository
from portable_agent.runtime import (
    LocalLlamaProcessManager,
    build_local_llama_launch_plan,
    discover_local_assets,
)


class FakeCompletionClient:
    def __init__(self):
        self.calls = []

    def complete_json(self, messages, *, max_tokens=500, temperature=0.0):
        self.calls.append({
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        })
        if "Tabellen-Analyseplan" in messages[0]["content"]:
            if "Einsatzdauer" in messages[0]["content"]:
                return {
                    "calculations": [
                        {
                            "label": "Dauer",
                            "aggregation": "average",
                            "column": "Einsatzdauer",
                        }
                    ]
                }
            return {
                "calculations": [
                    {"label": "FIX", "aggregation": "sum", "column": "Fix"}
                ]
            }
        return {"answer": "Die Frist betraegt drei Tage."}


class FakeManagedChildProcess:
    def __init__(self):
        self.returncode = None
        self.terminate_calls = 0

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminate_calls += 1

    def wait(self, timeout=None):
        self.returncode = 0
        return self.returncode

    def kill(self):
        self.returncode = -9


class LocalDocumentApplicationTests(unittest.TestCase):
    def setUp(self):
        self._memory_directory = tempfile.TemporaryDirectory()
        self.memory_repository = SqliteMemoryRepository(
            Path(self._memory_directory.name) / "memory.sqlite3"
        )

    def tearDown(self):
        self._memory_directory.cleanup()

    def create_application(self, **kwargs):
        return create_local_document_application(
            memory_repository=self.memory_repository,
            **kwargs,
        )

    def test_factory_binds_but_does_not_start_or_call_model(self):
        client = FakeCompletionClient()
        app = self.create_application(completion_client=client, port=0)
        try:
            self.assertEqual(app.address[0], "127.0.0.1")
            self.assertGreater(app.address[1], 0)
            self.assertFalse(app.is_serving)
            self.assertFalse(app.is_closed)
            self.assertFalse(app.managed_model_running)
            self.assertEqual(client.calls, [])
        finally:
            app.shutdown()
        self.assertTrue(app.is_closed)

    def test_shutdown_stops_explicitly_started_managed_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime_path = root / "runtime" / "llama.cpp" / "llama-server.exe"
            model_path = root / "models" / "synthetic.gguf"
            runtime_path.parent.mkdir(parents=True)
            model_path.parent.mkdir()
            runtime_path.write_bytes(b"synthetic runtime")
            model_path.write_bytes(b"synthetic model")
            inventory = discover_local_assets(root)
            plan = build_local_llama_launch_plan(
                inventory,
                runtime_path="runtime/llama.cpp/llama-server.exe",
                model_path="models/synthetic.gguf",
            )
            process = FakeManagedChildProcess()
            manager = LocalLlamaProcessManager(
                root,
                process_factory=lambda *args, **kwargs: process,
            )
            manager.start(plan)
            app = self.create_application(
                completion_client=FakeCompletionClient(),
                model_process_manager=manager,
                port=0,
            )

            self.assertTrue(app.managed_model_running)
            app.shutdown()
            app.shutdown()

        self.assertEqual(process.terminate_calls, 1)
        self.assertFalse(manager.is_running)
        self.assertFalse(app.managed_model_running)
        self.assertTrue(app.is_closed)

    def test_factory_rejects_unmanaged_process_objects(self):
        with self.assertRaisesRegex(TypeError, "model_process_manager"):
            self.create_application(
                completion_client=FakeCompletionClient(),
                model_process_manager=object(),
                port=0,
            )

    def test_cleanup_failure_does_not_skip_managed_model_stop(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime_path = root / "runtime" / "llama.cpp" / "llama-server.exe"
            model_path = root / "models" / "synthetic.gguf"
            runtime_path.parent.mkdir(parents=True)
            model_path.parent.mkdir()
            runtime_path.write_bytes(b"synthetic runtime")
            model_path.write_bytes(b"synthetic model")
            inventory = discover_local_assets(root)
            plan = build_local_llama_launch_plan(
                inventory,
                runtime_path="runtime/llama.cpp/llama-server.exe",
                model_path="models/synthetic.gguf",
            )
            process = FakeManagedChildProcess()
            manager = LocalLlamaProcessManager(
                root,
                process_factory=lambda *args, **kwargs: process,
            )
            manager.start(plan)
            app = self.create_application(
                completion_client=FakeCompletionClient(),
                model_process_manager=manager,
                port=0,
            )

            with (
                patch.object(
                    app._workflow,
                    "release_all",
                    side_effect=RuntimeError("synthetic cleanup failure"),
                ),
                self.assertRaisesRegex(RuntimeError, "synthetic cleanup failure"),
            ):
                app.shutdown()

        self.assertEqual(process.terminate_calls, 1)
        self.assertFalse(manager.is_running)
        self.assertTrue(app.is_closed)

    def test_explicit_server_lifecycle_runs_complete_local_flow(self):
        client = FakeCompletionClient()
        sessions = DocumentSessionManager(id_factory=lambda: "app-session")
        app = self.create_application(
            completion_client=client,
            sessions=sessions,
            port=0,
        )
        thread = threading.Thread(target=app.serve_forever, daemon=True)
        thread.start()
        try:
            self.wait_until_serving(app)
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "synthetic.txt"
                path.write_text(
                    "Die lokale Frist betraegt drei Tage.",
                    encoding="utf-8",
                )
                opened = self.json_post(app, {
                    "operation": "open_document",
                    "path": str(path),
                })
                answered = self.json_post(app, {
                    "operation": "ask",
                    "session_id": "app-session",
                    "question": "Welche lokale Frist gilt?",
                })
                table_path = Path(temporary) / "synthetic.csv"
                table_path.write_text(
                    "Fix;InterneNotiz\n2;APP_GEHEIM_19\n3;APP_GEHEIM_73\n",
                    encoding="utf-8",
                )
                table_answered = self.json_post(
                    app,
                    {
                        "operation": "ask_table",
                        "path": str(table_path),
                        "question": "Wie viele FIX gibt es insgesamt?",
                    },
                    api_path="/api/table",
                )
                memory_added = self.json_post(
                    app,
                    {
                        "operation": "add_note",
                        "text": "Synthetische App-Notiz",
                        "confirmation": "confirmed",
                    },
                    api_path="/api/memory",
                )
                memory_listed = self.json_post(
                    app,
                    {"operation": "list_notes"},
                    api_path="/api/memory",
                )

            self.assertEqual(opened["session"]["session_id"], "app-session")
            self.assertEqual(answered["answer"]["matched_chunks"], 1)
            self.assertEqual(answered["answer"]["citations"][0]["display_name"], "synthetic.txt")
            self.assertEqual(table_answered["result"]["values"], {"FIX": 5})
            self.assertEqual(
                memory_listed["notes"],
                [memory_added["note"]],
            )
            self.assertEqual(len(client.calls), 2)
            self.assertEqual(client.calls[0]["temperature"], 0.0)
            self.assertNotIn("APP_GEHEIM_19", repr(client.calls))
            self.assertNotIn("APP_GEHEIM_73", repr(client.calls))
            self.assertEqual(app.active_session_count, 1)
        finally:
            app.shutdown()
            thread.join(timeout=2)

        self.assertFalse(thread.is_alive())
        self.assertFalse(app.is_serving)
        self.assertTrue(app.is_closed)
        self.assertEqual(app.active_session_count, 0)

    def test_shutdown_before_start_is_idempotent_and_closes_application(self):
        app = self.create_application(
            completion_client=FakeCompletionClient(),
            port=0,
        )
        app.shutdown()
        app.shutdown()

        self.assertTrue(app.is_closed)
        with self.assertRaisesRegex(LocalApplicationStateError, "geschlossen"):
            app.serve_forever()

    def test_shutdown_releases_pending_table_clarification(self):
        client = FakeCompletionClient()
        app = self.create_application(
            completion_client=client,
            port=0,
        )
        thread = threading.Thread(target=app.serve_forever, daemon=True)
        thread.start()
        try:
            self.wait_until_serving(app)
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "synthetic.csv"
                path.write_text("Einsatzdauer\n2\n4\n", encoding="utf-8")
                response = self.json_post(
                    app,
                    {
                        "operation": "ask_table",
                        "path": str(path),
                        "question": "Wie lange war der Einsatz?",
                    },
                    api_path="/api/table",
                )

            self.assertEqual(response["result"]["type"], "clarification")
            self.assertEqual(app.pending_table_clarification_count, 1)
            self.assertEqual(len(client.calls), 1)
        finally:
            app.shutdown()
            thread.join(timeout=2)

        self.assertEqual(app.pending_table_clarification_count, 0)
        self.assertTrue(app.is_closed)

    def test_invalid_poll_interval_is_rejected_without_starting(self):
        app = self.create_application(
            completion_client=FakeCompletionClient(),
            port=0,
        )
        try:
            for value in (True, 0, -1, float("inf")):
                with self.subTest(value=value):
                    with self.assertRaisesRegex(LocalApplicationStateError, "poll_interval"):
                        app.serve_forever(poll_interval=value)
            self.assertFalse(app.is_serving)
        finally:
            app.shutdown()

    def wait_until_serving(self, app):
        deadline = time.monotonic() + 2
        while not app.is_serving and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(app.is_serving)

    def json_post(self, app, payload, *, api_path="/api/document"):
        host, port = app.address
        connection = http.client.HTTPConnection(host, port, timeout=2)
        try:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            connection.request(
                "POST",
                api_path,
                body=body,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
            response = connection.getresponse()
            response_body = json.loads(response.read())
            self.assertEqual(response.status, 200)
            return response_body
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
