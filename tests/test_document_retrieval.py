import sys
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.analysis import RetrievalQueryError, search_document
from portable_agent.sources import DocumentSegment, InMemoryDocumentSource


class DocumentRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.source = InMemoryDocumentSource(
            [
                DocumentSegment(
                    "Die lokale Verschluesselung schützt gespeicherte Dokumente.",
                    page=1,
                    paragraph="p1",
                    heading="Sicherheit",
                ),
                DocumentSegment(
                    "Dokumente werden ausschliesslich lokal verarbeitet.",
                    page=2,
                    paragraph="p2",
                    heading="Lokaler Betrieb",
                ),
                DocumentSegment(
                    "Die Kündigungsfrist beträgt drei Monate.",
                    page=3,
                    paragraph="p3",
                    heading="Vertrag",
                ),
            ],
            source_id="doc-1",
            display_name="synthetic.txt",
        )

    def test_best_lexical_match_keeps_original_citation(self):
        result = search_document(self.source, "lokale Verschlüsselung Dokumente")
        self.assertTrue(result.found)
        self.assertEqual(result.matches[0].chunk.source_ref.page, 1)
        self.assertEqual(result.matches[0].chunk.source_ref.paragraph, "p1")
        self.assertEqual(result.matches[0].matched_terms, ("lokale", "verschluesselung", "dokumente"))

    def test_unicode_and_case_are_normalized(self):
        result = search_document(self.source, "KÜNDIGUNGSFRIST")
        self.assertEqual(result.matches[0].chunk.source_ref.page, 3)

    def test_ties_are_stable_by_document_order(self):
        source = InMemoryDocumentSource([
            DocumentSegment("Gleicher Begriff", paragraph="p1"),
            DocumentSegment("Gleicher Begriff", paragraph="p2"),
        ])
        result = search_document(source, "Begriff")
        self.assertEqual([match.chunk.ordinal for match in result.matches], [1, 2])

    def test_result_limit_is_enforced(self):
        result = search_document(self.source, "Dokumente", max_results=1)
        self.assertEqual(len(result.matches), 1)

    def test_missing_and_stopword_only_queries_are_explicit(self):
        missing = search_document(self.source, "Quantenphysik")
        self.assertFalse(missing.found)
        self.assertEqual(missing.message, "Keine passende Fundstelle im Dokument gefunden.")

        stopwords = search_document(self.source, "wie ist das")
        self.assertFalse(stopwords.found)
        self.assertIn("keine lokal suchbaren Begriffe", stopwords.message)

    def test_invalid_query_and_limits_are_rejected(self):
        with self.assertRaisesRegex(RetrievalQueryError, "nicht leer"):
            search_document(self.source, " ")
        with self.assertRaisesRegex(RetrievalQueryError, "max_results"):
            search_document(self.source, "Dokument", max_results=0)
        with self.assertRaisesRegex(RetrievalQueryError, "min_score"):
            search_document(self.source, "Dokument", min_score=True)


if __name__ == "__main__":
    unittest.main()
