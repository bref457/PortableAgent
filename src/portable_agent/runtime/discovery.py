"""Metadata-only discovery in fixed directories below the project root."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


_LLAMA_RUNTIME_PATHS = (
    Path("runtime/llama.cpp/llama-server.exe"),
    Path("runtime/llama.cpp/llama-server"),
    Path("runtime/llama.cpp/bin/llama-server.exe"),
    Path("runtime/llama.cpp/bin/llama-server"),
)
_MODEL_DIRECTORY = Path("models")


class LocalAssetDiscoveryError(ValueError):
    """Raised when the requested project root is not a usable directory."""


@dataclass(frozen=True, slots=True)
class LocalLlamaRuntime:
    """Metadata for an allowlisted llama.cpp server executable."""

    relative_path: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class LocalGgufModel:
    """Filename metadata for a directly contained GGUF model."""

    name: str
    relative_path: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class LocalAssetInventory:
    """Deterministic snapshot without automatic selection or execution."""

    llama_runtimes: tuple[LocalLlamaRuntime, ...]
    gguf_models: tuple[LocalGgufModel, ...]


def discover_local_assets(project_root: str | Path | None = None) -> LocalAssetInventory:
    """List known local assets without opening them or starting a process.

    Only exact llama.cpp paths below ``runtime/llama.cpp`` and direct ``.gguf``
    children of ``models`` are inspected. Symlinks and nested model directories
    are intentionally ignored.
    """
    root = _validated_project_root(project_root)

    runtimes: list[LocalLlamaRuntime] = []
    for relative_path in _LLAMA_RUNTIME_PATHS:
        candidate = _regular_file_without_symlinks(root, relative_path)
        if candidate is None:
            continue
        runtimes.append(
            LocalLlamaRuntime(
                relative_path=relative_path.as_posix(),
                size_bytes=candidate.stat().st_size,
            )
        )

    models: list[LocalGgufModel] = []
    model_directory = _directory_without_symlinks(root, _MODEL_DIRECTORY)
    if model_directory is not None:
        children = sorted(model_directory.iterdir(), key=lambda path: path.name.casefold())
        for child in children:
            if child.suffix.casefold() != ".gguf" or child.is_symlink() or not child.is_file():
                continue
            relative_path = _MODEL_DIRECTORY / child.name
            models.append(
                LocalGgufModel(
                    name=child.name,
                    relative_path=relative_path.as_posix(),
                    size_bytes=child.stat().st_size,
                )
            )

    return LocalAssetInventory(tuple(runtimes), tuple(models))


def _validated_project_root(project_root: str | Path | None) -> Path:
    if project_root is None:
        root = Path(__file__).resolve().parents[3]
    elif isinstance(project_root, (str, Path)):
        root = Path(project_root)
    else:
        raise LocalAssetDiscoveryError(
            "Der Projektstamm muss eine Zeichenkette oder Path sein."
        )

    if not root.is_dir():
        raise LocalAssetDiscoveryError("Der Projektstamm ist kein Verzeichnis.")
    return root.resolve()


def _directory_without_symlinks(root: Path, relative_path: Path) -> Path | None:
    candidate = root
    for part in relative_path.parts:
        candidate /= part
        if candidate.is_symlink():
            return None
    if not candidate.is_dir():
        return None
    return candidate


def _regular_file_without_symlinks(root: Path, relative_path: Path) -> Path | None:
    candidate = root
    for part in relative_path.parts:
        candidate /= part
        if candidate.is_symlink():
            return None
    if not candidate.is_file():
        return None
    return candidate
