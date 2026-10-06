import io
import json
import logging
import sys
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError, register_exception_handlers
from backend.app.observability.logging import (
    configure_logging,
    install_request_context,
)


class RequestContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        register_exception_handlers(self.app)
        install_request_context(self.app)
        self.logger = configure_logging()
        self.handler = self.logger.handlers[0]
        self.previous_stream = self.handler.stream
        self.log_output = io.StringIO()
        self.handler.stream = self.log_output

        @self.app.get("/items/{item_id}")
        async def get_item(item_id: str) -> dict[str, str]:
            return {"id": item_id}

        @self.app.get("/failure")
        async def fail() -> None:
            raise ApplicationError(ErrorCategory.NOT_FOUND, "Item not found.")

    def tearDown(self) -> None:
        self.handler.flush()
        self.handler.stream = self.previous_stream

    def test_correlation_id_is_generated_echoed_and_logged(self) -> None:
        response = TestClient(self.app).get("/items/media-123?token=query-canary")

        correlation_id = response.headers["X-Correlation-ID"]
        self.assertTrue(correlation_id)

        logged = json.loads(self.log_output.getvalue())
        self.assertEqual(logged["correlation_id"], correlation_id)
        self.assertEqual(logged["operation"], "/items/{item_id}")
        self.assertEqual(logged["request_type"], "GET")
        self.assertEqual(logged["status_category"], "success")
        self.assertNotIn("query-canary", self.log_output.getvalue())
        self.assertNotIn("media-123", self.log_output.getvalue())

    def test_error_envelope_and_log_share_correlation_id(self) -> None:
        response = TestClient(self.app).get("/failure")
        payload = response.json()
        logged = json.loads(self.log_output.getvalue())

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.headers["X-Correlation-ID"], payload["correlationId"]
        )
        self.assertEqual(logged["correlation_id"], payload["correlationId"])
        self.assertEqual(logged["status_category"], "not_found")

    def test_logging_handler_writes_to_stdout_not_a_file(self) -> None:
        logger = logging.getLogger("red_webapp")

        self.assertTrue(logger.handlers)
        for handler in logger.handlers:
            self.assertIsInstance(handler, logging.StreamHandler)
            self.assertIsNotNone(handler.stream)
            self.assertFalse(hasattr(handler, "baseFilename"))
        self.assertIs(self.previous_stream, sys.stdout)


if __name__ == "__main__":
    unittest.main()
