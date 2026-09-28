"""Deterministic semantic policy checks independent from model output."""

from __future__ import annotations

import unicodedata
import re
from dataclasses import replace

from portable_agent.analysis import count_matching_rows
from portable_agent.domain import (
    ClarificationOption,
    ClarificationRequest,
    EntityClarificationRequest,
    Filter,
    QueryPlan,
    QueryResult,
)
from portable_agent.sources import TableSource

from .catalog import SemanticCatalog, normalize_name


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
                    f"Aggregation '{calculation.aggregation}' widerspricht der ausdrücklichen Frage."
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
                f"Welche Berechnung ist für '{calculation.column}' gemeint?"
            ),
            calculation_label=calculation.label,
            column=calculation.column,
            matched_rows=matched_rows,
            options=options,
            original_plan=plan,
        )
    return None


def resolve_clarification(
    request: ClarificationRequest | EntityClarificationRequest,
    option_id: str,
) -> QueryPlan:
    """Apply one selected aggregation or entity without another model call."""
    if isinstance(request, EntityClarificationRequest):
        option = next((item for item in request.options if item.id == option_id), None)
        if option is None:
            raise SemanticPolicyError("Die gewählte Rückfrageoption ist ungültig.")
        entity_filter = Filter(request.column, "==", option.value)
        return replace(
            request.original_plan,
            filters=(
                entity_filter,
                *request.original_plan.filters,
            ),
            required_filters=(
                entity_filter,
                *request.original_plan.required_filters,
            ),
        )
    option = next((item for item in request.options if item.id == option_id), None)
    if option is None:
        raise SemanticPolicyError("Die gewählte Rückfrageoption ist ungültig.")
    calculations = tuple(
        replace(item, aggregation=option.aggregation)
        if item.label == request.calculation_label and item.column == request.column
        else item
        for item in request.original_plan.calculations
    )
    return replace(request.original_plan, calculations=calculations)


def attach_result_semantics(
    result: QueryResult,
    plan: QueryPlan,
    catalog: SemanticCatalog,
    columns: tuple[str, ...] = (),
) -> QueryResult:
    """Attach trusted display metadata without changing calculated values."""
    value_semantics: dict[str, dict[str, str]] = {}
    for calculation in plan.calculations:
        if calculation.column is None:
            continue
        field = catalog.field_for_column(calculation.column)
        if field is None:
            continue
        description = {"data_type": field.data_type}
        if field.unit is not None:
            description["unit"] = field.unit
        value_semantics[calculation.label] = description

    metadata = dict(result.metadata)
    if value_semantics:
        metadata["value_semantics"] = value_semantics
    column_semantics: dict[str, dict[str, str]] = {}
    for column in columns:
        field = catalog.field_for_column(column)
        if field is None:
            continue
        description = {"data_type": field.data_type}
        if field.unit is not None:
            description["unit"] = field.unit
        column_semantics[column] = description
    if column_semantics:
        metadata["column_semantics"] = column_semantics
    if metadata == result.metadata:
        return result
    return replace(result, metadata=metadata)


def normalize_semantic_filters(
    source: TableSource,
    plan: QueryPlan,
    catalog: SemanticCatalog,
) -> QueryPlan:
    """Resolve safe text-filter spelling variants against local source values."""
    target_columns = {
        item.column
        for item in plan.filters
        if item.op in {"==", "!="}
        and isinstance(item.value, str)
        and (field := catalog.field_for_column(item.column)) is not None
        and field.data_type == "text"
    }
    if not target_columns:
        return plan

    source_values: dict[str, set[str]] = {column: set() for column in target_columns}
    for row in source.iter_rows():
        for column in target_columns:
            value = row.values.get(column)
            if isinstance(value, str):
                source_values[column].add(value)

    filters = tuple(
        replace(item, value=_resolve_text_filter_value(item, plan, source_values))
        for item in plan.filters
    )
    return replace(plan, filters=filters)


def _resolve_text_filter_value(
    item: Filter,
    plan: QueryPlan,
    source_values: dict[str, set[str]],
) -> str:
    values = source_values.get(item.column, set())
    direct = _unique_normalized_match(item.value, values)
    if direct is not None:
        return direct

    match = re.search(r"\s+((?:19|20)\d{2})\s*$", item.value)
    if match is None:
        return item.value
    year = int(match.group(1))
    if not _has_date_range_for_year(plan, year):
        return item.value
    without_year = item.value[:match.start()].strip()
    resolved = _unique_normalized_match(without_year, values)
    return resolved if resolved is not None else item.value


def _unique_normalized_match(wanted: str, values: set[str]) -> str | None:
    normalized = normalize_name(wanted)
    matches = [value for value in values if normalize_name(value) == normalized]
    return matches[0] if len(matches) == 1 else None


def _has_date_range_for_year(plan: QueryPlan, year: int) -> bool:
    lower = f"{year:04d}-01-01"
    upper = f"{year + 1:04d}-01-01"
    return (
        any(item.op == ">=" and item.value == lower for item in plan.filters)
        and any(item.op == "<" and item.value == upper for item in plan.filters)
    )


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
            f"Aggregation '{aggregation}' ist für '{column}' nicht erlaubt."
        )


def _explicit_aggregation_intents(question: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", question.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return {
        aggregation
        for aggregation, words in _INTENT_WORDS.items()
        if any(word in normalized for word in words)
    }
