import sys
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.agent import TableAgent
from portable_agent.domain import ClarificationRequest, QueryResult
from portable_agent.semantics import SemanticPolicyError, load_default_semantic_catalog
from portable_agent.sources import InMemoryTableSource


class StaticGenerator:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def generate_plan(self, question, columns, semantic_definitions):
        self.calls += 1
        return self.payload


class SemanticPolicyTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_default_semantic_catalog()
        self.source = InMemoryTableSource([
            {"Aktion": "ALPHA", "Einsatzdauer": 7.0},
            {"Aktion": "ALPHA", "Einsatzdauer": 5.0},
        ])

    def test_disallowed_aggregation_is_rejected(self):
        generator = StaticGenerator({
            "calculations": [{"label": "Aktion", "aggregation": "sum", "column": "Aktion"}]
        })
        agent = TableAgent(self.source, generator, self.catalog)
        with self.assertRaisesRegex(SemanticPolicyError, "nicht erlaubt"):
            agent.ask("Summiere die Aktion")

    def test_ambiguous_multi_row_measure_returns_typed_clarification(self):
        generator = StaticGenerator({
            "filters": [{"column": "Aktion", "op": "==", "value": "ALPHA"}],
            "calculations": [{"label": "Dauer", "aggregation": "sum", "column": "Einsatzdauer"}],
        })
        agent = TableAgent(self.source, generator, self.catalog)

        result = agent.ask("Wie lange war die Einsatzdauer bei ALPHA?")

        self.assertIsInstance(result, ClarificationRequest)
        self.assertEqual(result.matched_rows, 2)
        self.assertEqual(
            [option.id for option in result.options],
            ["sum", "average", "min", "max"],
        )

    def test_explicit_total_executes_without_clarification(self):
        generator = StaticGenerator({
            "calculations": [{"label": "Dauer", "aggregation": "sum", "column": "Einsatzdauer"}]
        })
        agent = TableAgent(self.source, generator, self.catalog)

        result = agent.ask("Wie hoch war die gesamte Einsatzdauer?")

        self.assertIsInstance(result, QueryResult)
        self.assertEqual(result.values, {"Dauer": 12.0})

    def test_clarification_selection_executes_without_second_model_call(self):
        generator = StaticGenerator({
            "calculations": [{"label": "Dauer", "aggregation": "sum", "column": "Einsatzdauer"}]
        })
        agent = TableAgent(self.source, generator, self.catalog)
        clarification = agent.ask("Wie lange war die Einsatzdauer?")

        result = agent.resolve(clarification, "average")

        self.assertEqual(result.values, {"Dauer": 6.0})
        self.assertEqual(generator.calls, 1)

    def test_single_matching_row_does_not_require_clarification(self):
        generator = StaticGenerator({
            "filters": [{"column": "Einsatzdauer", "op": "==", "value": 7.0}],
            "calculations": [{"label": "Dauer", "aggregation": "sum", "column": "Einsatzdauer"}],
        })
        agent = TableAgent(self.source, generator, self.catalog)

        result = agent.ask("Wie lange war die Einsatzdauer mit dem Wert sieben?")

        self.assertIsInstance(result, QueryResult)
        self.assertEqual(result.values, {"Dauer": 7.0})

    def test_date_max_is_allowed_by_catalog_operation(self):
        source = InMemoryTableSource([
            {"Datum": "2026-01-02", "Aktion": "ALPHA"},
            {"Datum": "2026-08-09", "Aktion": "BETA"},
        ])
        generator = StaticGenerator({
            "calculations": [
                {"label": "Letzter Einsatz", "aggregation": "max", "column": "Datum"}
            ]
        })
        agent = TableAgent(source, generator, self.catalog)

        result = agent.ask("Was ist das Maximum des Datums?")

        self.assertIsInstance(result, QueryResult)
        self.assertEqual(result.values, {"Letzter Einsatz": "2026-08-09"})


if __name__ == "__main__":
    unittest.main()
