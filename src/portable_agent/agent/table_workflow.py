"""Application boundary for one explicit local table question."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from uuid import uuid4

from portable_agent.domain import ClarificationRequest, QueryResult
from portable_agent.semantics import SemanticCatalog, load_default_semantic_catalog
from portable_agent.sources import TableSource, open_table_source

from .planning import PlanGenerator
from .table_agent import TableAgent


MAX_ID_ATTEMPTS = 10
DEFAULT_MAX_PENDING_CLARIFICATIONS = 32


class TableWorkflowError(ValueError):
    """A temporary table-clarification request is invalid."""


@dataclass(frozen=True, slots=True)
class PendingTableClarification:
    """Public handle for one temporary, locally resolvable clarification."""

    clarification_id: str
    request: ClarificationRequest


@dataclass(frozen=True, slots=True)
class _PendingState:
    source: TableSource
    request: ClarificationRequest


class TableWorkflow:
    """Open one read-only table, answer one question, then release the source."""

    def __init__(
        self,
        generator: PlanGenerator,
        *,
        catalog: SemanticCatalog | None = None,
        id_factory: Callable[[], str] | None = None,
        max_pending_clarifications: int = DEFAULT_MAX_PENDING_CLARIFICATIONS,
    ) -> None:
        if (
            type(max_pending_clarifications) is not int
            or max_pending_clarifications <= 0
        ):
            raise TableWorkflowError(
                "max_pending_clarifications muss eine positive ganze Zahl sein."
            )
        self._generator = generator
        self._catalog = catalog or load_default_semantic_catalog()
        self._id_factory = id_factory or (lambda: uuid4().hex)
        self._max_pending = max_pending_clarifications
        self._pending: dict[str, _PendingState] = {}
        self._lock = RLock()

    @property
    def pending_clarification_count(self) -> int:
        with self._lock:
            return len(self._pending)

    def ask_file(
        self,
        path: str | Path,
        question: str,
        *,
        sheet_name: str | None = None,
    ) -> QueryResult | PendingTableClarification:
        """Answer one question against an explicitly selected local table file."""
        source = open_table_source(path, sheet_name=sheet_name)
        agent = TableAgent(
            source=source,
            generator=self._generator,
            catalog=self._catalog,
        )
        result = agent.ask(question)
        if isinstance(result, ClarificationRequest):
            return self._register_clarification(source, result)
        return result

    def resolve(self, clarification_id: str, option_id: str) -> QueryResult:
        """Resolve one offered option locally and consume the temporary state."""
        clean_id = _nonempty_id(clarification_id, "clarification_id")
        clean_option = _nonempty_id(option_id, "option_id")
        with self._lock:
            try:
                state = self._pending[clean_id]
            except KeyError as exc:
                raise TableWorkflowError(
                    "Tabellen-Rueckfrage wurde nicht gefunden oder bereits aufgeloest."
                ) from exc
            if clean_option not in {item.id for item in state.request.options}:
                raise TableWorkflowError(
                    "Die gewählte Tabellen-Rückfrageoption ist ungültig."
                )
            del self._pending[clean_id]

        agent = TableAgent(
            source=state.source,
            generator=self._generator,
            catalog=self._catalog,
        )
        return agent.resolve(state.request, clean_option)

    def release_all(self) -> int:
        """Drop every unresolved table clarification and its source reference."""
        with self._lock:
            released_count = len(self._pending)
            self._pending.clear()
            return released_count

    def _register_clarification(
        self,
        source: TableSource,
        request: ClarificationRequest,
    ) -> PendingTableClarification:
        with self._lock:
            if len(self._pending) >= self._max_pending:
                raise TableWorkflowError(
                    "Zu viele offene Tabellen-Rueckfragen. Bitte offene Rueckfragen beantworten."
                )
            for _ in range(MAX_ID_ATTEMPTS):
                clarification_id = _nonempty_id(
                    self._id_factory(), "generierte clarification_id"
                )
                if clarification_id not in self._pending:
                    self._pending[clarification_id] = _PendingState(source, request)
                    return PendingTableClarification(clarification_id, request)
        raise TableWorkflowError(
            "Es konnte keine eindeutige Tabellen-Rueckfrage-ID erzeugt werden."
        )


def _nonempty_id(value: str, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise TableWorkflowError(f"{path} muss eine nicht leere Zeichenkette sein.")
    clean = value.strip()
    if len(clean) > 256 or "\x00" in clean:
        raise TableWorkflowError(f"{path} ist ungültig.")
    return clean
