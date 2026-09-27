"""Local source parsers and routing."""

from .csv_source import CsvSourceError, CsvTableSource
from .document import (
    DocumentChunk,
    DocumentSegment,
    DocumentSource,
    InMemoryDocumentSource,
)
from .docx_source import DocxDocumentSource, DocxSourceError
from .pdf_source import PdfDependencyError, PdfDocumentSource, PdfSourceError
from .router import (
    PLANNED_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    SUPPORTED_DOCUMENT_EXTENSIONS,
    SUPPORTED_TABLE_EXTENSIONS,
    SourceFormatNotAllowedError,
    SourceFormatNotImplementedError,
    SourceRoutingError,
    open_document_source,
    open_table_source,
)
from .table import InMemoryTableSource, TableRow, TableSource
from .txt_source import TxtDocumentSource, TxtSourceError
from .xlsx_source import (
    SheetSelectionRequiredError,
    XlsxDependencyError,
    XlsxSourceError,
    XlsxTableSource,
    list_sheet_names,
)

__all__ = [
    "CsvSourceError",
    "CsvTableSource",
    "DocumentChunk",
    "DocumentSegment",
    "DocumentSource",
    "DocxDocumentSource",
    "DocxSourceError",
    "PdfDependencyError",
    "PdfDocumentSource",
    "PdfSourceError",
    "InMemoryTableSource",
    "InMemoryDocumentSource",
    "PLANNED_EXTENSIONS",
    "SUPPORTED_EXTENSIONS",
    "SUPPORTED_DOCUMENT_EXTENSIONS",
    "SUPPORTED_TABLE_EXTENSIONS",
    "SourceFormatNotAllowedError",
    "SourceFormatNotImplementedError",
    "SourceRoutingError",
    "SheetSelectionRequiredError",
    "TableRow",
    "TableSource",
    "TxtDocumentSource",
    "TxtSourceError",
    "XlsxDependencyError",
    "XlsxSourceError",
    "XlsxTableSource",
    "list_sheet_names",
    "open_document_source",
    "open_table_source",
]
