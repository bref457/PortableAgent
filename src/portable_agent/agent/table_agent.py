"""Composition root for one read-only table-analysis session."""

from __future__ import annotations

from dataclasses import dataclass

from portable_agent.analysis import execute_table_plan
from portable_agent.domain import ClarificationRequest, QueryResult
from portable_agent.semantics import (
    SemanticCatalog,
    load_default_semantic_catalog,
    resolve_clarification,
)
from portable_agent.sources import TableSource

from .planning import PlanGenerator, answer_table_question


@dataclass(frozen=True, slots=True)
class TableAgent:
    """Binds one source, one planner and one already validated catalog."""

    source: TableSource
    generator: PlanGenerator
    catalog: SemanticCatalog

    @classmethod
    def with_default_catalog(
        cls,
        source: TableSource,
        generator: PlanGenerator,
    ) -> "TableAgent":
        """Create an agent and load the project catalog exactly once."""
        return cls(
            source=source,
            generator=generator,
            catalog=load_default_semantic_catalog(),
        )

    def ask(self, question: str) -> QueryResult | ClarificationRequest:
        definitions = self.catalog.definitions_for_columns(self.source.columns)
        return answer_table_question(
            self.source,
            question,
            self.generator,
            semantic_definitions=definitions,
            semantic_catalog=self.catalog,
        )

    def resolve(
        self,
        request: ClarificationRequest,
        option_id: str,
    ) -> QueryResult:
        """Execute a selected clarification option without another LLM call."""
        plan = resolve_clarification(request, option_id)
        return execute_table_plan(self.source, plan)
