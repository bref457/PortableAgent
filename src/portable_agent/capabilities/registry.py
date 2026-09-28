"""Static allowlist for trusted, read-only PortableAgent capabilities."""

from __future__ import annotations

from dataclasses import dataclass

from portable_agent.domain import QueryPlan


_CAPABILITY_DESCRIPTIONS = {
    "table.inspect": "Tabellenschema ohne Nutzdaten erkennen.",
    "table.resolve_entity": "Entitaeten lokal gegen Tabellenwerte aufloesen.",
    "table.filter": "Zeilen mit validierten Vergleichsoperatoren filtern.",
    "table.aggregate": "Validierte Tabellenwerte deterministisch aggregieren.",
    "table.first_occurrence": "Das erste passende Vorkommen bestimmen.",
    "table.last_occurrence": "Das letzte passende Vorkommen bestimmen.",
    "table.source_rows": "Exakt benoetigte Belegzeilen bereitstellen.",
    "result.verify": "Ergebnis und Belege unabhaengig nachrechnen.",
}


class CapabilityDeniedError(RuntimeError):
    """A workflow requested a capability that is not registered."""


@dataclass(frozen=True, slots=True)
class Capability:
    """Describe one built-in operation without a dynamic implementation path."""

    id: str
    description: str
    source_kind: str = "table"
    read_only: bool = True


@dataclass(frozen=True, slots=True)
class CapabilityRegistry:
    """Immutable collection of explicitly allowed built-in capabilities."""

    capabilities: tuple[Capability, ...]

    def __post_init__(self) -> None:
        ids = tuple(item.id for item in self.capabilities)
        if len(ids) != len(set(ids)):
            raise ValueError("Capability-IDs muessen eindeutig sein.")
        if any(not item.read_only for item in self.capabilities):
            raise ValueError("PortableAgent erlaubt nur read-only Capabilities.")
        if any(item.source_kind != "table" for item in self.capabilities):
            raise ValueError("Die aktuelle Registry erlaubt nur Tabellen-Capabilities.")
        unknown = sorted(set(ids) - set(_CAPABILITY_DESCRIPTIONS))
        if unknown:
            raise ValueError("Unbekannte Capability-ID: " + ", ".join(unknown))
        for item in self.capabilities:
            if item.description != _CAPABILITY_DESCRIPTIONS[item.id]:
                raise ValueError(f"Capability-Metadaten sind nicht statisch: {item.id}")

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.capabilities)

    def require(self, *capability_ids: str) -> None:
        """Fail closed when a workflow asks for an unregistered operation."""
        missing = sorted(set(capability_ids) - set(self.ids))
        if missing:
            raise CapabilityDeniedError(
                "Nicht registrierte Capability: " + ", ".join(missing)
            )


DEFAULT_CAPABILITY_REGISTRY = CapabilityRegistry(tuple(
    Capability(capability_id, description)
    for capability_id, description in _CAPABILITY_DESCRIPTIONS.items()
))


def required_execution_capabilities(plan: QueryPlan) -> tuple[str, ...]:
    """Derive the bounded operations needed to execute and verify one plan."""
    required = ["table.source_rows", "result.verify"]
    if plan.filters:
        required.append("table.filter")
    if plan.calculations or plan.group_by is not None:
        required.append("table.aggregate")
    return tuple(required)


def require_temporal_capability(
    registry: CapabilityRegistry,
    plan: QueryPlan,
) -> None:
    """Authorize the specialized first/last-occurrence operation in a plan."""
    aggregations = {item.aggregation for item in plan.calculations}
    if "min" in aggregations:
        registry.require("table.first_occurrence")
    if "max" in aggregations:
        registry.require("table.last_occurrence")
