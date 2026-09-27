"""Deterministic semantic policy checks independent from model output."""

from __future__ import annotations

import unicodedata
from dataclasses import replace

from portable_agent.analysis import count_matching_rows
from portable_agent.domain import (
    ClarificationOption,
    ClarificationRequest,
    QueryPlan,
)
from portable_agent.sources import TableSource

from .catalog import SemanticCatalog


_INTENT_WORDS = {
    "sum": ("gesamt", "gesamte", "insgesamt", "summe", "total", "aufsummiert"),
    "average": ("durchschnitt", "durchschnittlich", "mittelwert", "im mittel"),
    "max": (
        "maximum", "maximal", "hoechste", "hochste", "groesste", "grosste",
        "laengste", "langste", "meisten",
        "letzte", "letzter", "letztes", "neueste", "neuster", "neustes",
        "spateste", "jungste",
    ),
    "min": (
        "minimum", "minimal", "niedrigste", "kleinste", "kuerzeste", "kurzeste",
        "wenigsten", "erste", "erster", "erstes", "frueheste", "fruheste",
        "aelteste", "alteste",
    ),
}
_OPTION_LABELS = {
    "sum": "Gesamter Wert",
    "average": "Durchschnittlicher Wert",
    "min": "Kleinster Wert",
    "max": "Groesster Wert",
}


class SemanticPolicyError(ValueError):
    """A syntactically valid plan violates catalog policy."""


def apply_semantic_policy(
    source: TableSource,
    plan: QueryPlan,
    question: str,
    catalog: SemanticCatalog,
) -> ClarificationRequest | None:
    """Enforce field rules and return one typed clarification if required."""
    matched_rows: int | None = None
    explicit_intents = _explicit_aggregation_intents(question)

    for calculation in plan.calculations:
        if calculation.column is None:
            continue
        field = catalog.field_for_column(calculation.column)
        if field is None:
            continue
        _enforce_allowed_aggregation(calculation.aggregation, calculation.column, field)

        if not field.clarify_on_multiple:
            continue
        if explicit_intents:
            if calculation.aggregation not in explicit_intents:
                raise SemanticPolicyError(
                    f"Aggregation '{calculation.aggregation}' widerspricht der ausdruecklichen Frage."
                )
            continue
        if matched_rows is None:
            matched_rows = count_matching_rows(source, plan)
        if matched_rows <= 1:
            continue

        options = tuple(
            ClarificationOption(
                id=aggregation,
                label=_OPTION_LABELS.get(aggregation, aggregation),
                aggregation=aggregation,
            )
            for aggregation in field.allowed_aggregations
        )
        return ClarificationRequest(
            question=(
                f"Welche Berechnung ist fuer '{calculation.column}' gemeint?"
            ),
            calculation_label=calculation.label,
            column=calculation.column,
            matched_rows=matched_rows,
            options=options,
            original_plan=plan,
        )
    return None


def resolve_clarification(
    request: ClarificationRequest,
    option_id: str,
) -> QueryPlan:
    """Apply a selected offered aggregation without invoking a model again."""
    option = next((item for item in request.options if item.id == option_id), None)
    if option is None:
        raise SemanticPolicyError("Die gewaehlte Rueckfrageoption ist ungueltig.")
    calculations = tuple(
        replace(item, aggregation=option.aggregation)
        if item.label == request.calculation_label and item.column == request.column
        else item
        for item in request.original_plan.calculations
    )
    return replace(request.original_plan, calculations=calculations)


def _enforce_allowed_aggregation(aggregation, column, field) -> None:
    if aggregation == "count":
        allowed = "count" in field.allowed_operations or "count" in field.allowed_aggregations
    else:
        allowed = (
            aggregation in field.allowed_aggregations
            or aggregation in field.allowed_operations
        )
    if not allowed:
        raise SemanticPolicyError(
            f"Aggregation '{aggregation}' ist fuer '{column}' nicht erlaubt."
        )


def _explicit_aggregation_intents(question: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", question.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return {
        aggregation
        for aggregation, words in _INTENT_WORDS.items()
        if any(word in normalized for word in words)
    }
