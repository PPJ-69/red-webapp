from contextlib import contextmanager
from collections.abc import Iterator

from backend.tests.fixtures.fake_cdn import FakeCDN


@contextmanager
def fake_cdn_server(*, chunk_delay: float = 0.05) -> Iterator[FakeCDN]:
    """Start and reliably stop the shared loopback CDN test server."""
    with FakeCDN(chunk_delay=chunk_delay) as cdn:
        yield cdn
