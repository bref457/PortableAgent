import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.agent import answer_table_question
from portable_agent.analysis import (
    ResultVerificationError,
    execute_table_plan,
    execute_verified_table_plan,
    verify_table_result,
)
from portable_agent.domain import (
    Calculation,
    Filter,
    QueryPlan,
    QueryResult,
    SortRule,
    SourceRef,
)
from portable_agent.plans import PlanValidationError
from portable_agent.semantics import (
    build_explicit_total_plan,
    build_temporal_extreme_plan,
    load_default_semantic_catalog,
    resolve_clarification,
)
from portable_agent.sources import InMemoryTableSource


class RecordingGenerator:
    def __init__(self):
        self.calls = []

    def generate_plan(self, question, columns, semantic_definitions):
        self.calls.append((question, columns, dict(semantic_definitions)))
        return {}


class OneShotSource:
    def __init__(self, source):
        self.columns = source.columns
        self._rows = tuple(source.iter_rows())
        self.calls = 0

    def iter_rows(self):
        self.calls += 1
        if self.calls > 1:
            raise AssertionError("Originalquelle darf nur einmal gelesen werden.")
        return iter(self._rows)


class TableVerifierTests(unittest.TestCase):
    def setUp(self):
        self.source = InMemoryTableSource([
            {"Datum": "2024-03-02", "Aktion": "ALPHA", "Stunden": 4},
            {"Datum": "2024-02-01", "Aktion": "ALPHA", "Stunden": 6},
            {"Datum": "2023-01-01", "Aktion": "BETA", "Stunden": 9},
        ])
        entity_filter = Filter("Aktion", "==", "ALPHA")
        self.first_plan = QueryPlan(
            filters=(entity_filter,),
            calculations=(Calculation("Erster Einsatz", "min", "Datum"),),
            required_filters=(entity_filter,),
        )

    def test_valid_filtered_result_and_decisive_evidence_pass(self):
        result = execute_table_plan(self.source, self.first_plan)

        verify_table_result(self.source, self.first_plan, result)

    def test_wrong_extreme_value_is_rejected(self):
        result = execute_table_plan(self.source, self.first_plan)
        tampered = replace(result, values={"Erster Einsatz": "2023-01-01"})

        with self.assertRaisesRegex(ResultVerificationError, "Tabellenergebnis"):
            verify_table_result(self.source, self.first_plan, tampered)

    def test_incorrect_metadata_is_rejected(self):
        result = execute_table_plan(self.source, self.first_plan)
        tampered = replace(
            result,
            metadata={"matched_rows": 3, "grouped": False},
        )

        with self.assertRaisesRegex(ResultVerificationError, "Ergebnismetadaten"):
            verify_table_result(self.source, self.first_plan, tampered)

    def test_foreign_or_wrong_evidence_row_is_rejected(self):
        result = execute_table_plan(self.source, self.first_plan)
        foreign = SourceRef(
            source_id="foreign",
            display_name="foreign.xlsx",
            section="Andere",
            row=99,
        )

        with self.assertRaisesRegex(ResultVerificationError, "Zeilenbelege"):
            verify_table_result(
                self.source,
                self.first_plan,
                replace(result, citations=(foreign,)),
            )

    def test_sum_requires_every_contributing_row_as_evidence(self):
        plan = QueryPlan(
            filters=(Filter("Aktion", "==", "ALPHA"),),
            calculations=(Calculation("Stunden", "sum", "Stunden"),),
        )
        result = execute_table_plan(self.source, plan)

        with self.assertRaisesRegex(ResultVerificationError, "Zeilenbelege"):
            verify_table_result(
                self.source,
                plan,
                replace(result, citations=result.citations[:1]),
            )

    def test_equal_extreme_requires_every_decisive_row(self):
        source = InMemoryTableSource([
            {"Aktion": "ALPHA", "Datum": "2024-01-01"},
            {"Aktion": "ALPHA", "Datum": "2024-01-01"},
        ])
        plan = QueryPlan(
            calculations=(Calculation("Erster Einsatz", "min", "Datum"),),
        )
        result = execute_table_plan(source, plan)

        with self.assertRaisesRegex(ResultVerificationError, "Zeilenbelege"):
            verify_table_result(
                source,
                plan,
                replace(result, citations=result.citations[:1]),
            )

    def test_fabricated_value_for_zero_matches_is_rejected(self):
        plan = QueryPlan(
            filters=(Filter("Aktion", "==", "OMEGA"),),
            calculations=(Calculation("Stunden", "sum", "Stunden"),),
        )
        fabricated = QueryResult(
            values={"Stunden": 99},
            citations=(),
            metadata={"matched_rows": 0, "grouped": False},
        )

        with self.assertRaisesRegex(ResultVerificationError, "Tabellenergebnis"):
            verify_table_result(self.source, plan, fabricated)

    def test_grouped_top_one_and_its_evidence_are_recomputed(self):
        plan = QueryPlan(
            calculations=(Calculation("Stunden", "sum", "Stunden"),),
            group_by="Aktion",
            sort=(SortRule("Stunden", "desc"),),
            limit=1,
        )
        result = execute_table_plan(self.source, plan)
        wrong = replace(
            result,
            values={"groups": [{"Aktion": "BETA", "Stunden": 9}]},
        )

        with self.assertRaisesRegex(ResultVerificationError, "Tabellenergebnis"):
            verify_table_result(self.source, plan, wrong)

    def test_missing_required_entity_filter_is_rejected_before_execution(self):
        required = Filter("Aktion", "==", "ALPHA")
        plan = QueryPlan(
            calculations=(Calculation("Erster Einsatz", "min", "Datum"),),
            required_filters=(required,),
        )

        with self.assertRaisesRegex(PlanValidationError, "Erforderlicher Filter"):
            execute_verified_table_plan(self.source, plan)

    def test_required_entity_must_exist_in_the_source(self):
        required = Filter("Aktion", "==", "OMEGA")
        plan = QueryPlan(
            filters=(required,),
            calculations=(Calculation("Erster Einsatz", "min", "Datum"),),
            required_filters=(required,),
        )

        with self.assertRaisesRegex(ResultVerificationError, "keine Quellzeile"):
            execute_verified_table_plan(self.source, plan)

    def test_required_entity_filter_must_be_exact_nonempty_text(self):
        for required in (
            Filter("Aktion", "contains", "ALPHA"),
            Filter("Aktion", "==", "   "),
            Filter("Aktion", "==", 1),
        ):
            with self.subTest(required=required):
                plan = QueryPlan(
                    filters=(required,),
                    calculations=(Calculation("Anzahl", "count"),),
                    required_filters=(required,),
                )
                with self.assertRaisesRegex(
                    PlanValidationError,
                    "exakte, nicht leere Textgleichheit",
                ):
                    execute_verified_table_plan(self.source, plan)

    def test_temporal_builder_marks_its_entity_filter_as_required(self):
        plan = build_temporal_extreme_plan(
            self.source,
            "Wann war ALPHA erstmals?",
            load_default_semantic_catalog(),
        )

        self.assertIsInstance(plan, QueryPlan)
        expected = Filter("Aktion", "==", "ALPHA")
        self.assertIn(expected, plan.filters)
        self.assertEqual(plan.required_filters, (expected,))

    def test_total_builder_marks_its_entity_filter_as_required(self):
        source = InMemoryTableSource([
            {"Datum": "2026-01-02", "Aktion": "ALPHA", "Einsatzstunden": 4},
        ])
        plan = build_explicit_total_plan(
            source,
            "Gesamte Einsatzstunden ALPHA 2026",
            load_default_semantic_catalog(),
        )

        self.assertIsInstance(plan, QueryPlan)
        expected = Filter("Aktion", "==", "ALPHA")
        self.assertIn(expected, plan.filters)
        self.assertEqual(plan.required_filters, (expected,))

    def test_entity_clarification_resolution_adds_required_filter(self):
        source = InMemoryTableSource([
            {"Datum": "2024-01-02", "Aktion": "ALPHA NORD"},
            {"Datum": "2024-01-03", "Aktion": "ALPHA SUED"},
        ])
        request = build_temporal_extreme_plan(
            source,
            "Wann war ALPHA erstmals?",
            load_default_semantic_catalog(),
        )
        plan = resolve_clarification(request, "entity-2")

        expected = Filter("Aktion", "==", "ALPHA SUED")
        self.assertIn(expected, plan.filters)
        self.assertEqual(plan.required_filters, (expected,))

    def test_verified_execution_reads_original_source_only_once(self):
        source = OneShotSource(self.source)

        result = execute_verified_table_plan(source, self.first_plan)

        self.assertEqual(result.values, {"Erster Einsatz": "2024-02-01"})
        self.assertEqual(source.calls, 1)

    def test_verification_failure_has_no_model_retry_or_fallback(self):
        generator = RecordingGenerator()

        with patch(
            "portable_agent.analysis.verification.verify_table_result",
            side_effect=ResultVerificationError("synthetischer Fehler"),
        ):
            with self.assertRaisesRegex(ResultVerificationError, "synthetischer"):
                answer_table_question(
                    self.source,
                    "Wann war ALPHA erstmals?",
                    generator,
                    semantic_catalog=load_default_semantic_catalog(),
                )

        self.assertEqual(generator.calls, [])


if __name__ == "__main__":
    unittest.main()
