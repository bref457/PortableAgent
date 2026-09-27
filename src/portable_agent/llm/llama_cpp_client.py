"""Minimal local llama.cpp client with no remote fallback."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from ipaddress import ip_address
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)


LLAMA_CPP_CHAT_PATH = "/v1/chat/completions"
LLAMA_CPP_HEALTH_PATH = "/health"


class LlamaCppError(RuntimeError):
    """Raised when the local inference endpoint cannot answer safely."""


class LlamaCppUnavailableError(LlamaCppError):
    """The fixed local inference endpoint is not reachable or not ready."""


class LlamaCppResponseError(LlamaCppError):
    """The reached local endpoint returned an unusable response."""


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True, slots=True)
class LlamaCppClient:
    endpoint: str = "http://127.0.0.1:8080/v1/chat/completions"
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        _validate_local_endpoint(self.endpoint)
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds muss eine positive endliche Zahl sein.")

    def complete_json(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 500,
        temperature: float = 0.0,
    ) -> dict:
        _validate_local_endpoint(self.endpoint)
        payload = json.dumps(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
            }
        ).encode("utf-8")
        request = Request(
            self.endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            opener = build_opener(ProxyHandler({}), _NoRedirectHandler())
            with opener.open(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise LlamaCppResponseError(
                "llama.cpp hat die lokale Anfrage abgelehnt."
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise LlamaCppUnavailableError(
                "Der lokale llama.cpp-Endpunkt ist nicht erreichbar."
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LlamaCppResponseError(
                "llama.cpp lieferte keine gueltige JSON-Antwort."
            ) from exc

        try:
            content = body["choices"][0]["message"]["content"]
            result = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LlamaCppResponseError(
                "llama.cpp lieferte kein gueltiges JSON-Objekt."
            ) from exc
        if not isinstance(result, dict):
            raise LlamaCppResponseError(
                "Die Modellantwort muss ein JSON-Objekt sein."
            )
        return result

    def is_ready(self, *, timeout_seconds: float = 1.0) -> bool:
        """Check only the matching local llama.cpp health endpoint."""
        _validate_local_endpoint(self.endpoint)
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError(
                "readiness timeout_seconds muss eine positive endliche Zahl sein."
            )
        parsed = urlsplit(self.endpoint)
        health_endpoint = urlunsplit(
            (parsed.scheme, parsed.netloc, LLAMA_CPP_HEALTH_PATH, "", "")
        )
        request = Request(
            health_endpoint,
            headers={"Accept": "application/json"},
            method="GET",
        )
        try:
            opener = build_opener(ProxyHandler({}), _NoRedirectHandler())
            with opener.open(request, timeout=float(timeout_seconds)) as response:
                status = response.status
        except (HTTPError, URLError, TimeoutError, OSError):
            return False
        return type(status) is int and 200 <= status < 300


def _validate_local_endpoint(endpoint: str) -> None:
    if type(endpoint) is not str or not endpoint or endpoint != endpoint.strip():
        raise ValueError("Der llama.cpp-Endpunkt muss eine saubere URL sein.")
    if any(ord(character) < 32 or ord(character) == 127 for character in endpoint):
        raise ValueError("Der llama.cpp-Endpunkt enthaelt unzulaessige Steuerzeichen.")
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Der llama.cpp-Endpunkt ist keine gueltige URL.") from exc
    if parsed.scheme != "http":
        raise ValueError("Der llama.cpp-Endpunkt muss lokales HTTP verwenden.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Der llama.cpp-Endpunkt darf keine Benutzerinformationen enthalten.")
    if parsed.hostname is None or "%" in parsed.hostname:
        raise ValueError("Der llama.cpp-Endpunkt benoetigt eine literale Loopback-IP.")
    try:
        host = ip_address(parsed.hostname)
    except ValueError as exc:
        raise ValueError(
            "Der llama.cpp-Endpunkt benoetigt eine literale Loopback-IP."
        ) from exc
    if not host.is_loopback:
        raise ValueError("Der llama.cpp-Endpunkt muss eine Loopback-IP verwenden.")
    if port is None or not 1 <= port <= 65_535:
        raise ValueError("Der llama.cpp-Endpunkt benoetigt einen gueltigen Port.")
    if parsed.path != LLAMA_CPP_CHAT_PATH:
        raise ValueError(
            f"Der llama.cpp-Endpunkt muss den Pfad {LLAMA_CPP_CHAT_PATH} verwenden."
        )
    if parsed.query or parsed.fragment:
        raise ValueError(
            "Der llama.cpp-Endpunkt darf weder Queryparameter noch Fragment enthalten."
        )
