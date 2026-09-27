"""Minimal SQLite repository for explicitly confirmed knowledge notes."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


DEFAULT_MAX_NOTE_CHARS = 4_000
DEFAULT_MEMORY_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "memory.sqlite3"
)


class MemoryError(ValueError):
    """A persistent-memory request violates the explicit storage policy."""


class MemoryConfirmation(Enum):
    CONFIRMED = "confirmed"


@dataclass(frozen=True, slots=True)
class MemoryNote:
    id: int
    text: str
    created_at: str


class SqliteMemoryRepository:
    """Stores only confirmed notes and their minimal local metadata."""

    def __init__(
        self,
        path: str | Path,
        *,
        max_note_chars: int = DEFAULT_MAX_NOTE_CHARS,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(path, (str, Path)):
            raise MemoryError("Memory-Pfad muss eine Zeichenkette oder Path sein.")
        if type(max_note_chars) is not int or max_note_chars <= 0:
            raise MemoryError("max_note_chars muss eine positive ganze Zahl sein.")
        self._path = Path(path)
        if self._path.exists() and self._path.is_dir():
            raise MemoryError("Memory-Pfad darf kein Verzeichnis sein.")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._max_note_chars = max_note_chars
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._initialize()

    @classmethod
    def with_default_path(cls) -> "SqliteMemoryRepository":
        """Use the portable project-relative data path."""
        return cls(DEFAULT_MEMORY_PATH)

    @property
    def path(self) -> Path:
        return self._path

    def add_note(
        self,
        text: str,
        *,
        confirmation: MemoryConfirmation,
    ) -> MemoryNote:
        _require_confirmation(confirmation)
        clean = _validate_note_text(text, self._max_note_chars)
        created_at = _utc_timestamp(self._clock())
        with self._session() as connection:
            cursor = connection.execute(
                "INSERT INTO knowledge_notes(text, created_at) VALUES (?, ?)",
                (clean, created_at),
            )
            note_id = int(cursor.lastrowid)
        return MemoryNote(note_id, clean, created_at)

    def list_notes(self) -> tuple[MemoryNote, ...]:
        with self._session() as connection:
            rows = connection.execute(
                "SELECT id, text, created_at FROM knowledge_notes ORDER BY id"
            ).fetchall()
        return tuple(MemoryNote(int(row[0]), row[1], row[2]) for row in rows)

    def delete_note(
        self,
        note_id: int,
        *,
        confirmation: MemoryConfirmation,
    ) -> MemoryNote:
        _require_confirmation(confirmation)
        if type(note_id) is not int or note_id <= 0:
            raise MemoryError("note_id muss eine positive ganze Zahl sein.")
        with self._session() as connection:
            row = connection.execute(
                "SELECT id, text, created_at FROM knowledge_notes WHERE id = ?",
                (note_id,),
            ).fetchone()
            if row is None:
                raise MemoryError("Wissensnotiz wurde nicht gefunden.")
            connection.execute("DELETE FROM knowledge_notes WHERE id = ?", (note_id,))
        return MemoryNote(int(row[0]), row[1], row[2])

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=5.0)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _session(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        try:
            with self._session() as connection:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version not in {0, 1}:
                    raise MemoryError(
                        f"Nicht unterstuetzte Memory-Schemaversion: {version}"
                    )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS knowledge_notes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        text TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                if version == 0:
                    connection.execute("PRAGMA user_version = 1")
        except sqlite3.Error as exc:
            raise MemoryError(f"SQLite-Memory konnte nicht initialisiert werden: {exc}") from exc


def _require_confirmation(confirmation: MemoryConfirmation) -> None:
    if confirmation is not MemoryConfirmation.CONFIRMED:
        raise MemoryError("Persistente Memory-Aenderung erfordert explizite Bestaetigung.")


def _validate_note_text(text: str, max_chars: int) -> str:
    if not isinstance(text, str):
        raise MemoryError("Wissensnotiz muss Text sein.")
    clean = " ".join(text.split())
    if not clean:
        raise MemoryError("Wissensnotiz darf nicht leer sein.")
    if "\x00" in text:
        raise MemoryError("Wissensnotiz darf keine Nullbytes enthalten.")
    if len(clean) > max_chars:
        raise MemoryError(
            f"Wissensnotiz darf hoechstens {max_chars} Zeichen enthalten."
        )
    return clean


def _utc_timestamp(value: datetime) -> str:
    if not isinstance(value, datetime):
        raise MemoryError("Memory-Uhr lieferte keinen datetime-Wert.")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
