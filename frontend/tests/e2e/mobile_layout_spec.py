from __future__ import annotations

import json
import unittest
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect, sync_playwright

from frontend.tests.e2e.player_basic_spec import PlayerBasicBrowserTests


class MobileLayoutBrowserTests(PlayerBasicBrowserTests):
    test_media_player_loads_plays_buffers_and_releases_previous_source = None


def load_tests(
    loader: unittest.TestLoader,
    standard_tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    del standard_tests, pattern
    return loader.loadTestsFromTestCase(MobileLayoutBrowserTests)


if __name__ == "__main__":
    unittest.main()
