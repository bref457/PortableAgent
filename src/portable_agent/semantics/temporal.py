"""Deterministic plans for unambiguous calendar questions."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from portable_agent.domain import (
    Calculation,
    EntityClarificationOption,
    EntityClarificationRequest,
    Filter,
    QueryPlan,
    SortRule,
)
from portable_agent.sources import TableSource

from .catalog import SemanticCatalog, normalize_name


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
    "ersten",
    "erster",
    "erstes",
    "fruheste",
    "fruhester",
    "fruhestes",
    "alteste",
    "altester",
    "altestes",
    "erstmals",
    "erstmalig",
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
_NAMED_ACTION_PATTERNS = (
    re.compile(
        r"\baktion\s+(?P<entity>.+?)\s+(?:das\s+)?"
        r"(?:erste|ersten|letzte|letzten|erstmals|erstmalig|zuletzt)\b"
    ),
    re.compile(
        r"\b(?:war|wurde|fand|wir)\s+(?P<entity>.+?)\s+"
        r"(?:(?:19|20)\d{2}\s+)?(?:erstmals|erstmalig|zuletzt|"
        r"zum\s+ersten|das\s+erste|das\s+letzte)\b"
    ),
)
_ENTITY_STOPWORDS = frozenset({
    "an", "am", "bei", "das", "dem", "den", "der", "die", "ein", "eine",
    "einem", "einen", "einer", "einsatz", "erst", "erste", "ersten",
    "erster", "erstes", "erstmal", "erstmalig", "erstmals", "fand", "fuer",
    "gefahren", "im", "in", "ist", "jahr", "letzte", "letzten", "letzter",
    "letztes", "mal", "statt", "und", "vom", "von", "wann", "war", "welchem",
    "welcher", "welches", "wurde", "wir", "zu", "zuletzt", "zum",
    "durchgefuehrt", "durchgefuhrt", "frueheste", "fruheste", "spaeteste",
    "spateste", "neueste", "aelteste", "alteste", "juengste", "jungste",
})


class TemporalEntityNotFoundError(ValueError):
    """A named action cannot be safely resolved from local table values."""


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
    source: TableSource,
    question: str,
    catalog: SemanticCatalog,
) -> QueryPlan | EntityClarificationRequest | None:
    """Return a safe year-bounded min/max date plan when intent is exact.

    Cell values are inspected only in local Python to resolve an explicitly
    named action. They are never passed to the model.
    """
    normalized = _normalize(question)
    years = {int(match) for match in _YEAR_PATTERN.findall(normalized)}
    if len(years) > 1:
        return None
    year = next(iter(years), None)
    if year is not None and year >= 9999:
        return None

    wants_latest = any(_mentions(normalized, word) for word in _LATEST_WORDS)
    wants_earliest = any(_mentions(normalized, word) for word in _EARLIEST_WORDS)
    if wants_latest == wants_earliest:
        return None

    date_columns = tuple(
        column
        for column in source.columns
        if (field := catalog.field_for_column(column)) is not None
        and field.data_type == "date"
    )
    if len(date_columns) != 1:
        return None

    date_column = date_columns[0]
    aggregation = "max" if wants_latest else "min"
    label = "Letzter Einsatz" if wants_latest else "Erster Einsatz"
    date_filters = () if year is None else (
        Filter(date_column, ">=", f"{year:04d}-01-01"),
        Filter(date_column, "<", f"{year + 1:04d}-01-01"),
    )
    action_columns = tuple(
        column
        for column in source.columns
        if (field := catalog.field_for_column(column)) is not None
        and field.canonical_name == "Aktion"
    )
    if len(action_columns) == 1:
        action_column = action_columns[0]
        action_resolution = _resolve_named_action(
            source,
            normalized,
            action_column,
            catalog,
        )
        base_plan = QueryPlan(
            filters=date_filters,
            calculations=(Calculation(label, aggregation, date_column),),
        )
        if isinstance(action_resolution, str):
            return QueryPlan(
                filters=(Filter(action_column, "==", action_resolution), *date_filters),
                calculations=base_plan.calculations,
            )
        if isinstance(action_resolution, EntityClarificationRequest):
            return EntityClarificationRequest(
                question=action_resolution.question,
                column=action_column,
                options=action_resolution.options,
                original_plan=base_plan,
            )

    group_by = action_columns[0] if len(action_columns) == 1 else None
    return QueryPlan(
        filters=date_filters,
        calculations=(Calculation(label, aggregation, date_column),),
        group_by=group_by,
        sort=(SortRule(label, "desc" if wants_latest else "asc"),) if group_by else (),
        limit=1 if group_by else None,
    )


def _resolve_named_action(
    source: TableSource,
    normalized_question: str,
    action_column: str,
    catalog: SemanticCatalog,
) -> str | EntityClarificationRequest | None:
    values = tuple(dict.fromkeys(
        value
        for row in source.iter_rows()
        if isinstance((value := row.values.get(action_column)), str) and value.strip()
    ))
    exact = tuple(
        value for value in values
        if _mentions(normalized_question, _normalize(value))
    )
    if exact:
        longest = max(len(normalize_name(value)) for value in exact)
        best = tuple(value for value in exact if len(normalize_name(value)) == longest)
        if len(best) == 1:
            return best[0]
        return _entity_clarification(action_column, best, "Welche Aktion ist gemeint?")

    hints = _entity_hint_tokens(normalized_question, catalog)
    if not hints:
        return None
    candidates = tuple(
        value for value in values if _is_possible_action(hints, value)
    )
    if candidates:
        question = (
            "Welche Aktion ist gemeint?"
            if len(candidates) > 1
            else "Meintest du diese Aktion?"
        )
        return _entity_clarification(action_column, candidates, question)
    if _looks_like_named_action(normalized_question):
        raise TemporalEntityNotFoundError(
            "Die genannte Aktion wurde in der Tabelle nicht gefunden. "
            "Bitte verwende ihre genaue Bezeichnung."
        )
    return None


def _entity_hint_tokens(
    normalized_question: str,
    catalog: SemanticCatalog,
) -> tuple[str, ...]:
    ignored = set(_ENTITY_STOPWORDS)
    ignored.update(_LATEST_WORDS)
    ignored.update(_EARLIEST_WORDS)
    for field in catalog.fields:
        if field.canonical_name in {"Aktion", "Datum"}:
            for name in field.all_names:
                ignored.update(re.findall(r"[a-z0-9]+", _normalize(name)))
    return tuple(
        token
        for token in re.findall(r"[a-z0-9]+", normalized_question)
        if token not in ignored
        and not _YEAR_PATTERN.fullmatch(token)
        and len(token) >= 2
    )


def _is_possible_action(hints: tuple[str, ...], value: str) -> bool:
    value_tokens = tuple(re.findall(r"[a-z0-9]+", _normalize(value)))
    compact_value = normalize_name(value)
    for hint in hints:
        compact_hint = normalize_name(hint)
        if compact_hint in value_tokens:
            return True
        if len(compact_hint) >= 3 and (
            compact_value.startswith(compact_hint)
            or compact_hint.startswith(compact_value)
        ):
            return True
        if len(compact_hint) >= 4 and any(
            SequenceMatcher(None, compact_hint, token).ratio() >= 0.8
            for token in value_tokens
        ):
            return True
    return False


def _looks_like_named_action(normalized_question: str) -> bool:
    for pattern in _NAMED_ACTION_PATTERNS:
        match = pattern.search(normalized_question)
        if match is None:
            continue
        entity = match.group("entity")
        meaningful = tuple(
            token
            for token in re.findall(r"[a-z0-9]+", entity)
            if token not in _ENTITY_STOPWORDS
            and not _YEAR_PATTERN.fullmatch(token)
        )
        if meaningful:
            return True
    return False


def _entity_clarification(
    action_column: str,
    values: tuple[str, ...],
    question: str,
) -> EntityClarificationRequest:
    return EntityClarificationRequest(
        question=question,
        column=action_column,
        options=tuple(
            EntityClarificationOption(
                id=f"entity-{index}",
                label=value,
                value=value,
            )
            for index, value in enumerate(values, start=1)
        ),
        original_plan=QueryPlan(),
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
