"""Read-only UTF-8 TXT document source."""

from __future__ import annotations

from pathlib import Path

from .document import DocumentChunk, DocumentSegment, InMemoryDocumentSource


DEFAULT_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_PARAGRAPHS = 100_000


class TxtSourceError(ValueError):
    """A TXT source cannot be opened under the read-only source policy."""


class TxtDocumentSource:
    """Snapshots one explicit UTF-8 text file as paragraph chunks."""

    def __init__(
        self,
        path: str | Path,
        *,
        encoding: str = "utf-8-sig",
        max_bytes: int = DEFAULT_MAX_BYTES,
        max_paragraphs: int = DEFAULT_MAX_PARAGRAPHS,
    ) -> None:
        source_path = Path(path)
        _validate_request(source_path, encoding, max_bytes, max_paragraphs)
        try:
            size = source_path.stat().st_size
        except OSError as exc:
            raise TxtSourceError(f"Textdatei nicht lesbar: {exc}") from exc
        if size > max_bytes:
            raise TxtSourceError(
                f"Textdatei ist groesser als das erlaubte Limit von {max_bytes} Bytes."
            )
        try:
            text = source_path.read_text(encoding=encoding)
        except (OSError, UnicodeError) as exc:
            raise TxtSourceError(f"Textdatei konnte nicht als UTF-8 gelesen werden: {exc}") from exc
        if "\x00" in text:
            raise TxtSourceError("Textdatei enthaelt binaere Nullbytes.")

        segments = _paragraph_segments(text, max_paragraphs=max_paragraphs)
        if not segments:
            raise TxtSourceError("Textdatei enthaelt keinen lesbaren Text.")
        self._delegate = InMemoryDocumentSource(
            segments,
            source_id=f"txt:{source_path.name}",
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


def _validate_request(path, encoding, max_bytes, max_paragraphs) -> None:
    if path.suffix.casefold() != ".txt":
        raise TxtSourceError("Nur Dateien mit der Endung .txt sind erlaubt.")
    if not path.exists() or not path.is_file():
        raise TxtSourceError("Textdatei wurde nicht gefunden.")
    if encoding not in {"utf-8", "utf-8-sig"}:
        raise TxtSourceError("Nur UTF-8 ist als Textkodierung erlaubt.")
    if type(max_bytes) is not int or max_bytes <= 0:
        raise TxtSourceError("max_bytes muss eine positive ganze Zahl sein.")
    if type(max_paragraphs) is not int or max_paragraphs <= 0:
        raise TxtSourceError("max_paragraphs muss eine positive ganze Zahl sein.")


def _paragraph_segments(text: str, *, max_paragraphs: int) -> list[DocumentSegment]:
    segments: list[DocumentSegment] = []
    current: list[str] = []
    start_line: int | None = None
    end_line: int | None = None

    def flush() -> None:
        nonlocal current, start_line, end_line
        if not current:
            return
        if len(segments) >= max_paragraphs:
            raise TxtSourceError(
                f"Textdatei enthaelt mehr als {max_paragraphs} Absaetze."
            )
        paragraph_number = len(segments) + 1
        line_reference = (
            f"Absatz {paragraph_number}, Zeile {start_line}"
            if start_line == end_line
            else f"Absatz {paragraph_number}, Zeilen {start_line}-{end_line}"
        )
        segments.append(DocumentSegment(
            text="\n".join(current).strip(),
            paragraph=line_reference,
        ))
        current = []
        start_line = None
        end_line = None

    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            flush()
            continue
        if start_line is None:
            start_line = line_number
        end_line = line_number
        current.append(line.strip())
    flush()
    return segments

