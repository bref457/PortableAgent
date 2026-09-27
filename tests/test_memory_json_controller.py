import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.memory import SqliteMemoryRepository
from portable_agent.web import MemoryJsonController, MemoryJsonError


FIXED_TIME = datetime(2026, 9, 27, 12, 30, tzinfo=timezone.utc)


class MemoryJsonControllerTests(unittest.TestCase):
    def controller(self, directory):
        repository = SqliteMemoryRepository(
            Path(directory) / "memory.sqlite3",
            clock=lambda: FIXED_TIME,
        )
        return MemoryJsonController(repository)

    def request(self, controller, payload):
        return json.loads(controller.handle_json(json.dumps(payload)))

    def test_confirmed_add_list_and_delete_round_trip(self):
        with tempfile.TemporaryDirectory() as temporary:
            controller = self.controller(temporary)
            added = self.request(controller, {
                "operation": "add_note",
                "text": "  Synthetische   Praeferenz. ",
                "confirmation": "confirmed",
            })
            listed = self.request(controller, {"operation": "list_notes"})
            deleted = self.request(controller, {
                "operation": "delete_note",
                "note_id": added["note"]["id"],
                "confirmation": "confirmed",
            })
            empty = self.request(controller, {"operation": "list_notes"})

        self.assertEqual(added["note"], {
            "created_at": "2026-09-27T12:30:00Z",
            "id": 1,
            "text": "Synthetische Praeferenz.",
        })
        self.assertEqual(listed["notes"], [added["note"]])
        self.assertEqual(deleted["deleted_note"], added["note"])
        self.assertEqual(empty["notes"], [])

    def test_mutations_require_exact_typed_confirmation(self):
        with tempfile.TemporaryDirectory() as temporary:
            controller = self.controller(temporary)
            for confirmation in (True, "yes", "CONFIRMED", None):
                with self.subTest(confirmation=confirmation):
                    with self.assertRaisesRegex(MemoryJsonError, "confirmation=confirmed"):
                        self.request(controller, {
                            "operation": "add_note",
                            "text": "Nicht speichern",
                            "confirmation": confirmation,
                        })
            listed = self.request(controller, {"operation": "list_notes"})

        self.assertEqual(listed["notes"], [])

    def test_unknown_missing_wrong_typed_and_extra_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            controller = self.controller(temporary)
            cases = (
                ({"operation": "unknown"}, "Unbekannte Memory-Operation"),
                ({"operation": "add_note", "text": "x"}, "fehlen Pflichtfelder"),
                (
                    {
                        "operation": "add_note",
                        "text": "x",
                        "confirmation": "confirmed",
                        "document": "nicht erlaubt",
                    },
                    "unbekannte Felder: document",
                ),
                (
                    {
                        "operation": "delete_note",
                        "note_id": True,
                        "confirmation": "confirmed",
                    },
                    "positive ganze Zahl",
                ),
            )
            for payload, pattern in cases:
                with self.subTest(payload=payload):
                    with self.assertRaisesRegex(MemoryJsonError, pattern):
                        self.request(controller, payload)

    def test_malformed_duplicate_nonstandard_and_oversized_json_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            controller = self.controller(temporary)
            cases = (
                ('{"operation":', "Ungueltiger JSON-Request"),
                (
                    '{"operation":"list_notes","operation":"list_notes"}',
                    "doppeltes Feld",
                ),
                ('{"operation":"list_notes","value":NaN}', "Nicht standardkonstanter"),
                ("x" * 16_385, "groesser als das Limit"),
            )
            for request_json, pattern in cases:
                with self.subTest(pattern=pattern):
                    with self.assertRaisesRegex(MemoryJsonError, pattern):
                        controller.handle_json(request_json)


if __name__ == "__main__":
    unittest.main()
