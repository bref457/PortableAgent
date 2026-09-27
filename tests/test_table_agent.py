import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.agent import TableAgent
from portable_agent.semantics import load_default_semantic_catalog
from portable_agent.sources import InMemoryTableSource


class RecordingGenerator:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def generate_plan(self, question, columns, semantic_definitions):
        self.calls.append((question, columns, dict(semantic_definitions)))
        return self.payload


class TableAgentTests(unittest.TestCase):
    def setUp(self):
        self.source = InMemoryTableSource([
            {"Fix": 2, "Miliz": 1, "InterneNotiz": "NICHT_AN_MODELL"},
            {"Fix": 3, "Miliz": 4, "InterneNotiz": "AUCH_NICHT"},
        ])

    def test_agent_automatically_applies_catalog_to_existing_columns(self):
        generator = RecordingGenerator({
            "calculations": [{"label": "FIX", "aggregation": "sum", "column": "Fix"}]
        })
        agent = TableAgent(
            source=self.source,
            generator=generator,
            catalog=load_default_semantic_catalog(),
        )

        result = agent.ask("Wie viele FIX gibt es?")

        self.assertEqual(result.values, {"FIX": 5})
        definitions = generator.calls[0][2]
        self.assertEqual(set(definitions), {"Fix", "Miliz"})
        self.assertNotIn("NICHT_AN_MODELL", repr(generator.calls))
        self.assertNotIn("AUCH_NICHT", repr(generator.calls))

    def test_default_catalog_is_loaded_once_when_agent_is_created(self):
        catalog = load_default_semantic_catalog()
        generator = RecordingGenerator({
            "calculations": [{"label": "Eintraege", "aggregation": "count"}]
        })
        with patch(
            "portable_agent.agent.table_agent.load_default_semantic_catalog",
            return_value=catalog,
        ) as loader:
            agent = TableAgent.with_default_catalog(self.source, generator)
            agent.ask("Wie viele Eintraege?")
            agent.ask("Wie viele Eintraege insgesamt?")

        loader.assert_called_once_with()
        self.assertEqual(len(generator.calls), 2)

    def test_citations_remain_bound_to_the_agents_source(self):
        generator = RecordingGenerator({
            "filters": [{"column": "Miliz", "op": ">", "value": 1}],
            "calculations": [{"label": "Miliz", "aggregation": "sum", "column": "Miliz"}],
        })
        agent = TableAgent.with_default_catalog(self.source, generator)

        result = agent.ask("Miliz ueber eins")

        self.assertEqual(result.values, {"Miliz": 4})
        self.assertEqual([citation.row for citation in result.citations], [3])


if __name__ == "__main__":
    unittest.main()

