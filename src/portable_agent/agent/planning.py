"""Planner boundary for natural-language table questions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from portable_agent.analysis import execute_table_plan
from portable_agent.domain import (
    ClarificationRequest,
    EntityClarificationRequest,
    QueryResult,
)
from portable_agent.plans import PlanDecodeError, PlanValidationError, query_plan_from_dict
from portable_agent.semantics import (
    SemanticCatalog,
    TemporalEntityNotFoundError,
    apply_semantic_policy,
    attach_result_semantics,
    build_explicit_total_plan,
    build_temporal_extreme_plan,
    normalize_semantic_filters,
)
from portable_agent.sources import TableSource

from .table_query import run_table_query


class PlanGenerator(Protocol):
    """Produces untrusted plan JSON from schema-only context."""

    def generate_plan(
        self,
        question: str,
        columns: tuple[str, ...],
        semantic_definitions: Mapping[str, str],
    ) -> Any: ...


class TableQuestionError(ValueError):
    """The question cannot safely enter the planning pipeline."""


def answer_table_question(
    source: TableSource,
    question: str,
    generator: PlanGenerator,
    *,
    semantic_definitions: Mapping[str, str] | None = None,
    semantic_catalog: SemanticCatalog | None = None,
) -> QueryResult | ClarificationRequest | EntityClarificationRequest:
    """Generate, decode, validate and execute a table plan with citations."""
    if not isinstance(question, str) or not question.strip():
        raise TableQuestionError("Die Frage darf nicht leer sein.")
    if not source.columns:
        raise TableQuestionError("Die Tabellenquelle hat keine Spalten.")

    definitions = semantic_definitions or {}
    allowed_definitions = {
        column: description
        for column, description in definitions.items()
        if column in source.columns and isinstance(description, str)
    }
    clean_question = question.strip()
    if semantic_catalog is not None:
        explicit_total_plan = build_explicit_total_plan(
            source,
            clean_question,
            semantic_catalog,
        )
        if explicit_total_plan is not None:
            apply_semantic_policy(
                source,
                explicit_total_plan,
                clean_question,
                semantic_catalog,
            )
            return attach_result_semantics(
                execute_table_plan(source, explicit_total_plan),
                explicit_total_plan,
                semantic_catalog,
                tuple(source.columns),
            )
        try:
            temporal_plan = build_temporal_extreme_plan(
                source,
                clean_question,
                semantic_catalog,
            )
        except TemporalEntityNotFoundError as exc:
            raise TableQuestionError(str(exc)) from exc
        if isinstance(temporal_plan, EntityClarificationRequest):
            return temporal_plan
        if temporal_plan is not None:
            apply_semantic_policy(source, temporal_plan, clean_question, semantic_catalog)
            return attach_result_semantics(
                execute_table_plan(source, temporal_plan),
                temporal_plan,
                semantic_catalog,
                tuple(source.columns),
            )

    for attempt in range(2):
        payload = generator.generate_plan(
            clean_question,
            tuple(source.columns),
            allowed_definitions,
        )
        try:
            if semantic_catalog is None:
                return run_table_query(source, payload)

            plan = query_plan_from_dict(payload)
            plan = normalize_semantic_filters(source, plan, semantic_catalog)
            clarification = apply_semantic_policy(
                source,
                plan,
                clean_question,
                semantic_catalog,
            )
            if clarification is not None:
                return clarification
            return attach_result_semantics(
                execute_table_plan(source, plan),
                plan,
                semantic_catalog,
                tuple(source.columns),
            )
        except (PlanDecodeError, PlanValidationError) as exc:
            if attempt == 1:
                raise TableQuestionError(
                    "Das lokale Modell lieferte keinen gültigen Tabellenplan. "
                    "Bitte formuliere deine Frage eindeutiger."
                ) from exc

    raise AssertionError("Unerreichbarer Tabellenplan-Zustand.")
