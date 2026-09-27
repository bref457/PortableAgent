"""Validated, side-effect-free launch plans for a local llama.cpp server."""

from __future__ import annotations

from dataclasses import dataclass

from .discovery import LocalAssetInventory


LOOPBACK_HOST = "127.0.0.1"
DEFAULT_LLAMA_PORT = 8080
DEFAULT_CONTEXT_SIZE = 4096
MIN_CONTEXT_SIZE = 512
MAX_CONTEXT_SIZE = 131_072
_ALLOWED_RUNTIME_PATHS = frozenset(
    {
        "runtime/llama.cpp/llama-server.exe",
        "runtime/llama.cpp/llama-server",
        "runtime/llama.cpp/bin/llama-server.exe",
        "runtime/llama.cpp/bin/llama-server",
    }
)


class LocalLaunchPlanError(ValueError):
    """Raised when an explicit local launch selection is not safe."""


@dataclass(frozen=True, slots=True)
class LocalLlamaLaunchPlan:
    """A relative executable and fixed argument vector, never a shell string."""

    executable: str
    model_path: str
    port: int
    context_size: int

    @property
    def arguments(self) -> tuple[str, ...]:
        return (
            "--model",
            self.model_path,
            "--host",
            LOOPBACK_HOST,
            "--port",
            str(self.port),
            "--ctx-size",
            str(self.context_size),
        )

    @property
    def command(self) -> tuple[str, ...]:
        return (self.executable, *self.arguments)


def build_local_llama_launch_plan(
    inventory: LocalAssetInventory,
    *,
    runtime_path: str,
    model_path: str,
    port: int = DEFAULT_LLAMA_PORT,
    context_size: int = DEFAULT_CONTEXT_SIZE,
) -> LocalLlamaLaunchPlan:
    """Build an inert argument vector from two explicitly selected assets."""
    if not isinstance(inventory, LocalAssetInventory):
        raise LocalLaunchPlanError("inventory muss ein LocalAssetInventory sein.")
    _validate_clean_relative_path(runtime_path, "runtime_path")
    _validate_clean_relative_path(model_path, "model_path")
    if runtime_path not in _ALLOWED_RUNTIME_PATHS:
        raise LocalLaunchPlanError(
            "runtime_path ist kein erlaubter llama.cpp-Serverpfad."
        )
    model_parts = model_path.split("/")
    if (
        len(model_parts) != 2
        or model_parts[0] != "models"
        or not model_parts[1].casefold().endswith(".gguf")
    ):
        raise LocalLaunchPlanError(
            "model_path muss ein direktes GGUF-Modell unter models sein."
        )
    _validate_integer_range(port, "port", 1, 65_535)
    _validate_integer_range(
        context_size,
        "context_size",
        MIN_CONTEXT_SIZE,
        MAX_CONTEXT_SIZE,
    )

    known_runtimes = {
        runtime.relative_path for runtime in inventory.llama_runtimes
    }
    if runtime_path not in known_runtimes:
        raise LocalLaunchPlanError(
            "Die ausgewaehlte Runtime wurde nicht im lokalen Inventar erkannt."
        )

    known_models = {model.relative_path for model in inventory.gguf_models}
    if model_path not in known_models:
        raise LocalLaunchPlanError(
            "Das ausgewaehlte GGUF-Modell wurde nicht im lokalen Inventar erkannt."
        )

    return LocalLlamaLaunchPlan(
        executable=runtime_path,
        model_path=model_path,
        port=port,
        context_size=context_size,
    )


def _validate_clean_relative_path(value: object, field_name: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise LocalLaunchPlanError(
            f"{field_name} muss ein sauberer relativer Pfad sein."
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise LocalLaunchPlanError(f"{field_name} enthaelt Steuerzeichen.")
    if "\\" in value or value.startswith("/"):
        raise LocalLaunchPlanError(
            f"{field_name} muss den portablen relativen Pfad verwenden."
        )
    parts = value.split("/")
    if ":" in parts[0] or any(part in {"", ".", ".."} for part in parts):
        raise LocalLaunchPlanError(
            f"{field_name} darf den Projektstamm nicht verlassen."
        )


def _validate_integer_range(
    value: object,
    field_name: str,
    minimum: int,
    maximum: int,
) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        raise LocalLaunchPlanError(
            f"{field_name} muss zwischen {minimum} und {maximum} liegen."
        )
