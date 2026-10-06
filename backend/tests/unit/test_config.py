import unittest

from backend.app.config import AppEnvironment, ConfigurationError, Settings


class SettingsTests(unittest.TestCase):
    def test_loads_supported_environment(self) -> None:
        settings = Settings.from_environment({"APP_ENV": "test"})

        self.assertEqual(settings.app_env, AppEnvironment.TEST)

    def test_missing_environment_fails_fast(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "APP_ENV must be set"):
            Settings.from_environment({})

    def test_invalid_environment_fails_fast(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "APP_ENV must be one of"):
            Settings.from_environment({"APP_ENV": "staging"})


if __name__ == "__main__":
    unittest.main()
