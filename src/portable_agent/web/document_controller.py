"""Strict transport-neutral JSON boundary for the local document workflow."""

from __future__ import annotations

import json
from typing import Any

from portable_agent.agent import DocumentWorkflow
from portable_agent.domain import DocumentAnswer, SourceRef
from portable_agent.sessions import DocumentSession


DEFAULT_MAX_REQUEST_CHARS = 16_384
_SCHEMAS = {
    "list_sessions": frozenset({"operation"}),
    "open_document": frozenset({"operation", "path"}),
    "ask": frozenset({"operation", "session_id", "question"}),
    "release": frozenset({"operation", "session_id"}),
    "release_all": frozenset({"operation"}),
}


class DocumentJsonError(ValueError):
    """An untrusted JSON request does not match the accepted API shape."""


class DocumentJsonController:
    """Maps strict JSON requests to an in-process DocumentWorkflow."""

    def __init__(
        self,
        workflow: DocumentWorkflow,
        *,
        max_request_chars: int = DEFAULT_MAX_REQUEST_CHARS,
    ) -> None:
        if not isinstance(workflow, DocumentWorkflow):
            raise TypeError("workflow muss ein DocumentWorkflow sein.")
        if type(max_request_chars) is not int or max_request_chars <= 0:
            raise DocumentJsonError(
                "max_request_chars muss eine positive ganze Zahl sein."
            )
        self._workflow = workflow
        self._max_request_chars = max_request_chars

    def handle_json(self, request_json: str) -> str:
        request = _decode_request(request_json, self._max_request_chars)
        operation = _nonempty_string(request.get("operation"), "operation", max_chars=64)
        schema = _SCHEMAS.get(operation)
        if schema is None:
            raise DocumentJsonError(f"Unbekannte Dokumentoperation: {operation}")
        _require_exact_fields(request, schema, operation)

        if operation == "list_sessions":
            response = {
                "active_session_count": self._workflow.active_session_count,
                "ok": True,
                "operation": operation,
                "sessions": [
                    _session_dict(session)
                    for session in self._workflow.list_sessions()
                ],
            }
        elif operation == "open_document":
            path = _nonempty_string(request["path"], "path", max_chars=4_096)
            session = self._workflow.open_document(path)
            response = {
                "active_session_count": self._workflow.active_session_count,
                "ok": True,
                "operation": operation,
                "session": _session_dict(session),
            }
        elif operation == "ask":
            session_id = _nonempty_string(
                request["session_id"], "session_id", max_chars=256
            )
            question = _nonempty_string(
                request["question"], "question", max_chars=10_000
            )
            answer = self._workflow.ask(session_id, question)
            response = {
                "answer": _answer_dict(answer),
                "ok": True,
                "operation": operation,
            }
        elif operation == "release":
            session_id = _nonempty_string(
                request["session_id"], "session_id", max_chars=256
            )
            released = self._workflow.release(session_id)
            response = {
                "active_session_count": self._workflow.active_session_count,
                "ok": True,
                "operation": operation,
                "released_session": _session_dict(released),
            }
        else:
            released_count = self._workflow.release_all()
            response = {
                "active_session_count": self._workflow.active_session_count,
                "ok": True,
                "operation": operation,
                "released_count": released_count,
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
        raise DocumentJsonError("JSON-Request muss eine nicht leere Zeichenkette sein.")
    if len(request_json) > max_chars:
        raise DocumentJsonError(
            f"JSON-Request ist groesser als das Limit von {max_chars} Zeichen."
        )
    try:
        payload = json.loads(
            request_json,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_nonstandard_constant,
        )
    except json.JSONDecodeError as exc:
        raise DocumentJsonError(f"Ungueltiger JSON-Request: {exc.msg}") from exc
    if type(payload) is not dict:
        raise DocumentJsonError("JSON-Request muss ein Objekt sein.")
    return payload


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DocumentJsonError(f"JSON-Request enthaelt doppeltes Feld: {key}")
        result[key] = value
    return result


def _reject_nonstandard_constant(value: str) -> None:
    raise DocumentJsonError(f"Nicht standardkonstanter JSON-Wert ist unzulaessig: {value}")


def _require_exact_fields(
    request: dict[str, Any],
    expected: frozenset[str],
    operation: str,
) -> None:
    unknown = sorted(set(request) - expected)
    if unknown:
        raise DocumentJsonError(
            f"{operation} enthaelt unbekannte Felder: {', '.join(unknown)}"
        )
    missing = sorted(expected - set(request))
    if missing:
        raise DocumentJsonError(
            f"{operation} fehlen Pflichtfelder: {', '.join(missing)}"
        )


def _nonempty_string(value: Any, path: str, *, max_chars: int) -> str:
    if type(value) is not str or not value.strip():
        raise DocumentJsonError(f"{path} muss eine nicht leere Zeichenkette sein.")
    if "\x00" in value:
        raise DocumentJsonError(f"{path} darf keine Nullbytes enthalten.")
    if len(value) > max_chars:
        raise DocumentJsonError(
            f"{path} darf hoechstens {max_chars} Zeichen enthalten."
        )
    return value.strip()


def _session_dict(session: DocumentSession) -> dict[str, Any]:
    return {
        "created_at": session.created_at,
        "display_name": session.source.display_name,
        "session_id": session.session_id,
        "source_id": session.source.source_id,
    }


def _answer_dict(answer: DocumentAnswer) -> dict[str, Any]:
    return {
        "citations": [_source_ref_dict(citation) for citation in answer.citations],
        "generated": answer.generated,
        "matched_chunks": answer.matched_chunks,
        "text": answer.text,
    }


def _source_ref_dict(source_ref: SourceRef) -> dict[str, Any]:
    return {
        "display_name": source_ref.display_name,
        "excerpt": source_ref.excerpt,
        "page": source_ref.page,
        "paragraph": source_ref.paragraph,
        "row": source_ref.row,
        "section": source_ref.section,
        "source_id": source_ref.source_id,
    }
