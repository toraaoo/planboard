from typing import Any

from planboard.domain.plan import Plan
from planboard.domain.search import search
from tests.support import plan_document

TASKS = [
    {"id": "middleware", "title": "Middleware", "summary": "Reject with a 429."},
    {"id": "token-bucket", "title": "Token bucket", "note": "Used by middleware."},
]


def plans(**overrides: Any) -> dict[str, Plan]:
    document = plan_document(title="Rate limiting", tasks=TASKS, **overrides)
    return {"api/rate-limiting": Plan.model_validate(document)}


def refs(query: str) -> list[str]:
    return [hit.ref for hit in search(plans(), query)]


def test_finds_words_with_a_typo() -> None:
    assert refs("bukcet")[0] == "api/rate-limiting#token-bucket"
    assert refs("rejct") == ["api/rate-limiting#middleware"]


def test_every_word_must_match() -> None:
    assert refs("reject 429") == ["api/rate-limiting#middleware"]
    assert refs("reject bucket") == []


def test_ranks_a_title_before_a_mention() -> None:
    assert refs("middleware")[:2] == [
        "api/rate-limiting#middleware",
        "api/rate-limiting#token-bucket",
    ]


def test_finds_a_prefix_and_text_in_blocks() -> None:
    assert "api/rate-limiting" in refs("limit")
    hits = search(plans(), "flow")
    assert {hit.kind for hit in hits} >= {"diagram"}


def test_nothing_matches_an_unrelated_word() -> None:
    assert refs("xyzzy") == []
