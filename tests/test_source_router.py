import sys
import tempfile
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.sources import (
    CsvTableSource,
    SourceFormatNotAllowedError,
    SourceRoutingError,
    open_table_source,
)


class SourceRouterTests(unittest.TestCase):
    def test_csv_is_routed_to_read_only_adapter(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.csv"
            path.write_text("Name,Wert\nALPHA,2\n", encoding="utf-8")
            source = open_table_source(path)
        self.assertIsInstance(source, CsvTableSource)
        self.assertEqual(source.columns, ("Name", "Wert"))

    def test_extension_matching_is_case_insensitive(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.CSV"
            path.write_text("Wert\n2\n", encoding="utf-8")
            source = open_table_source(str(path))
        self.assertEqual(next(source.iter_rows()).values["Wert"], 2)

    def test_pdf_is_not_a_table_source(self):
        with self.assertRaisesRegex(SourceFormatNotAllowedError, "'.pdf'"):
            open_table_source("dokument.pdf")

    def test_unknown_extension_and_missing_extension_are_not_allowed(self):
        with self.assertRaisesRegex(SourceFormatNotAllowedError, "'.exe'"):
            open_table_source("programm.exe")
        with self.assertRaisesRegex(SourceFormatNotAllowedError, "ohne Endung"):
            open_table_source("quelle")

    def test_non_path_input_is_rejected(self):
        with self.assertRaisesRegex(SourceRoutingError, "Quellenpfad"):
            open_table_source(None)


if __name__ == "__main__":
    unittest.main()
