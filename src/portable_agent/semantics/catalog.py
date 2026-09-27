"""Strict loader for trusted technical semantic-catalog metadata."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CATALOG_PATH = (
    Path(__file__).resolve().parents[3] / "config" / "semantic_catalog.json"
)
_ROOT_FIELDS = frozenset({"version", "description", "fields"})
_FIELD_FIELDS = frozenset({
    "canonical_name", "aliases", "role", "data_type", "description",
    "allowed_operations", "allowed_aggregations", "unit",
    "default_aggregation", "clarify_on_multiple", "non_negative",
})
_REQUIRED_FIELD_FIELDS = frozenset({
    "canonical_name", "aliases", "role", "data_type", "description"
})
_ROLES = frozenset({"dimension", "measure", "text"})
_DATA_TYPES = frozenset({"text", "date", "number", "duration"})
_OPERATIONS = frozenset({"filter", "group", "distinct", "count", "list", "min", "max"})
_AGGREGATIONS = frozenset({"sum", "average", "min", "max", "count"})


class CatalogValidationError(ValueError):
    """The technical catalog is malformed or contains unsupported metadata."""


@dataclass(frozen=True, slots=True)
class SemanticField:
    canonical_name: str
    aliases: tuple[str, ...]
    role: str
    data_type: str
    description: str
    allowed_operations: tuple[str, ...] = ()
    allowed_aggregations: tuple[str, ...] = ()
    unit: str | None = None
    default_aggregation: str | None = None
    clarify_on_multiple: bool = False
    non_negative: bool = False

    @property
    def all_names(self) -> tuple[str, ...]:
        return (self.canonical_name, *self.aliases)

    def planner_description(self) -> str:
        parts = [self.description, f"Typ={self.data_type}", f"Rolle={self.role}"]
        if self.unit:
            parts.append(f"Einheit={self.unit}")
        if self.allowed_aggregations:
            parts.append("Erlaubte Aggregationen=" + ",".join(self.allowed_aggregations))
        if self.default_aggregation:
            parts.append(f"Standardaggregation={self.default_aggregation}")
        if self.clarify_on_multiple:
            parts.append("Bei Mehrdeutigkeit Rueckfrage erforderlich")
        return "; ".join(parts)


@dataclass(frozen=True, slots=True)
class SemanticCatalog:
    version: int
    description: str
    fields: tuple[SemanticField, ...]

    def field_for_column(self, column: str) -> SemanticField | None:
        wanted = normalize_name(column)
        for field in self.fields:
            if wanted in {normalize_name(name) for name in field.all_names}:
                return field
        return None

    def definitions_for_columns(self, columns: tuple[str, ...]) -> dict[str, str]:
        definitions: dict[str, str] = {}
        for column in columns:
            field = self.field_for_column(column)
            if field is not None:
                definitions[column] = field.planner_description()
        return definitions


def load_default_semantic_catalog() -> SemanticCatalog:
    """Load the project catalog relative to this module, never the CWD."""
    return load_semantic_catalog(DEFAULT_CATALOG_PATH)


def load_semantic_catalog(path: Path) -> SemanticCatalog:
    """Read and strictly validate one technical JSON catalog."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CatalogValidationError(f"Semantischer Katalog nicht lesbar: {exc}") from exc
    root = _object(payload, "Katalog")
    _exact_fields(root, _ROOT_FIELDS, _ROOT_FIELDS, "Katalog")
    if type(root["version"]) is not int or root["version"] != 1:
        raise CatalogValidationError("Katalog.version muss exakt 1 sein.")
    description = _text(root["description"], "Katalog.description")
    raw_fields = _list(root["fields"], "Katalog.fields")
    if not raw_fields:
        raise CatalogValidationError("Katalog.fields darf nicht leer sein.")
    fields = tuple(_decode_field(item, index) for index, item in enumerate(raw_fields))
    _validate_unique_names(fields)
    return SemanticCatalog(root["version"], description, fields)


def normalize_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value))
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", without_marks.casefold())


