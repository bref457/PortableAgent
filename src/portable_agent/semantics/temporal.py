"""Deterministic plans for unambiguous calendar questions."""

from __future__ import annotations

import re
import unicodedata

from portable_agent.domain import Calculation, Filter, QueryPlan, SortRule
from portable_agent.sources import TableSource

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
_TOTAL_WORDS = ("gesamt", "gesamte", "gesamten", "insgesamt", "summe")
_NON_SUM_STEMS = (
    "durchschnitt",
    "mittelwert",
    "langste",
    "kurzeste",
    "hochste",
    "niedrigste",
    "maximum",
    "minimum",
    "maximal",
    "minimal",
)
_QUANTITY_PATTERNS = (
    re.compile(r"\bwieviel\b"),
    re.compile(r"\bwie\s+viel(?:e|en|er|es)?\b"),
)


def build_explicit_total_plan(
    source: TableSource,
    question: str,
    catalog: SemanticCatalog,
) -> QueryPlan | None:
    """Build a local sum plan for an explicitly named measure and action.

    This deliberately narrow shortcut prevents a local language model from
    changing an otherwise unambiguous question. Cell values are inspected only
    in Python to identify the action named by the user and are never passed to
    the model.
    """
    normalized = _normalize(question)
    explicit_total = any(_mentions(normalized, word) for word in _TOTAL_WORDS)
    quantity_question = any(pattern.search(normalized) for pattern in _QUANTITY_PATTERNS)
    if any(stem in normalized for stem in _NON_SUM_STEMS):
        return None

    years = {int(match) for match in _YEAR_PATTERN.findall(normalized)}
    if len(years) != 1:
        return None
    year = next(iter(years))
    if year >= 9999:
        return None

    measure_columns = [
        column
        for column in source.columns
        if (field := catalog.field_for_column(column)) is not None
        and field.role == "measure"
        and "sum" in field.allowed_aggregations
        and any(_mentions(normalized, _normalize(name)) for name in field.all_names)
    ]
    if len(measure_columns) != 1:
        return None
    measure_field = catalog.field_for_column(measure_columns[0])
    if measure_field is None or not (
        explicit_total
        or (quantity_question and measure_field.default_aggregation == "sum")
    ):
        return None

    action_columns = [
        column
        for column in source.columns
        if (field := catalog.field_for_column(column)) is not None
        and field.canonical_name == "Aktion"
    ]
    if len(action_columns) != 1:
        return None
    action_column = action_columns[0]

    matching_actions: dict[str, object] = {}
    for row in source.iter_rows():
        value = row.values.get(action_column)
        if value is None:
            continue
        normalized_value = _normalize(str(value))
        if len(normalized_value) >= 3 and _mentions(normalized, normalized_value):
            matching_actions.setdefault(normalized_value, value)
    if not matching_actions:
        return None
    longest = max(len(name) for name in matching_actions)
    best = [value for name, value in matching_actions.items() if len(name) == longest]
    if len(best) != 1:
        return None

    filters = [Filter(action_column, "==", best[0])]
    date_columns = [
        column
        for column in source.columns
        if (field := catalog.field_for_column(column)) is not None
        and field.data_type == "date"
    ]
    if len(date_columns) != 1:
        return None
    filters.extend((
        Filter(date_columns[0], ">=", f"{year:04d}-01-01"),
        Filter(date_columns[0], "<", f"{year + 1:04d}-01-01"),
    ))

    measure_column = measure_columns[0]
    return QueryPlan(
        filters=tuple(filters),
        calculations=(Calculation(f"Gesamte {measure_column}", "sum", measure_column),),
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


def _mentions(question: str, phrase: str) -> bool:
    if not phrase:
        return False
    return re.search(
        rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])",
        question,
    ) is not None
