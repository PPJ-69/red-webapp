from __future__ import annotations

import asyncio
import math
import time
import unittest
from urllib.parse import urlsplit

from backend.app.domain.models import (
    InternalSourceTarget,
    MediaSource,
    SourceResolution,
)
from backend.app.observability.metrics import MetricsRegistry
from backend.app.services.media_resolver import MediaResolver
from backend.app.services.search_service import SearchService
from backend.app.services.stream_service import StreamService
from backend.app.upstream.stream_transport import StreamTransport
from backend.tests.fakes.fake_provider import FakeMediaProvider
from backend.tests.fixtures.fake_cdn import FakeCDN


_SAMPLES = 100
_RELAY_SAMPLES = 30


def _p95_ms(samples: list[float]) -> float:
    rank = math.ceil(0.95 * len(samples))
    return sorted(samples)[rank - 1] * 1000


def _local_cdn_validator(base_url: str):
    expected = urlsplit(base_url)

    def validate(target: str) -> str:
        parsed = urlsplit(target)
        if (
            parsed.scheme != "http"
            or parsed.hostname != expected.hostname
            or parsed.port != expected.port
        ):
            raise ValueError("Test target is outside the local fake CDN.")
        return target

    return validate


class _RelayResolver:
    def __init__(self, cdn_url: str) -> None:
        self._target = InternalSourceTarget(url=f"{cdn_url}/media/sample.avi")

    async def resolve_resolution(
        self, media_id: str, quality: str = "auto"
    ) -> SourceResolution:
        return SourceResolution(
            descriptor=MediaSource(playbackUrl=f"/api/stream/{media_id}"),
            target=self._target,
        )

    def invalidate(self, media_id: str, quality: str = "auto") -> None:
        return


class ServiceLatencyPerformanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_and_uncached_source_resolution_p95_targets(self) -> None:
        provider = FakeMediaProvider()
        search = SearchService(provider)
        resolver = MediaResolver(
            provider,
            ttl_seconds=60,
            metrics_registry=MetricsRegistry(),
        )
        search_samples: list[float] = []
        resolution_samples: list[float] = []

        for index in range(_SAMPLES):
            started = time.perf_counter()
            result = await search.search(query=f"load-{index}")
            search_samples.append(time.perf_counter() - started)
            self.assertEqual(result.page, 1)

            resolver.invalidate("sample-media")
            started = time.perf_counter()
            resolution = await resolver.resolve_resolution("sample-media")
            resolution_samples.append(time.perf_counter() - started)
            self.assertEqual(resolution.descriptor.kind, "relay")

        search_p95 = _p95_ms(search_samples)
        resolution_p95 = _p95_ms(resolution_samples)
        print(
            "Fake-provider latency p95: "
            f"search={search_p95:.2f} ms, "
            f"uncached source resolution={resolution_p95:.2f} ms "
            f"({_SAMPLES} samples each)"
        )
        self.assertLess(search_p95, 1500)
        self.assertLess(resolution_p95, 1000)

    async def test_fake_cdn_relay_first_byte_p95_target(self) -> None:
        cdn = FakeCDN(chunk_delay=0).start()
        transport = StreamTransport(
            target_validator=_local_cdn_validator(cdn.base_url),
            chunk_size=16 * 1024,
            connect_timeout_seconds=2,
            header_timeout_seconds=2,
            idle_timeout_seconds=2,
            total_timeout_seconds=5,
        )
        service = StreamService(_RelayResolver(cdn.base_url), transport)
        samples: list[float] = []
        try:
            for index in range(_RELAY_SAMPLES):
                started = time.perf_counter()
                relay = await service.stream(f"relay-{index}", None)
                try:
                    async for chunk in relay.body:
                        if chunk:
                            samples.append(time.perf_counter() - started)
                            break
                finally:
                    await relay.close()

            relay_p95 = _p95_ms(samples)
            print(
                "Loopback fake-CDN relay first-byte p95: "
                f"{relay_p95:.2f} ms ({len(samples)} samples)"
            )
            self.assertEqual(len(samples), _RELAY_SAMPLES)
            self.assertLess(relay_p95, 1500)
            self.assertTrue(
                await asyncio.to_thread(
                    cdn.wait_for_closed_connections, _RELAY_SAMPLES, 5
                ),
                "The fake CDN retained a connection after a completed sample.",
            )
        finally:
            await transport.aclose()
            cdn.close()


if __name__ == "__main__":
    unittest.main()
