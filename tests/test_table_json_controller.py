import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.agent import TableWorkflow
from portable_agent.domain import QueryResult
from portable_agent.web import TableJsonController, TableJsonError


class RecordingGenerator:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def generate_plan(self, question, columns, semantic_definitions):
        self.calls.append((question, columns, dict(semantic_definitions)))
        return self.payload


class TableJsonControllerTests(unittest.TestCase):
    def test_csv_result_has_fixed_values_metadata_and_citations(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.csv"
            path.write_text(
                "Fix;InterneNotiz\n2;VERTRAULICH_771\n3;VERTRAULICH_883\n",
                encoding="utf-8",
            )
            before = path.read_bytes()
            generator = RecordingGenerator({
                "calculations": [
                    {"label": "FIX", "aggregation": "sum", "column": "Fix"}
                ]
            })
            controller = TableJsonController(TableWorkflow(generator))

            response = self.request(controller, {
                "operation": "ask_table",
                "path": str(path),
                "question": "Wie viele FIX gibt es insgesamt?",
            })

            self.assertEqual(response["result"]["type"], "query_result")
            self.assertEqual(response["result"]["values"], {"FIX": 5})
            self.assertEqual(response["result"]["metadata"]["matched_rows"], 2)
            self.assertEqual(
                [item["row"] for item in response["result"]["citations"]],
                [2, 3],
            )
            self.assertEqual(path.read_bytes(), before)
            self.assertNotIn("VERTRAULICH_771", repr(generator.calls))
            self.assertNotIn("VERTRAULICH_883", repr(generator.calls))

    def test_optional_sheet_name_is_forwarded_exactly_once(self):
        generator = RecordingGenerator({
            "calculations": [{"label": "Zeilen", "aggregation": "count"}]
        })
        workflow = TableWorkflow(generator)
        controller = TableJsonController(workflow)
        expected = QueryResult(values={"Zeilen": 2})

        with patch.object(workflow, "ask_file", return_value=expected) as ask_file:
            response = self.request(controller, {
                "operation": "ask_table",
                "path": "synthetic.xlsx",
                "question": "Wie viele Zeilen?",
                "sheet_name": "Daten",
            })

        ask_file.assert_called_once_with(
            "synthetic.xlsx",
            "Wie viele Zeilen?",
            sheet_name="Daten",
        )
        self.assertEqual(response["result"]["values"], {"Zeilen": 2})

    def test_clarification_has_options_but_no_internal_plan(self):
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
                id_factory=lambda: "json-clarification",
            )
            controller = TableJsonController(workflow)

            response = self.request(controller, {
                "operation": "ask_table",
                "path": str(path),
                "question": "Wie lange war der Einsatz?",
            })

            resolved = self.request(controller, {
                "operation": "resolve_table",
                "clarification_id": "json-clarification",
                "option_id": "max",
            })

        result = response["result"]
        self.assertEqual(result["type"], "clarification")
        self.assertEqual(result["column"], "Einsatzdauer")
        self.assertEqual(result["clarification_id"], "json-clarification")
        self.assertEqual(result["matched_rows"], 2)
        self.assertEqual(
            [option["id"] for option in result["options"]],
            ["sum", "average", "min", "max"],
        )
        self.assertNotIn("original_plan", result)
        self.assertEqual(resolved["result"]["type"], "query_result")
        self.assertEqual(resolved["result"]["values"], {"Dauer": 4})
        self.assertEqual(len(generator.calls), 1)

    def test_invalid_fields_fail_before_the_workflow_is_called(self):
        generator = RecordingGenerator({
            "calculations": [{"label": "Zeilen", "aggregation": "count"}]
        })
        workflow = TableWorkflow(generator)
        controller = TableJsonController(workflow)
        cases = (
            ({"operation": "execute_code"}, "Unbekannte Tabellenoperation"),
            (
                {
                    "operation": "ask_table",
                    "path": "x.csv",
                    "question": "q",
                    "code": "x",
                },
                "unbekannte Felder",
            ),
            ({"operation": "ask_table", "path": "x.csv"}, "fehlen Pflichtfelder"),
            (
                {"operation": "ask_table", "path": 123, "question": "q"},
                "path muss",
            ),
            (
                {
                    "operation": "ask_table",
                    "path": "x.xlsx",
                    "question": "q",
                    "sheet_name": None,
                },
                "sheet_name muss",
            ),
            (
                {
                    "operation": "ask_table",
                    "path": "x.csv",
                    "question": "a\u0000b",
                },
                "Nullbytes",
            ),
            (
                {
                    "operation": "resolve_table",
                    "clarification_id": "x",
                },
                "fehlen Pflichtfelder",
            ),
        )

        with patch.object(workflow, "ask_file") as ask_file:
            for payload, pattern in cases:
                with self.subTest(payload=payload):
                    with self.assertRaisesRegex(TableJsonError, pattern):
                        controller.handle_json(json.dumps(payload))
            ask_file.assert_not_called()

    def test_malformed_duplicate_nonstandard_and_oversized_json_are_rejected(self):
        generator = RecordingGenerator({
            "calculations": [{"label": "Zeilen", "aggregation": "count"}]
        })
        workflow = TableWorkflow(generator)
        controller = TableJsonController(workflow)
        invalid = (
            ('{"operation":', "Ungueltiger JSON"),
            (
                '{"operation":"ask_table","operation":"ask_table"}',
                "doppeltes Feld",
            ),
            (
                '{"operation":"ask_table","path":"x.csv","question":NaN}',
                "unzulaessig",
            ),
        )

        with patch.object(workflow, "ask_file") as ask_file:
            for payload, pattern in invalid:
                with self.subTest(payload=payload):
                    with self.assertRaisesRegex(TableJsonError, pattern):
                        controller.handle_json(payload)

            limited = TableJsonController(workflow, max_request_chars=10)
            with self.assertRaisesRegex(TableJsonError, "groesser als"):
                limited.handle_json('{"operation":"ask_table"}')
            ask_file.assert_not_called()

    @staticmethod
    def request(controller, payload):
        return json.loads(controller.handle_json(
            json.dumps(payload, ensure_ascii=False)
        ))


if __name__ == "__main__":
    unittest.main()
