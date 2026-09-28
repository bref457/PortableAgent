"""Independent deterministic verification for table-analysis results."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from numbers import Number
from types import MappingProxyType
from typing import Any

from portable_agent.capabilities import (
    DEFAULT_CAPABILITY_REGISTRY,
    CapabilityRegistry,
    required_execution_capabilities,
)
from portable_agent.domain import Calculation, Filter, QueryPlan, QueryResult
from portable_agent.plans import validate_plan
from portable_agent.sources import TableRow, TableSource

from .table_engine import _execute_table_plan


class ResultVerificationError(RuntimeError):
    """A calculated result does not agree with its plan, rows or evidence."""


def execute_verified_table_plan(
    source: TableSource,
    plan: QueryPlan,
    *,
    capability_registry: CapabilityRegistry = DEFAULT_CAPABILITY_REGISTRY,
) -> QueryResult:
    """Execute one plan and reject any result that cannot be reproduced."""
    capability_registry.require(*required_execution_capabilities(plan))
    snapshot = _SnapshotTableSource(
        tuple(source.columns),
        tuple(
            TableRow(
                values=MappingProxyType(dict(row.values)),
                source_ref=row.source_ref,
            )
            for row in source.iter_rows()
        ),
    )
    result = _execute_table_plan(snapshot, plan)
    verify_table_result(snapshot, plan, result)
    return result


def execute_table_plan(source: TableSource, plan: QueryPlan) -> QueryResult:
    """Public safe execution boundary with mandatory result verification."""
    return execute_verified_table_plan(source, plan)


@dataclass(frozen=True, slots=True)
class _SnapshotTableSource:
    columns: tuple[str, ...]
    rows: tuple[TableRow, ...]

    def iter_rows(self):
        return iter(self.rows)


def verify_table_result(
    source: TableSource,
    plan: QueryPlan,
    result: QueryResult,
) -> None:
    """Recompute plan facts independently and verify values and citations.

    The verifier reads only the already selected read-only table source. It
    does not repair results and never creates a plausible fallback answer.
    """
    validate_plan(plan, set(source.columns))
    rows = tuple(source.iter_rows())
    _verify_required_filters(rows, plan.required_filters)
    matched = tuple(row for row in rows if _matches_all(row, plan.filters))

    if plan.group_by is None:
        expected_values = {
            calculation.label: _calculate(matched, calculation)
            for calculation in plan.calculations
        }
        expected_citations = tuple(
            row.source_ref
            for row in _supporting_rows(matched, plan.calculations)
        )
        expected_metadata = {"matched_rows": len(matched), "grouped": False}
    else:
        expected_values, expected_citations, expected_metadata = _grouped_result(
            matched,
            plan,
        )

    if result.values != expected_values:
        raise ResultVerificationError(
            "Tabellenergebnis stimmt nicht mit Plan und Quelldaten ueberein."
        )
    if result.citations != expected_citations:
        raise ResultVerificationError(
            "Zeilenbelege stimmen nicht mit den entscheidenden Quelldaten ueberein."
        )
    if result.metadata != expected_metadata:
        raise ResultVerificationError(
            "Ergebnismetadaten stimmen nicht mit der verifizierten Auswertung ueberein."
        )


def _verify_required_filters(
    rows: tuple[TableRow, ...],
    required_filters: tuple[Filter, ...],
) -> None:
    for item in required_filters:
        if not any(_matches(row.values.get(item.column), item) for row in rows):
            raise ResultVerificationError(
                "Ein erforderlicher Entitaetsfilter trifft keine Quellzeile."
            )


def _grouped_result(
    matched: tuple[TableRow, ...],
    plan: QueryPlan,
) -> tuple[dict[str, Any], tuple[Any, ...], dict[str, Any]]:
    assert plan.group_by is not None
    grouped: dict[Any, list[TableRow]] = {}
    for row in matched:
        grouped.setdefault(row.values.get(plan.group_by), []).append(row)

    result_rows = [
        {
            plan.group_by: key,
            **{
                calculation.label: _calculate(tuple(rows), calculation)
                for calculation in plan.calculations
            },
        }
        for key, rows in grouped.items()
    ]
    for sort_rule in reversed(plan.sort):
        try:
            result_rows.sort(
                key=lambda item: _sortable(item[sort_rule.by]),
                reverse=sort_rule.direction == "desc",
            )
        except (KeyError, TypeError) as exc:
            raise ResultVerificationError(
                "Gruppiertes Ergebnis kann nicht sicher nachgeprueft werden."
            ) from exc
    if plan.limit is not None:
        result_rows = result_rows[:plan.limit]

    included_groups = {item[plan.group_by] for item in result_rows}
    selected_row_ids: set[int] = set()
    for key, rows in grouped.items():
        if key not in included_groups:
            continue
        selected_row_ids.update(
            id(row) for row in _supporting_rows(tuple(rows), plan.calculations)
        )
    citations = tuple(
        row.source_ref for row in matched if id(row) in selected_row_ids
    )
    return (
        {"groups": result_rows},
        citations,
        {
            "matched_rows": len(matched),
            "returned_groups": len(result_rows),
            "grouped": True,
        },
    )


def _supporting_rows(
    rows: tuple[TableRow, ...],
    calculations: tuple[Calculation, ...],
) -> tuple[TableRow, ...]:
    if not calculations or any(
        item.aggregation not in {"min", "max"} or item.column is None
        for item in calculations
    ):
        return rows
    extremes = tuple(
        (item.column, _calculate(rows, item))
        for item in calculations
    )
    return tuple(
        row
        for row in rows
        if any(
            extreme is not None and row.values.get(column) == extreme
            for column, extreme in extremes
        )
    )


def _matches_all(row: TableRow, filters: Iterable[Filter]) -> bool:
    return all(_matches(row.values.get(item.column), item) for item in filters)


def _matches(actual: Any, item: Filter) -> bool:
    if item.op == "contains":
        return str(item.value).casefold() in str(actual or "").casefold()
    try:
        if item.op == "==":
            return actual == item.value
        if item.op == "!=":
            return actual != item.value
        if item.op == ">":
            return actual > item.value
        if item.op == ">=":
            return actual >= item.value
        if item.op == "<":
            return actual < item.value
        if item.op == "<=":
            return actual <= item.value
    except TypeError as exc:
        raise ResultVerificationError(
            "Ein Filter kann nicht sicher gegen die Quelldaten geprueft werden."
        ) from exc
    raise ResultVerificationError("Nicht unterstuetzter Filter im Verifier.")


def _calculate(rows: Iterable[TableRow], calculation: Calculation) -> Any:
    materialized = tuple(rows)
    if calculation.aggregation == "count":
        return len(materialized)
    values = tuple(
        row.values.get(calculation.column)
        for row in materialized
        if row.values.get(calculation.column) is not None
    )
    if not values:
        return None
    if calculation.aggregation in {"sum", "average"}:
        if any(isinstance(value, bool) or not isinstance(value, Number) for value in values):
            raise ResultVerificationError(
                "Eine numerische Berechnung kann nicht sicher nachgeprueft werden."
            )
        total = sum(values)
        return total if calculation.aggregation == "sum" else total / len(values)
    try:
        if calculation.aggregation == "min":
            return min(values)
        if calculation.aggregation == "max":
            return max(values)
    except TypeError as exc:
        raise ResultVerificationError(
            "Extremwerte koennen nicht sicher nachgeprueft werden."
        ) from exc
    raise ResultVerificationError("Nicht unterstuetzte Berechnung im Verifier.")


def _sortable(value: Any) -> tuple[bool, Any]:
    return value is None, value
