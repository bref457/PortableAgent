import sys
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.sources import DocumentSegment, InMemoryDocumentSource


class InMemoryDocumentSourceTests(unittest.TestCase):
    def test_chunks_have_stable_page_and_paragraph_citations(self):
        source = InMemoryDocumentSource(
            [
                DocumentSegment(
                    "Erster synthetischer Absatz.",
                    page=1,
                    paragraph="p1",
                    heading="Einleitung",
                ),
                DocumentSegment(
                    "Zweiter synthetischer Absatz.",
                    page=2,
                    paragraph="p2",
                ),
            ],
            source_id="doc-1",
            display_name="synthetic.pdf",
        )

        chunks = list(source.iter_chunks())

        self.assertEqual([chunk.chunk_id for chunk in chunks], ["doc-1:chunk:1", "doc-1:chunk:2"])
        self.assertEqual([chunk.ordinal for chunk in chunks], [1, 2])
        self.assertEqual(chunks[0].source_ref.page, 1)
        self.assertEqual(chunks[0].source_ref.paragraph, "p1")
        self.assertEqual(chunks[0].source_ref.display_name, "synthetic.pdf")
        self.assertEqual(chunks[0].heading, "Einleitung")

    def test_excerpt_is_compacted_and_bounded(self):
        source = InMemoryDocumentSource(
            [DocumentSegment("Viele    Leerzeichen\nund ein laengerer Text")],
            excerpt_chars=20,
        )
        chunk = next(source.iter_chunks())
        self.assertTrue(chunk.source_ref.excerpt.startswith("Viele Leerzeichen"))
        self.assertTrue(chunk.source_ref.excerpt.endswith("…"))
        self.assertLessEqual(len(chunk.source_ref.excerpt), 20)

    def test_input_iterable_is_snapshotted(self):
        segments = [DocumentSegment("Original")]
        source = InMemoryDocumentSource(segments)
        segments.append(DocumentSegment("Spaeter hinzugefuegt"))
        self.assertEqual([chunk.text for chunk in source.iter_chunks()], ["Original"])

    def test_invalid_segments_are_rejected(self):
        invalid = (
            DocumentSegment("   "),
            DocumentSegment("Text", page=0),
            DocumentSegment("Text", paragraph=""),
            DocumentSegment("Text", heading=" "),
        )
        for segment in invalid:
            with self.subTest(segment=segment):
                with self.assertRaises(ValueError):
                    InMemoryDocumentSource([segment])


if __name__ == "__main__":
    unittest.main()
