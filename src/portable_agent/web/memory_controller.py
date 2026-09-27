"""Strict transport-neutral JSON boundary for confirmed local memory notes."""

from __future__ import annotations

import json
from typing import Any

from portable_agent.memory import (
    MemoryConfirmation,
    MemoryNote,
    SqliteMemoryRepository,
)


DEFAULT_MAX_MEMORY_REQUEST_CHARS = 16_384
_SCHEMAS = {
    "list_notes": frozenset({"operation"}),
    "add_note": frozenset({"operation", "text", "confirmation"}),
    "delete_note": frozenset({"operation", "note_id", "confirmation"}),
}


class MemoryJsonError(ValueError):
    """An untrusted JSON request does not match the memory API shape."""


class MemoryJsonController:
    """Maps exact JSON requests to explicitly confirmed memory operations."""

    def __init__(
        self,
        repository: SqliteMemoryRepository,
        *,
        max_request_chars: int = DEFAULT_MAX_MEMORY_REQUEST_CHARS,
    ) -> None:
        if not isinstance(repository, SqliteMemoryRepository):
            raise TypeError("repository muss ein SqliteMemoryRepository sein.")
        if type(max_request_chars) is not int or max_request_chars <= 0:
            raise MemoryJsonError(
                "max_request_chars muss eine positive ganze Zahl sein."
            )
        self._repository = repository
        self._max_request_chars = max_request_chars

    def handle_json(self, request_json: str) -> str:
        request = _decode_request(request_json, self._max_request_chars)
        operation = _nonempty_string(request.get("operation"), "operation", 64)
        schema = _SCHEMAS.get(operation)
        if schema is None:
            raise MemoryJsonError(f"Unbekannte Memory-Operation: {operation}")
        _require_exact_fields(request, schema, operation)

        if operation == "list_notes":
            notes = self._repository.list_notes()
            response = {
                "notes": [_note_dict(note) for note in notes],
                "ok": True,
                "operation": operation,
            }
        elif operation == "add_note":
            text = _nonempty_string(request["text"], "text", 4_000)
            confirmation = _confirmation(request["confirmation"])
            note = self._repository.add_note(text, confirmation=confirmation)
            response = {
                "note": _note_dict(note),
                "ok": True,
                "operation": operation,
            }
        else:
            note_id = request["note_id"]
            if type(note_id) is not int or note_id <= 0:
                raise MemoryJsonError("note_id muss eine positive ganze Zahl sein.")
            confirmation = _confirmation(request["confirmation"])
            note = self._repository.delete_note(
                note_id,
                confirmation=confirmation,
            )
            response = {
                "deleted_note": _note_dict(note),
                "ok": True,
                "operation": operation,
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
        raise MemoryJsonError("JSON-Request muss eine nicht leere Zeichenkette sein.")
    if len(request_json) > max_chars:
        raise MemoryJsonError(
            f"JSON-Request ist groesser als das Limit von {max_chars} Zeichen."
        )
    try:
        payload = json.loads(
            request_json,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_nonstandard_constant,
        )
    except json.JSONDecodeError as exc:
        raise MemoryJsonError(f"Ungueltiger JSON-Request: {exc.msg}") from exc
    if type(payload) is not dict:
        raise MemoryJsonError("JSON-Request muss ein Objekt sein.")
    return payload


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MemoryJsonError(f"JSON-Request enthaelt doppeltes Feld: {key}")
        result[key] = value
    return result


def _reject_nonstandard_constant(value: str) -> None:
    raise MemoryJsonError(
        f"Nicht standardkonstanter JSON-Wert ist unzulaessig: {value}"
    )


def _require_exact_fields(
    request: dict[str, Any],
    expected: frozenset[str],
    operation: str,
) -> None:
    unknown = sorted(set(request) - expected)
    if unknown:
        raise MemoryJsonError(
            f"{operation} enthaelt unbekannte Felder: {', '.join(unknown)}"
        )
    missing = sorted(expected - set(request))
    if missing:
        raise MemoryJsonError(
            f"{operation} fehlen Pflichtfelder: {', '.join(missing)}"
        )


def _nonempty_string(value: Any, path: str, max_chars: int) -> str:
    if type(value) is not str or not value.strip():
        raise MemoryJsonError(f"{path} muss eine nicht leere Zeichenkette sein.")
    if "\x00" in value:
        raise MemoryJsonError(f"{path} darf keine Nullbytes enthalten.")
    if len(value) > max_chars:
        raise MemoryJsonError(f"{path} darf hoechstens {max_chars} Zeichen enthalten.")
    return value


def _confirmation(value: Any) -> MemoryConfirmation:
    if value != MemoryConfirmation.CONFIRMED.value or type(value) is not str:
        raise MemoryJsonError(
            "Persistente Memory-Aenderung erfordert confirmation=confirmed."
        )
    return MemoryConfirmation.CONFIRMED


def _note_dict(note: MemoryNote) -> dict[str, Any]:
    return {
        "created_at": note.created_at,
        "id": note.id,
        "text": note.text,
    }
