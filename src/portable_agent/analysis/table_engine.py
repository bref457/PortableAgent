"""Deterministic execution of validated plans against read-only tables."""

from __future__ import annotations

from collections.abc import Iterable
from numbers import Number
from typing import Any

from portable_agent.domain import Calculation, Filter, QueryPlan, QueryResult
from portable_agent.plans import validate_plan
from portable_agent.sources import TableRow, TableSource


class PlanExecutionError(ValueError):
    """A valid plan cannot be applied to the supplied row values."""


def execute_table_plan(source: TableSource, plan: QueryPlan) -> QueryResult:
    """Validate and execute a plan without mutating or persisting source data."""
    validate_plan(plan, set(source.columns))
    matched = tuple(row for row in source.iter_rows() if _matches_all(row, plan.filters))

    if plan.group_by is None:
        values = {
            calculation.label: _calculate(matched, calculation)
            for calculation in plan.calculations
        }
        citations = tuple(row.source_ref for row in matched)
        return QueryResult(
            values=values,
            citations=citations,
            metadata={"matched_rows": len(matched), "grouped": False},
        )

    grouped: dict[Any, list[TableRow]] = {}
    for row in matched:
        key = row.values.get(plan.group_by)
        grouped.setdefault(key, []).append(row)

    result_rows = [
        {
            plan.group_by: key,
            **{
                calculation.label: _calculate(rows, calculation)
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
        except TypeError as exc:
            raise PlanExecutionError(
                f"Werte fuer '{sort_rule.by}' sind nicht gemeinsam sortierbar."
            ) from exc
    if plan.limit is not None:
        result_rows = result_rows[: plan.limit]

    included_groups = {item[plan.group_by] for item in result_rows}
    citations = tuple(
        row.source_ref
        for row in matched
        if row.values.get(plan.group_by) in included_groups
    )
    return QueryResult(
        values={"groups": result_rows},
        citations=citations,
        metadata={
            "matched_rows": len(matched),
            "returned_groups": len(result_rows),
            "grouped": True,
        },
    )


def count_matching_rows(source: TableSource, plan: QueryPlan) -> int:
    """Count rows selected by a valid plan without executing calculations."""
    validate_plan(plan, set(source.columns))
    return sum(1 for row in source.iter_rows() if _matches_all(row, plan.filters))


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
        raise PlanExecutionError(
            f"Filter '{item.column} {item.op}' ist fuer diese Werte nicht anwendbar."
        ) from exc
    raise PlanExecutionError(f"Nicht unterstuetzter Filteroperator: {item.op}")


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
            raise PlanExecutionError(
                f"'{calculation.label}' erwartet ausschliesslich numerische Werte."
            )
        total = sum(values)
        return total if calculation.aggregation == "sum" else total / len(values)

    try:
        if calculation.aggregation == "min":
            return min(values)
        if calculation.aggregation == "max":
            return max(values)
    except TypeError as exc:
        raise PlanExecutionError(
            f"Werte fuer '{calculation.label}' sind nicht gemeinsam vergleichbar."
        ) from exc
    raise PlanExecutionError(
        f"Nicht unterstuetzte Aggregation: {calculation.aggregation}"
    )


def _sortable(value: Any) -> tuple[bool, Any]:
    return value is None, value
