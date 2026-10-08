import unittest

from backend.app.services.range_semantics import (
    ByteRange,
    InvalidRangeHeader,
    map_range_response,
    parse_range_header,
)


class RangeSemanticsTests(unittest.TestCase):
    def test_no_range_preserves_full_response(self) -> None:
        response = map_range_response(
            None,
            200,
            {
                "Content-Type": "video/mp4",
                "Content-Length": "1000",
                "Accept-Ranges": "bytes",
                "ETag": '"abc"',
                "Last-Modified": "Wed, 21 Oct 2015 07:28:00 GMT",
                "Cache-Control": "private, max-age=30",
                "Set-Cookie": "must-not-pass",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers,
            {
                "content-type": "video/mp4",
                "content-length": "1000",
                "accept-ranges": "bytes",
                "etag": '"abc"',
                "last-modified": "Wed, 21 Oct 2015 07:28:00 GMT",
                "cache-control": "private, max-age=30",
            },
        )

    def test_missing_cache_control_defaults_to_no_store(self) -> None:
        response = map_range_response(None, 200, {"Content-Length": "100"})

        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_parses_closed_range(self) -> None:
        self.assertEqual(parse_range_header("bytes=10-19"), ByteRange(10, 19))

    def test_closed_range_preserves_partial_response_semantics(self) -> None:
        response = map_range_response(
            "bytes=10-19",
            206,
            {
                "Content-Range": "bytes 10-19/100",
                "Content-Type": "video/mp4",
                "ETag": '"abc"',
            },
        )

        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.headers["content-range"], "bytes 10-19/100")
        self.assertEqual(response.headers["content-length"], "10")
        self.assertEqual(response.headers["accept-ranges"], "bytes")
        self.assertEqual(response.headers["etag"], '"abc"')

    def test_parses_open_ended_range(self) -> None:
        parsed = parse_range_header("bytes=10-")

        self.assertEqual(parsed, ByteRange(10, None))
        self.assertEqual(parsed.as_header(), "bytes=10-")

    def test_parses_suffix_range(self) -> None:
        parsed = parse_range_header("bytes=-25")

        self.assertEqual(parsed, ByteRange(None, None, suffix_length=25))
        self.assertEqual(parsed.as_header(), "bytes=-25")

    def test_invalid_range_with_known_size_returns_416(self) -> None:
        response = map_range_response(
            "bytes=100-",
            200,
            {"Content-Length": "100", "Content-Type": "video/mp4"},
        )

        self.assertEqual(response.status_code, 416)
        self.assertEqual(
            response.headers,
            {
                "content-type": "video/mp4",
                "accept-ranges": "bytes",
                "content-length": "0",
                "content-range": "bytes */100",
                "cache-control": "no-store",
            },
        )

    def test_suffix_range_on_empty_object_returns_416(self) -> None:
        response = map_range_response("bytes=-5", 200, {"Content-Length": "0"})

        self.assertEqual(response.status_code, 416)
        self.assertEqual(response.headers["content-range"], "bytes */0")

    def test_malformed_range_with_known_size_returns_416(self) -> None:
        response = map_range_response("bytes=invalid", 200, {"Content-Length": "10"})

        self.assertEqual(response.status_code, 416)
        self.assertEqual(response.headers["content-range"], "bytes */10")

    def test_malformed_range_with_unknown_size_falls_back_to_full_response(self) -> None:
        response = map_range_response("bytes=invalid", 200, {"Content-Type": "video/mp4"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers,
            {"content-type": "video/mp4", "cache-control": "no-store"},
        )

    def test_multi_range_is_treated_as_no_range(self) -> None:
        parsed = parse_range_header("bytes=0-9,20-29")
        response = map_range_response(
            "bytes=0-9,20-29",
            200,
            {"Content-Length": "100", "Content-Range": "bytes 0-9/100"},
        )

        self.assertIsNone(parsed)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("content-range", response.headers)

    def test_upstream_ignoring_range_returns_full_response(self) -> None:
        response = map_range_response(
            "bytes=10-19",
            200,
            {
                "Content-Type": "video/mp4",
                "Content-Length": "100",
                "Content-Range": "bytes 10-19/100",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-length"], "100")
        self.assertNotIn("content-range", response.headers)

    def test_unknown_size_preserves_upstream_partial_response(self) -> None:
        response = map_range_response(
            "bytes=10-",
            206,
            {"Content-Range": "bytes 10-19/*", "Content-Type": "video/mp4"},
        )

        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.headers["content-range"], "bytes 10-19/*")
        self.assertEqual(response.headers["content-length"], "10")
        self.assertEqual(response.headers["accept-ranges"], "bytes")

    def test_upstream_416_synthesizes_content_range_when_size_is_known(self) -> None:
        response = map_range_response(
            "bytes=200-",
            416,
            {"Content-Range": "bytes */100", "Cache-Control": "no-store"},
        )

        self.assertEqual(response.status_code, 416)
        self.assertEqual(response.headers["content-range"], "bytes */100")
        self.assertEqual(response.headers["accept-ranges"], "bytes")
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_rejects_empty_and_reversed_ranges(self) -> None:
        for value in ("bytes=-", "bytes=20-10", "items=0-1"):
            with self.subTest(value=value), self.assertRaises(InvalidRangeHeader):
                parse_range_header(value)

    def test_ignores_response_headers_with_line_breaks(self) -> None:
        response = map_range_response(
            None,
            200,
            {"Content-Type": "video/mp4\r\nSet-Cookie: leak", "Content-Length": "1"},
        )

        self.assertNotIn("content-type", response.headers)
        self.assertEqual(response.headers["content-length"], "1")

    def test_ignores_malformed_range_response_headers(self) -> None:
        response = map_range_response(
            None,
            200,
            {"Content-Length": "-1", "Content-Range": "invalid", "Accept-Ranges": "items"},
        )

        self.assertEqual(response.headers, {"cache-control": "no-store"})


if __name__ == "__main__":
    unittest.main()
