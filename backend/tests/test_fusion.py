import pytest

from app.fusion import reciprocal_rank_fusion

ORDER = {name: (0, number) for number, name in enumerate("abcdef")}


def test_plain_rrf_scores_and_ranks():
    fused = reciprocal_rank_fusion({"dense": ["a", "b", "c"], "bm25": ["c", "a"]}, ORDER, k=60)

    assert [item.chunk_id for item in fused] == ["a", "c", "b"]
    assert fused[0].score == pytest.approx(1 / 61 + 1 / 62)
    assert fused[0].ranks == {"dense": 1, "bm25": 2}
    assert fused[1].ranks == {"dense": 3, "bm25": 1}
    assert fused[2].ranks == {"dense": 2}


def test_deduplicates_by_chunk_id():
    fused = reciprocal_rank_fusion({"dense": ["a", "a", "b"], "bm25": ["b"]}, ORDER)

    assert [item.chunk_id for item in fused] == ["b", "a"]
    assert fused[1].ranks == {"dense": 1}          # the repeated "a" does not count twice


def test_single_retriever_keeps_its_order():
    fused = reciprocal_rank_fusion({"dense": ["c", "a", "b"]}, ORDER)
    assert [item.chunk_id for item in fused] == ["c", "a", "b"]


def test_ties_are_deterministic():
    # a and b have the same score (rank 1 in one list each): the document/chunk order decides, in any input order.
    one = reciprocal_rank_fusion({"dense": ["b"], "bm25": ["a"]}, ORDER)
    two = reciprocal_rank_fusion({"bm25": ["a"], "dense": ["b"]}, ORDER)

    assert [item.chunk_id for item in one] == [item.chunk_id for item in two] == ["a", "b"]


def test_score_tie_is_broken_by_best_rank_then_order_key():
    # Same score for a and b; both have a rank 1 somewhere, so the order key decides: b (0, 1) before a (0, 5).
    fused = reciprocal_rank_fusion({"dense": ["a", "b"], "bm25": ["b", "a"]}, {"a": (0, 5), "b": (0, 1)})

    assert fused[0].score == pytest.approx(fused[1].score)
    assert [item.chunk_id for item in fused] == ["b", "a"]

    # c: 1/61 + 1/63 vs d: 1/62 + 1/62 are not tied (c is larger), so the score still wins over the order key.
    unequal = reciprocal_rank_fusion({"dense": ["c", "d"], "bm25": ["d", "c"]}, {"c": (0, 9), "d": (0, 1)})
    assert unequal[0].score == pytest.approx(unequal[1].score)           # still a tie: both are 1/61 + 1/62
    three = reciprocal_rank_fusion({"dense": ["c", "d"], "bm25": ["d", "x", "c"]}, {"c": (0, 9), "d": (0, 1), "x": (0, 2)})
    assert [item.chunk_id for item in three][:2] == ["d", "c"]           # 1/62+1/61 beats 1/61+1/63: the score wins


def test_weights_change_the_order():
    rankings = {"dense": ["a", "b"], "bm25": ["b", "a"]}
    plain = reciprocal_rank_fusion(rankings, ORDER)
    weighted = reciprocal_rank_fusion(rankings, ORDER, weights={"bm25": 3.0})
    dense_heavy = reciprocal_rank_fusion(rankings, ORDER, weights={"dense": 3.0})

    assert plain[0].score == pytest.approx(plain[1].score)     # a perfect tie without weights
    assert weighted[0].chunk_id == "b"
    assert dense_heavy[0].chunk_id == "a"


def test_empty_input():
    assert reciprocal_rank_fusion({}, {}) == []
    assert reciprocal_rank_fusion({"dense": [], "bm25": []}, {}) == []
