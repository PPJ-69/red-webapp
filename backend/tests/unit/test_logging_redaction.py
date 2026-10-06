import io
import json
import logging
import unittest

from backend.app.observability.logging import (
    JsonLogFormatter,
    redact_text,
    redact_value,
)


class LoggingRedactionTests(unittest.TestCase):
    def test_redacts_bearer_authorization_and_cookie_headers(self) -> None:
        message = (
            "Authorization: Bearer bearer-canary\n"
            "Cookie: session=cookie-canary; preference=dark"
        )

        redacted = redact_text(message)

        self.assertNotIn("bearer-canary", redacted)
        self.assertNotIn("cookie-canary", redacted)
        self.assertIn("Authorization=[REDACTED]", redacted)
        self.assertIn("Cookie=[REDACTED]", redacted)

    def test_redacts_session_values_and_signed_url_query_parameters(self) -> None:
        message = (
            "session_state=session-canary "
            "https://cdn.example.invalid/video.mp4?quality=hd"
            "&X-Amz-Signature=signature-canary&token=url-token-canary"
        )

        redacted = redact_text(message)

        for canary in ("session-canary", "signature-canary", "url-token-canary"):
            self.assertNotIn(canary, redacted)
        self.assertIn("quality=hd", redacted)
        self.assertIn("%5BREDACTED%5D", redacted)

    def test_redacts_sensitive_nested_fields_and_embedded_secrets(self) -> None:
        payload = {
            "operation": "search",
            "session": {"favorites": ["session-canary"]},
            "details": ["Bearer bearer-canary"],
        }

        redacted = redact_value(payload)
        serialized = json.dumps(redacted)

        self.assertEqual(redacted["session"], "[REDACTED]")
        self.assertNotIn("session-canary", serialized)
        self.assertNotIn("bearer-canary", serialized)
        self.assertIn("operation", redacted)

    def test_redacts_json_encoded_session_and_credential_fields(self) -> None:
        message = (
            '{"session":{"state":"session-canary"},'
            '"authorization":"authorization-canary",'
            '"access_token":"token-canary"}'
        )

        redacted = redact_text(message)

        for canary in ("session-canary", "authorization-canary", "token-canary"):
            self.assertNotIn(canary, redacted)

    def test_json_formatter_emits_structured_redacted_fields(self) -> None:
        record = logging.LogRecord(
            "test",
            logging.INFO,
            __file__,
            1,
            "request completed",
            (),
            None,
        )
        record.correlation_id = "request-123"
        record.cookie = "cookie-canary"
        record.status = 200

        payload = json.loads(JsonLogFormatter().format(record))

        self.assertEqual(payload["correlation_id"], "request-123")
        self.assertEqual(payload["cookie"], "[REDACTED]")
        self.assertEqual(payload["status"], 200)
        self.assertNotIn("cookie-canary", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
