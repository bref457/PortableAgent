"""Application boundary for the temporary local document lifecycle."""

from __future__ import annotations

from pathlib import Path

from portable_agent.domain import DocumentAnswer
from portable_agent.sessions import (
    DocumentSession,
    DocumentSessionManager,
    open_document_session,
)

from .document_agent import DocumentAnswerGenerator
from .session_document_agent import SessionDocumentAgent


class DocumentWorkflow:
    """Composes document import, grounded questions and explicit release."""

    def __init__(
        self,
        generator: DocumentAnswerGenerator,
        *,
        sessions: DocumentSessionManager | None = None,
        max_results: int = 5,
        min_score: int = 1,
    ) -> None:
        if sessions is not None and not isinstance(sessions, DocumentSessionManager):
            raise TypeError("sessions muss ein DocumentSessionManager sein.")
        self._sessions = sessions or DocumentSessionManager()
        self._agent = SessionDocumentAgent(
            sessions=self._sessions,
            generator=generator,
            max_results=max_results,
            min_score=min_score,
        )

    @property
    def active_session_count(self) -> int:
        return self._sessions.count

    def list_sessions(self) -> tuple[DocumentSession, ...]:
        return self._sessions.list_sessions()

    def open_document(self, path: str | Path) -> DocumentSession:
        return open_document_session(path, self._sessions)

    def ask(self, session_id: str, question: str) -> DocumentAnswer:
        return self._agent.ask(session_id, question)

    def release(self, session_id: str) -> DocumentSession:
        return self._sessions.release(session_id)

    def release_all(self) -> int:
        return self._sessions.release_all()
