from __future__ import annotations

import uvicorn

from backend.tests.poc_app import create_poc_app
from backend.tests.fixtures.fake_cdn import FakeCDN


def main() -> None:
    cdn = FakeCDN()
    uvicorn.run(
        create_poc_app(cdn),
        host="127.0.0.1",
        port=8001,
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
