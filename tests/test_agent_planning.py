import sys
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.agent import TableQuestionError, answer_table_question
from portable_agent.llm import LlamaCppPlanGenerator
from portable_agent.semantics import load_default_semantic_catalog
from portable_agent.sources import InMemoryTableSource


class FakePlanGenerator:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def generate_plan(self, question, columns, semantic_definitions):
        self.calls.append((question, columns, dict(semantic_definitions)))
        return self.payload


class SequencePlanGenerator:
    def __init__(self, payloads):
        self.payloads = iter(payloads)
        self.calls = 0

    def generate_plan(self, question, columns, semantic_definitions):
        self.calls += 1
        return next(self.payloads)


class SpyJsonClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def complete_json(self, messages, *, max_tokens=500, temperature=0.0):
        self.calls.append({
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        })
        return self.response


class AgentPlanningTests(unittest.TestCase):
    def test_natural_question_reaches_cited_result_through_fake(self):
        source = InMemoryTableSource([
            {"Aktion": "ALPHA", "Stunden": 4},
            {"Aktion": "ALPHA", "Stunden": 6},
            {"Aktion": "BETA", "Stunden": 3},
        ])
        generator = FakePlanGenerator({
            "filters": [{"column": "Aktion", "op": "==", "value": "ALPHA"}],
            "calculations": [{"label": "Stunden", "aggregation": "sum", "column": "Stunden"}],
        })

        result = answer_table_question(
            source,
            "Wie viele Stunden hatte ALPHA?",
            generator,
            semantic_definitions={
                "Stunden": "Erfasster Aufwand",
                "NichtVorhanden": "Darf nicht weitergegeben werden",
            },
        )

        self.assertEqual(result.values, {"Stunden": 10})
        self.assertEqual([citation.row for citation in result.citations], [2, 3])
        self.assertEqual(generator.calls[0][1], ("Aktion", "Stunden"))
        self.assertEqual(generator.calls[0][2], {"Stunden": "Erfasster Aufwand"})

    def test_rows_and_values_are_not_passed_to_generator(self):
        secret = "SENSITIVER_ZELLWERT"
        source = InMemoryTableSource([{"Name": secret, "Wert": 5}])
        generator = FakePlanGenerator({
            "calculations": [{"label": "Anzahl", "aggregation": "count"}]
        })

        answer_table_question(source, "Wie viele Eintraege?", generator)

        captured = repr(generator.calls)
        self.assertNotIn(secret, captured)
        self.assertIn("Name", captured)
        self.assertIn("Wert", captured)

    def test_empty_question_is_rejected_before_generator(self):
        source = InMemoryTableSource([{"Wert": 1}])
        generator = FakePlanGenerator({})
        with self.assertRaisesRegex(TableQuestionError, "nicht leer"):
            answer_table_question(source, "   ", generator)
        self.assertEqual(generator.calls, [])

    def test_one_invalid_model_plan_is_retried_once(self):
        source = InMemoryTableSource([{"Wert": 2}, {"Wert": 3}])
        generator = SequencePlanGenerator([
            {"calculations": [{"label": "Summe", "aggregation": "total", "column": "Wert"}]},
            {"calculations": [{"label": "Summe", "aggregation": "sum", "column": "Wert"}]},
        ])

        result = answer_table_question(source, "Wie hoch ist die Summe?", generator)

        self.assertEqual(result.values, {"Summe": 5})
        self.assertEqual(generator.calls, 2)

    def test_two_invalid_model_plans_return_safe_question_error(self):
        source = InMemoryTableSource([{"Wert": 2}])
        generator = SequencePlanGenerator([
            {"sort": None},
            {"calculations": []},
        ])

        with self.assertRaisesRegex(TableQuestionError, "eindeutiger"):
            answer_table_question(source, "Was ist der Wert?", generator)
        self.assertEqual(generator.calls, 2)

    def test_latest_event_in_year_uses_deterministic_date_plan(self):
        source = InMemoryTableSource([
            {"Datum": "2025-12-31", "Aktion": "ALT"},
            {"Datum": "2026-02-03", "Aktion": "FRUEH"},
            {"Datum": "2026-11-19", "Aktion": "SPAET"},
            {"Datum": "2027-01-01", "Aktion": "NEU"},
        ])
        generator = FakePlanGenerator({})

        result = answer_table_question(
            source,
            "Wann war der letzte Einsatz im Jahr 2026?",
            generator,
            semantic_catalog=load_default_semantic_catalog(),
        )

        self.assertEqual(result.values, {"groups": [{
            "Aktion": "SPAET",
            "Letzter Einsatz": "2026-11-19",
        }]})
        self.assertEqual([citation.row for citation in result.citations], [4])
        self.assertEqual(result.metadata["matched_rows"], 2)
        self.assertEqual(generator.calls, [])

    def test_earliest_event_in_year_uses_deterministic_date_plan(self):
        source = InMemoryTableSource([
            {"Datum": "2026-07-10", "Aktion": "SPAET"},
            {"Datum": "2026-01-05", "Aktion": "FRUEH"},
        ])
        generator = FakePlanGenerator({})

        result = answer_table_question(
            source,
            "Wann war der erste Einsatz 2026?",
            generator,
            semantic_catalog=load_default_semantic_catalog(),
        )

        self.assertEqual(result.values, {"groups": [{
            "Aktion": "FRUEH",
            "Erster Einsatz": "2026-01-05",
        }]})
        self.assertEqual(generator.calls, [])

    def test_latest_event_without_year_also_includes_action(self):
        source = InMemoryTableSource([
            {"Datum": "2026-11-19", "Aktion": "ALPHA"},
            {"Datum": "2027-01-04", "Aktion": "BETA"},
        ])
        generator = FakePlanGenerator({})

        result = answer_table_question(
            source,
            "Wann war der letzte Einsatz?",
            generator,
            semantic_catalog=load_default_semantic_catalog(),
        )

        self.assertEqual(result.values, {"groups": [{
            "Aktion": "BETA",
            "Letzter Einsatz": "2027-01-04",
        }]})
        self.assertEqual([citation.row for citation in result.citations], [3])
        self.assertEqual(generator.calls, [])

    def test_temporal_shortcut_requires_one_known_date_column(self):
        source = InMemoryTableSource([{"Unbekannt": "2026-05-01"}])
        generator = FakePlanGenerator({
            "calculations": [{"label": "Eintraege", "aggregation": "count"}]
        })

        result = answer_table_question(
            source,
            "Wann war der letzte Einsatz im Jahr 2026?",
            generator,
            semantic_catalog=load_default_semantic_catalog(),
        )

        self.assertEqual(result.values, {"Eintraege": 1})
        self.assertEqual(len(generator.calls), 1)

    def test_llama_prompt_contains_schema_but_no_row_values(self):
        response = {"calculations": [{"label": "Anzahl", "aggregation": "count"}]}
        client = SpyJsonClient(response)
        generator = LlamaCppPlanGenerator(client)

        actual = generator.generate_plan(
            "Wie viele Eintraege?",
            ("Name", "Wert"),
            {"Wert": "Messwert", "Unsichtbar": "Nicht senden"},
        )

        self.assertIs(actual, response)
        prompt = repr(client.calls[0]["messages"])
        self.assertIn("Name", prompt)
        self.assertIn("Messwert", prompt)
        self.assertNotIn("Unsichtbar", prompt)
        self.assertIn("verwende [] statt null", prompt)
        self.assertIn('Datum >= "2026-01-01"', prompt)
        self.assertIn("bedeutet max auf der Datumsspalte", prompt)
        self.assertIn("Datum und Aktionsname verbunden", prompt)
        self.assertEqual(client.calls[0]["temperature"], 0.0)


if __name__ == "__main__":
    unittest.main()
