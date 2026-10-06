from .config import Settings


def get_settings() -> Settings:
    return Settings.from_environment()
