import sys
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.agent import answer_table_question
from portable_agent.analysis import execute_verified_table_plan
from portable_agent.capabilities import (
    DEFAULT_CAPABILITY_REGISTRY,
    Capability,
    CapabilityDeniedError,
    CapabilityRegistry,
)
from portable_agent.domain import Calculation, Filter, QueryPlan
from portable_agent.semantics import load_default_semantic_catalog
from portable_agent.sources import InMemoryTableSource


class RecordingGenerator:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def generate_plan(self, question, columns, semantic_definitions):
        self.calls += 1
        return self.payload


def registry_without(*excluded_ids):
    return CapabilityRegistry(tuple(
        capability
        for capability in DEFAULT_CAPABILITY_REGISTRY.capabilities
        if capability.id not in excluded_ids
    ))


class CapabilityRegistryTests(unittest.TestCase):
    def test_default_registry_contains_only_the_eight_phase_five_capabilities(self):
        self.assertEqual(DEFAULT_CAPABILITY_REGISTRY.ids, (
            "table.inspect",
            "table.resolve_entity",
            "table.filter",
            "table.aggregate",
            "table.first_occurrence",
            "table.last_occurrence",
            "table.source_rows",
            "result.verify",
        ))
        self.assertTrue(all(
            item.read_only and item.source_kind == "table"
            for item in DEFAULT_CAPABILITY_REGISTRY.capabilities
        ))

    def test_unknown_or_writable_capabilities_cannot_be_registered(self):
        with self.assertRaisesRegex(ValueError, "Unbekannte Capability-ID"):
            CapabilityRegistry((Capability("shell.execute", "Shell starten."),))
        with self.assertRaisesRegex(ValueError, "read-only"):
            CapabilityRegistry((Capability(
                "table.inspect",
                "Tabellenschema ohne Nutzdaten erkennen.",
                read_only=False,
            ),))

    def test_capability_metadata_cannot_redirect_an_implementation(self):
        with self.assertRaisesRegex(ValueError, "nicht statisch"):
            CapabilityRegistry((Capability(
                "table.inspect",
                "Beliebigen Modulpfad laden.",
            ),))

    def test_missing_verifier_capability_stops_before_source_is_read(self):
        source = InMemoryTableSource([{"Wert": 2}])
        plan = QueryPlan(calculations=(Calculation("Summe", "sum", "Wert"),))

        with self.assertRaisesRegex(CapabilityDeniedError, "result.verify"):
            execute_verified_table_plan(
                source,
                plan,
                capability_registry=registry_without("result.verify"),
            )

    def test_missing_inspect_capability_stops_before_model_call(self):
        source = InMemoryTableSource([{"Wert": 2}])
        generator = RecordingGenerator({
            "calculations": [{"label": "Summe", "aggregation": "sum", "column": "Wert"}]
        })

        with self.assertRaisesRegex(CapabilityDeniedError, "table.inspect"):
            answer_table_question(
                source,
                "Wie hoch ist die Summe?",
                generator,
                capability_registry=registry_without("table.inspect"),
            )
        self.assertEqual(generator.calls, 0)

    def test_model_plan_cannot_bypass_the_registry(self):
        source = InMemoryTableSource([{"Wert": 2}])
        generator = RecordingGenerator({
            "calculations": [{"label": "Summe", "aggregation": "sum", "column": "Wert"}]
        })

        with self.assertRaisesRegex(CapabilityDeniedError, "table.aggregate"):
            answer_table_question(
                source,
                "Wie hoch ist die Summe?",
                generator,
                capability_registry=registry_without("table.aggregate"),
            )
        self.assertEqual(generator.calls, 1)

    def test_filter_and_aggregate_are_authorized_from_the_typed_plan(self):
        source = InMemoryTableSource([{"Art": "A", "Wert": 2}])
        plan = QueryPlan(
            filters=(Filter("Art", "==", "A"),),
            calculations=(Calculation("Summe", "sum", "Wert"),),
        )

        for missing in ("table.filter", "table.aggregate", "table.source_rows"):
            with self.subTest(missing=missing):
                with self.assertRaisesRegex(CapabilityDeniedError, missing):
                    execute_verified_table_plan(
                        source,
                        plan,
                        capability_registry=registry_without(missing),
                    )

    def test_temporal_shortcut_requires_the_specific_occurrence_capability(self):
        source = InMemoryTableSource([
            {"Datum": "2026-01-01", "Aktion": "ALPHA"},
            {"Datum": "2026-02-01", "Aktion": "BETA"},
        ])
        generator = RecordingGenerator({})

        with self.assertRaisesRegex(CapabilityDeniedError, "table.first_occurrence"):
            answer_table_question(
                source,
                "Wann war der erste Einsatz 2026?",
                generator,
                semantic_catalog=load_default_semantic_catalog(),
                capability_registry=registry_without("table.first_occurrence"),
            )
        self.assertEqual(generator.calls, 0)


if __name__ == "__main__":
    unittest.main()
