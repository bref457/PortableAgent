import sys
import tempfile
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.agent import DocumentWorkflow
from portable_agent.sessions import DocumentSessionError, DocumentSessionManager
from portable_agent.sources import SourceFormatNotAllowedError


class RecordingAnswerGenerator:
    def __init__(self, answer="Die lokale Frist betraegt drei Tage."):
        self.answer = answer
        self.calls = []

    def generate_answer(self, question, contexts):
        self.calls.append((question, contexts))
        return self.answer


class DocumentWorkflowTests(unittest.TestCase):
    def test_complete_import_question_citation_and_release_flow(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.txt"
            path.write_text(
                "Die lokale Frist betraegt drei Tage.",
                encoding="utf-8",
            )
            before = path.read_bytes()
            generator = RecordingAnswerGenerator()
            sessions = DocumentSessionManager(id_factory=lambda: "workflow-session")
            workflow = DocumentWorkflow(generator, sessions=sessions)

            session = workflow.open_document(path)
            result = workflow.ask(session.session_id, "Welche lokale Frist gilt?")

            self.assertEqual(workflow.active_session_count, 1)
            self.assertTrue(result.generated)
            self.assertEqual(result.matched_chunks, 1)
            self.assertEqual(result.citations[0].display_name, "synthetic.txt")
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(len(generator.calls), 1)

            released = workflow.release(session.session_id)
            self.assertIs(released, session)
            self.assertEqual(workflow.active_session_count, 0)
            with self.assertRaisesRegex(DocumentSessionError, "bereits freigegeben"):
                workflow.ask(session.session_id, "Welche lokale Frist gilt?")
            self.assertEqual(len(generator.calls), 1)

    def test_failed_import_does_not_create_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.csv"
            path.write_text("nicht,als,dokument", encoding="utf-8")
            workflow = DocumentWorkflow(RecordingAnswerGenerator())

            with self.assertRaises(SourceFormatNotAllowedError):
                workflow.open_document(path)

            self.assertEqual(workflow.active_session_count, 0)
            self.assertEqual(workflow.list_sessions(), ())

    def test_release_all_clears_every_open_document(self):
        ids = iter(("first-session", "second-session"))
        sessions = DocumentSessionManager(id_factory=lambda: next(ids))
        workflow = DocumentWorkflow(RecordingAnswerGenerator(), sessions=sessions)
        with tempfile.TemporaryDirectory() as temporary:
            first_path = Path(temporary) / "first.txt"
            second_path = Path(temporary) / "second.txt"
            first_path.write_text("Erster lokaler Text.", encoding="utf-8")
            second_path.write_text("Zweiter lokaler Text.", encoding="utf-8")
            first = workflow.open_document(first_path)
            second = workflow.open_document(second_path)

            self.assertEqual(
                tuple(session.session_id for session in workflow.list_sessions()),
                (first.session_id, second.session_id),
            )
            self.assertEqual(workflow.release_all(), 2)
            self.assertEqual(workflow.active_session_count, 0)
            self.assertEqual(workflow.release_all(), 0)


if __name__ == "__main__":
    unittest.main()
