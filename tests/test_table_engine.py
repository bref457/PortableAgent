import sys
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.analysis import PlanExecutionError, execute_table_plan
from portable_agent.domain import Calculation, Filter, QueryPlan, SortRule
from portable_agent.plans import PlanValidationError
from portable_agent.sources import InMemoryTableSource


class TableEngineTests(unittest.TestCase):
    def setUp(self):
        self.input_rows = [
            {"Datum": "2026-09-08", "Aktion": "ALPHA", "Stunden": 7.5, "FIX": 6, "Miliz": 1},
            {"Datum": "2026-09-08", "Aktion": "ALPHA", "Stunden": 5.0, "FIX": 5, "Miliz": 2},
            {"Datum": "2026-09-07", "Aktion": "BETA", "Stunden": 9.0, "FIX": 2, "Miliz": 4},
        ]
        self.source = InMemoryTableSource(
            self.input_rows,
            display_name="synthetic.xlsx",
            section="Tabelle1",
        )

    def test_filtered_multi_calculation_returns_citations(self):
        plan = QueryPlan(
            filters=(Filter("Datum", "==", "2026-09-08"),),
            calculations=(
                Calculation("Miliz", "sum", "Miliz"),
                Calculation("FIX", "sum", "FIX"),
                Calculation("Eintraege", "count"),
            ),
        )

        result = execute_table_plan(self.source, plan)

        self.assertEqual(result.values, {"Miliz": 3, "FIX": 11, "Eintraege": 2})
        self.assertEqual(result.metadata["matched_rows"], 2)
        self.assertEqual([ref.row for ref in result.citations], [2, 3])
        self.assertTrue(all(ref.section == "Tabelle1" for ref in result.citations))

    def test_group_sort_limit_keeps_only_relevant_citations(self):
        plan = QueryPlan(
            calculations=(Calculation("Stunden", "sum", "Stunden"),),
            group_by="Aktion",
            sort=(SortRule("Stunden", "desc"),),
            limit=1,
        )

        result = execute_table_plan(self.source, plan)

        self.assertEqual(result.values["groups"], [{"Aktion": "ALPHA", "Stunden": 12.5}])
        self.assertEqual([ref.row for ref in result.citations], [2, 3])
        self.assertEqual(result.metadata["returned_groups"], 1)

    def test_maximum_cites_only_decisive_row(self):
        plan = QueryPlan(
            filters=(Filter("Aktion", "==", "ALPHA"),),
            calculations=(Calculation("Maximum", "max", "Stunden"),),
        )

        result = execute_table_plan(self.source, plan)

        self.assertEqual(result.values, {"Maximum": 7.5})
        self.assertEqual(result.metadata["matched_rows"], 2)
        self.assertEqual([ref.row for ref in result.citations], [2])

    def test_equal_extreme_values_are_all_cited(self):
        source = InMemoryTableSource([
            {"Aktion": "ALPHA", "Stunden": 7.5},
            {"Aktion": "ALPHA", "Stunden": 5.0},
            {"Aktion": "ALPHA", "Stunden": 7.5},
        ])
        plan = QueryPlan(
            calculations=(Calculation("Maximum", "max", "Stunden"),),
        )

        result = execute_table_plan(source, plan)

        self.assertEqual([ref.row for ref in result.citations], [2, 4])

    def test_grouped_maximum_cites_only_decisive_rows_per_group(self):
        plan = QueryPlan(
            calculations=(Calculation("Maximum", "max", "Stunden"),),
            group_by="Aktion",
        )

        result = execute_table_plan(self.source, plan)

        self.assertEqual([ref.row for ref in result.citations], [2, 4])

    def test_contains_is_case_insensitive(self):
        plan = QueryPlan(
            filters=(Filter("Aktion", "contains", "alp"),),
            calculations=(Calculation("Durchschnitt", "average", "Stunden"),),
        )
        result = execute_table_plan(self.source, plan)
        self.assertEqual(result.values["Durchschnitt"], 6.25)

    def test_unknown_column_is_rejected_before_execution(self):
        plan = QueryPlan(filters=(Filter("Geheim", "==", 1),))
        with self.assertRaisesRegex(PlanValidationError, "Unbekannte Filterspalte"):
            execute_table_plan(self.source, plan)

    def test_non_numeric_sum_is_rejected(self):
        plan = QueryPlan(
            calculations=(Calculation("Aktionen", "sum", "Aktion"),)
        )
        with self.assertRaisesRegex(PlanExecutionError, "numerische Werte"):
            execute_table_plan(self.source, plan)

    def test_source_snapshots_input_rows(self):
        self.input_rows[0]["FIX"] = 999
        plan = QueryPlan(calculations=(Calculation("FIX", "sum", "FIX"),))
        result = execute_table_plan(self.source, plan)
        self.assertEqual(result.values["FIX"], 13)


if __name__ == "__main__":
    unittest.main()
