import json
import math
import sys
import unittest
from pathlib import Path
from urllib.error import URLError
from unittest.mock import patch


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from portable_agent.llm import (
    LlamaCppClient,
    LlamaCppResponseError,
    LlamaCppUnavailableError,
)


class LlamaCppClientEndpointTests(unittest.TestCase):
    def test_literal_ipv4_and_ipv6_loopback_endpoints_are_accepted(self):
        ipv4 = LlamaCppClient("http://127.0.0.1:8080/v1/chat/completions")
        ipv6 = LlamaCppClient("http://[::1]:8080/v1/chat/completions")
        self.assertEqual(ipv4.timeout_seconds, 120.0)
        self.assertEqual(ipv6.endpoint, "http://[::1]:8080/v1/chat/completions")

    def test_remote_prefix_userinfo_hostname_and_non_http_tricks_are_rejected(self):
        endpoints = (
            "https://127.0.0.1:8080/v1/chat/completions",
            "http://localhost:8080/v1/chat/completions",
            "http://127.0.0.1:8080@evil.invalid/v1/chat/completions",
            "http://user@127.0.0.1:8080/v1/chat/completions",
            "http://192.0.2.1:8080/v1/chat/completions",
        )
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(ValueError):
                    LlamaCppClient(endpoint)

    def test_missing_invalid_port_path_query_fragment_and_controls_are_rejected(self):
        endpoints = (
            "http://127.0.0.1/v1/chat/completions",
            "http://127.0.0.1:0/v1/chat/completions",
            "http://127.0.0.1:99999/v1/chat/completions",
            "http://127.0.0.1:8080/other",
            "http://127.0.0.1:8080/v1/chat/completions?remote=true",
            "http://127.0.0.1:8080/v1/chat/completions#fragment",
            " http://127.0.0.1:8080/v1/chat/completions",
            "http://127.0.0.1:8080/v1/chat/completions\n",
        )
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(ValueError):
                    LlamaCppClient(endpoint)

    def test_invalid_timeouts_are_rejected(self):
        for timeout in (True, 0, -1, math.inf, math.nan, "10"):
            with self.subTest(timeout=timeout):
                with self.assertRaisesRegex(ValueError, "timeout_seconds"):
                    LlamaCppClient(timeout_seconds=timeout)

    @patch("portable_agent.llm.llama_cpp_client.build_opener")
    def test_request_uses_no_proxy_no_redirect_opener_without_real_network(self, build_opener):
        response_body = {
            "choices": [{"message": {"content": '{"answer":"local"}'}}]
        }
        response = build_opener.return_value.open.return_value.__enter__.return_value
        response.read.return_value = json.dumps(response_body).encode("utf-8")
        client = LlamaCppClient()

        result = client.complete_json([{"role": "user", "content": "synthetic"}])

        self.assertEqual(result, {"answer": "local"})
        handlers = build_opener.call_args.args
        self.assertEqual(handlers[0].proxies, {})
        self.assertEqual(handlers[1].__class__.__name__, "_NoRedirectHandler")
        request = build_opener.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, client.endpoint)
        self.assertEqual(build_opener.return_value.open.call_args.kwargs["timeout"], 120.0)

    @patch("portable_agent.llm.llama_cpp_client.build_opener")
    def test_readiness_uses_matching_loopback_health_without_request_body(self, build_opener):
        response = build_opener.return_value.open.return_value.__enter__.return_value
        response.status = 200
        client = LlamaCppClient("http://127.0.0.1:9090/v1/chat/completions")

        ready = client.is_ready(timeout_seconds=0.75)

        self.assertTrue(ready)
        handlers = build_opener.call_args.args
        self.assertEqual(handlers[0].proxies, {})
        self.assertEqual(handlers[1].__class__.__name__, "_NoRedirectHandler")
        call = build_opener.return_value.open.call_args
        request = call.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:9090/health")
        self.assertEqual(request.method, "GET")
        self.assertIsNone(request.data)
        self.assertEqual(call.kwargs["timeout"], 0.75)

    @patch("portable_agent.llm.llama_cpp_client.build_opener")
    def test_readiness_reports_unavailable_without_raising_network_details(self, build_opener):
        build_opener.return_value.open.side_effect = URLError("offline")

        self.assertFalse(LlamaCppClient().is_ready())

    @patch("portable_agent.llm.llama_cpp_client.build_opener")
    def test_completion_connection_failure_is_typed_as_unavailable(self, build_opener):
        build_opener.return_value.open.side_effect = URLError("synthetic offline")

        with self.assertRaises(LlamaCppUnavailableError):
            LlamaCppClient().complete_json([
                {"role": "user", "content": "synthetic"}
            ])

    @patch("portable_agent.llm.llama_cpp_client.build_opener")
    def test_completion_invalid_json_is_typed_as_response_error(self, build_opener):
        response = build_opener.return_value.open.return_value.__enter__.return_value
        response.read.return_value = b"not-json"

        with self.assertRaises(LlamaCppResponseError):
            LlamaCppClient().complete_json([
                {"role": "user", "content": "synthetic"}
            ])

    def test_invalid_readiness_timeouts_are_rejected(self):
        client = LlamaCppClient()
        for timeout in (True, 0, -1, math.inf, math.nan, "1"):
            with self.subTest(timeout=timeout):
                with self.assertRaisesRegex(ValueError, "readiness timeout_seconds"):
                    client.is_ready(timeout_seconds=timeout)


if __name__ == "__main__":
    unittest.main()
