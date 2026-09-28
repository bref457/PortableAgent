import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

from openpyxl import Workbook


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.agent import (
    PendingTableClarification,
    TableAgent,
    TableQuestionError,
    TableWorkflow,
    answer_table_question,
)
from portable_agent.domain import EntityClarificationRequest
from portable_agent.semantics import load_default_semantic_catalog
from portable_agent.sources import InMemoryTableSource, open_table_source


class RecordingGenerator:
    def __init__(self, payload=None):
        self.payload = payload or {}
        self.calls = []

    def generate_plan(self, question, columns, semantic_definitions):
        self.calls.append((question, columns, dict(semantic_definitions)))
        return self.payload


class TemporalOccurrenceTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_default_semantic_catalog()

    def test_natural_first_occurrence_variants_filter_the_named_action_first(self):
        questions = (
            "Wann war Aktion ALPHA das erste Mal?",
            "Wann sind wir ALPHA erstmals gefahren?",
            "Wann fand ALPHA zum ersten Mal statt?",
            "An welchem Datum wurde ALPHA erstmals durchgeführt?",
        )
        for question in questions:
            with self.subTest(question=question):
                source = InMemoryTableSource([
                    {"Datum": "2023-01-01", "Aktion": "BETA"},
                    {"Datum": "2025-08-10", "Aktion": "ALPHA"},
                    {"Datum": "2024-04-05", "Aktion": "ALPHA"},
                ])
                generator = RecordingGenerator()

                result = answer_table_question(
                    source,
                    question,
                    generator,
                    semantic_catalog=self.catalog,
                )

                self.assertEqual(result.values, {"Erster Einsatz": "2024-04-05"})
                self.assertEqual([item.row for item in result.citations], [4])
                self.assertEqual(result.metadata["matched_rows"], 2)
                self.assertEqual(generator.calls, [])

    def test_last_occurrence_filters_the_named_action_first(self):
        source = InMemoryTableSource([
            {"Datum": "2027-12-31", "Aktion": "BETA"},
            {"Datum": "2026-03-02", "Aktion": "ALPHA"},
            {"Datum": "2026-09-18", "Aktion": "ALPHA"},
        ])
        generator = RecordingGenerator()

        result = answer_table_question(
            source,
            "Wann wurde ALPHA zuletzt durchgeführt?",
            generator,
            semantic_catalog=self.catalog,
        )

        self.assertEqual(result.values, {"Letzter Einsatz": "2026-09-18"})
        self.assertEqual([item.row for item in result.citations], [4])
        self.assertEqual(generator.calls, [])

    def test_named_occurrence_honours_the_requested_year(self):
        source = InMemoryTableSource([
            {"Datum": "2025-01-03", "Aktion": "ALPHA"},
            {"Datum": "2026-07-08", "Aktion": "ALPHA"},
            {"Datum": "2026-02-04", "Aktion": "ALPHA"},
            {"Datum": "2026-01-01", "Aktion": "BETA"},
        ])

        result = answer_table_question(
            source,
            "Wann war ALPHA 2026 erstmals?",
            RecordingGenerator(),
            semantic_catalog=self.catalog,
        )

        self.assertEqual(result.values, {"Erster Einsatz": "2026-02-04"})
        self.assertEqual([item.row for item in result.citations], [4])
        self.assertEqual(result.metadata["matched_rows"], 2)

    def test_missing_dates_are_ignored_but_other_actions_never_fill_the_gap(self):
        source = InMemoryTableSource([
            {"Datum": "2020-01-01", "Aktion": "BETA"},
            {"Datum": None, "Aktion": "ALPHA"},
            {"Datum": "2024-06-11", "Aktion": "ALPHA"},
        ])

        result = answer_table_question(
            source,
            "Wann fand ALPHA erstmals statt?",
            RecordingGenerator(),
            semantic_catalog=self.catalog,
        )

        self.assertEqual(result.values, {"Erster Einsatz": "2024-06-11"})
        self.assertEqual([item.row for item in result.citations], [4])

    def test_only_missing_dates_return_no_value_or_foreign_evidence(self):
        source = InMemoryTableSource([
            {"Datum": "2020-01-01", "Aktion": "BETA"},
            {"Datum": None, "Aktion": "ALPHA"},
        ])

        result = answer_table_question(
            source,
            "Wann fand ALPHA erstmals statt?",
            RecordingGenerator(),
            semantic_catalog=self.catalog,
        )

        self.assertEqual(result.values, {"Erster Einsatz": None})
        self.assertEqual(result.citations, ())
        self.assertEqual(result.metadata["matched_rows"], 1)

    def test_equal_first_dates_keep_every_decisive_evidence_row(self):
        source = InMemoryTableSource([
            {"Datum": "2024-01-03", "Aktion": "ALPHA"},
            {"Datum": "2024-01-03", "Aktion": "ALPHA"},
            {"Datum": "2023-01-01", "Aktion": "BETA"},
        ])

        result = answer_table_question(
            source,
            "Wann war ALPHA erstmals?",
            RecordingGenerator(),
            semantic_catalog=self.catalog,
        )

        self.assertEqual(result.values, {"Erster Einsatz": "2024-01-03"})
        self.assertEqual([item.row for item in result.citations], [2, 3])

    def test_similar_action_names_return_a_typed_clarification(self):
        source = InMemoryTableSource([
            {"Datum": "2024-01-02", "Aktion": "ALPHA NORD"},
            {"Datum": "2024-01-03", "Aktion": "ALPHA SUED"},
        ])
        generator = RecordingGenerator()

        result = answer_table_question(
            source,
            "Wann war ALPHA erstmals?",
            generator,
            semantic_catalog=self.catalog,
        )

        self.assertIsInstance(result, EntityClarificationRequest)
        self.assertEqual([item.label for item in result.options], [
            "ALPHA NORD",
            "ALPHA SUED",
        ])
        self.assertEqual(generator.calls, [])

    def test_typo_is_suggested_but_never_silently_accepted(self):
        source = InMemoryTableSource([
            {"Datum": "2024-01-02", "Aktion": "ALPHA"},
        ])

        result = answer_table_question(
            source,
            "Wann war ALPGA erstmals?",
            RecordingGenerator(),
            semantic_catalog=self.catalog,
        )

        self.assertIsInstance(result, EntityClarificationRequest)
        self.assertEqual(result.question, "Meintest du diese Aktion?")
        self.assertEqual([item.label for item in result.options], ["ALPHA"])

    def test_unknown_action_stops_before_the_model(self):
        source = InMemoryTableSource([
            {"Datum": "2024-01-02", "Aktion": "ALPHA"},
        ])
        generator = RecordingGenerator()

        with self.assertRaisesRegex(TableQuestionError, "nicht gefunden"):
            answer_table_question(
                source,
                "Wann war OMEGA erstmals?",
                generator,
                semantic_catalog=self.catalog,
            )

        self.assertEqual(generator.calls, [])

    def test_polite_global_question_is_not_mistaken_for_an_action_name(self):
        source = InMemoryTableSource([
            {"Datum": "2025-05-02", "Aktion": "ALPHA"},
            {"Datum": "2024-03-01", "Aktion": "BETA"},
        ])
        generator = RecordingGenerator()

        result = answer_table_question(
            source,
            "Kannst du mir bitte sagen, wann der früheste Einsatz war?",
            generator,
            semantic_catalog=self.catalog,
        )

        self.assertEqual(result.values, {"groups": [{
            "Aktion": "BETA",
            "Erster Einsatz": "2024-03-01",
        }]})
        self.assertEqual(generator.calls, [])

    def test_entity_clarification_is_resolved_locally_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "actions.csv"
            path.write_text(
                "Datum;Aktion\n"
                "2024-03-02;ALPHA NORD\n"
                "2024-02-01;ALPHA SUED\n",
                encoding="utf-8",
            )
            generator = RecordingGenerator()
            workflow = TableWorkflow(
                generator,
                catalog=self.catalog,
                id_factory=lambda: "entity-question",
            )

            pending = workflow.ask_file(path, "Wann war ALPHA erstmals?")
            self.assertIsInstance(pending, PendingTableClarification)
            self.assertIsInstance(pending.request, EntityClarificationRequest)

            result = workflow.resolve(pending.clarification_id, "entity-2")

        self.assertEqual(result.values, {"Erster Einsatz": "2024-02-01"})
        self.assertEqual([item.row for item in result.citations], [3])
        self.assertEqual(generator.calls, [])
        self.assertEqual(workflow.pending_clarification_count, 0)

    def test_selected_xlsx_sheet_is_the_only_source_for_named_occurrence(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "actions.xlsx"
            workbook = Workbook()
            overview = workbook.active
            overview.title = "Uebersicht"
            overview.append(["Datum", "Aktion"])
            overview.append([date(2020, 1, 1), "ALPHA"])
            data = workbook.create_sheet("Einsaetze")
            data.append(["Datum", "Aktion"])
            data.append([date(2026, 8, 4), "ALPHA"])
            data.append([date(2026, 5, 9), "ALPHA"])
            workbook.save(path)
            workbook.close()
            before = path.read_bytes()
            source = open_table_source(path, sheet_name="Einsaetze")
            agent = TableAgent(source, RecordingGenerator(), self.catalog)

            result = agent.ask("Wann war ALPHA 2026 erstmals?")
            after = path.read_bytes()

        self.assertEqual(result.values, {"Erster Einsatz": "2026-05-09"})
        self.assertEqual([item.section for item in result.citations], ["Einsaetze"])
        self.assertEqual([item.row for item in result.citations], [3])
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
