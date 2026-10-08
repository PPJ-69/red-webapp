import unittest
import json
from pathlib import Path

from backend.app.domain.models import SearchQuery
from backend.app.services.query_normalization import normalize_search_query, parse_search_tokens


ROOT = Path(__file__).resolve().parents[3]


class QueryNormalizationTests(unittest.TestCase):
    def test_shared_query_vectors_match_backend_normalization(self) -> None:
        vectors = json.loads(
            (ROOT / "shared" / "fixtures" / "query_vectors.json").read_text(
                encoding="utf-8"
            )
        )
        for vector in vectors:
            with self.subTest(vector=vector["name"]):
                normalized = normalize_search_query(**vector["input"])
                self.assertEqual(
                    {
                        "query": normalized.query,
                        "tags": normalized.tags,
                        "mode": normalized.mode,
                        "page": normalized.page,
                        "limit": normalized.limit,
                    },
                    vector["expected"],
                )

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
