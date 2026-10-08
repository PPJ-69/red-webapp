import socket
import unittest
from unittest.mock import patch

from backend.app.security.validation import validate_upstream_target


class UpstreamTargetValidationTests(unittest.TestCase):
    def test_allows_https_host_on_allowlist(self) -> None:
        with patch.object(socket, "getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 443))]):
            validated = validate_upstream_target(
                "https://cdn.example.invalid/media/test.mp4",
                allowed_hosts=["cdn.example.invalid"],
            )

        self.assertEqual(validated, "https://cdn.example.invalid/media/test.mp4")

    def test_rejects_non_allowlisted_hosts(self) -> None:
        with patch.object(socket, "getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 443))]):
            with self.assertRaisesRegex(ValueError, "not allowlisted"):
                validate_upstream_target(
                    "https://blocked.example.invalid/media/test.mp4",
                    allowed_hosts=["cdn.example.invalid"],
                )

    def test_rejects_private_and_local_targets(self) -> None:
        cases = [
            "https://localhost/media/test.mp4",
            "https://127.0.0.1/media/test.mp4",
            "https://10.0.0.5/media/test.mp4",
            "https://169.254.10.1/media/test.mp4",
            "https://[::1]/media/test.mp4",
        ]
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_upstream_target(value, allowed_hosts=["localhost", "127.0.0.1", "10.0.0.5", "169.254.10.1", "[::1]"])

    def test_rejects_non_https_targets(self) -> None:
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            validate_upstream_target("http://cdn.example.invalid/media/test.mp4", allowed_hosts=["cdn.example.invalid"])

    def test_rejects_hostname_resolving_to_private_address(self) -> None:
        with patch.object(socket, "getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 443))]):
            with self.assertRaisesRegex(ValueError, "prohibited network address"):
                validate_upstream_target(
                    "https://private.example.invalid/media/test.mp4",
                    allowed_hosts=["private.example.invalid"],
                )


if __name__ == "__main__":
    unittest.main()