def _decode_field(payload: Any, index: int) -> SemanticField:
    path = f"Katalog.fields[{index}]"
    item = _object(payload, path)
    _exact_fields(item, _FIELD_FIELDS, _REQUIRED_FIELD_FIELDS, path)
    role = _choice(item["role"], _ROLES, f"{path}.role")
    data_type = _choice(item["data_type"], _DATA_TYPES, f"{path}.data_type")
    operations = _string_choices(item.get("allowed_operations", []), _OPERATIONS, f"{path}.allowed_operations")
    aggregations = _string_choices(item.get("allowed_aggregations", []), _AGGREGATIONS, f"{path}.allowed_aggregations")
    default = item.get("default_aggregation")
    if default is not None:
        default = _choice(default, _AGGREGATIONS, f"{path}.default_aggregation")
        if default not in aggregations:
            raise CatalogValidationError(
                f"{path}.default_aggregation muss in allowed_aggregations stehen."
            )
    return SemanticField(
        canonical_name=_text(item["canonical_name"], f"{path}.canonical_name"),
        aliases=_string_list(item["aliases"], f"{path}.aliases"),
        role=role,
        data_type=data_type,
        description=_text(item["description"], f"{path}.description"),
        allowed_operations=operations,
        allowed_aggregations=aggregations,
        unit=_optional_text(item.get("unit"), f"{path}.unit"),
        default_aggregation=default,
        clarify_on_multiple=_boolean(item.get("clarify_on_multiple", False), f"{path}.clarify_on_multiple"),
        non_negative=_boolean(item.get("non_negative", False), f"{path}.non_negative"),
    )


def _validate_unique_names(fields: tuple[SemanticField, ...]) -> None:
    owners: dict[str, str] = {}
    for field in fields:
        for name in field.all_names:
            normalized = normalize_name(name)
            if not normalized:
                raise CatalogValidationError("Feldnamen duerfen nicht leer normalisieren.")
            owner = owners.get(normalized)
            if owner is not None and owner != field.canonical_name:
                raise CatalogValidationError(
                    f"Alias '{name}' ist fuer '{owner}' und '{field.canonical_name}' definiert."
                )
            owners[normalized] = field.canonical_name


def _object(value: Any, path: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise CatalogValidationError(f"{path} muss ein JSON-Objekt sein.")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if type(value) is not list:
        raise CatalogValidationError(f"{path} muss eine JSON-Liste sein.")
    return value


def _exact_fields(
    item: dict[str, Any],
    allowed: frozenset[str],
    required: frozenset[str],
    path: str,
) -> None:
    unknown = sorted(set(item) - allowed)
    missing = sorted(required - set(item))
    if unknown:
        raise CatalogValidationError(f"{path} enthaelt unbekannte Felder: {', '.join(unknown)}")
    if missing:
        raise CatalogValidationError(f"{path} fehlen Pflichtfelder: {', '.join(missing)}")


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip() or "\n" in value or "\r" in value:
        raise CatalogValidationError(f"{path} muss eine einzeilige, nicht leere Zeichenkette sein.")
    return value.strip()


def _optional_text(value: Any, path: str) -> str | None:
    return None if value is None else _text(value, path)


def _boolean(value: Any, path: str) -> bool:
    if type(value) is not bool:
        raise CatalogValidationError(f"{path} muss true oder false sein.")
    return value


def _choice(value: Any, choices: frozenset[str], path: str) -> str:
    text = _text(value, path)
    if text not in choices:
        raise CatalogValidationError(f"{path} enthaelt einen nicht erlaubten Wert: {text}")
    return text


def _string_list(value: Any, path: str) -> tuple[str, ...]:
    return tuple(_text(item, f"{path}[{index}]") for index, item in enumerate(_list(value, path)))


def _string_choices(value: Any, choices: frozenset[str], path: str) -> tuple[str, ...]:
    return tuple(
        _choice(item, choices, f"{path}[{index}]")
        for index, item in enumerate(_list(value, path))
    )

