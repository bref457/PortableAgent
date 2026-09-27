import sys
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.domain import Calculation, Filter, QueryPlan, SortRule, SourceRef
from portable_agent.llm import LlamaCppClient
from portable_agent.plans import PlanValidationError, validate_plan


class PlanValidationTests(unittest.TestCase):
    def setUp(self):
        self.columns = {"Datum", "Aktion", "Einsatzstunden", "FIX", "Miliz"}

    def test_valid_multi_calculation_plan(self):
        plan = QueryPlan(
            filters=(Filter("Datum", "==", "2026-09-08"),),
            calculations=(
                Calculation("Miliz", "sum", "Miliz"),
                Calculation("FIX", "sum", "FIX"),
            ),
        )
        validate_plan(plan, self.columns)

    def test_unknown_column_is_rejected(self):
        plan = QueryPlan(
            calculations=(Calculation("Erfunden", "sum", "Nicht vorhanden"),)
        )
        with self.assertRaisesRegex(PlanValidationError, "Unbekannte Berechnungsspalte"):
            validate_plan(plan, self.columns)

    def test_sort_must_reference_calculation_label(self):
        plan = QueryPlan(
            calculations=(Calculation("Stunden", "sum", "Einsatzstunden"),),
            sort=(SortRule("Unbekannt", "desc"),),
        )
        with self.assertRaisesRegex(PlanValidationError, "Unbekanntes Sortierfeld"):
            validate_plan(plan, self.columns)

    def test_citation_can_address_table_or_document(self):
        row = SourceRef("source-1", "synthetic.xlsx", section="Tabelle1", row=2)
        page = SourceRef("source-2", "synthetic.pdf", page=3, excerpt="Beleg")
        self.assertEqual(row.row, 2)
        self.assertEqual(page.page, 3)

    def test_llama_client_rejects_remote_endpoint(self):
        with self.assertRaisesRegex(ValueError, "lokal"):
            LlamaCppClient("https://example.invalid/v1/chat/completions")


if __name__ == "__main__":
    unittest.main()
