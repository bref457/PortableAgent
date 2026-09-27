"""Strict source routing by allowlisted file extension."""

from __future__ import annotations

from pathlib import Path

from .csv_source import CsvTableSource
from .table import TableSource
from .document import DocumentSource
from .docx_source import DocxDocumentSource
from .pdf_source import PdfDocumentSource
from .txt_source import TxtDocumentSource
from .xlsx_source import XlsxTableSource


SUPPORTED_TABLE_EXTENSIONS = frozenset({".csv", ".xlsx", ".xlsm"})
SUPPORTED_DOCUMENT_EXTENSIONS = frozenset({".txt", ".docx", ".pdf"})
PLANNED_EXTENSIONS = frozenset()
SUPPORTED_EXTENSIONS = SUPPORTED_TABLE_EXTENSIONS | SUPPORTED_DOCUMENT_EXTENSIONS


class SourceRoutingError(ValueError):
    """Base error for rejected source-routing requests."""


class SourceFormatNotAllowedError(SourceRoutingError):
    """The extension is outside the project's explicit allowlist."""


class SourceFormatNotImplementedError(SourceRoutingError):
    """The extension is planned but no safe adapter exists yet."""


def open_table_source(path: str | Path, *, sheet_name: str | None = None) -> TableSource:
    """Open an explicitly supplied table path through an allowlisted adapter."""
    if not isinstance(path, (str, Path)):
        raise SourceRoutingError("Der Quellenpfad muss eine Zeichenkette oder Path sein.")
    source_path = Path(path)
    extension = source_path.suffix.casefold()

    if extension == ".csv":
        if sheet_name is not None:
            raise SourceRoutingError("CSV-Dateien besitzen keine Tabellenblaetter.")
        return CsvTableSource(source_path)
    if extension in {".xlsx", ".xlsm"}:
        return XlsxTableSource(source_path, sheet_name=sheet_name)
    if extension in PLANNED_EXTENSIONS:
        raise SourceFormatNotImplementedError(
            f"Das Format '{extension}' ist geplant, aber noch nicht implementiert."
        )
    shown = extension or "ohne Endung"
    raise SourceFormatNotAllowedError(
        f"Das Dateiformat '{shown}' ist nicht erlaubt."
    )


def open_document_source(path: str | Path) -> DocumentSource:
    """Open an explicitly supplied document path through an allowlisted adapter."""
    if not isinstance(path, (str, Path)):
        raise SourceRoutingError("Der Quellenpfad muss eine Zeichenkette oder Path sein.")
    source_path = Path(path)
    extension = source_path.suffix.casefold()

    if extension == ".txt":
        return TxtDocumentSource(source_path)
    if extension == ".docx":
        return DocxDocumentSource(source_path)
    if extension == ".pdf":
        return PdfDocumentSource(source_path)
    if extension in PLANNED_EXTENSIONS:
        raise SourceFormatNotImplementedError(
            f"Das Format '{extension}' ist geplant, aber noch nicht implementiert."
        )
    shown = extension or "ohne Endung"
    raise SourceFormatNotAllowedError(
        f"Das Dateiformat '{shown}' ist nicht als Dokumentquelle erlaubt."
    )
