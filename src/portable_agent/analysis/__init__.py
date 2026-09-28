"""Deterministic local analysis engines."""

from .document_retrieval import (
    RetrievalMatch,
    RetrievalQueryError,
    RetrievalResult,
    search_document,
)
from .table_engine import PlanExecutionError, count_matching_rows
from .verification import (
    ResultVerificationError,
    execute_table_plan,
    execute_verified_table_plan,
    verify_table_result,
)

__all__ = [
    "PlanExecutionError",
    "RetrievalMatch",
    "RetrievalQueryError",
    "RetrievalResult",
    "ResultVerificationError",
    "count_matching_rows",
    "execute_table_plan",
    "execute_verified_table_plan",
    "search_document",
    "verify_table_result",
]
