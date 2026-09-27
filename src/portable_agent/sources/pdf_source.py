"""Read-only PDF text source with stable page citations."""

from __future__ import annotations

import re
from pathlib import Path

try:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError
except ImportError:  # pragma: no cover - exercised only without project dependencies
    PdfReader = None
    PdfReadError = Exception

from .document import DocumentSegment, InMemoryDocumentSource


DEFAULT_MAX_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_PAGES = 1_000
DEFAULT_MAX_CHARS_PER_PAGE = 1_000_000
DEFAULT_MAX_TOTAL_CHARS = 10_000_000


class PdfSourceError(ValueError):
    """A PDF source cannot be opened under the read-only source policy."""


class PdfDependencyError(PdfSourceError):
    """The declared local PDF dependency is unavailable."""


class PdfDocumentSource:
    """Snapshots plain text from one explicit, unencrypted PDF file."""

    def __init__(
        self,
        path: str | Path,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
        max_pages: int = DEFAULT_MAX_PAGES,
        max_chars_per_page: int = DEFAULT_MAX_CHARS_PER_PAGE,
        max_total_chars: int = DEFAULT_MAX_TOTAL_CHARS,
    ) -> None:
        source_path = Path(path)
        limits = (max_bytes, max_pages, max_chars_per_page, max_total_chars)
        _validate_request(source_path, limits)
        if PdfReader is None:
            raise PdfDependencyError(
                "PDF-Unterstuetzung erfordert die lokale Projektabhaengigkeit pypdf."
            )
        try:
            size = source_path.stat().st_size
        except OSError as exc:
            raise PdfSourceError(f"PDF-Datei nicht lesbar: {exc}") from exc
        if size > max_bytes:
            raise PdfSourceError(
                f"PDF-Datei ist groesser als das erlaubte Limit von {max_bytes} Bytes."
            )

        try:
            with source_path.open("rb") as stream:
                reader = PdfReader(stream, strict=True)
                if reader.is_encrypted:
                    raise PdfSourceError("Verschluesselte PDF-Dateien sind nicht erlaubt.")
                page_count = len(reader.pages)
                if page_count > max_pages:
                    raise PdfSourceError(
                        f"PDF-Datei enthaelt mehr als {max_pages} Seiten."
                    )
                segments = _extract_segments(
                    reader,
                    max_chars_per_page=max_chars_per_page,
                    max_total_chars=max_total_chars,
                )
        except PdfSourceError:
            raise
        except (OSError, PdfReadError, ValueError, TypeError, KeyError) as exc:
            raise PdfSourceError(f"PDF-Datei konnte nicht gelesen werden: {exc}") from exc

        if not segments:
            raise PdfSourceError("PDF-Datei enthaelt keinen extrahierbaren Text.")
        self._delegate = InMemoryDocumentSource(
            segments,
            source_id=f"pdf:{source_path.name}",
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
    if path.suffix.casefold() != ".pdf":
        raise PdfSourceError("Nur Dateien mit der Endung .pdf sind erlaubt.")
    if not path.exists() or not path.is_file():
        raise PdfSourceError("PDF-Datei wurde nicht gefunden.")
    if any(type(value) is not int or value <= 0 for value in limits):
        raise PdfSourceError("Alle PDF-Limits muessen positive ganze Zahlen sein.")


def _extract_segments(
    reader,
    *,
    max_chars_per_page: int,
    max_total_chars: int,
) -> list[DocumentSegment]:
    segments: list[DocumentSegment] = []
    total_chars = 0
    for page_number, page in enumerate(reader.pages, start=1):
        text = _normalize_page_text(page.extract_text() or "")
        if len(text) > max_chars_per_page:
            raise PdfSourceError(
                f"Text auf Seite {page_number} ueberschreitet das Zeichenlimit."
            )
        total_chars += len(text)
        if total_chars > max_total_chars:
            raise PdfSourceError("PDF-Text ueberschreitet das Gesamtzeichenlimit.")
        if text:
            segments.append(DocumentSegment(
                text=text,
                page=page_number,
                paragraph=f"Seite {page_number}",
            ))
    return segments


def _normalize_page_text(text: str) -> str:
    if "\x00" in text:
        raise PdfSourceError("Extrahierter PDF-Text enthaelt Nullbytes.")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()
