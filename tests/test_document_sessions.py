import gc
import sys
import unittest
import weakref
from datetime import datetime, timezone
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.sessions import DocumentSessionError, DocumentSessionManager
from portable_agent.sources import DocumentSegment, InMemoryDocumentSource


def synthetic_source(source_id="doc-1"):
    return InMemoryDocumentSource(
        [DocumentSegment("Rein synthetischer Dokumenttext.", paragraph="p1")],
        source_id=source_id,
        display_name=f"{source_id}.txt",
    )


class DocumentSessionManagerTests(unittest.TestCase):
    def test_create_get_and_list_are_process_local(self):
        manager = DocumentSessionManager(
            id_factory=lambda: "session-1",
            clock=lambda: datetime(2026, 9, 27, 10, 30, tzinfo=timezone.utc),
        )
        source = synthetic_source()

        created = manager.create(source)

        self.assertEqual(created.session_id, "session-1")
        self.assertEqual(created.created_at, "2026-09-27T10:30:00Z")
        self.assertIs(created.source, source)
        self.assertIs(manager.get("session-1"), created)
        self.assertEqual(manager.list_sessions(), (created,))
        self.assertEqual(manager.count, 1)

    def test_create_retries_id_collision(self):
        ids = iter(("same-id", "same-id", "second-id"))
        manager = DocumentSessionManager(id_factory=lambda: next(ids))

        first = manager.create(synthetic_source("first"))
        second = manager.create(synthetic_source("second"))

        self.assertEqual(first.session_id, "same-id")
        self.assertEqual(second.session_id, "second-id")
        self.assertEqual(manager.count, 2)

    def test_release_removes_only_requested_session(self):
        ids = iter(("one", "two"))
        manager = DocumentSessionManager(id_factory=lambda: next(ids))
        first = manager.create(synthetic_source("first"))
        second = manager.create(synthetic_source("second"))

        released = manager.release(first.session_id)

        self.assertIs(released, first)
        self.assertIs(manager.get(second.session_id), second)
        self.assertEqual(manager.count, 1)
        with self.assertRaisesRegex(DocumentSessionError, "bereits freigegeben"):
            manager.get(first.session_id)

    def test_release_all_clears_every_session(self):
        ids = iter(("one", "two"))
        manager = DocumentSessionManager(id_factory=lambda: next(ids))
        manager.create(synthetic_source("first"))
        manager.create(synthetic_source("second"))

        self.assertEqual(manager.release_all(), 2)
        self.assertEqual(manager.release_all(), 0)
        self.assertEqual(manager.list_sessions(), ())

    def test_invalid_source_and_session_ids_are_rejected(self):
        manager = DocumentSessionManager(id_factory=lambda: "session-1")
        with self.assertRaisesRegex(DocumentSessionError, "Dokumentquelle"):
            manager.create(None)
        with self.assertRaisesRegex(DocumentSessionError, "session_id"):
            manager.get("   ")
        with self.assertRaisesRegex(DocumentSessionError, "nicht gefunden"):
            manager.release("unknown")

    def test_release_drops_manager_reference_to_source(self):
        manager = DocumentSessionManager(id_factory=lambda: "session-1")
        source = synthetic_source()
        source_ref = weakref.ref(source)
        session = manager.create(source)
        del source

        gc.collect()
        self.assertIsNotNone(source_ref())

        released = manager.release(session.session_id)
        del session
        del released
        gc.collect()
        self.assertIsNone(source_ref())


if __name__ == "__main__":
    unittest.main()
