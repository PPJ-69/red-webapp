import unittest

from backend.app.config import AppEnvironment, ConfigurationError, Settings


class SettingsTests(unittest.TestCase):
    def test_loads_supported_environment(self) -> None:
        settings = Settings.from_environment({"APP_ENV": "test"})

        self.assertEqual(settings.app_env, AppEnvironment.TEST)
        self.assertEqual(settings.upstream_allowed_hosts, ())

    def test_loads_allowlisted_upstream_hosts(self) -> None:
        settings = Settings.from_environment({
            "APP_ENV": "test",
            "UPSTREAM_ALLOWED_HOSTS": "cdn.example.invalid, images.example.invalid",
        })

        self.assertEqual(
            settings.upstream_allowed_hosts,
            ("cdn.example.invalid", "images.example.invalid"),
        )

    def test_missing_environment_fails_fast(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "APP_ENV must be set"):
            Settings.from_environment({})

    def test_invalid_environment_fails_fast(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "APP_ENV must be one of"):
            Settings.from_environment({"APP_ENV": "staging"})


if __name__ == "__main__":
    unittest.main()
