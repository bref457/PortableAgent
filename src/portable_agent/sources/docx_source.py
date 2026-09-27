"""Minimal read-only DOCX source using ZIP and XML standard libraries."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from .document import DocumentSegment, InMemoryDocumentSource


DEFAULT_MAX_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
DEFAULT_MAX_XML_BYTES = 20 * 1024 * 1024
DEFAULT_MAX_MEMBERS = 5_000
DEFAULT_MAX_PARAGRAPHS = 100_000
_DOCUMENT_XML = "word/document.xml"
_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_W = f"{{{_WORD_NS}}}"


class DocxSourceError(ValueError):
    """A DOCX source cannot be opened under the read-only source policy."""


class DocxDocumentSource:
    """Snapshots paragraph text from one explicit macro-free DOCX file."""

    def __init__(
        self,
        path: str | Path,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
        max_uncompressed_bytes: int = DEFAULT_MAX_UNCOMPRESSED_BYTES,
        max_xml_bytes: int = DEFAULT_MAX_XML_BYTES,
        max_members: int = DEFAULT_MAX_MEMBERS,
        max_paragraphs: int = DEFAULT_MAX_PARAGRAPHS,
    ) -> None:
        source_path = Path(path)
        limits = (max_bytes, max_uncompressed_bytes, max_xml_bytes, max_members, max_paragraphs)
        _validate_request(source_path, limits)
        try:
            size = source_path.stat().st_size
        except OSError as exc:
            raise DocxSourceError(f"DOCX-Datei nicht lesbar: {exc}") from exc
        if size > max_bytes:
            raise DocxSourceError(
                f"DOCX-Datei ist groesser als das erlaubte Limit von {max_bytes} Bytes."
            )

        try:
            xml_data = _read_document_xml(
                source_path,
                max_uncompressed_bytes=max_uncompressed_bytes,
                max_xml_bytes=max_xml_bytes,
                max_members=max_members,
            )
            segments = _parse_segments(xml_data, max_paragraphs=max_paragraphs)
        except DocxSourceError:
            raise
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            raise DocxSourceError(f"DOCX-Datei konnte nicht gelesen werden: {exc}") from exc

        if not segments:
            raise DocxSourceError("DOCX-Datei enthaelt keinen lesbaren Absatztext.")
        self._delegate = InMemoryDocumentSource(
            segments,
            source_id=f"docx:{source_path.name}",
            display_name=source_path.name,
        )

    @property
    def source_id(self) -> str:
        return self._delegate.source_id

    @property
    def display_name(self) -> str:
        return self._delegate.display_name

    def iter_chunks(self):
        return self._delegate.iter_chunks()


def _validate_request(path: Path, limits: tuple[int, ...]) -> None:
    if path.suffix.casefold() != ".docx":
        raise DocxSourceError("Nur Dateien mit der Endung .docx sind erlaubt.")
    if not path.exists() or not path.is_file():
        raise DocxSourceError("DOCX-Datei wurde nicht gefunden.")
    if any(type(value) is not int or value <= 0 for value in limits):
        raise DocxSourceError("Alle DOCX-Limits muessen positive ganze Zahlen sein.")


def _read_document_xml(
    path: Path,
    *,
    max_uncompressed_bytes: int,
    max_xml_bytes: int,
    max_members: int,
) -> bytes:
    with zipfile.ZipFile(path, mode="r") as archive:
        members = archive.infolist()
        if len(members) > max_members:
            raise DocxSourceError(
                f"DOCX-Container enthaelt mehr als {max_members} Eintraege."
            )
        if any(info.flag_bits & 0x1 for info in members):
            raise DocxSourceError("Verschluesselte DOCX-Eintraege sind nicht erlaubt.")
        if sum(info.file_size for info in members) > max_uncompressed_bytes:
            raise DocxSourceError("Entpackter DOCX-Inhalt ueberschreitet das Groessenlimit.")
        names = {info.filename for info in members}
        if any(name.casefold().endswith("vbaproject.bin") for name in names):
            raise DocxSourceError("DOCX-Container mit Makroinhalt wird abgewiesen.")
        if _DOCUMENT_XML not in names:
            raise DocxSourceError("DOCX-Container enthaelt kein word/document.xml.")
        info = archive.getinfo(_DOCUMENT_XML)
        if info.file_size > max_xml_bytes:
            raise DocxSourceError("word/document.xml ueberschreitet das Groessenlimit.")
        data = archive.read(info)
        if len(data) > max_xml_bytes:
            raise DocxSourceError("word/document.xml ueberschreitet das Groessenlimit.")
        return data


def _parse_segments(xml_data: bytes, *, max_paragraphs: int) -> list[DocumentSegment]:
    upper_prefix = xml_data[:4096].upper()
    if b"<!DOCTYPE" in upper_prefix or b"<!ENTITY" in upper_prefix:
        raise DocxSourceError("DTD- und Entity-Deklarationen sind in DOCX-XML nicht erlaubt.")
    try:
        root = ElementTree.fromstring(xml_data)
    except ElementTree.ParseError as exc:
        raise DocxSourceError(f"word/document.xml ist ungueltig: {exc}") from exc

    segments: list[DocumentSegment] = []
    for xml_paragraph, paragraph in enumerate(root.iter(f"{_W}p"), start=1):
        text = _paragraph_text(paragraph)
        if not text:
            continue
        if len(segments) >= max_paragraphs:
            raise DocxSourceError(
                f"DOCX-Datei enthaelt mehr als {max_paragraphs} lesbare Absaetze."
            )
        segments.append(DocumentSegment(
            text=text,
            paragraph=f"Absatz {xml_paragraph}",
            heading=_paragraph_heading(paragraph),
        ))
    return segments


def _paragraph_text(paragraph) -> str:
    parts: list[str] = []
    for element in paragraph.iter():
        if element.tag == f"{_W}t" and element.text:
            parts.append(element.text)
        elif element.tag == f"{_W}tab":
            parts.append("\t")
        elif element.tag in {f"{_W}br", f"{_W}cr"}:
            parts.append("\n")
        elif element.tag == f"{_W}noBreakHyphen":
            parts.append("-")
    text = "".join(parts).replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _paragraph_heading(paragraph) -> str | None:
    style = paragraph.find(f"{_W}pPr/{_W}pStyle")
    if style is None:
        return None
    value = style.attrib.get(f"{_W}val", "")
    folded = value.casefold()
    if folded.startswith("heading") or folded.startswith("uberschrift"):
        return _paragraph_text(paragraph)
    return None

