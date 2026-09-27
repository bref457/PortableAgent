import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.sources import (
    DocxDocumentSource,
    DocxSourceError,
    open_document_source,
)


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def document_xml(paragraphs):
    body = []
    for text, style in paragraphs:
        style_xml = (
            f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        )
        body.append(
            f'<w:p>{style_xml}<w:r><w:t>{text}</w:t></w:r></w:p>'
        )
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W}"><w:body>{"".join(body)}</w:body></w:document>'
    ).encode("utf-8")


class DocxDocumentSourceTests(unittest.TestCase):
    def test_docx_paragraphs_are_read_only_and_cited(self):
        xml = document_xml([
            ("Vertrag", "Heading1"),
            ("Die Frist betraegt drei Monate.", None),
        ])
        with self.docx_file(xml) as path:
            before = path.read_bytes()
            source = open_document_source(path)
            chunks = list(source.iter_chunks())
            after = path.read_bytes()

        self.assertIsInstance(source, DocxDocumentSource)
        self.assertEqual([chunk.text for chunk in chunks], [
            "Vertrag", "Die Frist betraegt drei Monate."
        ])
        self.assertEqual([chunk.source_ref.paragraph for chunk in chunks], [
            "Absatz 1", "Absatz 2"
        ])
        self.assertEqual(chunks[0].heading, "Vertrag")
        self.assertEqual(chunks[0].source_ref.display_name, "synthetic.docx")
        self.assertEqual(before, after)

    def test_tabs_breaks_and_hyphens_are_normalized(self):
        xml = (
            f'<w:document xmlns:w="{W}"><w:body><w:p><w:r>'
            '<w:t>Teil</w:t><w:tab/><w:t>Eins</w:t><w:br/>'
            '<w:t>Zwei</w:t><w:noBreakHyphen/><w:t>Drei</w:t>'
            '</w:r></w:p></w:body></w:document>'
        ).encode("utf-8")
        with self.docx_file(xml) as path:
            text = next(DocxDocumentSource(path).iter_chunks()).text
        self.assertEqual(text, "Teil Eins\nZwei-Drei")

    def test_macro_payload_is_rejected_without_processing(self):
        with self.docx_file(document_xml([("Text", None)]), macro=True) as path:
            with self.assertRaisesRegex(DocxSourceError, "Makroinhalt"):
                DocxDocumentSource(path)

    def test_dtd_or_entity_declaration_is_rejected(self):
        xml = b'<!DOCTYPE x [<!ENTITY y "text">]><x>&y;</x>'
        with self.docx_file(xml) as path:
            with self.assertRaisesRegex(DocxSourceError, "DTD- und Entity"):
                DocxDocumentSource(path)

    def test_missing_document_xml_and_invalid_zip_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing.docx"
            with zipfile.ZipFile(missing, "w") as archive:
                archive.writestr("other.xml", "<x/>")
            with self.assertRaisesRegex(DocxSourceError, "kein word/document.xml"):
                DocxDocumentSource(missing)

            invalid = Path(temporary) / "invalid.docx"
            invalid.write_bytes(b"kein zip")
            with self.assertRaisesRegex(DocxSourceError, "konnte nicht gelesen"):
                DocxDocumentSource(invalid)

    def test_container_and_paragraph_limits_are_enforced(self):
        xml = document_xml([("Eins", None), ("Zwei", None)])
        with self.docx_file(xml) as path:
            with self.assertRaisesRegex(DocxSourceError, "Entpackter DOCX-Inhalt"):
                DocxDocumentSource(path, max_uncompressed_bytes=10)
            with self.assertRaisesRegex(DocxSourceError, "mehr als 1 lesbare Absaetze"):
                DocxDocumentSource(path, max_paragraphs=1)

    def docx_file(self, xml, macro=False):
        class SyntheticDocx:
            def __enter__(inner_self):
                inner_self.temporary = tempfile.TemporaryDirectory()
                inner_self.path = Path(inner_self.temporary.name) / "synthetic.docx"
                with zipfile.ZipFile(inner_self.path, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("[Content_Types].xml", "<Types/>")
                    archive.writestr("word/document.xml", xml)
                    if macro:
                        archive.writestr("word/vbaProject.bin", b"synthetic macro")
                return inner_self.path

            def __exit__(inner_self, exc_type, exc_value, traceback):
                inner_self.temporary.cleanup()

        return SyntheticDocx()


if __name__ == "__main__":
    unittest.main()

