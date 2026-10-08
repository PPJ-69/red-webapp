"""Interfaces for replaceable upstream providers."""

from .auth import AuthManager, UpstreamAuthError
from .redgifs_client import RedgifsClient
from .transport import UpstreamTransport

__all__ = ["AuthManager", "RedgifsClient", "UpstreamAuthError", "UpstreamTransport"]
