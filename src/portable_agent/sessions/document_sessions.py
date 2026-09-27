"""In-memory lifecycle management for temporary document sources."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from portable_agent.sources import DocumentSource


MAX_ID_ATTEMPTS = 10


class DocumentSessionError(ValueError):
    """A temporary document-session request is invalid."""


@dataclass(frozen=True, slots=True)
class DocumentSession:
    """A process-local reference to one loaded document source."""

    session_id: str
    source: DocumentSource
    created_at: str


class DocumentSessionManager:
    """Keeps document sources in memory until they are explicitly released."""

    def __init__(
        self,
        *,
        id_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._id_factory = id_factory or (lambda: uuid4().hex)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._sessions: dict[str, DocumentSession] = {}
        self._lock = RLock()

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def create(self, source: DocumentSource) -> DocumentSession:
        _validate_source(source)
        created_at = _utc_timestamp(self._clock())
        with self._lock:
            for _ in range(MAX_ID_ATTEMPTS):
                session_id = _validate_generated_id(self._id_factory())
                if session_id not in self._sessions:
                    session = DocumentSession(session_id, source, created_at)
                    self._sessions[session_id] = session
                    return session
        raise DocumentSessionError(
            "Es konnte keine eindeutige Dokument-Sitzungs-ID erzeugt werden."
        )

    def get(self, session_id: str) -> DocumentSession:
        clean_id = _validate_requested_id(session_id)
        with self._lock:
            try:
                return self._sessions[clean_id]
            except KeyError as exc:
                raise DocumentSessionError(
                    "Dokument-Sitzung wurde nicht gefunden oder bereits freigegeben."
                ) from exc

    def list_sessions(self) -> tuple[DocumentSession, ...]:
        with self._lock:
            return tuple(self._sessions.values())

    def release(self, session_id: str) -> DocumentSession:
        clean_id = _validate_requested_id(session_id)
        with self._lock:
            try:
                return self._sessions.pop(clean_id)
            except KeyError as exc:
                raise DocumentSessionError(
                    "Dokument-Sitzung wurde nicht gefunden oder bereits freigegeben."
                ) from exc

    def release_all(self) -> int:
        with self._lock:
            released_count = len(self._sessions)
            self._sessions.clear()
            return released_count


def _validate_source(source: DocumentSource) -> None:
    if source is None:
        raise DocumentSessionError("Dokumentquelle darf nicht fehlen.")
    try:
        source_id = source.source_id
        display_name = source.display_name
        iter_chunks = source.iter_chunks
    except (AttributeError, TypeError) as exc:
        raise DocumentSessionError("Objekt erfuellt die DocumentSource-Schnittstelle nicht.") from exc
    if not isinstance(source_id, str) or not source_id.strip():
        raise DocumentSessionError("Dokumentquelle hat keine gueltige source_id.")
    if not isinstance(display_name, str) or not display_name.strip():
        raise DocumentSessionError("Dokumentquelle hat keinen gueltigen display_name.")
    if not callable(iter_chunks):
        raise DocumentSessionError("Dokumentquelle besitzt keinen iter_chunks-Aufruf.")


def _validate_generated_id(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DocumentSessionError("Sitzungs-ID-Generator lieferte keine gueltige ID.")
    return value.strip()


def _validate_requested_id(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DocumentSessionError("session_id muss eine nicht leere Zeichenkette sein.")
    return value.strip()


def _utc_timestamp(value: datetime) -> str:
    if not isinstance(value, datetime):
        raise DocumentSessionError("Sitzungs-Uhr lieferte keinen datetime-Wert.")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
