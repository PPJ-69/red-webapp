from __future__ import annotations

import asyncio
import ctypes
import os
import sys
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from backend.app.domain.models import InternalSourceTarget, MediaSource, SourceResolution
from backend.app.services.stream_service import RelayResponse, StreamService
from backend.app.upstream.stream_transport import StreamTransport
from backend.tests.fixtures.fake_cdn import FakeCDN, FakeCDNFault


_SYNTHETIC_SIZE = 128 * 1024 * 1024
_MAX_RSS_GROWTH = 48 * 1024 * 1024


class _SyntheticResolver:
    def __init__(self, cdn_url: str) -> None:
        self._cdn_url = cdn_url

    async def resolve_resolution(
        self, media_id: str, quality: str = "auto"
    ) -> SourceResolution:
        return SourceResolution(
            descriptor=MediaSource(playbackUrl=f"/api/stream/{media_id}"),
            target=InternalSourceTarget(
                url=f"{self._cdn_url}/synthetic/{_SYNTHETIC_SIZE}"
            ),
        )

    def invalidate(self, media_id: str, quality: str = "auto") -> None:
        return


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


def _rss_bytes() -> int:
    if sys.platform == "win32":
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemoryCounters),
            wintypes.DWORD,
        )
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        if not psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            raise OSError("GetProcessMemoryInfo failed.")
        return int(counters.WorkingSetSize)

    statm = Path("/proc/self/statm")
    if statm.exists():
        resident_pages = int(statm.read_text(encoding="ascii").split()[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE")

    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


class RelayMemoryPerformanceTests(unittest.TestCase):
    def test_large_concurrent_relay_stays_bounded_and_cancellation_closes_upstream(self) -> None:
        async def scenario() -> None:
            cdn = FakeCDN(chunk_delay=0.05).start()
            transport = StreamTransport(
                target_validator=_local_cdn_validator(cdn.base_url),
                chunk_size=16 * 1024,
                connect_timeout_seconds=2,
                header_timeout_seconds=2,
                idle_timeout_seconds=10,
                total_timeout_seconds=120,
            )
            service = StreamService(_SyntheticResolver(cdn.base_url), transport)
            held: list[RelayResponse] = []
            try:
                baseline = _rss_bytes()
                cdn.set_fault(FakeCDNFault.SLOW)
                held = [
                    await service.stream(f"cancel-{index}", None)
                    for index in range(3)
                ]

                first_chunks = [asyncio.Event() for _ in held]

                async def hold_open(
                    relay: RelayResponse, first_chunk: asyncio.Event
                ) -> None:
                    try:
                        async for chunk in relay.body:
                            if chunk:
                                first_chunk.set()
                                await asyncio.Event().wait()
                    finally:
                        await relay.close()

                holding_tasks = [
                    asyncio.create_task(hold_open(relay, event))
                    for relay, event in zip(held, first_chunks)
                ]
                for first_chunk in first_chunks:
                    await asyncio.wait_for(first_chunk.wait(), timeout=5)

                cdn.set_fault(None)
                large = await service.stream("large", None)
                main_first_chunk = asyncio.Event()
                received = 0
                peak = baseline

                async def drain_large() -> None:
                    nonlocal received, peak
                    chunk_number = 0
                    async for chunk in large.body:
                        received += len(chunk)
                        chunk_number += 1
                        if chunk_number == 1:
                            main_first_chunk.set()
                        if chunk_number % 64 == 0:
                            peak = max(peak, _rss_bytes())

                drain_task = asyncio.create_task(drain_large())
                await asyncio.wait_for(main_first_chunk.wait(), timeout=5)
                for task in holding_tasks:
                    task.cancel()
                results = await asyncio.gather(*holding_tasks, return_exceptions=True)
                self.assertTrue(
                    all(isinstance(result, asyncio.CancelledError) for result in results)
                )
                await drain_task
                peak = max(peak, _rss_bytes())

                self.assertEqual(received, _SYNTHETIC_SIZE)
                self.assertLess(
                    peak - baseline,
                    _MAX_RSS_GROWTH,
                    f"RSS grew by {(peak - baseline) / (1024 * 1024):.1f} MiB",
                )
                opened, closed, active = cdn.connection_counts
                self.assertGreaterEqual(opened, 4)
                self.assertTrue(
                    await asyncio.to_thread(
                        cdn.wait_for_closed_connections, opened, 10
                    ),
                    "The fake CDN retained an upstream connection after cancellation.",
                )
                opened, closed, active = cdn.connection_counts
                self.assertEqual(active, 0)
                self.assertEqual(opened, closed)
                print(
                    "Relay RSS increase: "
                    f"{(peak - baseline) / (1024 * 1024):.1f} MiB "
                    f"(limit: {_MAX_RSS_GROWTH / (1024 * 1024):.0f} MiB)"
                )
            finally:
                for relay in held:
                    await relay.close()
                await transport.aclose()
                cdn.close()

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
