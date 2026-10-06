import unittest
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import (
    ERROR_STATUS_CODES,
    ApplicationError,
    register_exception_handlers,
)


class ErrorEnvelopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        register_exception_handlers(self.app)
        self.client = TestClient(self.app)

    def test_every_category_has_an_http_status(self) -> None:
        self.assertEqual(set(ERROR_STATUS_CODES), set(ErrorCategory))

    def test_each_category_returns_its_status_and_envelope(self) -> None:
        @self.app.get("/failure/{category}")
        async def fail(category: str) -> None:
            error_category = ErrorCategory(category)
            raise ApplicationError(error_category, "Request failed.")

        for category, status_code in ERROR_STATUS_CODES.items():
            with self.subTest(category=category):
                response = self.client.get(f"/failure/{category.value}")

                self.assertEqual(response.status_code, status_code)
                self.assertEqual(response.json()["category"], category.value)
                self.assertEqual(response.json()["message"], "Request failed.")
                self.assertTrue(response.json()["correlationId"])

    def test_application_error_returns_envelope_and_retry_after(self) -> None:
        @self.app.get("/failure")
        async def fail() -> None:
            raise ApplicationError(ErrorCategory.RATE_LIMITED, "Wait.", retry_after=12)

        response = self.client.get("/failure")

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "12")
        payload = response.json()
        self.assertEqual(payload["category"], "rate_limited")
        self.assertEqual(payload["message"], "Wait.")
        self.assertEqual(payload["retryAfter"], 12)
        UUID(payload["correlationId"])

    def test_validation_error_uses_the_shared_envelope(self) -> None:
        @self.app.get("/items/{item_id}")
        async def item(item_id: int) -> dict[str, int]:
            return {"itemId": item_id}

        response = self.client.get("/items/not-an-integer")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["category"], "invalid_request")
        self.assertIn("correlationId", response.json())


if __name__ == "__main__":
    unittest.main()
