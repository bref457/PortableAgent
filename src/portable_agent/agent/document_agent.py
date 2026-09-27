"""Grounded document-answer use case over local retrieval results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from portable_agent.analysis import search_document
from portable_agent.domain import DocumentAnswer, SourceRef
from portable_agent.sources import DocumentSource


class DocumentAnswerError(ValueError):
    """A document answer cannot be produced under the grounding policy."""


@dataclass(frozen=True, slots=True)
class DocumentContext:
    """Only the retrieved text and its citation enter answer generation."""

    chunk_id: str
    text: str
    citation: SourceRef
    heading: str | None = None


class DocumentAnswerGenerator(Protocol):
    def generate_answer(
        self,
        question: str,
        contexts: tuple[DocumentContext, ...],
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class DocumentAgent:
    source: DocumentSource
    generator: DocumentAnswerGenerator
    max_results: int = 5
    min_score: int = 1

    def ask(self, question: str) -> DocumentAnswer:
        retrieval = search_document(
            self.source,
            question,
            max_results=self.max_results,
            min_score=self.min_score,
        )
        if not retrieval.found:
            return DocumentAnswer(
                text=retrieval.message,
                citations=(),
                matched_chunks=0,
                generated=False,
            )

        contexts = tuple(
            DocumentContext(
                chunk_id=match.chunk.chunk_id,
                text=match.chunk.text,
                citation=match.chunk.source_ref,
                heading=match.chunk.heading,
            )
            for match in retrieval.matches
        )
        answer = self.generator.generate_answer(question.strip(), contexts)
        if not isinstance(answer, str) or not answer.strip():
            raise DocumentAnswerError(
                "Die lokale Antwortkomponente lieferte keine verwendbare Antwort."
            )
        return DocumentAnswer(
            text=answer.strip(),
            citations=tuple(context.citation for context in contexts),
            matched_chunks=len(contexts),
            generated=True,
        )

