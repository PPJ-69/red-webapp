from __future__ import annotations

import http.client
import time
import unittest
import urllib.error
import urllib.request

from backend.tests.conftest import fake_cdn_server
from backend.tests.fixtures.fake_cdn import FakeCDNFault, iter_synthetic_body


class FakeCDNTests(unittest.TestCase):
    def test_sample_fixture_is_a_small_avi_video(self) -> None:
        with fake_cdn_server() as cdn:
            with urllib.request.urlopen(
                f"{cdn.base_url}/media/sample-media-auto.avi", timeout=2
            ) as response:
                body = response.read()

        self.assertLess(cdn.sample_size, 1024)
        self.assertEqual(body[:4], b"RIFF")
        self.assertEqual(body[8:12], b"AVI ")
        self.assertIn(b"vids", body)
        self.assertIn(b"00db", body)

    def test_closed_open_ended_and_suffix_ranges(self) -> None:
        with fake_cdn_server() as cdn:
            cases = (
                ("bytes=4-11", 4, 8),
                ("bytes=4-", 4, cdn.sample_size - 4),
                ("bytes=-8", cdn.sample_size - 8, 8),
            )
            for range_header, offset, length in cases:
                with self.subTest(range_header=range_header):
                    request = urllib.request.Request(
                        f"{cdn.base_url}/media/sample-media-auto.avi",
                        headers={"Range": range_header},
                    )
                    with urllib.request.urlopen(request, timeout=2) as response:
                        body = response.read()

                    self.assertEqual(response.status, 206)
                    self.assertEqual(len(body), length)
                    self.assertEqual(body, cdn.sample_bytes[offset : offset + length])
                    self.assertEqual(
                        response.headers["Content-Range"],
                        f"bytes {offset}-{offset + length - 1}/{cdn.sample_size}",
                    )
                    self.assertEqual(response.headers["Accept-Ranges"], "bytes")

    def test_unsatisfiable_range_returns_416_with_known_size(self) -> None:
        with fake_cdn_server() as cdn:
            request = urllib.request.Request(
                f"{cdn.base_url}/media/sample.avi",
                headers={"Range": "bytes=999999-"},
            )
            with self.assertRaises(urllib.error.HTTPError) as raised:
                urllib.request.urlopen(request, timeout=2)
            raised.exception.close()

        self.assertEqual(raised.exception.code, 416)
        self.assertEqual(
            raised.exception.headers["Content-Range"],
            f"bytes */{cdn.sample_size}",
        )

    def test_synthetic_large_stream_is_generated_in_bounded_chunks(self) -> None:
        size = 4 * 1024 * 1024
        self.assertLessEqual(max(map(len, iter_synthetic_body(size))), 16 * 1024)

        with fake_cdn_server() as cdn:
            request = urllib.request.Request(
                f"{cdn.base_url}/synthetic/{size}",
                headers={"Range": "bytes=250-761"},
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                body = response.read()

        self.assertEqual(response.status, 206)
        self.assertEqual(response.headers["Content-Range"], f"bytes 250-761/{size}")
        self.assertEqual(body, bytes(index % 251 for index in range(250, 762)))

    def test_status_faults_fire_with_expected_status(self) -> None:
        expected = {
            FakeCDNFault.UNAUTHORIZED: 401,
            FakeCDNFault.FORBIDDEN: 403,
            FakeCDNFault.NOT_FOUND: 404,
            FakeCDNFault.RATE_LIMITED: 429,
            FakeCDNFault.SERVER_ERROR: 500,
        }
        with fake_cdn_server() as cdn:
            for fault, status in expected.items():
                with self.subTest(fault=fault):
                    cdn.set_fault(fault)
                    with self.assertRaises(urllib.error.HTTPError) as raised:
                        urllib.request.urlopen(
                            f"{cdn.base_url}/media/sample.avi", timeout=2
                        )
                    self.assertEqual(raised.exception.code, status)
                    if status == 429:
                        self.assertEqual(raised.exception.headers["Retry-After"], "1")
                    raised.exception.close()

    def test_expired_signature_fault_fires(self) -> None:
        with fake_cdn_server() as cdn:
            with self.assertRaises(urllib.error.HTTPError) as raised:
                urllib.request.urlopen(
                    f"{cdn.base_url}/media/sample.avi?signature=expired", timeout=2
                )
            raised.exception.close()

        self.assertEqual(raised.exception.code, 403)

    def test_required_auth_header_forces_relay_behavior(self) -> None:
        with fake_cdn_server() as cdn:
            cdn.set_fault(FakeCDNFault.REQUIRED_AUTH_HEADER)
            with self.assertRaises(urllib.error.HTTPError) as raised:
                urllib.request.urlopen(
                    f"{cdn.base_url}/media/sample.avi", timeout=2
                )
            self.assertEqual(raised.exception.code, 401)
            raised.exception.close()

            request = urllib.request.Request(
                f"{cdn.base_url}/media/sample.avi",
                headers={"X-Fake-Provider": "test"},
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read()[:4], b"RIFF")

    def test_missing_content_length_fault_omits_header(self) -> None:
        with fake_cdn_server() as cdn:
            cdn.set_fault(FakeCDNFault.MISSING_CONTENT_LENGTH)
            with urllib.request.urlopen(
                f"{cdn.base_url}/media/sample.avi", timeout=2
            ) as response:
                self.assertIsNone(response.headers.get("Content-Length"))
                self.assertEqual(len(response.read()), cdn.sample_size)

    def test_no_range_support_ignores_client_range(self) -> None:
        with fake_cdn_server() as cdn:
            cdn.set_fault(FakeCDNFault.NO_RANGE_SUPPORT)
            request = urllib.request.Request(
                f"{cdn.base_url}/media/sample.avi",
                headers={"Range": "bytes=4-11"},
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                self.assertEqual(response.status, 200)
                self.assertIsNone(response.headers.get("Content-Range"))
                self.assertEqual(response.read(), cdn.sample_bytes)

    def test_slow_response_fault_delays_body(self) -> None:
        with fake_cdn_server(chunk_delay=0.03) as cdn:
            cdn.set_fault(FakeCDNFault.SLOW)
            started = time.monotonic()
            with urllib.request.urlopen(
                f"{cdn.base_url}/media/sample.avi", timeout=2
            ) as response:
                response.read()
            elapsed = time.monotonic() - started

        self.assertGreaterEqual(elapsed, 0.02)

    def test_mid_stream_disconnect_truncates_advertised_body(self) -> None:
        with fake_cdn_server() as cdn:
            cdn.set_fault(FakeCDNFault.MID_STREAM_DISCONNECT)
            with urllib.request.urlopen(
                f"{cdn.base_url}/media/sample.avi", timeout=2
            ) as response:
                self.assertEqual(response.headers["Content-Length"], str(cdn.sample_size))
                with self.assertRaises(http.client.IncompleteRead):
                    response.read()

    def test_connection_counters_close_completed_requests(self) -> None:
        with fake_cdn_server() as cdn:
            with urllib.request.urlopen(
                f"{cdn.base_url}/media/sample.avi", timeout=2
            ) as response:
                response.read()

            self.assertTrue(cdn.wait_for_closed_connections(1))
            self.assertEqual(cdn.connections_opened, 1)
            self.assertEqual(cdn.connections_closed, 1)
            self.assertEqual(cdn.active_connections, 0)

    def test_client_disconnect_is_visible_in_connection_counters(self) -> None:
        with fake_cdn_server(chunk_delay=0.01) as cdn:
            cdn.set_fault(FakeCDNFault.SLOW)
            response = urllib.request.urlopen(
                f"{cdn.base_url}/synthetic/100000000", timeout=2
            )
            response.read(32 * 1024)
            response.close()

            self.assertTrue(cdn.wait_for_closed_connections(1, timeout=4))
            self.assertEqual(cdn.connections_opened, 1)
            self.assertEqual(cdn.connections_closed, 1)
            self.assertEqual(cdn.active_connections, 0)


if __name__ == "__main__":
    unittest.main()
