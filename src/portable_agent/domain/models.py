"""Typed, dependency-free domain models for plans and citations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Filter:
    column: str
    op: str
    value: Any


@dataclass(frozen=True, slots=True)
class Calculation:
    label: str
    aggregation: str
    column: str | None = None


@dataclass(frozen=True, slots=True)
class SortRule:
    by: str
    direction: str = "asc"


@dataclass(frozen=True, slots=True)
class QueryPlan:
    filters: tuple[Filter, ...] = ()
    calculations: tuple[Calculation, ...] = ()
    group_by: str | None = None
    sort: tuple[SortRule, ...] = ()
    limit: int | None = None


@dataclass(frozen=True, slots=True)
class SourceRef:
    source_id: str
    display_name: str
    section: str | None = None
    row: int | None = None
    page: int | None = None
    paragraph: str | None = None
    excerpt: str | None = None
    row_values: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class QueryResult:
    values: dict[str, Any]
    citations: tuple[SourceRef, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ClarificationOption:
    id: str
    label: str
    aggregation: str


@dataclass(frozen=True, slots=True)
class ClarificationRequest:
    question: str
    calculation_label: str
    column: str
    matched_rows: int
    options: tuple[ClarificationOption, ...]
    original_plan: QueryPlan


@dataclass(frozen=True, slots=True)
class EntityClarificationOption:
    id: str
    label: str
    value: str


@dataclass(frozen=True, slots=True)
class EntityClarificationRequest:
    question: str
    column: str
    options: tuple[EntityClarificationOption, ...]
    original_plan: QueryPlan


@dataclass(frozen=True, slots=True)
class DocumentAnswer:
    text: str
    citations: tuple[SourceRef, ...]
    matched_chunks: int
    generated: bool
