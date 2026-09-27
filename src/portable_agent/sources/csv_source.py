"""Read-only CSV table source using only the Python standard library."""

from __future__ import annotations

import csv
import re
from collections.abc import Iterator
from pathlib import Path

from .table import InMemoryTableSource, TableRow


DEFAULT_MAX_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_ROWS = 1_000_000
_DELIMITERS = ",;\t|"
_INTEGER = re.compile(r"^-?(?:0|[1-9]\d*)$")
_DECIMAL = re.compile(r"^-?(?:0|[1-9]\d*)[.,]\d+$")


class CsvSourceError(ValueError):
    """A CSV source cannot be opened under the read-only source policy."""


class CsvTableSource:
    """Snapshots one explicitly supplied CSV file without modifying it."""

    def __init__(
        self,
        path: str | Path,
        *,
        delimiter: str | None = None,
        encoding: str = "utf-8-sig",
        max_bytes: int = DEFAULT_MAX_BYTES,
        max_rows: int = DEFAULT_MAX_ROWS,
    ) -> None:
        source_path = Path(path)
        _validate_request(source_path, delimiter, max_bytes, max_rows)
        try:
            size = source_path.stat().st_size
        except OSError as exc:
            raise CsvSourceError(f"CSV-Datei nicht lesbar: {exc}") from exc
        if size > max_bytes:
            raise CsvSourceError(
                f"CSV-Datei ist groesser als das erlaubte Limit von {max_bytes} Bytes."
            )

        try:
            rows, headers = _read_rows(
                source_path,
                delimiter=delimiter,
                encoding=encoding,
                max_rows=max_rows,
            )
        except (OSError, UnicodeError, csv.Error) as exc:
            raise CsvSourceError(f"CSV-Datei konnte nicht gelesen werden: {exc}") from exc

        self._delegate = InMemoryTableSource(
            rows,
            source_id=f"csv:{source_path.name}",
            display_name=source_path.name,
            first_row_number=2,
        )
        self._columns = headers

    @property
    def columns(self) -> tuple[str, ...]:
        return self._columns

    def iter_rows(self) -> Iterator[TableRow]:
        return self._delegate.iter_rows()


def _validate_request(
    path: Path,
    delimiter: str | None,
    max_bytes: int,
    max_rows: int,
) -> None:
    if path.suffix.casefold() != ".csv":
        raise CsvSourceError("Nur Dateien mit der Endung .csv sind erlaubt.")
    if not path.exists() or not path.is_file():
        raise CsvSourceError("CSV-Datei wurde nicht gefunden.")
    if delimiter is not None and (
        len(delimiter) != 1 or delimiter in {"\r", "\n", '"'}
    ):
        raise CsvSourceError("Das Trennzeichen muss genau ein sicheres Zeichen sein.")
    if type(max_bytes) is not int or max_bytes <= 0:
        raise CsvSourceError("max_bytes muss eine positive ganze Zahl sein.")
    if type(max_rows) is not int or max_rows <= 0:
        raise CsvSourceError("max_rows muss eine positive ganze Zahl sein.")


def _read_rows(
    path: Path,
    *,
    delimiter: str | None,
    encoding: str,
    max_rows: int,
) -> tuple[list[dict[str, object]], tuple[str, ...]]:
    with path.open("r", encoding=encoding, newline="") as handle:
        if delimiter is None:
            sample = handle.read(8192)
            handle.seek(0)
            try:
                delimiter = csv.Sniffer().sniff(sample, delimiters=_DELIMITERS).delimiter
            except csv.Error:
                delimiter = ","

        reader = csv.reader(handle, delimiter=delimiter, strict=True)
        try:
            raw_headers = next(reader)
        except StopIteration as exc:
            raise CsvSourceError("CSV-Datei ist leer.") from exc
        headers = tuple(header.strip() for header in raw_headers)
        if not headers or any(not header for header in headers):
            raise CsvSourceError("CSV-Kopfzeile enthaelt einen leeren Spaltennamen.")
        if len(set(headers)) != len(headers):
            raise CsvSourceError("CSV-Kopfzeile enthaelt doppelte Spaltennamen.")

        rows: list[dict[str, object]] = []
        for row_number, raw_row in enumerate(reader, start=2):
            if len(rows) >= max_rows:
                raise CsvSourceError(
                    f"CSV-Datei enthaelt mehr als {max_rows} Datenzeilen."
                )
            if len(raw_row) != len(headers):
                raise CsvSourceError(
                    f"CSV-Zeile {row_number} hat {len(raw_row)} statt {len(headers)} Felder."
                )
            rows.append({
                header: _parse_scalar(value)
                for header, value in zip(headers, raw_row, strict=True)
            })
    return rows, headers


def _parse_scalar(value: str) -> object:
    text = value.strip()
    if not text:
        return None
    if _INTEGER.fullmatch(text):
        return int(text)
    if _DECIMAL.fullmatch(text):
        return float(text.replace(",", "."))
    return text

