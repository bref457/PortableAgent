import json
import sys
import tempfile
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.agent import DocumentWorkflow
from portable_agent.sessions import DocumentSessionError, DocumentSessionManager
from portable_agent.web import DocumentJsonController, DocumentJsonError


class RecordingAnswerGenerator:
    def __init__(self):
        self.calls = []

    def generate_answer(self, question, contexts):
        self.calls.append((question, contexts))
        return "Die Frist betraegt drei Tage."


class DocumentJsonControllerTests(unittest.TestCase):
    def setUp(self):
        self.generator = RecordingAnswerGenerator()
        sessions = DocumentSessionManager(id_factory=lambda: "json-session")
        self.workflow = DocumentWorkflow(self.generator, sessions=sessions)
        self.controller = DocumentJsonController(self.workflow)

    def test_complete_json_flow_has_fixed_metadata_answer_and_citations(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.txt"
            path.write_text("Die lokale Frist betraegt drei Tage.", encoding="utf-8")

            opened = self.request({"operation": "open_document", "path": str(path)})
            listed = self.request({"operation": "list_sessions"})
            answered = self.request({
                "operation": "ask",
                "session_id": "json-session",
                "question": "Welche lokale Frist gilt?",
            })
            released = self.request({
                "operation": "release",
                "session_id": "json-session",
            })

        self.assertEqual(opened["session"]["session_id"], "json-session")
        self.assertNotIn("drei Tage", json.dumps(opened))
        self.assertEqual(listed["active_session_count"], 1)
        self.assertEqual(len(listed["sessions"]), 1)
        self.assertEqual(answered["answer"]["matched_chunks"], 1)
        self.assertEqual(answered["answer"]["citations"][0]["paragraph"], "Absatz 1, Zeile 1")
        self.assertEqual(released["active_session_count"], 0)
        self.assertEqual(released["released_session"]["session_id"], "json-session")

    def test_unknown_extra_missing_and_wrong_typed_fields_are_rejected(self):
        cases = (
            ({"operation": "execute_code"}, "Unbekannte Dokumentoperation"),
            ({"operation": "ask", "session_id": "x", "question": "q", "code": "x"}, "unbekannte Felder"),
            ({"operation": "ask", "session_id": "x"}, "fehlen Pflichtfelder"),
            ({"operation": "open_document", "path": 123}, "path muss"),
            ({"operation": "ask", "session_id": "x", "question": "a\u0000b"}, "Nullbytes"),
        )
        for payload, pattern in cases:
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(DocumentJsonError, pattern):
                    self.controller.handle_json(json.dumps(payload))
        self.assertEqual(self.generator.calls, [])
        self.assertEqual(self.workflow.active_session_count, 0)

    def test_malformed_duplicate_nonstandard_and_oversized_json_are_rejected(self):
        invalid = (
            ('{"operation":', "Ungültiger JSON"),
            ('{"operation":"list_sessions","operation":"ask"}', "doppeltes Feld"),
            ('{"operation":"ask","session_id":"x","question":NaN}', "unzulaessig"),
        )
        for payload, pattern in invalid:
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(DocumentJsonError, pattern):
                    self.controller.handle_json(payload)

        limited = DocumentJsonController(self.workflow, max_request_chars=10)
        with self.assertRaisesRegex(DocumentJsonError, "größer als"):
            limited.handle_json('{"operation":"list_sessions"}')

    def test_unknown_session_propagates_before_generator_call(self):
        with self.assertRaisesRegex(DocumentSessionError, "nicht gefunden"):
            self.request({
                "operation": "ask",
                "session_id": "unknown",
                "question": "Welche Frist gilt?",
            })
        self.assertEqual(self.generator.calls, [])

    def test_release_all_returns_exact_count(self):
        ids = iter(("one", "two"))
        workflow = DocumentWorkflow(
            self.generator,
            sessions=DocumentSessionManager(id_factory=lambda: next(ids)),
        )
        controller = DocumentJsonController(workflow)
        with tempfile.TemporaryDirectory() as temporary:
            for name in ("one.txt", "two.txt"):
                path = Path(temporary) / name
                path.write_text(f"Synthetischer Text {name}.", encoding="utf-8")
                controller.handle_json(json.dumps({
                    "operation": "open_document",
                    "path": str(path),
                }))

            response = json.loads(controller.handle_json(
                '{"operation":"release_all"}'
            ))

        self.assertEqual(response["released_count"], 2)
        self.assertEqual(response["active_session_count"], 0)

    def request(self, payload):
        response_json = self.controller.handle_json(
            json.dumps(payload, ensure_ascii=False)
        )
        return json.loads(response_json)


if __name__ == "__main__":
    unittest.main()
