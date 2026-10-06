from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class AppEnvironment(str, Enum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class ConfigurationError(ValueError):
    """Raised when required environment configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    app_env: AppEnvironment

    @classmethod
    def from_environment(
        cls, environ: Mapping[str, str] | None = None
    ) -> "Settings":
        if environ is None:
            import os

            environ = os.environ

        value = environ.get("APP_ENV", "").strip().lower()
        if not value:
            raise ConfigurationError("APP_ENV must be set.")

        try:
            app_env = AppEnvironment(value)
        except ValueError as exc:
            allowed = ", ".join(environment.value for environment in AppEnvironment)
            raise ConfigurationError(
                f"APP_ENV must be one of: {allowed}."
            ) from exc

        return cls(app_env=app_env)
