import sys
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.agent import DocumentAgent, DocumentAnswerError
from portable_agent.sources import DocumentSegment, InMemoryDocumentSource


class RecordingAnswerGenerator:
    def __init__(self, answer="Lokale belegte Antwort"):
        self.answer = answer
        self.calls = []

    def generate_answer(self, question, contexts):
        self.calls.append((question, contexts))
        return self.answer


class DocumentAgentTests(unittest.TestCase):
    def setUp(self):
        self.source = InMemoryDocumentSource(
            [
                DocumentSegment(
                    "Die Kündigungsfrist beträgt drei Monate.",
                    page=2,
                    paragraph="p2",
                    heading="Vertrag",
                ),
                DocumentSegment(
                    "SENSITIVER_IRRELEVANTER_INHALT zur internen Planung.",
                    page=5,
                    paragraph="p5",
                    heading="Intern",
                ),
            ],
            source_id="doc-1",
            display_name="synthetic.txt",
        )

    def test_only_retrieved_context_reaches_answer_generator(self):
        generator = RecordingAnswerGenerator("Die Frist beträgt drei Monate.")
        agent = DocumentAgent(self.source, generator, max_results=1)

        result = agent.ask("Wie lang ist die Kündigungsfrist?")

        self.assertTrue(result.generated)
        self.assertEqual(result.matched_chunks, 1)
        self.assertEqual(len(generator.calls), 1)
        captured = repr(generator.calls)
        self.assertIn("drei Monate", captured)
        self.assertNotIn("SENSITIVER_IRRELEVANTER_INHALT", captured)

    def test_answer_citations_come_only_from_retrieval_matches(self):
        generator = RecordingAnswerGenerator()
        result = DocumentAgent(self.source, generator).ask("Kündigungsfrist Vertrag")
        self.assertEqual(len(result.citations), 1)
        self.assertEqual(result.citations[0].page, 2)
        self.assertEqual(result.citations[0].paragraph, "p2")

    def test_no_match_does_not_call_generator(self):
        generator = RecordingAnswerGenerator()
        result = DocumentAgent(self.source, generator).ask("Quantenphysik")
        self.assertFalse(result.generated)
        self.assertEqual(result.citations, ())
        self.assertEqual(result.text, "Keine passende Fundstelle im Dokument gefunden.")
        self.assertEqual(generator.calls, [])

    def test_result_limit_controls_context_and_citations(self):
        source = InMemoryDocumentSource([
            DocumentSegment("Regel gilt lokal.", paragraph="p1"),
            DocumentSegment("Weitere lokale Regel.", paragraph="p2"),
        ])
        generator = RecordingAnswerGenerator()
        result = DocumentAgent(source, generator, max_results=1).ask("lokale Regel")
        self.assertEqual(result.matched_chunks, 1)
        self.assertEqual(len(result.citations), 1)
        self.assertEqual(len(generator.calls[0][1]), 1)

    def test_empty_generated_answer_is_rejected(self):
        generator = RecordingAnswerGenerator("   ")
        agent = DocumentAgent(self.source, generator)
        with self.assertRaisesRegex(DocumentAnswerError, "keine verwendbare Antwort"):
            agent.ask("Kündigungsfrist")


if __name__ == "__main__":
    unittest.main()

