import sys
import tempfile
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.agent import TableAgent
from portable_agent.semantics import load_default_semantic_catalog
from portable_agent.sources import CsvSourceError, CsvTableSource


class StaticGenerator:
    def __init__(self, payload):
        self.payload = payload

    def generate_plan(self, question, columns, semantic_definitions):
        return self.payload


class CsvTableSourceTests(unittest.TestCase):
    def test_semicolon_csv_supports_decimal_comma_and_citations(self):
        content = "Aktion;Einsatzstunden;FIX\nALPHA;7,5;2\nALPHA;5,0;3\n"
        with self.synthetic_file("source.csv", content) as path:
            before = path.read_bytes()
            source = CsvTableSource(path)
            agent = TableAgent(
                source,
                StaticGenerator({
                    "filters": [{"column": "Aktion", "op": "==", "value": "ALPHA"}],
                    "calculations": [{
                        "label": "Stunden",
                        "aggregation": "sum",
                        "column": "Einsatzstunden",
                    }],
                }),
                load_default_semantic_catalog(),
            )
            result = agent.ask("Wie viele Einsatzstunden insgesamt?")
            after = path.read_bytes()

        self.assertEqual(source.columns, ("Aktion", "Einsatzstunden", "FIX"))
        self.assertEqual(result.values, {"Stunden": 12.5})
        self.assertEqual([citation.row for citation in result.citations], [2, 3])
        self.assertEqual([citation.display_name for citation in result.citations], ["source.csv", "source.csv"])
        self.assertEqual(before, after)

    def test_leading_zero_identifier_remains_text(self):
        with self.synthetic_file("ids.csv", "Code,Wert\n001,2\n") as path:
            source = CsvTableSource(path)
            row = next(source.iter_rows())
        self.assertEqual(row.values["Code"], "001")
        self.assertEqual(row.values["Wert"], 2)

    def test_non_csv_extension_is_rejected_before_reading(self):
        with self.synthetic_file("source.txt", "A,B\n1,2\n") as path:
            with self.assertRaisesRegex(CsvSourceError, "Endung .csv"):
                CsvTableSource(path)

    def test_duplicate_headers_are_rejected(self):
        with self.synthetic_file("duplicate.csv", "Wert,Wert\n1,2\n") as path:
            with self.assertRaisesRegex(CsvSourceError, "doppelte Spaltennamen"):
                CsvTableSource(path)

    def test_inconsistent_row_width_is_rejected(self):
        with self.synthetic_file("broken.csv", "A,B\n1,2,3\n") as path:
            with self.assertRaisesRegex(CsvSourceError, "statt 2 Felder"):
                CsvTableSource(path)

    def test_size_and_row_limits_are_enforced(self):
        with self.synthetic_file("limited.csv", "A\n1\n2\n") as path:
            with self.assertRaisesRegex(CsvSourceError, "groesser als"):
                CsvTableSource(path, max_bytes=2)
            with self.assertRaisesRegex(CsvSourceError, "mehr als 1 Datenzeilen"):
                CsvTableSource(path, max_rows=1)

    def synthetic_file(self, name, content):
        test_case = self

        class SyntheticFile:
            def __enter__(self):
                self.temporary = tempfile.TemporaryDirectory()
                self.path = Path(self.temporary.name) / name
                self.path.write_text(content, encoding="utf-8")
                return self.path

            def __exit__(self, exc_type, exc_value, traceback):
                self.temporary.cleanup()

        return SyntheticFile()


if __name__ == "__main__":
    unittest.main()

