"""Reciprocal rank fusion (RRF).

score(chunk) = sum over the retrievers that found it of  weight / (k + rank)      (rank is one-based)

With every weight equal to 1 this is plain RRF (Cormack et al., k = 60 by default). Chunks are deduplicated by
chunk ID. Ties are broken deterministically: higher score, then the better (smaller) best rank in any retriever,
then the caller's ``order`` key (selected-document order, then chunk position). Scores are rounded to 12 decimals
so that sums that differ only by floating-point noise count as ties.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Fused:
    chunk_id: str
    score: float
    ranks: dict[str, int]       # retriever name -> one-based rank in that retriever's candidate list


def reciprocal_rank_fusion(
    rankings: dict[str, list[str]],
    order: dict[str, tuple],
    k: int = 60,
    weights: dict[str, float] | None = None,
) -> list[Fused]:
    weights = weights or {}
    scores: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}

    for name in sorted(rankings):                      # fixed order: the sum never depends on dict order
        weight = weights.get(name, 1.0)

        for position, chunk_id in enumerate(dict.fromkeys(rankings[name]), start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + weight / (k + position)
            ranks.setdefault(chunk_id, {})[name] = position

    ordered = sorted(
        scores,
        key=lambda chunk_id: (-round(scores[chunk_id], 12), min(ranks[chunk_id].values()), order[chunk_id]),
    )

    return [Fused(chunk_id, scores[chunk_id], ranks[chunk_id]) for chunk_id in ordered]
