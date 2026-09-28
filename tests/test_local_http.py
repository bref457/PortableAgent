import http.client
import json
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.agent import DocumentWorkflow, TableWorkflow
from portable_agent.llm import LlamaCppResponseError, LlamaCppUnavailableError
from portable_agent.memory import SqliteMemoryRepository
from portable_agent.runtime import (
    LocalAssetInventory,
    LocalGgufModel,
    LocalLlamaRuntime,
)
from portable_agent.sessions import DocumentSessionManager
from portable_agent.web import (
    DOCUMENT_UPLOAD_PATH,
    TABLE_FILE_API_PATH,
    DocumentJsonController,
    LocalHttpConfigurationError,
    MemoryJsonController,
    TableJsonController,
    create_local_http_server,
)


class FixedAnswerGenerator:
    def generate_answer(self, question, contexts):
        return "Die Frist betraegt drei Tage."


class FixedPlanGenerator:
    def __init__(self):
        self.calls = []

    def generate_plan(self, question, columns, semantic_definitions):
        self.calls.append((question, columns, dict(semantic_definitions)))
        if "Einsatzdauer" in columns:
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


class RaisingPlanGenerator:
    def __init__(self, error):
        self.error = error

    def generate_plan(self, question, columns, semantic_definitions):
        raise self.error


