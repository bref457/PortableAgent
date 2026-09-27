import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.sessions import DocumentSessionManager, open_document_session
from portable_agent.sources import (
    DocxSourceError,
    SourceFormatNotAllowedError,
)


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


class DocumentSessionImportTests(unittest.TestCase):
    def test_txt_is_opened_read_only_and_registered(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.txt"
            path.write_text("Lokaler synthetischer Text.", encoding="utf-8")
            before = path.read_bytes()
            manager = DocumentSessionManager(id_factory=lambda: "txt-session")

            session = open_document_session(path, manager)
            chunks = tuple(session.source.iter_chunks())

            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(session.session_id, "txt-session")
            self.assertEqual(chunks[0].text, "Lokaler synthetischer Text.")
            self.assertIs(manager.get(session.session_id), session)

    def test_docx_is_opened_read_only_and_registered(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.docx"
            xml = (
                f'<w:document xmlns:w="{W}"><w:body><w:p><w:r>'
                '<w:t>Synthetischer DOCX-Text.</w:t>'
                '</w:r></w:p></w:body></w:document>'
            ).encode("utf-8")
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("[Content_Types].xml", "<Types/>")
                archive.writestr("word/document.xml", xml)
            before = path.read_bytes()
            manager = DocumentSessionManager(id_factory=lambda: "docx-session")

            session = open_document_session(path, manager)
            chunks = tuple(session.source.iter_chunks())

            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(session.session_id, "docx-session")
            self.assertEqual(chunks[0].text, "Synthetischer DOCX-Text.")
            self.assertEqual(manager.count, 1)

    def test_disallowed_format_does_not_create_session_or_read_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.csv"
            path.write_text("soll,nicht,gelesen,werden", encoding="utf-8")
            before = path.read_bytes()
            manager = DocumentSessionManager(id_factory=lambda: "unused")

            with self.assertRaisesRegex(SourceFormatNotAllowedError, "Dokumentquelle"):
                open_document_session(path, manager)

            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(manager.count, 0)

    def test_invalid_document_does_not_create_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid.docx"
            path.write_bytes(b"synthetic but not a zip")
            before = path.read_bytes()
            manager = DocumentSessionManager(id_factory=lambda: "unused")

            with self.assertRaises(DocxSourceError):
                open_document_session(path, manager)

            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(manager.count, 0)


if __name__ == "__main__":
    unittest.main()
