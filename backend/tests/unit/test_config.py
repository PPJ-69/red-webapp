import unittest

from backend.app.config import (
    AppEnvironment,
    ConfigurationError,
    Settings,
    UpstreamProviderMode,
)


class SettingsTests(unittest.TestCase):
    def test_loads_supported_environment(self) -> None:
        settings = Settings.from_environment({"APP_ENV": "test"})

        self.assertEqual(settings.app_env, AppEnvironment.TEST)
        self.assertEqual(settings.upstream_provider, UpstreamProviderMode.DISABLED)
        self.assertIsNone(settings.redgifs_token_file)
        self.assertEqual(settings.upstream_allowed_hosts, ())
        self.assertEqual(settings.max_active_streams_per_ip, 3)
        self.assertEqual(settings.source_cache_ttl_seconds, 60.0)
        self.assertEqual(settings.trusted_proxy_ips, ())
        self.assertEqual(settings.cors_allowed_origins, ())
        self.assertFalse(settings.enable_hls)

    def test_hls_is_disabled_by_default_and_requires_a_boolean(self) -> None:
        enabled = Settings.from_environment(
            {"APP_ENV": "test", "ENABLE_HLS": "yes"}
        )
        self.assertTrue(enabled.enable_hls)
        disabled = Settings.from_environment(
            {"APP_ENV": "test", "ENABLE_HLS": "0"}
        )
        self.assertFalse(disabled.enable_hls)
        with self.assertRaisesRegex(ConfigurationError, "ENABLE_HLS"):
            Settings.from_environment(
                {"APP_ENV": "test", "ENABLE_HLS": "sometimes"}
            )

    def test_provider_configuration_is_opt_in_and_requires_secret_file(self) -> None:
        settings = Settings.from_environment(
            {
                "APP_ENV": "production",
                "UPSTREAM_PROVIDER": "redgifs",
                "REDGIFS_TOKEN_FILE": "/run/secrets/redgifs_token",
            }
        )
        self.assertEqual(settings.upstream_provider, UpstreamProviderMode.REDGIFS)
        self.assertEqual(
            settings.redgifs_token_file.as_posix(),
            "/run/secrets/redgifs_token",
        )

        for environ in (
            {"APP_ENV": "production", "UPSTREAM_PROVIDER": "unknown"},
            {"APP_ENV": "production", "UPSTREAM_PROVIDER": "redgifs"},
            {
                "APP_ENV": "production",
                "REDGIFS_TOKEN_FILE": "/run/secrets/redgifs_token",
            },
        ):
            with self.subTest(environ=environ), self.assertRaises(ConfigurationError):
                Settings.from_environment(environ)

    def test_loads_allowlisted_upstream_hosts(self) -> None:
        settings = Settings.from_environment({
            "APP_ENV": "test",
            "UPSTREAM_ALLOWED_HOSTS": "cdn.example.invalid, images.example.invalid",
        })

        self.assertEqual(
            settings.upstream_allowed_hosts,
            ("cdn.example.invalid", "images.example.invalid"),
        )

    def test_loads_stream_limit_and_trusted_proxy_networks(self) -> None:
        settings = Settings.from_environment(
            {
                "APP_ENV": "test",
                "MAX_ACTIVE_STREAMS_PER_IP": "5",
                "TRUSTED_PROXY_IPS": "10.0.0.4, 192.168.0.0/24",
            }
        )

        self.assertEqual(settings.max_active_streams_per_ip, 5)
        self.assertEqual(settings.trusted_proxy_ips, ("10.0.0.4/32", "192.168.0.0/24"))

    def test_rejects_invalid_stream_limit_or_proxy_network(self) -> None:
        for value in ("0", "-1", "many"):
            with self.subTest(value=value), self.assertRaisesRegex(
                ConfigurationError, "MAX_ACTIVE_STREAMS_PER_IP"
            ):
                Settings.from_environment(
                    {"APP_ENV": "test", "MAX_ACTIVE_STREAMS_PER_IP": value}
                )
        with self.assertRaisesRegex(ConfigurationError, "TRUSTED_PROXY_IPS"):
            Settings.from_environment(
                {"APP_ENV": "test", "TRUSTED_PROXY_IPS": "not-an-ip"}
            )

    def test_loads_and_validates_source_cache_ttl(self) -> None:
        settings = Settings.from_environment(
            {"APP_ENV": "test", "SOURCE_CACHE_TTL_SECONDS": "45.5"}
        )

        self.assertEqual(settings.source_cache_ttl_seconds, 45.5)
        for value in ("0", "-1", "NaN", "inf", "many"):
            with self.subTest(value=value), self.assertRaisesRegex(
                ConfigurationError, "SOURCE_CACHE_TTL_SECONDS"
            ):
                Settings.from_environment(
                    {"APP_ENV": "test", "SOURCE_CACHE_TTL_SECONDS": value}
                )

    def test_normalizes_explicit_cors_origins(self) -> None:
        settings = Settings.from_environment(
            {
                "APP_ENV": "test",
                "CORS_ALLOWED_ORIGINS": (
                    " https://frontend.example/ , http://localhost:5173, "
                    "https://frontend.example "
                ),
            }
        )

        self.assertEqual(
            settings.cors_allowed_origins,
            ("https://frontend.example", "http://localhost:5173"),
        )

    def test_rejects_wildcard_or_non_origin_cors_entries(self) -> None:
        for origin in (
            "*",
            "https://*.example.com",
            "https://frontend.example/path",
            "https://user:password@frontend.example",
            "https://frontend.example?token=secret",
        ):
            with self.subTest(origin=origin), self.assertRaisesRegex(
                ConfigurationError, "CORS_ALLOWED_ORIGINS"
            ):
                Settings.from_environment(
                    {"APP_ENV": "test", "CORS_ALLOWED_ORIGINS": origin}
                )

    def test_missing_environment_fails_fast(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "APP_ENV must be set"):
            Settings.from_environment({})

    def test_invalid_environment_fails_fast(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "APP_ENV must be one of"):
            Settings.from_environment({"APP_ENV": "staging"})


if __name__ == "__main__":
    unittest.main()