class LocalHttpTests(unittest.TestCase):
    def setUp(self):
        workflow = DocumentWorkflow(
            FixedAnswerGenerator(),
            sessions=DocumentSessionManager(id_factory=lambda: "http-session"),
        )
        self.controller = DocumentJsonController(workflow)
        self.plan_generator = FixedPlanGenerator()
        self.table_controller = TableJsonController(
            TableWorkflow(self.plan_generator)
        )
        self.model_ready = True

    def test_health_endpoint_is_local_json_and_not_cached(self):
        with self.running_server() as port:
            status, headers, payload = self.request(port, "GET", "/health")

        self.assertEqual(status, 200)
        self.assertEqual(payload, {
            "assets": {
                "gguf_models": {"available": False, "count": 0},
                "llama_runtime": {"available": False, "count": 0},
                "status": "ready",
            },
            "model": {"status": "ready"},
            "ok": True,
            "service": "portable-agent",
            "status": "ready",
        })
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    def test_health_reports_unavailable_model_without_failing_application(self):
        self.model_ready = False
        with self.running_server() as port:
            status, _, payload = self.request(port, "GET", "/health")

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["model"]["status"], "unavailable")

    def test_health_reports_only_counts_for_detected_portable_assets(self):
        inventory = LocalAssetInventory(
            llama_runtimes=(
                LocalLlamaRuntime(
                    relative_path="runtime/llama.cpp/llama-server.exe",
                    size_bytes=123,
                ),
            ),
            gguf_models=(
                LocalGgufModel(
                    name="synthetic.gguf",
                    relative_path="models/synthetic.gguf",
                    size_bytes=456,
                ),
            ),
        )
        with self.running_server(
            asset_inventory_provider=lambda: inventory,
        ) as port:
            status, _, payload = self.request(port, "GET", "/health")

        self.assertEqual(status, 200)
        self.assertEqual(payload["assets"], {
            "gguf_models": {"available": True, "count": 1},
            "llama_runtime": {"available": True, "count": 1},
            "status": "ready",
        })
        self.assertNotIn("synthetic.gguf", repr(payload))
        self.assertNotIn("llama-server.exe", repr(payload))

    def test_health_contains_asset_provider_failure(self):
        def fail():
            raise OSError("synthetic failure")

        with self.running_server(asset_inventory_provider=fail) as port:
            status, _, payload = self.request(port, "GET", "/health")

        self.assertEqual(status, 200)
        self.assertEqual(payload["assets"]["status"], "unavailable")
        self.assertFalse(payload["assets"]["llama_runtime"]["available"])
        self.assertFalse(payload["assets"]["gguf_models"]["available"])

    def test_local_start_page_has_restrictive_security_policy(self):
        with self.running_server() as port:
            status, headers, body = self.raw_request(port, "GET", "/")

        html = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        self.assertIn("connect-src 'self'", headers["Content-Security-Policy"])
        self.assertNotIn("'unsafe-inline'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        self.assertIn("PortableAgent", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("style=", html)

    def test_css_and_javascript_are_local_assets_without_external_dependencies(self):
        with self.running_server() as port:
            css_status, css_headers, css_body = self.raw_request(
                port, "GET", "/assets/app.css"
            )
            modes_status, modes_headers, modes_body = self.raw_request(
                port, "GET", "/assets/modes.css"
            )
            js_status, js_headers, js_body = self.raw_request(
                port, "GET", "/assets/app.js"
            )

        css = css_body.decode("utf-8")
        modes = modes_body.decode("utf-8")
        javascript = js_body.decode("utf-8")
        self.assertEqual(css_status, 200)
        self.assertEqual(modes_status, 200)
        self.assertEqual(js_status, 200)
        self.assertEqual(css_headers["Content-Type"], "text/css; charset=utf-8")
        self.assertEqual(modes_headers["Content-Type"], "text/css; charset=utf-8")
        self.assertEqual(js_headers["Content-Type"], "text/javascript; charset=utf-8")
        self.assertIn("prefers-reduced-motion", css + modes)
        self.assertIn('const DOCUMENT_API = "/api/document"', javascript)
        self.assertIn('const TABLE_API = "/api/table"', javascript)
        self.assertIn('const MEMORY_API = "/api/memory"', javascript)
        self.assertIn("textContent", javascript)
        self.assertNotIn("innerHTML", javascript)
        self.assertNotIn("localStorage", javascript)
        self.assertNotIn("https://", css + modes + javascript)

    def test_document_post_runs_synthetic_import_and_question(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.txt"
            path.write_text("Die lokale Frist betraegt drei Tage.", encoding="utf-8")
            before = path.read_bytes()
            with self.running_server() as port:
                opened = self.json_post(port, {
                    "operation": "open_document",
                    "path": str(path),
                })
                answered = self.json_post(port, {
                    "operation": "ask",
                    "session_id": "http-session",
                    "question": "Welche lokale Frist gilt?",
                })

            self.assertEqual(path.read_bytes(), before)

        self.assertEqual(opened[0], 200)
        self.assertEqual(opened[2]["session"]["session_id"], "http-session")
        self.assertEqual(answered[0], 200)
        self.assertEqual(answered[2]["answer"]["matched_chunks"], 1)
        self.assertEqual(
            answered[2]["answer"]["citations"][0]["display_name"],
            "synthetic.txt",
        )

    def test_document_picker_upload_opens_synthetic_file_locally(self):
        body = "Die lokale Frist betraegt drei Tage.".encode("utf-8")
        with self.running_server() as port:
            opened = self.request(
                port,
                "POST",
                DOCUMENT_UPLOAD_PATH,
                body=body,
                headers={
                    "Content-Type": "application/octet-stream",
                    "X-PortableAgent-Filename": "synthetisch%20lokal.txt",
                },
            )
            answered = self.json_post(port, {
                "operation": "ask",
                "session_id": "http-session",
                "question": "Welche lokale Frist gilt?",
            })

        self.assertEqual(opened[0], 200)
        self.assertEqual(opened[2]["session"]["display_name"], "synthetisch lokal.txt")
        self.assertEqual(answered[0], 200)
        self.assertEqual(
            answered[2]["answer"]["citations"][0]["display_name"],
            "synthetisch lokal.txt",
        )

    def test_document_picker_rejects_unsafe_name_type_and_size(self):
        with self.running_server(max_document_upload_bytes=8) as port:
            unsafe = self.request(
                port,
                "POST",
                DOCUMENT_UPLOAD_PATH,
                body=b"text",
                headers={
                    "Content-Type": "application/octet-stream",
                    "X-PortableAgent-Filename": "..%2Fprivat.txt",
                },
            )
            wrong_format = self.request(
                port,
                "POST",
                DOCUMENT_UPLOAD_PATH,
                body=b"text",
                headers={
                    "Content-Type": "application/octet-stream",
                    "X-PortableAgent-Filename": "daten.csv",
                },
            )
            too_large = self.request(
                port,
                "POST",
                DOCUMENT_UPLOAD_PATH,
                body=b"123456789",
                headers={
                    "Content-Type": "application/octet-stream",
                    "X-PortableAgent-Filename": "synthetic.txt",
                },
            )

        self.assertEqual(unsafe[0], 400)
        self.assertEqual(wrong_format[0], 400)
        self.assertEqual(too_large[0], 413)

    def test_table_post_runs_one_synthetic_read_only_question(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.csv"
            path.write_text(
                "Fix;InterneNotiz\n2;HTTP_GEHEIM_41\n3;HTTP_GEHEIM_82\n",
                encoding="utf-8",
            )
            before = path.read_bytes()
            with self.running_server() as port:
                response = self.json_post(
                    port,
                    {
                        "operation": "ask_table",
                        "path": str(path),
                        "question": "Wie viele FIX gibt es insgesamt?",
                    },
                    api_path="/api/table",
                )

            self.assertEqual(path.read_bytes(), before)

        self.assertEqual(response[0], 200)
        self.assertEqual(response[2]["result"]["values"], {"FIX": 5})
        self.assertEqual(
            [item["row"] for item in response[2]["result"]["citations"]],
            [2, 3],
        )
        self.assertNotIn("HTTP_GEHEIM_41", repr(self.plan_generator.calls))
        self.assertNotIn("HTTP_GEHEIM_82", repr(self.plan_generator.calls))

    def test_table_picker_lists_sheets_and_asks_selected_sheet(self):
        from openpyxl import Workbook

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.xlsm"
            workbook = Workbook()
            first = workbook.active
            first.title = "Uebersicht"
            first.append(["Fix"])
            first.append([99])
            data = workbook.create_sheet("Daten")
            data.append(["Fix"])
            data.append([2])
            data.append([3])
            workbook.save(path)
            workbook.close()
            file_bytes = path.read_bytes()

            with self.running_server() as port:
                listed = self.table_file_post(
                    port,
                    file_bytes,
                    {"operation": "list_sheets", "filename": "synthetic.xlsm"},
                )
                answered = self.table_file_post(
                    port,
                    file_bytes,
                    {
                        "operation": "ask_table",
                        "filename": "synthetic.xlsm",
                        "question": "Wie viele FIX gibt es insgesamt?",
                        "sheet_name": "Daten",
                    },
                )

        self.assertEqual(listed[0], 200)
        self.assertEqual(listed[2]["sheet_names"], ["Uebersicht", "Daten"])
        self.assertEqual(listed[2]["file_type"], "excel")
        self.assertEqual(answered[0], 200)
        self.assertEqual(answered[2]["result"]["values"], {"FIX": 5})
        self.assertEqual(
            [item["section"] for item in answered[2]["result"]["citations"]],
            ["Daten", "Daten"],
        )

    def test_table_picker_rejects_unsafe_name_and_size(self):
        with self.running_server(max_table_upload_bytes=128) as port:
            missing_name = self.table_file_post(
                port,
                b"synthetic",
                {"operation": "list_sheets"},
            )
            unsafe = self.table_file_post(
                port,
                b"synthetic",
                {"operation": "list_sheets", "filename": "../privat.csv"},
            )
            too_large = self.table_file_post(
                port,
                b"x" * 256,
                {"operation": "list_sheets", "filename": "synthetic.csv"},
            )

        self.assertEqual(missing_name[0], 400)
        self.assertEqual(unsafe[0], 400)
        self.assertEqual(too_large[0], 413)

    def test_memory_endpoint_persists_only_explicitly_confirmed_note(self):
        with tempfile.TemporaryDirectory() as temporary:
            memory_controller = MemoryJsonController(
                SqliteMemoryRepository(Path(temporary) / "memory.sqlite3")
            )
            with self.running_server(memory_controller=memory_controller) as port:
                rejected = self.json_post(
                    port,
                    {
                        "operation": "add_note",
                        "text": "Nicht bestaetigt",
                        "confirmation": "yes",
                    },
                    api_path="/api/memory",
                )
                added = self.json_post(
                    port,
                    {
                        "operation": "add_note",
                        "text": "Synthetische bestaetigte Notiz",
                        "confirmation": "confirmed",
                    },
                    api_path="/api/memory",
                )
                listed = self.json_post(
                    port,
                    {"operation": "list_notes"},
                    api_path="/api/memory",
                )

        self.assertEqual(rejected[0], 400)
        self.assertEqual(rejected[2]["error"]["code"], "invalid_request")
        self.assertEqual(added[0], 200)
        self.assertEqual(listed[2]["notes"], [added[2]["note"]])

    def test_local_model_failures_have_safe_distinct_http_errors(self):
        cases = (
            (
                LlamaCppUnavailableError("SYNTHETIC_PRIVATE_NETWORK_DETAIL"),
                503,
                "local_model_unavailable",
                "noch nicht bereit",
            ),
            (
                LlamaCppResponseError("SYNTHETIC_PRIVATE_RESPONSE_DETAIL"),
                502,
                "invalid_local_model_response",
                "keine gültige Antwort",
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.csv"
            path.write_text("Fix\n2\n", encoding="utf-8")
            for error, expected_status, expected_code, expected_message in cases:
                with self.subTest(expected_code=expected_code):
                    table_controller = TableJsonController(
                        TableWorkflow(RaisingPlanGenerator(error))
                    )
                    with self.running_server(
                        table_controller=table_controller,
                    ) as port:
                        status, _, payload = self.json_post(
                            port,
                            {
                                "operation": "ask_table",
                                "path": str(path),
                                "question": "Wie hoch ist FIX?",
                            },
                            api_path="/api/table",
                        )

                self.assertEqual(status, expected_status)
                self.assertEqual(payload["error"]["code"], expected_code)
                self.assertIn(expected_message, payload["error"]["message"])
                self.assertNotIn("SYNTHETIC_PRIVATE", repr(payload))

    def test_table_clarification_is_resolved_over_http_without_second_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.csv"
            path.write_text("Einsatzdauer\n2\n4\n", encoding="utf-8")
            with self.running_server() as port:
                asked = self.json_post(
                    port,
                    {
                        "operation": "ask_table",
                        "path": str(path),
                        "question": "Wie lange war der Einsatz?",
                    },
                    api_path="/api/table",
                )
                resolved = self.json_post(
                    port,
                    {
                        "operation": "resolve_table",
                        "clarification_id": asked[2]["result"]["clarification_id"],
                        "option_id": "max",
                    },
                    api_path="/api/table",
                )

        self.assertEqual(asked[2]["result"]["type"], "clarification")
        self.assertEqual(resolved[2]["result"]["values"], {"Dauer": 4})
        self.assertEqual(len(self.plan_generator.calls), 1)

    def test_shutdown_post_returns_before_stopping_serve_loop(self):
        server = create_local_http_server(
            self.controller,
            self.table_controller,
            port=0,
            readiness_probe=lambda: self.model_ready,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, _, payload = self.json_post(
                server.server_address[1],
                {"operation": "shutdown"},
                api_path="/api/shutdown",
            )
            thread.join(timeout=2)

            self.assertEqual(status, 200)
            self.assertEqual(payload, {
                "ok": True,
                "operation": "shutdown",
                "status": "stopping",
            })
            self.assertFalse(thread.is_alive())
        finally:
            if thread.is_alive():
                server.shutdown()
            server.server_close()

    def test_shutdown_request_must_match_exact_json_shape(self):
        with self.running_server() as port:
            invalid = self.json_post(
                port,
                {"operation": "shutdown", "force": True},
                api_path="/api/shutdown",
            )
            health = self.request(port, "GET", "/health")

        self.assertEqual(invalid[0], 400)
        self.assertEqual(invalid[2]["error"]["code"], "invalid_request")
        self.assertEqual(health[0], 200)

    def test_invalid_path_json_and_content_type_return_json_errors(self):
        with self.running_server() as port:
            missing = self.request(port, "GET", "/missing")
            malformed = self.request(
                port,
                "POST",
                "/api/document",
                body=b'{"operation":',
                headers={"Content-Type": "application/json"},
            )
            wrong_type = self.request(
                port,
                "POST",
                "/api/document",
                body=b"{}",
                headers={"Content-Type": "text/plain"},
            )

        self.assertEqual(missing[0], 404)
        self.assertEqual(malformed[0], 400)
        self.assertEqual(malformed[2]["error"]["code"], "invalid_request")
        self.assertEqual(wrong_type[0], 415)
        self.assertFalse(wrong_type[2]["ok"])

    def test_non_loopback_host_header_is_rejected(self):
        with self.running_server() as port:
            status, _, payload = self.request(
                port,
                "GET",
                "/health",
                headers={"Host": "attacker.invalid"},
            )

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "invalid_host")

    def test_body_limit_is_checked_before_controller(self):
        with self.running_server(max_body_bytes=8) as port:
            status, _, payload = self.request(
                port,
                "POST",
                "/api/document",
                body=b'{"operation":"list_sessions"}',
                headers={"Content-Type": "application/json"},
            )

        self.assertEqual(status, 413)
        self.assertEqual(payload["error"]["code"], "body_too_large")

    def test_non_loopback_bind_and_invalid_limits_are_rejected(self):
        with self.assertRaisesRegex(LocalHttpConfigurationError, "127.0.0.1"):
            create_local_http_server(
                self.controller, self.table_controller, host="0.0.0.0"
            )
        with self.assertRaisesRegex(LocalHttpConfigurationError, "port"):
            create_local_http_server(
                self.controller, self.table_controller, port=True
            )
        with self.assertRaisesRegex(LocalHttpConfigurationError, "max_body_bytes"):
            create_local_http_server(
                self.controller, self.table_controller, max_body_bytes=0
            )
        with self.assertRaisesRegex(LocalHttpConfigurationError, "readiness_probe"):
            create_local_http_server(
                self.controller,
                self.table_controller,
                readiness_probe="invalid",
            )
        with self.assertRaisesRegex(
            LocalHttpConfigurationError, "asset_inventory_provider"
        ):
            create_local_http_server(
                self.controller,
                self.table_controller,
                asset_inventory_provider="invalid",
            )
        with self.assertRaisesRegex(TypeError, "memory_controller"):
            create_local_http_server(
                self.controller,
                self.table_controller,
                memory_controller=object(),
            )

    @contextmanager
    def running_server(self, **kwargs):
        readiness_probe = kwargs.pop(
            "readiness_probe", lambda: self.model_ready
        )
        table_controller = kwargs.pop("table_controller", self.table_controller)
        server = create_local_http_server(
            self.controller,
            table_controller,
            port=0,
            readiness_probe=readiness_probe,
            **kwargs,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.assertEqual(server.server_address[0], "127.0.0.1")
            yield server.server_address[1]
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())

    def json_post(self, port, payload, *, api_path="/api/document"):
        return self.request(
            port,
            "POST",
            api_path,
            body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    def table_file_post(self, port, file_bytes, metadata):
        encoded = json.dumps(
            metadata,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
        body = len(encoded).to_bytes(4, "big") + encoded + file_bytes
        return self.request(
            port,
            "POST",
            TABLE_FILE_API_PATH,
            body=body,
            headers={"Content-Type": "application/vnd.portable-agent.table"},
        )

    def request(self, port, method, path, body=None, headers=None):
        status, response_headers, raw = self.raw_request(
            port, method, path, body=body, headers=headers
        )
        return status, response_headers, json.loads(raw)

    def raw_request(self, port, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            raw = response.read()
            return response.status, dict(response.getheaders()), raw
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
