"""Explicit lifecycle for one validated local llama.cpp child process."""

from __future__ import annotations

import math
import subprocess
from collections.abc import Callable
from pathlib import Path
from threading import RLock
from typing import Protocol

from .discovery import LocalAssetDiscoveryError, discover_local_assets
from .launch_plan import (
    LocalLaunchPlanError,
    LocalLlamaLaunchPlan,
    build_local_llama_launch_plan,
)


class LocalLlamaProcessError(RuntimeError):
    """Base error for a rejected or failed managed process operation."""


class LocalLlamaProcessStateError(LocalLlamaProcessError):
    """Raised when the requested lifecycle transition is not allowed."""


class _ProcessHandle(Protocol):
    def poll(self) -> int | None: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...


class LocalLlamaProcessManager:
    """Starts and stops only the child process created from an explicit plan."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        stop_timeout_seconds: float = 5.0,
        process_factory: Callable[..., _ProcessHandle] | None = None,
    ) -> None:
        if (
            isinstance(stop_timeout_seconds, bool)
            or not isinstance(stop_timeout_seconds, (int, float))
            or not math.isfinite(stop_timeout_seconds)
            or stop_timeout_seconds <= 0
        ):
            raise LocalLlamaProcessError(
                "stop_timeout_seconds muss eine positive endliche Zahl sein."
            )
        try:
            discover_local_assets(project_root)
        except LocalAssetDiscoveryError as exc:
            raise LocalLlamaProcessError(str(exc)) from exc
        if process_factory is not None and not callable(process_factory):
            raise LocalLlamaProcessError("process_factory muss aufrufbar sein.")

        self._project_root = Path(project_root).resolve()
        self._stop_timeout_seconds = float(stop_timeout_seconds)
        self._process_factory = (
            process_factory if process_factory is not None else subprocess.Popen
        )
        self._process: _ProcessHandle | None = None
        self._lock = RLock()

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.poll() is None

    def start(self, plan: LocalLlamaLaunchPlan) -> None:
        if not isinstance(plan, LocalLlamaLaunchPlan):
            raise LocalLlamaProcessError(
                "plan muss ein LocalLlamaLaunchPlan sein."
            )
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                raise LocalLlamaProcessStateError(
                    "Der verwaltete llama.cpp-Prozess laeuft bereits."
                )
            self._process = None
            verified_plan = self._revalidate(plan)
            try:
                process = self._process_factory(
                    verified_plan.command,
                    cwd=str(self._project_root),
                    shell=False,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except OSError as exc:
                raise LocalLlamaProcessError(
                    "Der lokale llama.cpp-Prozess konnte nicht gestartet werden."
                ) from exc
            self._process = process

    def stop(self) -> bool:
        with self._lock:
            process = self._process
            if process is None:
                return False
            if process.poll() is not None:
                self._process = None
                return False

            process.terminate()
            try:
                process.wait(timeout=self._stop_timeout_seconds)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=self._stop_timeout_seconds)
            self._process = None
            return True

    def _revalidate(self, plan: LocalLlamaLaunchPlan) -> LocalLlamaLaunchPlan:
        inventory = discover_local_assets(self._project_root)
        try:
            verified = build_local_llama_launch_plan(
                inventory,
                runtime_path=plan.executable,
                model_path=plan.model_path,
                port=plan.port,
                context_size=plan.context_size,
            )
        except LocalLaunchPlanError as exc:
            raise LocalLlamaProcessError(str(exc)) from exc
        if verified != plan:
            raise LocalLlamaProcessError("Der lokale Startplan ist nicht unveraendert.")
        return verified
