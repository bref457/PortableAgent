"""Explicit command-line entry point for the local PortableAgent server."""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from portable_agent.application import (
    LocalDocumentApplication,
    create_local_document_application,
)
from portable_agent.runtime import (
    LocalAssetInventory,
    LocalLlamaProcessError,
    LocalLlamaProcessManager,
    build_local_llama_launch_plan,
    discover_local_assets,
)


DEFAULT_PORT = 8765
DEFAULT_LLAMA_ENDPOINT = "http://127.0.0.1:8080/v1/chat/completions"
DEFAULT_LLAMA_TIMEOUT = 120.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="portable-agent",
        description=(
            "Startet die lokale PortableAgent-API ausschliesslich auf 127.0.0.1."
        ),
    )
    parser.add_argument(
        "--port",
        type=_port,
        default=DEFAULT_PORT,
        help=f"Lokaler API-Port (Standard: {DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--llama-endpoint",
        default=DEFAULT_LLAMA_ENDPOINT,
        help="Bereits laufender lokaler llama.cpp-Chat-Completions-Endpunkt.",
    )
    parser.add_argument(
        "--llama-timeout",
        type=_positive_float,
        default=DEFAULT_LLAMA_TIMEOUT,
        help=f"Lokales Modell-Timeout in Sekunden (Standard: {DEFAULT_LLAMA_TIMEOUT:g}).",
    )
    parser.add_argument(
        "--local-runtime",
        help=(
            "Erkannter relativer llama.cpp-Serverpfad; nur gemeinsam mit "
            "--local-model."
        ),
    )
    parser.add_argument(
        "--local-model",
        help=(
            "Erkannter relativer GGUF-Modellpfad; nur gemeinsam mit "
            "--local-runtime."
        ),
    )
    parser.add_argument(
        "--list-local-assets",
        action="store_true",
        help=(
            "Erkannte portable llama.cpp-Runtimes und GGUF-Modelle auflisten, "
            "ohne einen Server oder Prozess zu starten."
        ),
    )
    parser.add_argument(
        "--start-detected-assets",
        action="store_true",
        help=(
            "Startet automatisch, aber nur wenn genau eine lokale Runtime "
            "und genau ein GGUF-Modell erkannt werden."
        ),
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    application_factory: Callable[..., LocalDocumentApplication] = (
        create_local_document_application
    ),
    process_manager_factory: Callable[..., LocalLlamaProcessManager] = (
        LocalLlamaProcessManager
    ),
    project_root: str | Path | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    root = (
        Path(project_root).resolve()
        if project_root is not None
        else Path(__file__).resolve().parents[2]
    )
    manager: LocalLlamaProcessManager | None = None
    try:
        if args.list_local_assets:
            if (
                args.local_runtime is not None
                or args.local_model is not None
                or args.start_detected_assets
            ):
                raise ValueError(
                    "--list-local-assets kann nicht mit einem Modellstart "
                    "kombiniert werden."
                )
            _print_local_assets(discover_local_assets(root))
            return 0
        if args.start_detected_assets:
            if args.local_runtime is not None or args.local_model is not None:
                raise ValueError(
                    "--start-detected-assets kann nicht mit einer expliziten "
                    "Asset-Auswahl kombiniert werden."
                )
            inventory = discover_local_assets(root)
            if len(inventory.llama_runtimes) != 1:
                raise ValueError(
                    "Der automatische Start benoetigt genau eine erkannte "
                    "llama.cpp-Runtime."
                )
            if len(inventory.gguf_models) != 1:
                raise ValueError(
                    "Der automatische Start benoetigt genau ein erkanntes "
                    "GGUF-Modell."
                )
            args.local_runtime = inventory.llama_runtimes[0].relative_path
            args.local_model = inventory.gguf_models[0].relative_path
        if (args.local_runtime is None) != (args.local_model is None):
            raise ValueError(
                "--local-runtime und --local-model muessen gemeinsam angegeben werden."
            )
        if args.local_runtime is not None:
            if args.llama_endpoint != DEFAULT_LLAMA_ENDPOINT:
                raise ValueError(
                    "Der verwaltete lokale Modellstart verwendet den festen "
                    f"Endpunkt {DEFAULT_LLAMA_ENDPOINT}."
                )
            inventory = discover_local_assets(root)
            plan = build_local_llama_launch_plan(
                inventory,
                runtime_path=args.local_runtime,
                model_path=args.local_model,
            )
            manager = process_manager_factory(root)
            manager.start(plan)

        application_options = {
            "endpoint": args.llama_endpoint,
            "llama_timeout_seconds": args.llama_timeout,
            "port": args.port,
        }
        if manager is not None:
            application_options["model_process_manager"] = manager
        application = application_factory(
            **application_options,
        )
    except (LocalLlamaProcessError, OSError, ValueError) as exc:
        if manager is not None:
            manager.stop()
        print(f"PortableAgent konnte nicht gestartet werden: {exc}", file=sys.stderr)
        return 2

    host, port = application.address
    print(f"PortableAgent lokal bereit unter http://{host}:{port}")
    print("Beenden mit Ctrl+C.")
    try:
        application.serve_forever()
    except KeyboardInterrupt:
        print("\nPortableAgent wird beendet.")
    finally:
        try:
            application.shutdown()
        finally:
            if manager is not None:
                manager.stop()
    return 0


def _print_local_assets(inventory: LocalAssetInventory) -> None:
    print("Erkannte portable llama.cpp-Runtimes:")
    if inventory.llama_runtimes:
        for runtime in inventory.llama_runtimes:
            print(f"- {runtime.relative_path} ({runtime.size_bytes} Bytes)")
    else:
        print("- keine")

    print("Erkannte lokale GGUF-Modelle:")
    if inventory.gguf_models:
        for model in inventory.gguf_models:
            print(f"- {model.relative_path} ({model.size_bytes} Bytes)")
    else:
        print("- keine")


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Port muss eine ganze Zahl sein.") from exc
    if not 1 <= port <= 65_535:
        raise argparse.ArgumentTypeError("Port muss zwischen 1 und 65535 liegen.")
    return port


def _positive_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Timeout muss eine Zahl sein.") from exc
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Timeout muss positiv und endlich sein.")
    return number


if __name__ == "__main__":
    raise SystemExit(main())
