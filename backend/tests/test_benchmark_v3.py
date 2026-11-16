import pytest

from app import benchmark_v3 as bench


def test_parse_plain_and_weighted_configs():
    assert bench.parse_config("dense") == {"name": "dense", "retrievers": ["dense"], "weights": None}
    assert bench.parse_config("dense+bm25") ["retrievers"] == ["dense", "bm25"]

    weighted = bench.parse_config("dense+bm25@bm25=0.5,dense=2")
    assert weighted["weights"] == {"bm25": 0.5, "dense": 2.0}


@pytest.mark.parametrize("text", ["", "magic", "dense+dense", "dense@bm25=2", "dense+bm25@bm25=abc", "dense+bm25@bm25"])
def test_parse_rejects_bad_configs(text):
    with pytest.raises(ValueError):
        bench.parse_config(text)


def test_first_hit_rank_uses_fused_order_and_span_overlap():
    evidence = [{"document_id": "d", "start": 100, "end": 120}]
    chunks = [
        {"document_id": "d", "start": 0, "end": 100},       # ends exactly where the evidence starts: no overlap
        {"document_id": "other", "start": 90, "end": 130},
        {"document_id": "d", "start": 110, "end": 300},
    ]

    assert bench.first_hit_rank(evidence, chunks) == 3
    assert bench.first_hit_rank(evidence, chunks[:2]) is None
    assert bench.first_hit_rank([], chunks) is None


def test_comparison_rows_cover_every_group_and_cutoff():
    metrics = {str(k): {"hit_rate": 1.0, "evidence_recall": 0.5, "complete_evidence_rate": 0.5} for k in bench.CUTOFFS}
    summary = {"answerable_questions": 2, "retrieval_errors": 0, "metrics": metrics}
    output = {
        "dataset_id": "kestrel", "run_id": "r1", "adapter_sha256": "a", "source_sha256": "s", "git_commit": "c",
        "retrieval_config": {"name": "dense", "candidate_depth": None, "rrf_k": 60},
        "snapshot": {"indexes": [{"document_id": "d", "chunk_size": 800, "overlap": 80, "model_name": "m", "index_id": "x"}]},
        "summary": summary, "by_type": {"two-hop": summary}, "latency_ms": {"mean": 12.0},
    }

    rows = bench.comparison_rows([output])

    assert len(rows) == 2 * len(bench.CUTOFFS)
    assert {r["group"] for r in rows} == {"overall", "two-hop"}
    assert "index_id" not in rows[0]["index_settings"]
