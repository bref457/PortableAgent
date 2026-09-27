import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pypdf import PdfReader, PdfWriter

from portable_agent.sources import PdfDocumentSource, PdfSourceError, open_document_source


def synthetic_text_pdf(text):
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
        + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)


class PdfDocumentSourceTests(unittest.TestCase):
    def test_pdf_text_is_read_only_and_has_page_citation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.pdf"
            path.write_bytes(synthetic_text_pdf("Synthetic local PDF text."))
            before = path.read_bytes()

            source = open_document_source(path)
            chunks = tuple(source.iter_chunks())

            self.assertIsInstance(source, PdfDocumentSource)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(chunks[0].text, "Synthetic local PDF text.")
            self.assertEqual(chunks[0].source_ref.page, 1)
            self.assertEqual(chunks[0].source_ref.paragraph, "Seite 1")
            self.assertEqual(chunks[0].source_ref.display_name, "synthetic.pdf")

    def test_size_page_and_text_limits_are_enforced(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "limited.pdf"
            path.write_bytes(synthetic_text_pdf("Long synthetic text"))
            with self.assertRaisesRegex(PdfSourceError, "groesser als"):
                PdfDocumentSource(path, max_bytes=10)
            self._make_two_page_pdf(path)
            with self.assertRaisesRegex(PdfSourceError, "mehr als 1 Seiten"):
                PdfDocumentSource(path, max_pages=1)
            path.write_bytes(synthetic_text_pdf("Long synthetic text"))
            with self.assertRaisesRegex(PdfSourceError, "Zeichenlimit"):
                PdfDocumentSource(path, max_chars_per_page=5)
            with self.assertRaisesRegex(PdfSourceError, "Gesamtzeichenlimit"):
                PdfDocumentSource(path, max_total_chars=5)

    def test_encrypted_pdf_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "encrypted.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=100, height=100)
            writer.encrypt("synthetic-password")
            with path.open("wb") as stream:
                writer.write(stream)
            before = path.read_bytes()

            with self.assertRaisesRegex(PdfSourceError, "Verschluesselte"):
                PdfDocumentSource(path)

            self.assertEqual(path.read_bytes(), before)

    def test_empty_and_invalid_pdf_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            empty = Path(temporary) / "empty.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=100, height=100)
            with empty.open("wb") as stream:
                writer.write(stream)
            with self.assertRaisesRegex(PdfSourceError, "keinen extrahierbaren Text"):
                PdfDocumentSource(empty)

            invalid = Path(temporary) / "invalid.pdf"
            invalid.write_bytes(b"not a pdf")
            with self.assertRaisesRegex(PdfSourceError, "konnte nicht gelesen"):
                PdfDocumentSource(invalid)

    def _make_two_page_pdf(self, path):
        reader = PdfReader(BytesIO(Path(path).read_bytes()))
        writer = PdfWriter()
        writer.add_page(reader.pages[0])
        writer.add_page(reader.pages[0])
        with Path(path).open("wb") as stream:
            writer.write(stream)


if __name__ == "__main__":
    unittest.main()
