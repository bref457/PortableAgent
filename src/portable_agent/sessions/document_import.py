"""Explicit file-to-session use case for allowlisted document sources."""

from __future__ import annotations

from pathlib import Path

from portable_agent.sources import open_document_source

from .document_sessions import DocumentSession, DocumentSessionManager


def open_document_session(
    path: str | Path,
    sessions: DocumentSessionManager,
) -> DocumentSession:
    """Open an allowlisted document read-only and keep it only in memory."""
    if not isinstance(sessions, DocumentSessionManager):
        raise TypeError("sessions muss ein DocumentSessionManager sein.")
    source = open_document_source(path)
    return sessions.create(source)
