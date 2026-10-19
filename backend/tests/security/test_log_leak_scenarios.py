from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.search import router as search_router
from backend.app.config import AppEnvironment, Settings
from backend.app.dependencies import get_upstream_provider
from backend.app.domain.errors import register_exception_handlers
from backend.app.domain.models import InternalSourceTarget
from backend.app.observability.logging import (
    configure_logging,
    install_request_context,
)
from backend.app.observability.metrics import MetricsRegistry
from backend.tests.conftest import fake_cdn_server
from backend.tests.fakes.fake_provider import FakeMediaProvider, FakeProviderFault
from backend.tests.fixtures.fake_cdn import FakeCDNFault
from backend.tests.integration.test_stream_relay import _service, _test_app

_CANARIES = (
    "provider-token-canary",
    "signed-url-canary",
    "cookie-canary",
    "session-state-canary",
    "query-token-canary",
)


def _authorization_header() -> dict[str, str]:
    return {"Authorization": " ".join(("Bearer", _CANARIES[0]))}


class _CanaryProvider(FakeMediaProvider):
    async def resolve_source(
        self, media_id: str, quality: str
    ) -> InternalSourceTarget:
        return InternalSourceTarget(
            url=(
                f"{self._cdn_base_url}/media/{media_id}-{quality}.avi"
                "?X-Amz-Signature=signed-url-canary&token=query-token-canary"
            ),
            headers={
                "Authorization": "Bearer provider-token-canary",
                "Cookie": "session=cookie-canary",
                "X-Session-State": "session-state-canary",
                **_authorization_header(),
            },
        )


class LogLeakScenarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = configure_logging()
        self.handler = self.logger.handlers[0]
        self.previous_stream = self.handler.stream
        self.output = io.StringIO()
        self.handler.stream = self.output

    def tearDown(self) -> None:
        self.handler.flush()
        self.handler.stream = self.previous_stream

    def test_upstream_status_failures_do_not_leak_canaries(self) -> None:
        for fault, expected_status in (
            (FakeCDNFault.UNAUTHORIZED, 502),
            (FakeCDNFault.FORBIDDEN, 403),
            (FakeCDNFault.RATE_LIMITED, 429),
        ):
            with self.subTest(fault=fault), fake_cdn_server() as cdn:
                cdn.set_fault(fault)
                service, transport = _service(
                    cdn.base_url,
                    provider=_CanaryProvider(cdn_base_url=cdn.base_url),
                )
                app = _test_app(service)
                try:
                    with TestClient(app, raise_server_exceptions=False) as client:
                        response = client.get(
                            "/api/stream/sample-media",
                            headers={
                                "Authorization": "Bearer provider-token-canary",
                                "Cookie": "session=cookie-canary",
                                "X-Session-State": "session-state-canary",
                                **_authorization_header(),
                            },
                        )
                finally:
                    asyncio.run(transport.aclose())

                self.assertEqual(response.status_code, expected_status)
                self._assert_no_canaries(self.output.getvalue())
                self._assert_metrics_have_no_labels(app.state.metrics)
                self.output.seek(0)
                self.output.truncate(0)

    def test_timeout_and_midstream_disconnect_do_not_leak_canaries(self) -> None:
        for fault in (
            FakeCDNFault.SLOW,
            FakeCDNFault.MID_STREAM_DISCONNECT,
        ):
            with self.subTest(fault=fault), fake_cdn_server(
                chunk_delay=0.05
            ) as cdn:
                cdn.set_fault(fault)
                service, transport = _service(
                    cdn.base_url,
                    provider=_CanaryProvider(cdn_base_url=cdn.base_url),
                    idle_timeout_seconds=0.02 if fault is FakeCDNFault.SLOW else 1,
                )
                app = _test_app(service)
                try:
                    with TestClient(app, raise_server_exceptions=False) as client:
                        response = client.get(
                            "/api/stream/sample-media",
                            headers={
                                "Authorization": "Bearer provider-token-canary",
                                "Cookie": "session=cookie-canary",
                                "X-Session-State": "session-state-canary",
                                **_authorization_header(),
                            },
                        )
                finally:
                    asyncio.run(transport.aclose())

                self.assertEqual(response.status_code, 200)
                self.assertGreater(
                    app.state.metrics.snapshot()[
                        "stream_upstream_errors_total"
                    ]["value"],
                    0,
                )
                self._assert_no_canaries(self.output.getvalue())
                self._assert_metrics_have_no_labels(app.state.metrics)
                self.output.seek(0)
                self.output.truncate(0)

    def test_malformed_upstream_item_does_not_leak_canaries(self) -> None:
        app = FastAPI()
        app.state.settings = Settings(AppEnvironment.TEST)
        app.state.metrics = MetricsRegistry()
        app.include_router(search_router)
        register_exception_handlers(app)
        install_request_context(app)
        app.dependency_overrides[get_upstream_provider] = lambda: FakeMediaProvider(
            {"search": FakeProviderFault.MALFORMED_ITEM}
        )
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get(
                    "/api/search",
                    headers={
                        "Authorization": "Bearer provider-token-canary",
                        "Cookie": "session=cookie-canary",
                        "X-Session-State": "session-state-canary",
                        **_authorization_header(),
                    },
                )
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 500)
        self._assert_no_canaries(self.output.getvalue())
        self._assert_metrics_have_no_labels(app.state.metrics)

    def test_metrics_snapshot_is_emitted_as_structured_stdout_log(self) -> None:
        from backend.app.main import app

        with patch.dict(os.environ, {**os.environ, "APP_ENV": "test"}, clear=True):
            with TestClient(app):
                pass

        lines = [json.loads(line) for line in self.output.getvalue().splitlines()]
        snapshot = next(line for line in lines if line["message"] == "metrics_snapshot")
        self.assertIn("direct_vs_relay_ratio", snapshot["metrics"])
        self.assertTrue(
            all("labels" not in value for value in snapshot["metrics"].values())
        )

    def _assert_no_canaries(self, logged: str) -> None:
        for canary in _CANARIES:
            self.assertNotIn(canary, logged)

    def _assert_metrics_have_no_labels(self, registry: MetricsRegistry) -> None:
        snapshot = json.dumps(registry.snapshot())
        self.assertTrue(
            all(canary not in snapshot for canary in _CANARIES)
        )
        self.assertNotIn("labels", snapshot)


if __name__ == "__main__":
    unittest.main()
