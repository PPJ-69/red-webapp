"""Interfaces for replaceable upstream providers."""

from .auth import AuthManager, UpstreamAuthError
from .transport import UpstreamTransport

__all__ = ["AuthManager", "UpstreamAuthError", "UpstreamTransport"]
