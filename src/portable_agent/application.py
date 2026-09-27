"""Explicit composition and lifecycle for the local PortableAgent application."""

from __future__ import annotations

import math
from collections.abc import Callable
from threading import RLock

from portable_agent.agent import DocumentWorkflow, TableWorkflow
from portable_agent.llm import (
    LlamaCppClient,
    LlamaCppDocumentAnswerGenerator,
    LlamaCppPlanGenerator,
)
from portable_agent.llm.plan_generator import JsonCompletionClient
from portable_agent.memory import SqliteMemoryRepository
from portable_agent.runtime import (
    LocalAssetInventory,
    LocalLlamaProcessManager,
    discover_local_assets,
)
from portable_agent.sessions import DocumentSessionManager
from portable_agent.web import (
    LOOPBACK_HOST,
    DocumentJsonController,
    MemoryJsonController,
    TableJsonController,
    create_local_http_server,
)


class LocalApplicationStateError(RuntimeError):
    """The local application lifecycle transition is not allowed."""


class LocalDocumentApplication:
    """Owns the composed workflows and explicitly controlled HTTP server."""

    def __init__(
        self,
        workflow: DocumentWorkflow,
        table_workflow: TableWorkflow,
        controller,
        server,
        model_process_manager: LocalLlamaProcessManager | None = None,
    ) -> None:
        self._workflow = workflow
        self._table_workflow = table_workflow
        self._controller = controller
        self._server = server
        self._model_process_manager = model_process_manager
        self._lock = RLock()
        self._serving = False
        self._closed = False

    @property
    def address(self) -> tuple[str, int]:
        host, port = self._server.server_address[:2]
        return str(host), int(port)

    @property
    def active_session_count(self) -> int:
        return self._workflow.active_session_count

    @property
    def pending_table_clarification_count(self) -> int:
        return self._table_workflow.pending_clarification_count

    @property
    def managed_model_running(self) -> bool:
        manager = self._model_process_manager
        return manager is not None and manager.is_running

    @property
    def is_serving(self) -> bool:
        with self._lock:
            return self._serving

    @property
    def is_closed(self) -> bool:
        with self._lock:
            return self._closed

    def serve_forever(self, *, poll_interval: float = 0.25) -> None:
        if (
            isinstance(poll_interval, bool)
            or not isinstance(poll_interval, (int, float))
            or not math.isfinite(poll_interval)
            or poll_interval <= 0
        ):
            raise LocalApplicationStateError(
                "poll_interval muss eine positive endliche Zahl sein."
            )
        with self._lock:
            if self._closed:
                raise LocalApplicationStateError("Die lokale Anwendung ist bereits geschlossen.")
            if self._serving:
                raise LocalApplicationStateError("Die lokale Anwendung laeuft bereits.")
            self._serving = True
        try:
            self._server.serve_forever(poll_interval=float(poll_interval))
        finally:
            with self._lock:
                self._serving = False
            self._finalize()

    def shutdown(self) -> None:
        with self._lock:
            if self._closed:
                return
            serving = self._serving
        if serving:
            self._server.shutdown()
        self._finalize()

    def _finalize(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        first_error: Exception | None = None
        cleanup_actions = [
            self._workflow.release_all,
            self._table_workflow.release_all,
        ]
        if self._model_process_manager is not None:
            cleanup_actions.append(self._model_process_manager.stop)
        cleanup_actions.append(self._server.server_close)
        for cleanup in cleanup_actions:
            try:
                cleanup()
            except Exception as exc:
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error


def create_local_document_application(
    *,
    endpoint: str = "http://127.0.0.1:8080/v1/chat/completions",
    llama_timeout_seconds: float = 120.0,
    completion_client: JsonCompletionClient | None = None,
    sessions: DocumentSessionManager | None = None,
    host: str = LOOPBACK_HOST,
    port: int = 0,
    max_body_bytes: int = 64 * 1024,
    max_results: int = 5,
    min_score: int = 1,
    answer_max_tokens: int = 700,
    asset_inventory_provider: Callable[[], LocalAssetInventory] | None = None,
    model_process_manager: LocalLlamaProcessManager | None = None,
    memory_repository: SqliteMemoryRepository | None = None,
) -> LocalDocumentApplication:
    """Compose and bind the local application without starting its serve loop."""
    if model_process_manager is not None and not isinstance(
        model_process_manager, LocalLlamaProcessManager
    ):
        raise TypeError(
            "model_process_manager muss ein LocalLlamaProcessManager sein."
        )
    if memory_repository is not None and not isinstance(
        memory_repository, SqliteMemoryRepository
    ):
        raise TypeError("memory_repository muss ein SqliteMemoryRepository sein.")
    client = completion_client
    if client is None:
        client = LlamaCppClient(
            endpoint=endpoint,
            timeout_seconds=llama_timeout_seconds,
        )
    generator = LlamaCppDocumentAnswerGenerator(
        client=client,
        max_tokens=answer_max_tokens,
    )
    document_workflow = DocumentWorkflow(
        generator,
        sessions=sessions,
        max_results=max_results,
        min_score=min_score,
    )
    table_workflow = TableWorkflow(LlamaCppPlanGenerator(client=client))
    document_controller = DocumentJsonController(document_workflow)
    table_controller = TableJsonController(table_workflow)
    repository = memory_repository or SqliteMemoryRepository.with_default_path()
    memory_controller = MemoryJsonController(repository)
    server = create_local_http_server(
        document_controller,
        table_controller,
        memory_controller=memory_controller,
        host=host,
        port=port,
        max_body_bytes=max_body_bytes,
        readiness_probe=(
            lambda: client.is_ready(timeout_seconds=1.0)
            if isinstance(client, LlamaCppClient)
            else False
        ),
        asset_inventory_provider=(
            asset_inventory_provider
            if asset_inventory_provider is not None
            else discover_local_assets
        ),
    )
    return LocalDocumentApplication(
        document_workflow,
        table_workflow,
        document_controller,
        server,
        model_process_manager,
    )
