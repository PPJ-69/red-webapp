import unittest

from backend.app.config import AppEnvironment, ConfigurationError, Settings


class SettingsTests(unittest.TestCase):
    def test_loads_supported_environment(self) -> None:
        settings = Settings.from_environment({"APP_ENV": "test"})

        self.assertEqual(settings.app_env, AppEnvironment.TEST)
        self.assertEqual(settings.upstream_allowed_hosts, ())
        self.assertEqual(settings.max_active_streams_per_ip, 3)
        self.assertEqual(settings.trusted_proxy_ips, ())

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

    def test_missing_environment_fails_fast(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "APP_ENV must be set"):
            Settings.from_environment({})

    def test_invalid_environment_fails_fast(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "APP_ENV must be one of"):
            Settings.from_environment({"APP_ENV": "staging"})


if __name__ == "__main__":
    unittest.main()
