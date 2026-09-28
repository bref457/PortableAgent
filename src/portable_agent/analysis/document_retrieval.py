"""Deterministic local lexical retrieval for document chunks."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from portable_agent.sources import DocumentChunk, DocumentSource


_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset({
    "aber", "alle", "als", "also", "am", "an", "auch", "auf", "aus",
    "bei", "das", "der", "die", "ein", "eine", "einer", "eines", "er",
    "es", "fuer", "hat", "im", "in", "ist", "mit", "nach", "oder",
    "sich", "sie", "sind", "und", "von", "was", "welche", "welcher",
    "welches", "wie", "wird", "wo", "zu", "zum", "zur",
})


class RetrievalQueryError(ValueError):
    """A retrieval request is structurally invalid."""


@dataclass(frozen=True, slots=True)
class RetrievalMatch:
    chunk: DocumentChunk
    score: int
    matched_terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    query: str
    matches: tuple[RetrievalMatch, ...]
    message: str

    @property
    def found(self) -> bool:
        return bool(self.matches)


def search_document(
    source: DocumentSource,
    query: str,
    *,
    max_results: int = 5,
    min_score: int = 1,
) -> RetrievalResult:
    """Rank chunks locally using token overlap, heading and phrase bonuses."""
    if not isinstance(query, str) or not query.strip():
        raise RetrievalQueryError("Die Suchfrage darf nicht leer sein.")
    if type(max_results) is not int or max_results <= 0:
        raise RetrievalQueryError("max_results muss eine positive ganze Zahl sein.")
    if type(min_score) is not int or min_score <= 0:
        raise RetrievalQueryError("min_score muss eine positive ganze Zahl sein.")

    query_terms = tuple(dict.fromkeys(_informative_tokens(query)))
    if not query_terms:
        return RetrievalResult(
            query=query.strip(),
            matches=(),
            message="Die Frage enthält keine lokal suchbaren Begriffe.",
        )
    phrase = " ".join(query_terms)
    ranked: list[RetrievalMatch] = []

    for chunk in source.iter_chunks():
        body_tokens = Counter(_tokens(chunk.text))
        heading_tokens = Counter(_tokens(chunk.heading or ""))
        matched = tuple(
            term
            for term in query_terms
            if term in body_tokens or term in heading_tokens
        )
        if not matched:
            continue
        score = sum(2 + min(body_tokens[term] - 1, 2) for term in matched if term in body_tokens)
        score += sum(3 for term in matched if term in heading_tokens)
        if len(query_terms) > 1 and phrase in " ".join(_tokens(chunk.text)):
            score += 5
        if score >= min_score:
            ranked.append(RetrievalMatch(chunk=chunk, score=score, matched_terms=matched))

    ranked.sort(key=lambda item: (-item.score, item.chunk.ordinal, item.chunk.chunk_id))
    matches = tuple(ranked[:max_results])
    if not matches:
        message = "Keine passende Fundstelle im Dokument gefunden."
    else:
        message = f"{len(matches)} passende Fundstelle(n) gefunden."
    return RetrievalResult(query=query.strip(), matches=matches, message=message)


def _informative_tokens(text: str) -> list[str]:
    return [token for token in _tokens(text) if len(token) >= 2 and token not in _STOPWORDS]


def _tokens(text: str) -> list[str]:
    folded = text.casefold().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue"}))
    normalized = unicodedata.normalize("NFKD", folded)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return _TOKEN.findall(normalized)
