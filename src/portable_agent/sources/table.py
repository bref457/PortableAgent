"""Read-only table-source abstractions without file-system access."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol

from portable_agent.domain import SourceRef


@dataclass(frozen=True, slots=True)
class TableRow:
    """One immutable logical row and its stable source reference."""

    values: Mapping[str, Any]
    source_ref: SourceRef


class TableSource(Protocol):
    """Minimal read-only contract consumed by the analysis engine."""

    @property
    def columns(self) -> tuple[str, ...]: ...

    def iter_rows(self) -> Iterator[TableRow]: ...


class InMemoryTableSource:
    """Synthetic/test source that snapshots rows instead of retaining them."""

    def __init__(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        source_id: str = "synthetic-table",
        display_name: str = "synthetic",
        section: str | None = None,
        first_row_number: int = 2,
        row_numbers: Iterable[int] | None = None,
    ) -> None:
        snapshots = [dict(row) for row in rows]
        numbers = (
            list(row_numbers)
            if row_numbers is not None
            else list(range(first_row_number, first_row_number + len(snapshots)))
        )
        if len(numbers) != len(snapshots):
            raise ValueError("row_numbers muss genau eine Nummer pro Zeile enthalten.")
        if any(type(number) is not int or number < 1 for number in numbers):
            raise ValueError("Zeilennummern muessen positive ganze Zahlen sein.")
        columns: list[str] = []
        seen: set[str] = set()
        for row in snapshots:
            for column in row:
                if column not in seen:
                    columns.append(column)
                    seen.add(column)

        self._columns = tuple(columns)
        self._rows = tuple(
            TableRow(
                values=MappingProxyType(row),
                source_ref=SourceRef(
                    source_id=source_id,
                    display_name=display_name,
                    section=section,
                    row=row_number,
                    row_values=tuple(row.items()),
                ),
            )
            for row, row_number in zip(snapshots, numbers, strict=True)
        )

    @property
    def columns(self) -> tuple[str, ...]:
        return self._columns

    def iter_rows(self) -> Iterator[TableRow]:
        return iter(self._rows)
