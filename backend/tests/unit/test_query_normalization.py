import unittest

from backend.app.domain.models import SearchQuery
from backend.app.services.query_normalization import normalize_search_query, parse_search_tokens


class QueryNormalizationTests(unittest.TestCase):
    def test_parse_search_tokens_handles_creator_and_tags(self) -> None:
        query_text, tags, creators = parse_search_tokens("cats #funny @alice user:sample creator:team")

        self.assertEqual(query_text, "cats")
        self.assertEqual(tags, ["funny"])
        self.assertEqual(sorted(creators), ["alice", "sample", "team"])

    def test_normalize_search_query_clamps_pagination(self) -> None:
        normalized = normalize_search_query("cats #funny", tags=["meme"], page=0, limit=500)

        self.assertEqual(normalized.query, "cats")
        self.assertEqual(normalized.tags, ["funny", "meme"])
        self.assertEqual(normalized.page, 1)
        self.assertEqual(normalized.limit, 100)

    def test_search_query_from_existing_model_preserves_order(self) -> None:
        normalized = normalize_search_query(SearchQuery(query="cats", mode="search", order="score", page=2, limit=20))

        self.assertEqual(normalized.order, "score")
        self.assertEqual(normalized.page, 2)
        self.assertEqual(normalized.limit, 20)


if __name__ == "__main__":
    unittest.main()
