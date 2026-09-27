import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.memory import (
    MemoryConfirmation,
    MemoryError,
    SqliteMemoryRepository,
)


FIXED_TIME = datetime(2026, 9, 27, 12, 30, tzinfo=timezone.utc)


class SqliteMemoryRepositoryTests(unittest.TestCase):
    def repository(self, path):
        return SqliteMemoryRepository(path, clock=lambda: FIXED_TIME)

    def test_add_requires_typed_explicit_confirmation(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = self.repository(Path(temporary) / "memory.sqlite3")
            with self.assertRaisesRegex(MemoryError, "explizite Bestaetigung"):
                repository.add_note("Synthetische Notiz", confirmation=True)
            self.assertEqual(repository.list_notes(), ())

    def test_confirmed_note_is_normalized_and_persists(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "memory.sqlite3"
            repository = self.repository(path)
            added = repository.add_note(
                "  FIX   bedeutet synthetisch   fest. ",
                confirmation=MemoryConfirmation.CONFIRMED,
            )
            reopened = self.repository(path)
            notes = reopened.list_notes()

        self.assertEqual(added.id, 1)
        self.assertEqual(added.text, "FIX bedeutet synthetisch fest.")
        self.assertEqual(added.created_at, "2026-09-27T12:30:00Z")
        self.assertEqual(notes, (added,))

    def test_delete_requires_confirmation_and_returns_exact_note(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = self.repository(Path(temporary) / "memory.sqlite3")
            note = repository.add_note(
                "Zu loeschende Notiz",
                confirmation=MemoryConfirmation.CONFIRMED,
            )
            with self.assertRaisesRegex(MemoryError, "explizite Bestaetigung"):
                repository.delete_note(note.id, confirmation=None)
            deleted = repository.delete_note(
                note.id,
                confirmation=MemoryConfirmation.CONFIRMED,
            )
            self.assertEqual(deleted, note)
            self.assertEqual(repository.list_notes(), ())

    def test_sql_text_is_stored_as_data_not_executed(self):
        text = "'); DROP TABLE knowledge_notes; --"
        with tempfile.TemporaryDirectory() as temporary:
            repository = self.repository(Path(temporary) / "memory.sqlite3")
            repository.add_note(text, confirmation=MemoryConfirmation.CONFIRMED)
            notes = repository.list_notes()
        self.assertEqual(notes[0].text, text)

    def test_invalid_note_content_and_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = SqliteMemoryRepository(
                Path(temporary) / "memory.sqlite3",
                max_note_chars=10,
            )
            for text, pattern in ((" ", "nicht leer"), ("Null\x00Byte", "Nullbytes"), ("x" * 11, "hoechstens")):
                with self.subTest(text=text):
                    with self.assertRaisesRegex(MemoryError, pattern):
                        repository.add_note(text, confirmation=MemoryConfirmation.CONFIRMED)
            with self.assertRaisesRegex(MemoryError, "positive ganze Zahl"):
                repository.delete_note(True, confirmation=MemoryConfirmation.CONFIRMED)

    def test_schema_contains_no_document_or_chat_storage(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "memory.sqlite3"
            self.repository(path)
            with closing(sqlite3.connect(path)) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                version = connection.execute("PRAGMA user_version").fetchone()[0]
        self.assertIn("knowledge_notes", tables)
        self.assertNotIn("document_chunks", tables)
        self.assertNotIn("chat_history", tables)
        self.assertEqual(version, 1)


if __name__ == "__main__":
    unittest.main()
