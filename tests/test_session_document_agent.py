import sys
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.agent import SessionDocumentAgent
from portable_agent.sessions import DocumentSessionError, DocumentSessionManager
from portable_agent.sources import DocumentSegment, InMemoryDocumentSource


class RecordingAnswerGenerator:
    def __init__(self, answer="Lokale Sitzungsantwort"):
        self.answer = answer
        self.calls = []

    def generate_answer(self, question, contexts):
        self.calls.append((question, contexts))
        return self.answer


class SessionDocumentAgentTests(unittest.TestCase):
    def setUp(self):
        ids = iter(("session-a", "session-b"))
        self.sessions = DocumentSessionManager(id_factory=lambda: next(ids))
        self.first = self.sessions.create(
            InMemoryDocumentSource(
                [DocumentSegment("Alpha besitzt eine lokale Frist von drei Tagen.")],
                source_id="alpha",
                display_name="alpha.txt",
            )
        )
        self.second = self.sessions.create(
            InMemoryDocumentSource(
                [DocumentSegment("Beta besitzt eine lokale Frist von fünf Tagen.")],
                source_id="beta",
                display_name="beta.txt",
            )
        )
        self.generator = RecordingAnswerGenerator()
        self.agent = SessionDocumentAgent(self.sessions, self.generator)

    def test_question_uses_only_source_bound_to_session_id(self):
        result = self.agent.ask(self.first.session_id, "Welche Frist hat Alpha?")

        self.assertTrue(result.generated)
        self.assertEqual(result.citations[0].source_id, "alpha")
        captured = repr(self.generator.calls)
        self.assertIn("drei Tagen", captured)
        self.assertNotIn("fünf Tagen", captured)

    def test_other_session_selects_other_source(self):
        result = self.agent.ask(self.second.session_id, "Welche Frist hat Beta?")

        self.assertEqual(result.citations[0].source_id, "beta")
        self.assertIn("fünf Tagen", repr(self.generator.calls))

    def test_unknown_session_fails_before_generator_call(self):
        with self.assertRaisesRegex(DocumentSessionError, "nicht gefunden"):
            self.agent.ask("unknown", "Welche Frist gilt?")

        self.assertEqual(self.generator.calls, [])

    def test_released_session_fails_before_generator_call(self):
        self.sessions.release(self.first.session_id)

        with self.assertRaisesRegex(DocumentSessionError, "bereits freigegeben"):
            self.agent.ask(self.first.session_id, "Welche Frist gilt?")

        self.assertEqual(self.generator.calls, [])

    def test_no_retrieval_match_does_not_call_generator(self):
        result = self.agent.ask(self.first.session_id, "Quantenphysik")

        self.assertFalse(result.generated)
        self.assertEqual(self.generator.calls, [])


if __name__ == "__main__":
    unittest.main()
