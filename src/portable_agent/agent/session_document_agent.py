"""Document-question use case bound to temporary in-memory sessions."""

from __future__ import annotations

from dataclasses import dataclass

from portable_agent.agent.document_agent import (
    DocumentAgent,
    DocumentAnswerGenerator,
)
from portable_agent.domain import DocumentAnswer
from portable_agent.sessions import DocumentSessionManager


@dataclass(frozen=True, slots=True)
class SessionDocumentAgent:
    """Answers questions only for a currently active document session."""

    sessions: DocumentSessionManager
    generator: DocumentAnswerGenerator
    max_results: int = 5
    min_score: int = 1

    def ask(self, session_id: str, question: str) -> DocumentAnswer:
        session = self.sessions.get(session_id)
        return DocumentAgent(
            source=session.source,
            generator=self.generator,
            max_results=self.max_results,
            min_score=self.min_score,
        ).ask(question)
