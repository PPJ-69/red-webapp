from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.config import Settings
from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.upstream.factory import create_upstream_provider
from backend.app.upstream.redgifs_client import RedgifsClient


class ProviderFactoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_is_disabled_by_default_without_network_activity(self) -> None:
        settings = Settings.from_environment({"APP_ENV": "production"})

        provider = await create_upstream_provider(settings)

        self.assertIsNone(provider)

    async def test_redgifs_provider_loads_token_from_file_without_network_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            token_file = Path(directory) / "provider-token"
            token_file.write_text("test-token\n", encoding="utf-8")
            settings = Settings.from_environment(
                {
                    "APP_ENV": "production",
                    "UPSTREAM_PROVIDER": "redgifs",
                    "REDGIFS_TOKEN_FILE": str(token_file),
                }
            )

            provider = await create_upstream_provider(settings)

            self.assertIsInstance(provider, RedgifsClient)
            self.assertEqual(provider.auth_manager.token, "test-token")
            await provider.aclose()

    async def test_auth_refresh_reads_rotated_secret_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            token_file = Path(directory) / "provider-token"
            token_file.write_text("initial-token", encoding="utf-8")
            provider = await create_upstream_provider(
                Settings.from_environment(
                    {
                        "APP_ENV": "production",
                        "UPSTREAM_PROVIDER": "redgifs",
                        "REDGIFS_TOKEN_FILE": str(token_file),
                    }
                )
            )
            try:
                token_file.write_text("rotated-token", encoding="utf-8")
                self.assertEqual(await provider.auth_manager.refresh(), "rotated-token")
            finally:
                await provider.aclose()

    async def test_invalid_secret_fails_without_leaking_secret_contents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            token_file = Path(directory) / "provider-token"
            token_file.write_text("Bearer do-not-log-this", encoding="utf-8")
            settings = Settings.from_environment(
                {
                    "APP_ENV": "production",
                    "UPSTREAM_PROVIDER": "redgifs",
                    "REDGIFS_TOKEN_FILE": str(token_file),
                }
            )

            with self.assertRaises(ApplicationError) as raised:
                await create_upstream_provider(settings)

        self.assertEqual(
            raised.exception.category,
            ErrorCategory.UPSTREAM_AUTHENTICATION_FAILED,
        )
        self.assertNotIn("do-not-log-this", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
