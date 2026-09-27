"""Deterministic plans for unambiguous calendar questions."""

from __future__ import annotations

import re
import unicodedata

from portable_agent.domain import Calculation, Filter, QueryPlan, SortRule

from .catalog import SemanticCatalog


_YEAR_PATTERN = re.compile(r"(?<!\d)([1-9]\d{3})(?!\d)")
_LATEST_WORDS = (
    "letzte",
    "letzter",
    "letztes",
    "zuletzt",
    "neueste",
    "neuster",
    "neustes",
    "spateste",
    "spatester",
    "spatestes",
    "jungste",
    "jungster",
    "jungstes",
)
_EARLIEST_WORDS = (
    "erste",
    "erster",
    "erstes",
    "fruheste",
    "fruhester",
    "fruhestes",
    "alteste",
    "altester",
    "altestes",
)


def build_temporal_extreme_plan(
    question: str,
    columns: tuple[str, ...],
    catalog: SemanticCatalog,
) -> QueryPlan | None:
    """Return a safe year-bounded min/max date plan when intent is exact.

    The helper uses only the question and trusted schema metadata. It never
    receives or inspects table rows or cell values.
    """
    normalized = _normalize(question)
    years = {int(match) for match in _YEAR_PATTERN.findall(normalized)}
    if len(years) > 1:
        return None
    year = next(iter(years), None)
    if year is not None and year >= 9999:
        return None

    wants_latest = any(word in normalized for word in _LATEST_WORDS)
    wants_earliest = any(word in normalized for word in _EARLIEST_WORDS)
    if wants_latest == wants_earliest:
        return None

    date_columns = tuple(
        column
        for column in columns
        if (field := catalog.field_for_column(column)) is not None
        and field.data_type == "date"
    )
    if len(date_columns) != 1:
        return None

    date_column = date_columns[0]
    aggregation = "max" if wants_latest else "min"
    label = "Letzter Einsatz" if wants_latest else "Erster Einsatz"
    filters = () if year is None else (
        Filter(date_column, ">=", f"{year:04d}-01-01"),
        Filter(date_column, "<", f"{year + 1:04d}-01-01"),
    )
    action_columns = tuple(
        column
        for column in columns
        if (field := catalog.field_for_column(column)) is not None
        and field.canonical_name == "Aktion"
    )
    group_by = action_columns[0] if len(action_columns) == 1 else None
    return QueryPlan(
        filters=filters,
        calculations=(Calculation(label, aggregation, date_column),),
        group_by=group_by,
        sort=(SortRule(label, "desc" if wants_latest else "asc"),) if group_by else (),
        limit=1 if group_by else None,
    )


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return re.sub(r"\s+", " ", without_marks).strip()
