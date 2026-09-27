import sys
import tempfile
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.sources import (
    SourceFormatNotAllowedError,
    TxtDocumentSource,
    TxtSourceError,
    open_document_source,
)


class TxtDocumentSourceTests(unittest.TestCase):
    def test_utf8_text_is_split_into_cited_paragraphs_without_changes(self):
        content = "Erster Absatz\nmit zweiter Zeile.\n\nZweiter Absatz mit Umlaut: Zürich.\n"
        with self.synthetic_file("synthetic.txt", content) as path:
            before = path.read_bytes()
            source = open_document_source(path)
            chunks = list(source.iter_chunks())
            after = path.read_bytes()

        self.assertIsInstance(source, TxtDocumentSource)
        self.assertEqual([chunk.text for chunk in chunks], [
            "Erster Absatz\nmit zweiter Zeile.",
            "Zweiter Absatz mit Umlaut: Zürich.",
        ])
        self.assertEqual([chunk.source_ref.paragraph for chunk in chunks], [
            "Absatz 1, Zeilen 1-2",
            "Absatz 2, Zeile 4",
        ])
        self.assertEqual([chunk.source_ref.display_name for chunk in chunks], [
            "synthetic.txt", "synthetic.txt"
        ])
        self.assertEqual(before, after)

    def test_utf8_bom_is_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bom.txt"
            path.write_bytes(b"\xef\xbb\xbfText")
            chunk = next(TxtDocumentSource(path).iter_chunks())
        self.assertEqual(chunk.text, "Text")

    def test_binary_invalid_utf8_and_empty_content_are_rejected(self):
        cases = (
            (b"Text\x00Daten", "Nullbytes"),
            (b"\xff\xfe", "UTF-8"),
            (b"  \n\n", "keinen lesbaren Text"),
        )
        for payload, pattern in cases:
            with self.subTest(pattern=pattern):
                with tempfile.TemporaryDirectory() as temporary:
                    path = Path(temporary) / "invalid.txt"
                    path.write_bytes(payload)
                    with self.assertRaisesRegex(TxtSourceError, pattern):
                        TxtDocumentSource(path)

    def test_size_and_paragraph_limits_are_enforced(self):
        with self.synthetic_file("limited.txt", "Eins\n\nZwei\n") as path:
            with self.assertRaisesRegex(TxtSourceError, "groesser als"):
                TxtDocumentSource(path, max_bytes=2)
            with self.assertRaisesRegex(TxtSourceError, "mehr als 1 Absaetze"):
                TxtDocumentSource(path, max_paragraphs=1)

    def test_document_router_rejects_table_format(self):
        with self.assertRaisesRegex(SourceFormatNotAllowedError, "Dokumentquelle"):
            open_document_source("tabelle.csv")

    def synthetic_file(self, name, content):
        class SyntheticFile:
            def __enter__(inner_self):
                inner_self.temporary = tempfile.TemporaryDirectory()
                inner_self.path = Path(inner_self.temporary.name) / name
                inner_self.path.write_text(content, encoding="utf-8")
                return inner_self.path

            def __exit__(inner_self, exc_type, exc_value, traceback):
                inner_self.temporary.cleanup()

        return SyntheticFile()


if __name__ == "__main__":
    unittest.main()
