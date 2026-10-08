from pathlib import Path
import unittest


class NoFullBufferingGuardTests(unittest.TestCase):
    def test_relay_modules_do_not_use_full_body_buffering_apis(self) -> None:
        root = Path(__file__).parents[2] / "app"
        paths = (
            root / "upstream" / "stream_transport.py",
            root / "services" / "stream_service.py",
            root / "api" / "stream.py",
        )
        forbidden = (".read(", ".aread(", ".content", "response.json(")

        for path in paths:
            source = path.read_text(encoding="utf-8")
            for pattern in forbidden:
                with self.subTest(path=path.name, pattern=pattern):
                    self.assertNotIn(pattern, source)


if __name__ == "__main__":
    unittest.main()
