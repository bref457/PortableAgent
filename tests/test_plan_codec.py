import sys
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.agent import run_table_query
from portable_agent.plans import PlanDecodeError, PlanValidationError, query_plan_from_dict
from portable_agent.sources import InMemoryTableSource


class PlanCodecTests(unittest.TestCase):
    def test_complete_payload_is_decoded_without_coercion(self):
        plan = query_plan_from_dict({
            "filters": [{"column": "Jahr", "op": "==", "value": 2026}],
            "calculations": [{"label": "Stunden", "aggregation": "sum", "column": "Stunden"}],
            "group_by": "Aktion",
            "sort": [{"by": "Stunden", "direction": "desc"}],
            "limit": 3,
        })
        self.assertEqual(plan.filters[0].value, 2026)
        self.assertEqual(plan.calculations[0].column, "Stunden")
        self.assertEqual(plan.group_by, "Aktion")
        self.assertEqual(plan.limit, 3)

    def test_unknown_top_level_field_is_rejected(self):
        with self.assertRaisesRegex(PlanDecodeError, "unbekannte Felder: python"):
            query_plan_from_dict({
                "calculations": [{"label": "Anzahl", "aggregation": "count"}],
                "python": "do_something()",
            })

    def test_model_cannot_supply_internal_verification_requirements(self):
        with self.assertRaisesRegex(
            PlanDecodeError,
            "unbekannte Felder: required_filters",
        ):
            query_plan_from_dict({
                "calculations": [{"label": "Anzahl", "aggregation": "count"}],
                "required_filters": [],
            })

    def test_unknown_nested_field_is_rejected(self):
        with self.assertRaisesRegex(PlanDecodeError, "unbekannte Felder: expression"):
            query_plan_from_dict({
                "calculations": [{
                    "label": "Summe",
                    "aggregation": "sum",
                    "column": "Wert",
                    "expression": "Wert * 2",
                }]
            })

    def test_wrong_container_type_is_rejected(self):
        with self.assertRaisesRegex(PlanDecodeError, "filters muss eine JSON-Liste"):
            query_plan_from_dict({
                "filters": {},
                "calculations": [{"label": "Anzahl", "aggregation": "count"}],
            })

    def test_optional_list_fields_accept_json_null_as_empty(self):
        plan = query_plan_from_dict({
            "filters": None,
            "calculations": [{"label": "Anzahl", "aggregation": "count"}],
            "sort": None,
        })
        self.assertEqual(plan.filters, ())
        self.assertEqual(plan.sort, ())

    def test_boolean_limit_is_not_accepted_as_integer(self):
        with self.assertRaisesRegex(PlanDecodeError, "limit muss eine ganze Zahl"):
            query_plan_from_dict({
                "calculations": [{"label": "Anzahl", "aggregation": "count"}],
                "limit": True,
            })

    def test_complex_filter_value_is_rejected(self):
        with self.assertRaisesRegex(PlanDecodeError, "einfacher JSON-Wert"):
            query_plan_from_dict({
                "filters": [{"column": "Wert", "op": "==", "value": {"$gt": 1}}],
                "calculations": [{"label": "Anzahl", "aggregation": "count"}],
            })

    def test_agent_use_case_decodes_validates_executes_and_cites(self):
        source = InMemoryTableSource(
            [
                {"Aktion": "ALPHA", "Stunden": 4},
                {"Aktion": "ALPHA", "Stunden": 6},
                {"Aktion": "BETA", "Stunden": 3},
            ],
            display_name="synthetic",
        )
        result = run_table_query(source, {
            "filters": [{"column": "Aktion", "op": "==", "value": "ALPHA"}],
            "calculations": [
                {"label": "Stunden", "aggregation": "sum", "column": "Stunden"},
                {"label": "Eintraege", "aggregation": "count"},
            ],
        })
        self.assertEqual(result.values, {"Stunden": 10, "Eintraege": 2})
        self.assertEqual([citation.row for citation in result.citations], [2, 3])

    def test_agent_use_case_rejects_unknown_source_column(self):
        source = InMemoryTableSource([{"Wert": 1}])
        with self.assertRaisesRegex(PlanValidationError, "Unbekannte Filterspalte"):
            run_table_query(source, {
                "filters": [{"column": "Geheim", "op": "==", "value": 1}],
                "calculations": [{"label": "Anzahl", "aggregation": "count"}],
            })


if __name__ == "__main__":
    unittest.main()
