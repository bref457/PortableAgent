"""Strict transport-neutral JSON boundary for one local table question."""

from __future__ import annotations

import json
from typing import Any

from portable_agent.agent import PendingTableClarification, TableWorkflow
from portable_agent.domain import (
    ClarificationRequest,
    EntityClarificationRequest,
    QueryResult,
    SourceRef,
)


DEFAULT_MAX_TABLE_REQUEST_CHARS = 16_384
_SCHEMAS = {
    "ask_table": (
        frozenset({"operation", "path", "question", "sheet_name"}),
        frozenset({"operation", "path", "question"}),
    ),
    "resolve_table": (
        frozenset({"operation", "clarification_id", "option_id"}),
        frozenset({"operation", "clarification_id", "option_id"}),
    ),
}


class TableJsonError(ValueError):
    """An untrusted JSON request does not match the accepted table API shape."""


class TableJsonController:
    """Maps one strict JSON request to an in-process TableWorkflow."""

    def __init__(
        self,
        workflow: TableWorkflow,
        *,
        max_request_chars: int = DEFAULT_MAX_TABLE_REQUEST_CHARS,
    ) -> None:
        if not isinstance(workflow, TableWorkflow):
            raise TypeError("workflow muss ein TableWorkflow sein.")
        if type(max_request_chars) is not int or max_request_chars <= 0:
            raise TableJsonError(
                "max_request_chars muss eine positive ganze Zahl sein."
            )
        self._workflow = workflow
        self._max_request_chars = max_request_chars

    def handle_json(self, request_json: str) -> str:
        request = _decode_request(request_json, self._max_request_chars)
        operation = _nonempty_string(
            request.get("operation"), "operation", max_chars=64
        )
        schema = _SCHEMAS.get(operation)
        if schema is None:
            raise TableJsonError(f"Unbekannte Tabellenoperation: {operation}")
        _require_fields(request, operation, *schema)

        if operation == "ask_table":
            path = _nonempty_string(request["path"], "path", max_chars=4_096)
            question = _nonempty_string(
                request["question"], "question", max_chars=10_000
            )
            sheet_name = None
            if "sheet_name" in request:
                sheet_name = _nonempty_string(
                    request["sheet_name"], "sheet_name", max_chars=255
                )
            result = self._workflow.ask_file(
                path,
                question,
                sheet_name=sheet_name,
            )
        else:
            clarification_id = _nonempty_string(
                request["clarification_id"],
                "clarification_id",
                max_chars=256,
            )
            option_id = _nonempty_string(
                request["option_id"], "option_id", max_chars=64
            )
            result = self._workflow.resolve(clarification_id, option_id)
        response = {
            "ok": True,
            "operation": operation,
            "result": _result_dict(result),
        }
        return json.dumps(
            response,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )


def _decode_request(request_json: Any, max_chars: int) -> dict[str, Any]:
    if type(request_json) is not str or not request_json.strip():
        raise TableJsonError("JSON-Request muss eine nicht leere Zeichenkette sein.")
    if len(request_json) > max_chars:
        raise TableJsonError(
            f"JSON-Request ist größer als das Limit von {max_chars} Zeichen."
        )
    try:
        payload = json.loads(
            request_json,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_nonstandard_constant,
        )
    except json.JSONDecodeError as exc:
        raise TableJsonError(f"Ungültiger JSON-Request: {exc.msg}") from exc
    if type(payload) is not dict:
        raise TableJsonError("JSON-Request muss ein Objekt sein.")
    return payload


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TableJsonError(f"JSON-Request enthält doppeltes Feld: {key}")
        result[key] = value
    return result


def _reject_nonstandard_constant(value: str) -> None:
    raise TableJsonError(
        f"Nicht standardkonstanter JSON-Wert ist unzulaessig: {value}"
    )


def _require_fields(
    request: dict[str, Any],
    operation: str,
    allowed: frozenset[str],
    required: frozenset[str],
) -> None:
    unknown = sorted(set(request) - allowed)
    if unknown:
        raise TableJsonError(
            f"{operation} enthält unbekannte Felder: {', '.join(unknown)}"
        )
    missing = sorted(required - set(request))
    if missing:
        raise TableJsonError(
            f"{operation} fehlen Pflichtfelder: {', '.join(missing)}"
        )


def _nonempty_string(value: Any, path: str, *, max_chars: int) -> str:
    if type(value) is not str or not value.strip():
        raise TableJsonError(f"{path} muss eine nicht leere Zeichenkette sein.")
    if "\x00" in value:
        raise TableJsonError(f"{path} darf keine Nullbytes enthalten.")
    if len(value) > max_chars:
        raise TableJsonError(
            f"{path} darf hoechstens {max_chars} Zeichen enthalten."
        )
    return value.strip()


def _result_dict(
    result: QueryResult | PendingTableClarification,
) -> dict[str, Any]:
    if isinstance(result, QueryResult):
        return {
            "citations": [_source_ref_dict(item) for item in result.citations],
            "metadata": result.metadata,
            "type": "query_result",
            "values": result.values,
        }
    if isinstance(result, PendingTableClarification):
        request = result.request
        if isinstance(request, EntityClarificationRequest):
            return {
                "candidate_count": len(request.options),
                "clarification_id": result.clarification_id,
                "clarification_kind": "entity",
                "column": request.column,
                "options": [
                    {"id": option.id, "label": option.label}
                    for option in request.options
                ],
                "question": request.question,
                "type": "clarification",
            }
        if not isinstance(request, ClarificationRequest):
            raise TypeError("Unbekannte Tabellen-Rueckfrage.")
        return {
            "calculation_label": request.calculation_label,
            "clarification_id": result.clarification_id,
            "clarification_kind": "aggregation",
            "column": request.column,
            "matched_rows": request.matched_rows,
            "options": [
                {
                    "aggregation": option.aggregation,
                    "id": option.id,
                    "label": option.label,
                }
                for option in request.options
            ],
            "question": request.question,
            "type": "clarification",
        }
    raise TypeError("TableWorkflow lieferte einen unbekannten Ergebnistyp.")


def _source_ref_dict(source_ref: SourceRef) -> dict[str, Any]:
    return {
        "display_name": source_ref.display_name,
        "excerpt": source_ref.excerpt,
        "page": source_ref.page,
        "paragraph": source_ref.paragraph,
        "row": source_ref.row,
        "row_values": dict(source_ref.row_values) if source_ref.row_values else None,
        "section": source_ref.section,
        "source_id": source_ref.source_id,
    }
