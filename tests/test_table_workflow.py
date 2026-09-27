import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.agent import (
    PendingTableClarification,
    TableWorkflow,
    TableWorkflowError,
)
from portable_agent.semantics import load_default_semantic_catalog
from portable_agent.sources import InMemoryTableSource, SourceRoutingError


class RecordingGenerator:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def generate_plan(self, question, columns, semantic_definitions):
        self.calls.append((question, columns, dict(semantic_definitions)))
        return self.payload


class TableWorkflowTests(unittest.TestCase):
    def test_csv_question_is_answered_without_changing_the_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.csv"
            path.write_text(
                "Fix;Miliz;InterneNotiz\n2;1;NICHT_AN_MODELL\n3;4;AUCH_NICHT\n",
                encoding="utf-8",
            )
            before = path.read_bytes()
            generator = RecordingGenerator({
                "calculations": [
                    {"label": "FIX", "aggregation": "sum", "column": "Fix"}
                ]
            })
            workflow = TableWorkflow(
                generator,
                catalog=load_default_semantic_catalog(),
            )

            result = workflow.ask_file(path, "Wie viele FIX gibt es insgesamt?")

            self.assertEqual(result.values, {"FIX": 5})
            self.assertEqual([citation.row for citation in result.citations], [2, 3])
            self.assertEqual(path.read_bytes(), before)

    def test_planner_receives_schema_and_semantics_but_no_cell_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.csv"
            path.write_text(
                "Fix;InterneNotiz\n7;SENSITIV_ALPHA_914\n8;SENSITIV_BETA_271\n",
                encoding="utf-8",
            )
            generator = RecordingGenerator({
                "calculations": [{"label": "Zeilen", "aggregation": "count"}]
            })
            workflow = TableWorkflow(generator)

            result = workflow.ask_file(path, "Wie viele Zeilen gibt es?")

            self.assertEqual(result.values, {"Zeilen": 2})
            self.assertEqual(generator.calls[0][1], ("Fix", "InterneNotiz"))
            self.assertEqual(set(generator.calls[0][2]), {"Fix"})
            self.assertNotIn("SENSITIV_ALPHA_914", repr(generator.calls))
            self.assertNotIn("SENSITIV_BETA_271", repr(generator.calls))

    def test_sheet_selection_is_forwarded_to_the_existing_router(self):
        generator = RecordingGenerator({
            "calculations": [{"label": "Zeilen", "aggregation": "count"}]
        })
        source = InMemoryTableSource([{"Fix": 1}, {"Fix": 2}])
        workflow = TableWorkflow(generator)

        with patch(
            "portable_agent.agent.table_workflow.open_table_source",
            return_value=source,
        ) as router:
            result = workflow.ask_file(
                "synthetic.xlsx",
                "Wie viele Zeilen?",
                sheet_name="Daten",
            )

        router.assert_called_once_with("synthetic.xlsx", sheet_name="Daten")
        self.assertEqual(result.values, {"Zeilen": 2})

    def test_csv_sheet_selection_fails_before_the_planner_is_called(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.csv"
            path.write_text("Fix\n1\n", encoding="utf-8")
            generator = RecordingGenerator({
                "calculations": [{"label": "Zeilen", "aggregation": "count"}]
            })
            workflow = TableWorkflow(generator)

            with self.assertRaisesRegex(SourceRoutingError, "keine Tabellenblaetter"):
                workflow.ask_file(path, "Wie viele Zeilen?", sheet_name="Daten")

            self.assertEqual(generator.calls, [])

    def test_clarification_is_resolved_once_without_another_planner_call(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.csv"
            path.write_text("Einsatzdauer\n2\n4\n", encoding="utf-8")
            generator = RecordingGenerator({
                "calculations": [
                    {
                        "label": "Dauer",
                        "aggregation": "average",
                        "column": "Einsatzdauer",
                    }
                ]
            })
            workflow = TableWorkflow(
                generator,
                id_factory=lambda: "clarification-1",
            )

            pending = workflow.ask_file(path, "Wie lange war der Einsatz?")

            self.assertIsInstance(pending, PendingTableClarification)
            self.assertEqual(pending.clarification_id, "clarification-1")
            self.assertEqual(workflow.pending_clarification_count, 1)
            self.assertEqual(len(generator.calls), 1)

            result = workflow.resolve(pending.clarification_id, "sum")

            self.assertEqual(result.values, {"Dauer": 6})
            self.assertEqual(workflow.pending_clarification_count, 0)
            self.assertEqual(len(generator.calls), 1)
            with self.assertRaisesRegex(TableWorkflowError, "bereits aufgeloest"):
                workflow.resolve(pending.clarification_id, "sum")

    def test_invalid_option_keeps_pending_clarification_available(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.csv"
            path.write_text("Einsatzdauer\n2\n4\n", encoding="utf-8")
            generator = RecordingGenerator({
                "calculations": [
                    {
                        "label": "Dauer",
                        "aggregation": "average",
                        "column": "Einsatzdauer",
                    }
                ]
            })
            workflow = TableWorkflow(
                generator,
                id_factory=lambda: "clarification-2",
            )
            pending = workflow.ask_file(path, "Wie lange war der Einsatz?")

            with self.assertRaisesRegex(TableWorkflowError, "ungueltig"):
                workflow.resolve(pending.clarification_id, "median")

            self.assertEqual(workflow.pending_clarification_count, 1)
            self.assertEqual(workflow.release_all(), 1)
            self.assertEqual(workflow.pending_clarification_count, 0)


if __name__ == "__main__":
    unittest.main()
