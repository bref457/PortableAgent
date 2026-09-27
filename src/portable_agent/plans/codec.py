"""Strict conversion of untrusted JSON objects into typed query plans."""

from __future__ import annotations

from typing import Any

from portable_agent.domain import Calculation, Filter, QueryPlan, SortRule


_TOP_LEVEL_FIELDS = frozenset({"filters", "calculations", "group_by", "sort", "limit"})
_FILTER_FIELDS = frozenset({"column", "op", "value"})
_CALCULATION_FIELDS = frozenset({"label", "aggregation", "column"})
_SORT_FIELDS = frozenset({"by", "direction"})
_JSON_SCALAR_TYPES = (str, int, float, bool, type(None))


class PlanDecodeError(ValueError):
    """Untrusted model JSON does not match the accepted plan shape."""


def query_plan_from_dict(payload: Any) -> QueryPlan:
    """Decode one exact plan schema without ignoring fields.

    Optional list fields may be omitted or set to JSON ``null``. Both forms mean
    that no operation of that type was requested. Nested values remain strict.
    """
    root = _object(payload, "Plan")
    _reject_unknown(root, _TOP_LEVEL_FIELDS, "Plan")

    filters_raw = _optional_list(root.get("filters"), "filters")
    calculations_raw = _list(root.get("calculations", []), "calculations")
    sort_raw = _optional_list(root.get("sort"), "sort")
    if not calculations_raw:
        raise PlanDecodeError("calculations muss mindestens einen Eintrag enthalten.")

    filters = tuple(_decode_filter(item, index) for index, item in enumerate(filters_raw))
    calculations = tuple(
        _decode_calculation(item, index)
        for index, item in enumerate(calculations_raw)
    )
    sort = tuple(_decode_sort(item, index) for index, item in enumerate(sort_raw))

    group_by = root.get("group_by")
    if group_by is not None:
        group_by = _nonempty_string(group_by, "group_by")

    limit = root.get("limit")
    if limit is not None and type(limit) is not int:
        raise PlanDecodeError("limit muss eine ganze Zahl oder null sein.")

    return QueryPlan(
        filters=filters,
        calculations=calculations,
        group_by=group_by,
        sort=sort,
        limit=limit,
    )


def _decode_filter(payload: Any, index: int) -> Filter:
    path = f"filters[{index}]"
    item = _object(payload, path)
    _reject_unknown(item, _FILTER_FIELDS, path)
    _require(item, _FILTER_FIELDS, path)
    value = item["value"]
    if not isinstance(value, _JSON_SCALAR_TYPES):
        raise PlanDecodeError(f"{path}.value muss ein einfacher JSON-Wert sein.")
    return Filter(
        column=_nonempty_string(item["column"], f"{path}.column"),
        op=_nonempty_string(item["op"], f"{path}.op"),
        value=value,
    )


def _decode_calculation(payload: Any, index: int) -> Calculation:
    path = f"calculations[{index}]"
    item = _object(payload, path)
    _reject_unknown(item, _CALCULATION_FIELDS, path)
    _require(item, {"label", "aggregation"}, path)
    column = item.get("column")
    if column is not None:
        column = _nonempty_string(column, f"{path}.column")
    return Calculation(
        label=_nonempty_string(item["label"], f"{path}.label"),
        aggregation=_nonempty_string(item["aggregation"], f"{path}.aggregation"),
        column=column,
    )


def _decode_sort(payload: Any, index: int) -> SortRule:
    path = f"sort[{index}]"
    item = _object(payload, path)
    _reject_unknown(item, _SORT_FIELDS, path)
    _require(item, {"by"}, path)
    direction = item.get("direction", "asc")
    return SortRule(
        by=_nonempty_string(item["by"], f"{path}.by"),
        direction=_nonempty_string(direction, f"{path}.direction"),
    )


def _object(value: Any, path: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise PlanDecodeError(f"{path} muss ein JSON-Objekt sein.")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if type(value) is not list:
        raise PlanDecodeError(f"{path} muss eine JSON-Liste sein.")
    return value


def _optional_list(value: Any, path: str) -> list[Any]:
    if value is None:
        return []
    return _list(value, path)


def _nonempty_string(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise PlanDecodeError(f"{path} muss eine nicht leere Zeichenkette sein.")
    return value


def _reject_unknown(item: dict[str, Any], allowed: frozenset[str], path: str) -> None:
    unknown = sorted(set(item) - allowed)
    if unknown:
        raise PlanDecodeError(f"{path} enthaelt unbekannte Felder: {', '.join(unknown)}")


def _require(item: dict[str, Any], required: set[str] | frozenset[str], path: str) -> None:
    missing = sorted(required - set(item))
    if missing:
        raise PlanDecodeError(f"{path} fehlen Pflichtfelder: {', '.join(missing)}")
