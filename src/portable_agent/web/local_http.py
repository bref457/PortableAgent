"""Loopback-only HTTP transport for the strict local JSON controllers."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock, Thread
from urllib.parse import unquote

from portable_agent.agent import DocumentAnswerError, TableQuestionError, TableWorkflowError
from portable_agent.llm import (
    DocumentGenerationError,
    LlamaCppResponseError,
    LlamaCppUnavailableError,
)
from portable_agent.memory import MemoryError
from portable_agent.runtime import LocalAssetInventory
from portable_agent.sessions import DocumentSessionError
from portable_agent.sources import (
    CsvSourceError,
    DocxSourceError,
    PdfSourceError,
    SourceRoutingError,
    TxtSourceError,
    XlsxSourceError,
    list_sheet_names,
)

from .document_controller import DocumentJsonController, DocumentJsonError
from .memory_controller import MemoryJsonController, MemoryJsonError
from .table_controller import TableJsonController, TableJsonError


LOOPBACK_HOST = "127.0.0.1"
DEFAULT_MAX_BODY_BYTES = 64 * 1024
DEFAULT_MAX_DOCUMENT_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_TABLE_METADATA_BYTES = 64 * 1024
DEFAULT_MAX_TABLE_UPLOAD_BYTES = (
    100 * 1024 * 1024 + MAX_TABLE_METADATA_BYTES + 4
)
DOCUMENT_API_PATH = "/api/document"
DOCUMENT_UPLOAD_PATH = "/api/document-upload"
TABLE_API_PATH = "/api/table"
TABLE_FILE_API_PATH = "/api/table-file"
MEMORY_API_PATH = "/api/memory"
HEALTH_PATH = "/health"
SHUTDOWN_PATH = "/api/shutdown"
_STATIC_ASSET_TYPES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/assets/app.css": ("app.css", "text/css; charset=utf-8"),
    "/assets/modes.css": ("modes.css", "text/css; charset=utf-8"),
    "/assets/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "connect-src 'self'; "
    "img-src 'self'; "
    "font-src 'none'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "frame-ancestors 'none'; "
    "object-src 'none'"
)


class ShutdownJsonError(ValueError):
    """The local shutdown request does not match its fixed JSON shape."""

_CLIENT_ERRORS = (
    DocumentAnswerError,
    DocumentJsonError,
    DocumentSessionError,
    MemoryError,
    MemoryJsonError,
    CsvSourceError,
    DocxSourceError,
    PdfSourceError,
    ShutdownJsonError,
    SourceRoutingError,
    TableJsonError,
    TableQuestionError,
    TableWorkflowError,
    TxtSourceError,
    XlsxSourceError,
)


class LocalHttpConfigurationError(ValueError):
    """The local HTTP adapter was configured outside its safety boundary."""


class _LocalHttpServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        document_controller: DocumentJsonController,
        table_controller: TableJsonController,
        memory_controller: MemoryJsonController | None,
        max_body_bytes: int,
        max_document_upload_bytes: int,
        max_table_upload_bytes: int,
        readiness_probe: Callable[[], bool],
        asset_inventory_provider: Callable[[], LocalAssetInventory],
    ) -> None:
        self.controllers = {
            DOCUMENT_API_PATH: document_controller,
            TABLE_API_PATH: table_controller,
        }
        if memory_controller is not None:
            self.controllers[MEMORY_API_PATH] = memory_controller
        self.max_body_bytes = max_body_bytes
        self.max_document_upload_bytes = max_document_upload_bytes
        self.max_table_upload_bytes = max_table_upload_bytes
        self.readiness_probe = readiness_probe
        self.asset_inventory_provider = asset_inventory_provider
        self.static_assets = _load_static_assets()
        self._shutdown_lock = Lock()
        self._shutdown_requested = False
        super().__init__(server_address, _LocalHttpHandler)

    def request_shutdown(self) -> bool:
        """Request serve-loop shutdown once, without blocking the handler."""
        with self._shutdown_lock:
            if self._shutdown_requested:
                return False
            self._shutdown_requested = True
        Thread(
            target=self.shutdown,
            name="portable-agent-shutdown",
            daemon=True,
        ).start()
        return True


class _LocalHttpHandler(BaseHTTPRequestHandler):
    server_version = "PortableAgent"
    sys_version = ""

    @property
    def local_server(self) -> _LocalHttpServer:
        return self.server  # type: ignore[return-value]

    def do_GET(self) -> None:
        if not self._has_valid_loopback_host():
            self._error(
                HTTPStatus.BAD_REQUEST,
                "invalid_host",
                "Host muss der gebundenen Loopback-Adresse entsprechen.",
            )
            return
        if self.path != HEALTH_PATH:
            asset = self.local_server.static_assets.get(self.path)
            if asset is None:
                self._error(HTTPStatus.NOT_FOUND, "not_found", "Endpunkt wurde nicht gefunden.")
                return
            body, content_type = asset
            self._raw_response(HTTPStatus.OK, body, content_type)
        else:
            try:
                model_ready = self.local_server.readiness_probe() is True
            except Exception:
                model_ready = False
            assets = _local_asset_status(self.local_server.asset_inventory_provider)
            self._json_response(
                HTTPStatus.OK,
                {
                    "assets": assets,
                    "model": {
                        "status": "ready" if model_ready else "unavailable",
                    },
                    "ok": True,
                    "service": "portable-agent",
                    "status": "ready",
                },
            )

    def do_POST(self) -> None:
        if not self._has_valid_loopback_host():
            self._error(
                HTTPStatus.BAD_REQUEST,
                "invalid_host",
                "Host muss der gebundenen Loopback-Adresse entsprechen.",
            )
            return
        is_shutdown = self.path == SHUTDOWN_PATH
        is_document_upload = self.path == DOCUMENT_UPLOAD_PATH
        is_table_file = self.path == TABLE_FILE_API_PATH
        controller = self.local_server.controllers.get(self.path)
        if is_document_upload:
            controller = self.local_server.controllers[DOCUMENT_API_PATH]
        elif is_table_file:
            controller = self.local_server.controllers[TABLE_API_PATH]
        if controller is None and not is_shutdown:
            self._error(HTTPStatus.NOT_FOUND, "not_found", "Endpunkt wurde nicht gefunden.")
            return
        if self.headers.get("Transfer-Encoding") is not None:
            self._error(
                HTTPStatus.BAD_REQUEST,
                "transfer_encoding_not_allowed",
                "Transfer-Encoding ist für diesen lokalen Endpunkt nicht erlaubt.",
            )
            return
        if is_document_upload:
            expected_content_type = "application/octet-stream"
        elif is_table_file:
            expected_content_type = "application/vnd.portable-agent.table"
        else:
            expected_content_type = "application/json"
        if self.headers.get_content_type() != expected_content_type:
            self._error(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                "content_type_required",
                f"Content-Type muss {expected_content_type} sein.",
            )
            return
        charset = self.headers.get_content_charset("utf-8").casefold()
        if not (is_document_upload or is_table_file) and charset != "utf-8":
            self._error(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                "utf8_required",
                "JSON-Requests müssen UTF-8 verwenden.",
            )
            return

        lengths = self.headers.get_all("Content-Length", failobj=[])
        if len(lengths) != 1:
            self._error(
                HTTPStatus.LENGTH_REQUIRED,
                "content_length_required",
                "Genau ein Content-Length-Header ist erforderlich.",
            )
            return
        try:
            content_length = int(lengths[0])
        except (TypeError, ValueError):
            self._error(
                HTTPStatus.BAD_REQUEST,
                "invalid_content_length",
                "Content-Length ist ungültig.",
            )
            return
        if content_length < 1:
            self._error(
                HTTPStatus.BAD_REQUEST,
                "empty_body",
                "JSON-Request darf nicht leer sein.",
            )
            return
        body_limit = (
            self.local_server.max_document_upload_bytes
            if is_document_upload
            else (
                self.local_server.max_table_upload_bytes
                if is_table_file
                else self.local_server.max_body_bytes
            )
        )
        if content_length > body_limit:
            self._error(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "body_too_large",
                "Die lokale Anfrage überschreitet das erlaubte Größenlimit.",
            )
            return

        body = self.rfile.read(content_length)
        if len(body) != content_length:
            self._error(
                HTTPStatus.BAD_REQUEST,
                "incomplete_body",
                "JSON-Request ist unvollstaendig.",
            )
            return
        try:
            if is_document_upload:
                response_json = _open_uploaded_document(
                    controller,
                    self.headers,
                    body,
                )
            elif is_table_file:
                response_json = _handle_table_file(controller, body)
            else:
                request_json = body.decode("utf-8", errors="strict")
            if is_shutdown:
                response_json = _shutdown_response_json(request_json)
            elif not (is_document_upload or is_table_file):
                response_json = controller.handle_json(request_json)
        except UnicodeDecodeError:
            self._error(
                HTTPStatus.BAD_REQUEST,
                "invalid_utf8",
                "JSON-Request ist kein gültiges UTF-8.",
            )
            return
        except LlamaCppUnavailableError:
            self._error(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "local_model_unavailable",
                "Das lokale Modell ist noch nicht bereit oder nicht erreichbar. "
                "Bitte warte kurz und versuche es erneut.",
            )
            return
        except (LlamaCppResponseError, DocumentGenerationError):
            self._error(
                HTTPStatus.BAD_GATEWAY,
                "invalid_local_model_response",
                "Das lokale Modell hat keine gültige Antwort geliefert. "
                "Bitte versuche es erneut oder formuliere deine Frage anders.",
            )
            return
        except _CLIENT_ERRORS as exc:
            self._error(HTTPStatus.BAD_REQUEST, "invalid_request", str(exc))
            return
        except Exception:
            self._error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "internal_error",
                "Interner lokaler Verarbeitungsfehler.",
            )
            return

        self._raw_json_response(HTTPStatus.OK, response_json.encode("utf-8"))
        if is_shutdown:
            self.wfile.flush()
            self.local_server.request_shutdown()

    def log_message(self, format: str, *args) -> None:
        """Disable request logging so paths and local metadata are not emitted."""

    def _has_valid_loopback_host(self) -> bool:
        values = self.headers.get_all("Host", failobj=[])
        if len(values) != 1:
            return False
        port = self.local_server.server_address[1]
        return values[0].casefold() == f"{LOOPBACK_HOST}:{port}"

    def _error(self, status: HTTPStatus, code: str, message: str) -> None:
        self._json_response(
            status,
            {"error": {"code": code, "message": message}, "ok": False},
        )

    def _json_response(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self._raw_json_response(status, body)

    def _raw_json_response(self, status: HTTPStatus, body: bytes) -> None:
        self._raw_response(status, body, "application/json; charset=utf-8")

    def _raw_response(
        self,
        status: HTTPStatus,
        body: bytes,
        content_type: str,
    ) -> None:
        self.send_response(status.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", _CONTENT_SECURITY_POLICY)
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)


def _load_static_assets() -> dict[str, tuple[bytes, str]]:
    static_root = files("portable_agent.web").joinpath("static")
    try:
        return {
            path: (static_root.joinpath(filename).read_bytes(), content_type)
            for path, (filename, content_type) in _STATIC_ASSET_TYPES.items()
        }
    except (FileNotFoundError, OSError) as exc:
        raise LocalHttpConfigurationError(
            "Lokale Weboberflaechen-Ressourcen fehlen oder sind nicht lesbar."
        ) from exc


def _shutdown_response_json(request_json: str) -> str:
    try:
        payload = json.loads(
            request_json,
            object_pairs_hook=_shutdown_object_without_duplicates,
            parse_constant=_reject_shutdown_constant,
        )
    except json.JSONDecodeError as exc:
        raise ShutdownJsonError("Ungültiger Shutdown-Request.") from exc
    if payload != {"operation": "shutdown"}:
        raise ShutdownJsonError(
            "Shutdown-Request muss exakt die Operation shutdown enthalten."
        )
    return json.dumps(
        {"ok": True, "operation": "shutdown", "status": "stopping"},
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _open_uploaded_document(
    controller: DocumentJsonController,
    headers,
    body: bytes,
) -> str:
    filename = _uploaded_filename(headers)
    with TemporaryDirectory(prefix="portable-agent-document-") as temporary:
        local_path = Path(temporary) / filename
        try:
            with local_path.open("xb") as stream:
                stream.write(body)
        except OSError as exc:
            raise DocumentJsonError(
                "Die ausgewählte Datei konnte nicht lokal vorbereitet werden."
            ) from exc
        request_json = json.dumps(
            {"operation": "open_document", "path": str(local_path)},
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        return controller.handle_json(request_json)


def _uploaded_filename(headers) -> str:
    values = headers.get_all("X-PortableAgent-Filename", failobj=[])
    if len(values) != 1 or not values[0]:
        raise DocumentJsonError(
            "Genau ein lokaler Dateiname ist für die Auswahl erforderlich."
        )
    encoded = values[0]
    if len(encoded) > 1_024 or re.search(r"%(?![0-9A-Fa-f]{2})", encoded):
        raise DocumentJsonError("Der lokale Dateiname ist ungültig kodiert.")
    try:
        filename = unquote(encoded, encoding="utf-8", errors="strict")
    except UnicodeError as exc:
        raise DocumentJsonError("Der lokale Dateiname ist kein gültiges UTF-8.") from exc
    if (
        not filename
        or len(filename) > 255
        or filename != filename.strip()
        or filename in {".", ".."}
        or any(ord(character) < 32 for character in filename)
        or any(character in '<>:"/\\|?*' for character in filename)
    ):
        raise DocumentJsonError("Der lokale Dateiname ist ungültig.")
    if Path(filename).suffix.casefold() not in {".txt", ".docx", ".pdf"}:
        raise DocumentJsonError(
            "Bitte wähle ein unterstütztes Dokument im Format TXT, DOCX oder PDF."
        )
    return filename


def _handle_table_file(controller: TableJsonController, body: bytes) -> str:
    metadata, file_bytes = _decode_table_envelope(body)
    operation = metadata["operation"]
    if operation not in {"list_sheets", "ask_table"}:
        raise TableJsonError("Ungültige lokale Tabellen-Dateianfrage.")
    expected = (
        {"operation", "filename"}
        if operation == "list_sheets"
        else {"operation", "filename", "question", "sheet_name"}
        if "sheet_name" in metadata
        else {"operation", "filename", "question"}
    )
    if set(metadata) != expected:
        raise TableJsonError("Ungültige lokale Tabellen-Dateianfrage.")
    filename = _safe_table_filename(metadata["filename"])

    question = None
    sheet_name = None
    if operation == "ask_table":
        question = _table_metadata_string(
            metadata["question"], "question", max_chars=10_000
        )
        if "sheet_name" in metadata:
            sheet_name = _table_metadata_string(
                metadata["sheet_name"], "sheet_name", max_chars=255
            )

    with TemporaryDirectory(prefix="portable-agent-table-") as temporary:
        local_path = Path(temporary) / filename
        try:
            with local_path.open("xb") as stream:
                stream.write(file_bytes)
        except OSError as exc:
            raise TableJsonError(
                "Die ausgewählte Tabelle konnte nicht lokal vorbereitet werden."
            ) from exc

        if operation == "list_sheets":
            extension = local_path.suffix.casefold()
            sheet_names = (
                list_sheet_names(local_path)
                if extension in {".xlsx", ".xlsm"}
                else ()
            )
            return json.dumps(
                {
                    "file_name": filename,
                    "file_type": "excel" if extension in {".xlsx", ".xlsm"} else "csv",
                    "ok": True,
                    "operation": operation,
                    "sheet_names": list(sheet_names),
                },
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )

        request = {
            "operation": "ask_table",
            "path": str(local_path),
            "question": question,
        }
        if sheet_name is not None:
            request["sheet_name"] = sheet_name
        return controller.handle_json(json.dumps(
            request,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ))


def _decode_table_envelope(body: bytes) -> tuple[dict, memoryview]:
    if len(body) < 5:
        raise TableJsonError("Lokale Tabellen-Dateianfrage ist unvollstaendig.")
    metadata_length = int.from_bytes(body[:4], byteorder="big", signed=False)
    if not 0 < metadata_length <= MAX_TABLE_METADATA_BYTES:
        raise TableJsonError("Tabellen-Metadaten überschreiten das erlaubte Limit.")
    file_offset = 4 + metadata_length
    if file_offset >= len(body):
        raise TableJsonError("Die ausgewählte Tabellendatei ist leer.")
    try:
        metadata_text = body[4:file_offset].decode("utf-8", errors="strict")
        metadata = json.loads(
            metadata_text,
            object_pairs_hook=_table_metadata_object_without_duplicates,
            parse_constant=_reject_table_metadata_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TableJsonError("Tabellen-Metadaten sind ungültiges UTF-8/JSON.") from exc
    if type(metadata) is not dict:
        raise TableJsonError("Tabellen-Metadaten müssen ein Objekt sein.")
    operation = _table_metadata_string(
        metadata.get("operation"), "operation", max_chars=64
    )
    metadata["operation"] = operation
    return metadata, memoryview(body)[file_offset:]


def _table_metadata_object_without_duplicates(pairs) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise TableJsonError(f"Tabellen-Metadaten enthalten doppeltes Feld: {key}")
        result[key] = value
    return result


def _reject_table_metadata_constant(value: str) -> None:
    raise TableJsonError(
        f"Nicht standardkonstanter Tabellen-Metadatenwert ist unzulaessig: {value}"
    )


def _table_metadata_string(value, path: str, *, max_chars: int) -> str:
    if type(value) is not str or not value.strip():
        raise TableJsonError(f"{path} muss eine nicht leere Zeichenkette sein.")
    clean = value.strip()
    if len(clean) > max_chars or "\x00" in clean:
        raise TableJsonError(f"{path} ist ungültig.")
    return clean


def _safe_table_filename(value) -> str:
    filename = _table_metadata_string(value, "filename", max_chars=255)
    if (
        filename != value
        or filename in {".", ".."}
        or any(ord(character) < 32 for character in filename)
        or any(character in '<>:"/\\|?*' for character in filename)
    ):
        raise TableJsonError("Der lokale Tabellen-Dateiname ist ungültig.")
    if Path(filename).suffix.casefold() not in {".csv", ".xlsx", ".xlsm"}:
        raise TableJsonError(
            "Bitte wähle eine unterstützte Tabelle im Format CSV, XLSX oder XLSM."
        )
    return filename


def _shutdown_object_without_duplicates(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ShutdownJsonError(
                f"Shutdown-Request enthält doppeltes Feld: {key}"
            )
        result[key] = value
    return result


def _reject_shutdown_constant(value: str) -> None:
    raise ShutdownJsonError(
        f"Nicht standardkonstanter Shutdown-Wert ist unzulaessig: {value}"
    )


def create_local_http_server(
    document_controller: DocumentJsonController,
    table_controller: TableJsonController,
    *,
    memory_controller: MemoryJsonController | None = None,
    host: str = LOOPBACK_HOST,
    port: int = 0,
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
    max_document_upload_bytes: int = DEFAULT_MAX_DOCUMENT_UPLOAD_BYTES,
    max_table_upload_bytes: int = DEFAULT_MAX_TABLE_UPLOAD_BYTES,
    readiness_probe: Callable[[], bool] | None = None,
    asset_inventory_provider: Callable[[], LocalAssetInventory] | None = None,
) -> ThreadingHTTPServer:
    """Create, but do not start, a strictly IPv4-loopback HTTP server."""
    if not isinstance(document_controller, DocumentJsonController):
        raise TypeError(
            "document_controller muss ein DocumentJsonController sein."
        )
    if not isinstance(table_controller, TableJsonController):
        raise TypeError("table_controller muss ein TableJsonController sein.")
    if memory_controller is not None and not isinstance(
        memory_controller, MemoryJsonController
    ):
        raise TypeError("memory_controller muss ein MemoryJsonController sein.")
    if host != LOOPBACK_HOST:
        raise LocalHttpConfigurationError(
            "Der lokale HTTP-Adapter darf nur an 127.0.0.1 binden."
        )
    if type(port) is not int or not 0 <= port <= 65_535:
        raise LocalHttpConfigurationError("port muss zwischen 0 und 65535 liegen.")
    if type(max_body_bytes) is not int or max_body_bytes <= 0:
        raise LocalHttpConfigurationError(
            "max_body_bytes muss eine positive ganze Zahl sein."
        )
    if (
        type(max_document_upload_bytes) is not int
        or max_document_upload_bytes <= 0
    ):
        raise LocalHttpConfigurationError(
            "max_document_upload_bytes muss eine positive ganze Zahl sein."
        )
    if type(max_table_upload_bytes) is not int or max_table_upload_bytes <= 0:
        raise LocalHttpConfigurationError(
            "max_table_upload_bytes muss eine positive ganze Zahl sein."
        )
    if readiness_probe is not None and not callable(readiness_probe):
        raise LocalHttpConfigurationError("readiness_probe muss aufrufbar sein.")
    if asset_inventory_provider is not None and not callable(asset_inventory_provider):
        raise LocalHttpConfigurationError(
            "asset_inventory_provider muss aufrufbar sein."
        )
    probe = readiness_probe or (lambda: False)
    inventory_provider = asset_inventory_provider or (
        lambda: LocalAssetInventory((), ())
    )
    return _LocalHttpServer(
        (host, port),
        document_controller,
        table_controller,
        memory_controller,
        max_body_bytes,
        max_document_upload_bytes,
        max_table_upload_bytes,
        probe,
        inventory_provider,
    )


def _local_asset_status(
    provider: Callable[[], LocalAssetInventory],
) -> dict[str, object]:
    try:
        inventory = provider()
        if not isinstance(inventory, LocalAssetInventory):
            raise TypeError("Ungültiger Asset-Snapshot.")
    except Exception:
        return {
            "gguf_models": {"available": False, "count": 0},
            "llama_runtime": {"available": False, "count": 0},
            "status": "unavailable",
        }

    runtime_count = len(inventory.llama_runtimes)
    model_count = len(inventory.gguf_models)
    return {
        "gguf_models": {"available": model_count > 0, "count": model_count},
        "llama_runtime": {
            "available": runtime_count > 0,
            "count": runtime_count,
        },
        "status": "ready",
    }
