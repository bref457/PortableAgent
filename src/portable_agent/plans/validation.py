"""Side-effect-free validation for model-produced query plans."""

from __future__ import annotations

from portable_agent.domain import QueryPlan


FILTER_OPERATORS = frozenset({"==", "!=", ">", ">=", "<", "<=", "contains"})
AGGREGATIONS = frozenset({"sum", "average", "min", "max", "count"})
SORT_DIRECTIONS = frozenset({"asc", "desc"})
MAX_RESULT_LIMIT = 1000


class PlanValidationError(ValueError):
    """A plan requests fields or operations outside the allowlist."""


def validate_plan(plan: QueryPlan, available_columns: set[str]) -> None:
    """Validate a plan without reading data or executing calculations."""
    labels: set[str] = set()

    for item in plan.filters:
        if item.column not in available_columns:
            raise PlanValidationError(f"Unbekannte Filterspalte: {item.column}")
        if item.op not in FILTER_OPERATORS:
            raise PlanValidationError(f"Unbekannter Filteroperator: {item.op}")

    for item in plan.calculations:
        if item.aggregation not in AGGREGATIONS:
            raise PlanValidationError(f"Unbekannte Aggregation: {item.aggregation}")
        if item.aggregation != "count" and item.column not in available_columns:
            raise PlanValidationError(f"Unbekannte Berechnungsspalte: {item.column}")
        if item.column is not None and item.column not in available_columns:
            raise PlanValidationError(f"Unbekannte Berechnungsspalte: {item.column}")
        if not item.label or item.label in labels:
            raise PlanValidationError("Berechnungslabels muessen eindeutig und nicht leer sein.")
        labels.add(item.label)

    if plan.group_by is not None and plan.group_by not in available_columns:
        raise PlanValidationError(f"Unbekannte Gruppierungsspalte: {plan.group_by}")

    for item in plan.sort:
        if item.by not in labels:
            raise PlanValidationError(f"Unbekanntes Sortierfeld: {item.by}")
        if item.direction not in SORT_DIRECTIONS:
            raise PlanValidationError(f"Unbekannte Sortierrichtung: {item.direction}")

    if plan.limit is not None and not 1 <= plan.limit <= MAX_RESULT_LIMIT:
        raise PlanValidationError(
            f"Limit muss zwischen 1 und {MAX_RESULT_LIMIT} liegen."
        )

