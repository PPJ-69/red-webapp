from backend.app.domain.models import (
    Creator,
    InternalSourceTarget,
    MediaItem,
    SearchQuery,
    SearchResult,
)
from backend.app.upstream.provider import UpstreamMediaProvider


class ProviderContract:
    def make_provider(self) -> UpstreamMediaProvider:
        raise NotImplementedError("Provider contract subclasses must supply a provider.")

    async def test_authentication_completes(self) -> None:
        await self.make_provider().authenticate()

    async def test_search_returns_canonical_result(self) -> None:
        result = await self.make_provider().search(SearchQuery(query="sample"))

        self.assertIsInstance(result, SearchResult)
        self.assertTrue(all(isinstance(item, MediaItem) for item in result.items))

    async def test_media_lookup_returns_canonical_item(self) -> None:
        item = await self.make_provider().get_media("sample-media")

        self.assertIsInstance(item, MediaItem)
        self.assertEqual(item.id, "sample-media")

    async def test_creator_lookup_returns_canonical_creator(self) -> None:
        creator = await self.make_provider().get_creator("sample")

        self.assertIsInstance(creator, Creator)
        self.assertEqual(creator.username, "sample")

    async def test_tag_suggestions_return_strings(self) -> None:
        tags = await self.make_provider().suggest_tags("sam")

        self.assertIn("sample", tags)
        self.assertTrue(all(isinstance(tag, str) for tag in tags))

    async def test_source_resolution_returns_internal_target(self) -> None:
        target = await self.make_provider().resolve_source("sample-media", "auto")

        self.assertIsInstance(target, InternalSourceTarget)
        self.assertTrue(target.url.startswith("https://"))
