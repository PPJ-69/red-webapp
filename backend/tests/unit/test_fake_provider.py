import unittest

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.dependencies import get_upstream_provider
from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.domain.models import (
    Creator,
    ErrorEnvelope,
    HealthStatus,
    InternalSourceTarget,
    MediaItem,
    MediaSource,
    SearchQuery,
    SearchResult,
    canonical_model_schemas,
)
from backend.app.upstream.provider import UpstreamMediaProvider
from backend.tests.contract.provider_contract import ProviderContract
from backend.tests.conftest import fake_cdn_server
from backend.tests.fakes.fake_provider import FakeMediaProvider, FakeProviderFault


class FakeProviderContractTests(ProviderContract, unittest.IsolatedAsyncioTestCase):
    def make_provider(self) -> UpstreamMediaProvider:
        return FakeMediaProvider()


class FakeProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_can_resolve_media_to_the_fake_cdn(self) -> None:
        with fake_cdn_server() as cdn:
            provider = FakeMediaProvider(cdn_base_url=cdn.base_url)

            target = await provider.resolve_source("sample-media", "auto")

        self.assertEqual(
            target.url,
            f"{cdn.base_url}/media/sample-media-auto.avi?signature=valid",
        )
        self.assertEqual(target.headers, {"X-Fake-Provider": "test"})

    async def test_fake_provider_faults_are_explicit(self) -> None:
        expected = {
            FakeProviderFault.NOT_FOUND: ErrorCategory.NOT_FOUND,
            FakeProviderFault.RATE_LIMITED: ErrorCategory.RATE_LIMITED,
            FakeProviderFault.AUTH_EXPIRED: ErrorCategory.UPSTREAM_AUTHENTICATION_FAILED,
        }
        for fault, category in expected.items():
            with self.subTest(fault=fault):
                provider = FakeMediaProvider({"get_media": fault})
                with self.assertRaises(ApplicationError) as raised:
                    await provider.get_media("sample-media")
                self.assertEqual(raised.exception.category, category)
                if fault is FakeProviderFault.RATE_LIMITED:
                    self.assertEqual(raised.exception.retry_after, 30)

    async def test_auth_expiry_can_be_injected_during_authentication(self) -> None:
        provider = FakeMediaProvider(
            {"authenticate": FakeProviderFault.AUTH_EXPIRED}
        )

        with self.assertRaises(ApplicationError) as raised:
            await provider.authenticate()

        self.assertEqual(
            raised.exception.category,
            ErrorCategory.UPSTREAM_AUTHENTICATION_FAILED,
        )

    async def test_malformed_item_fault_raises_model_validation_error(self) -> None:
        provider = FakeMediaProvider(
            {"get_media": FakeProviderFault.MALFORMED_ITEM}
        )

        with self.assertRaises(ValidationError):
            await provider.get_media("sample-media")

    async def test_provider_dependency_uses_application_injection(self) -> None:
        app = FastAPI()
        app.state.upstream_provider = FakeMediaProvider()

        @app.get("/provider")
        async def provider_info(
            provider: UpstreamMediaProvider = Depends(get_upstream_provider),
        ) -> dict[str, str]:
            item = await provider.get_media("sample-media")
            return {"id": item.id}

        response = TestClient(app).get("/provider")

        self.assertEqual(response.json(), {"id": "sample-media"})

    async def test_provider_dependency_fails_when_not_configured(self) -> None:
        app = FastAPI()

        @app.get("/provider")
        async def provider_info(
            _provider: UpstreamMediaProvider = Depends(get_upstream_provider),
        ) -> dict[str, str]:
            return {"status": "unexpected"}

        with self.assertRaisesRegex(RuntimeError, "No upstream media provider"):
            TestClient(app, raise_server_exceptions=True).get("/provider")

    def test_internal_source_target_is_not_serializable_in_api_models(self) -> None:
        target = InternalSourceTarget(
            url="https://cdn.example.invalid/media/signed.mp4",
            headers={"Authorization": "provider-secret"},
        )
        models_and_instances = (
            (Creator, Creator(id="creator", username="sample")),
            (MediaSource, MediaSource(playbackUrl="/api/stream/sample-media")),
            (MediaItem, MediaItem(id="sample-media", title="Sample")),
            (
                SearchResult,
                SearchResult(items=[], page=1, limit=20, hasMore=False),
            ),
            (SearchQuery, SearchQuery()),
            (
                ErrorEnvelope,
                ErrorEnvelope(
                    category=ErrorCategory.NOT_FOUND,
                    message="Not found.",
                    correlationId="request-id",
                ),
            ),
            (HealthStatus, HealthStatus(status="ok")),
        )

        for model, instance in models_and_instances:
            with self.subTest(model=model.__name__):
                serialized = instance.model_dump(by_alias=True)
                with self.assertRaises(ValidationError):
                    model.model_validate({**serialized, "sourceTarget": target})

        with self.assertRaises(ValidationError):
            MediaSource.model_validate(
                {
                    "playbackUrl": "/api/stream/sample-media",
                    "sourceTarget": target,
                }
            )

        self.assertNotIn("InternalSourceTarget", canonical_model_schemas())


if __name__ == "__main__":
    unittest.main()
