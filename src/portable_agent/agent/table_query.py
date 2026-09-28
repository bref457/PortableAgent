"""Small agent-core use case from untrusted plan JSON to cited result."""

from __future__ import annotations

from typing import Any

from portable_agent.analysis import execute_verified_table_plan
from portable_agent.domain import QueryResult
from portable_agent.plans import query_plan_from_dict
from portable_agent.sources import TableSource


def run_table_query(source: TableSource, plan_payload: Any) -> QueryResult:
    """Decode, validate, execute and verify one model-produced table plan."""
    plan = query_plan_from_dict(plan_payload)
    return execute_verified_table_plan(source, plan)
