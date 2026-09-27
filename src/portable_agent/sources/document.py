"""Read-only document-source abstractions with stable citations."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Protocol

from portable_agent.domain import SourceRef


DEFAULT_EXCERPT_CHARS = 240


@dataclass(frozen=True, slots=True)
class DocumentSegment:
    """Synthetic/parser output before source identity is attached."""

    text: str
    page: int | None = None
    paragraph: str | None = None
    heading: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    """One immutable, independently citable document fragment."""

    chunk_id: str
    text: str
    source_ref: SourceRef
    ordinal: int
    heading: str | None = None


class DocumentSource(Protocol):
    """Minimal read-only contract for local document retrieval."""

    @property
    def source_id(self) -> str: ...

    @property
    def display_name(self) -> str: ...

    def iter_chunks(self) -> Iterator[DocumentChunk]: ...


class InMemoryDocumentSource:
    """Snapshots synthetic segments and attaches stable source references."""

    def __init__(
        self,
        segments: Iterable[DocumentSegment],
        *,
        source_id: str = "synthetic-document",
        display_name: str = "synthetic",
        excerpt_chars: int = DEFAULT_EXCERPT_CHARS,
    ) -> None:
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("source_id darf nicht leer sein.")
        if not isinstance(display_name, str) or not display_name.strip():
            raise ValueError("display_name darf nicht leer sein.")
        if type(excerpt_chars) is not int or excerpt_chars <= 0:
            raise ValueError("excerpt_chars muss eine positive ganze Zahl sein.")

        snapshots = tuple(_validate_segment(segment) for segment in segments)
        self._source_id = source_id.strip()
        self._display_name = display_name.strip()
        self._chunks = tuple(
            DocumentChunk(
                chunk_id=f"{self._source_id}:chunk:{ordinal}",
                text=segment.text.strip(),
                source_ref=SourceRef(
                    source_id=self._source_id,
                    display_name=self._display_name,
                    page=segment.page,
                    paragraph=segment.paragraph,
                    excerpt=_excerpt(segment.text, excerpt_chars),
                ),
                ordinal=ordinal,
                heading=segment.heading.strip() if segment.heading else None,
            )
            for ordinal, segment in enumerate(snapshots, start=1)
        )

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def display_name(self) -> str:
        return self._display_name

    def iter_chunks(self) -> Iterator[DocumentChunk]:
        return iter(self._chunks)


def _validate_segment(segment: DocumentSegment) -> DocumentSegment:
    if not isinstance(segment, DocumentSegment):
        raise ValueError("segments darf nur DocumentSegment-Objekte enthalten.")
    if not isinstance(segment.text, str) or not segment.text.strip():
        raise ValueError("Dokumentsegmente duerfen keinen leeren Text enthalten.")
    if segment.page is not None and (type(segment.page) is not int or segment.page < 1):
        raise ValueError("Seitennummern muessen positive ganze Zahlen sein.")
    if segment.paragraph is not None and (
        not isinstance(segment.paragraph, str) or not segment.paragraph.strip()
    ):
        raise ValueError("Absatzreferenzen muessen nicht leere Zeichenketten sein.")
    if segment.heading is not None and (
        not isinstance(segment.heading, str) or not segment.heading.strip()
    ):
        raise ValueError("Ueberschriften muessen nicht leere Zeichenketten sein.")
    return DocumentSegment(
        text=segment.text.strip(),
        page=segment.page,
        paragraph=segment.paragraph.strip() if segment.paragraph else None,
        heading=segment.heading.strip() if segment.heading else None,
    )


def _excerpt(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: max(1, limit - 1)].rstrip() + "…"

