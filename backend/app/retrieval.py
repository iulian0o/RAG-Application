"""The shared retrieval service used by Ask (questions.py) and the benchmark (evaluation_v2.py).

    request -> one Snapshot of the active indexes -> each enabled retriever returns an ordered candidate list
            -> reciprocal rank fusion -> final top-k chunks, each with the rank every retriever gave it.

Retrievers are plain functions registered by name (``register_retriever``). Dense and BM25 live here; the
concept-graph retriever registers itself under "graph" when it exists. A request that omits ``retrievers`` is
dense-only, which behaves like the V2 function (same top-k chunks, same order, same distances).
"""
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Self

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app import bm25
from app.embeddings import embed_texts
from app.fusion import reciprocal_rank_fusion
from app.indexing import index_write_lock
from app.snapshot import Snapshot, load_snapshot
from app.vector_store import get_collection
from app.word_chunks import WordChunk, validate_chunk


router = APIRouter(prefix="/api/retrieval", tags=["retrieval"])
logger = logging.getLogger(__name__)

RetrieverName = Literal["dense", "bm25", "graph"]

# Candidate depth used when several retrievers are fused and the request does not choose one.
DEFAULT_CANDIDATE_DEPTH = 50


class RetrievalRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    question: str = Field(min_length=1, max_length=2000)
    document_ids: list[str] = Field(min_length=1, max_length=50)
    top_k: int = Field(default=5, ge=1, le=20, strict=True)

    # V3. Omitting all of these keeps the V2 behaviour (dense only).
    retrievers: list[RetrieverName] = Field(default_factory=lambda: ["dense"], min_length=1, max_length=3)
    # How many candidates each retriever contributes to the fusion. Default: top_k for a single retriever,
    # otherwise DEFAULT_CANDIDATE_DEPTH (never below top_k).
    candidate_depth: int | None = Field(default=None, ge=1, le=200, strict=True)
    rrf_k: int = Field(default=60, ge=1, le=1000, strict=True)
    # Weighted RRF. Retrievers without a weight use 1.0; omitted = plain RRF.
    weights: dict[RetrieverName, float] | None = None
    # Also return every retriever's own candidate list (used by the benchmark to compare candidate and fused ranks).
    include_candidates: bool = False

    @field_validator("document_ids")
    @classmethod
    def validate_document_ids(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]

        if any(not value for value in cleaned):
            raise ValueError("Document IDs cannot be blank.")

        return list(dict.fromkeys(cleaned))

    @field_validator("retrievers")
    @classmethod
    def validate_retrievers(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, values):
        if values is not None and any(not math.isfinite(w) or w <= 0 for w in values.values()):
            raise ValueError("Weights must be positive numbers.")

        return values

    @model_validator(mode="after")
    def validate_combination(self) -> Self:
        if self.weights is not None and not set(self.weights) <= set(self.retrievers):
            raise ValueError("Weights can only be given for enabled retrievers.")

        if self.candidate_depth is not None and self.candidate_depth < self.top_k:
            raise ValueError("candidate_depth cannot be smaller than top_k.")

        return self

    @property
    def depth(self) -> int:
        if self.candidate_depth is not None:
            return self.candidate_depth

        return self.top_k if len(self.retrievers) == 1 else max(self.top_k, DEFAULT_CANDIDATE_DEPTH)


class RetrievedChunk(BaseModel):
    chunk_id: str
    document_id: str
    index_id: str
    filename: str
    content_hash: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str
    # Cosine distance. Present only when the Dense retriever found this chunk.
    distance: float | None = Field(default=None, allow_inf_nan=False)
    # V3: where the chunk came from.
    fused_rank: int = Field(default=1, ge=1)
    fused_score: float = Field(default=0.0, allow_inf_nan=False)
    retriever_ranks: dict[str, int] = Field(default_factory=dict)      # retriever -> one-based rank
    evidence: dict[str, dict[str, Any]] = Field(default_factory=dict)  # retriever -> its own evidence
    # Filled by the graph retriever (path, matched entities, source chunks); empty for the others.
    graph_paths: list[dict[str, Any]] = Field(default_factory=list)


class CandidateRank(BaseModel):
    chunk_id: str
    rank: int
    distance: float | None = None
    score: float | None = None


class RetrievalResponse(BaseModel):
    question: str
    document_ids: list[str]
    top_k: int
    matches: list[RetrievedChunk]
    retrievers: list[str] = Field(default_factory=lambda: ["dense"])
    candidate_depth: int = 0
    rrf_k: int = 60
    weights: dict[str, float] = Field(default_factory=dict)
    candidate_counts: dict[str, int] = Field(default_factory=dict)
    timings_ms: dict[str, float] = Field(default_factory=dict)
    candidates: dict[str, list[CandidateRank]] | None = None


# ----- retriever interface --------------------------------------------------

@dataclass
class Candidate:
    chunk: WordChunk
    distance: float | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    graph_paths: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Query:
    question: str
    snapshot: Snapshot
    depth: int


Retriever = Callable[[Query], list[Candidate]]
RETRIEVERS: dict[str, Retriever] = {}


def register_retriever(name: str, function: Retriever) -> None:
    RETRIEVERS[name] = function


def dense_retriever(query: Query) -> list[Candidate]:
    snapshot = query.snapshot

    try:
        vector = embed_texts([query.question])[0]
    except ValueError as error:
        raise HTTPException(422, str(error)) from error

    count = min(query.depth, snapshot.total_chunks)
    result = get_collection().query(
        query_embeddings=[vector],
        n_results=count,
        where={"index_id": {"$in": snapshot.active_index_ids}},
        include=["documents", "metadatas", "distances"],
    )

    candidates = [
        Candidate(
            chunk=validate_chunk(chunk_id, text, metadata, snapshot.documents),
            distance=distance,
        )
        for chunk_id, text, metadata, distance in zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
        )
    ]

    if len(candidates) != count:
        raise RuntimeError("The index returned fewer chunks than expected.")

    return candidates


def bm25_retriever(query: Query) -> list[Candidate]:
    snapshot = query.snapshot
    index = bm25.get_index(snapshot.active_index_ids, snapshot.read_chunks)
    hits = index.search(query.question, query.depth, snapshot.document_order)

    return [
        Candidate(
            chunk=hit.chunk,
            evidence={"bm25": {"score": round(hit.score, 6), "matched_terms": list(hit.matched_terms)}},
        )
        for hit in hits
    ]


register_retriever("dense", dense_retriever)
register_retriever("bm25", bm25_retriever)


# ----- the service ----------------------------------------------------------

def retrieve_chunks(request: RetrievalRequest) -> RetrievalResponse:
    if not index_write_lock.acquire(blocking=False):
        raise HTTPException(
            409,
            "Another index operation is running. Retry shortly.",
        )

    try:
        started = time.perf_counter()

        for name in request.retrievers:
            if name not in RETRIEVERS:
                raise HTTPException(
                    409,
                    f"The {name} retriever is not available in this build.",
                )

        snapshot = load_snapshot(request.document_ids)
        query = Query(request.question, snapshot, request.depth)

        candidates: dict[str, list[Candidate]] = {}
        timings: dict[str, float] = {}

        for name in request.retrievers:
            began = time.perf_counter()
            candidates[name] = RETRIEVERS[name](query)
            timings[name] = round((time.perf_counter() - began) * 1000, 2)

        found: dict[str, dict[str, Candidate]] = {
            name: {c.chunk.chunk_id: c for c in candidates[name]}
            for name in request.retrievers
        }
        by_id: dict[str, Candidate] = {}
        for name in request.retrievers:
            for candidate in candidates[name]:
                by_id.setdefault(candidate.chunk.chunk_id, candidate)

        order_of_document = snapshot.document_order
        order = {
            chunk_id: (order_of_document[c.chunk.document_id], c.chunk.chunk_index)
            for chunk_id, c in by_id.items()
        }

        fused = reciprocal_rank_fusion(
            {name: [c.chunk.chunk_id for c in candidates[name]] for name in request.retrievers},
            order=order,
            k=request.rrf_k,
            weights=request.weights,
        )

        matches: list[RetrievedChunk] = []

        for position, item in enumerate(fused[:request.top_k], start=1):
            chunk = by_id[item.chunk_id].chunk
            distance = None
            evidence: dict[str, dict[str, Any]] = {}
            graph_paths: list[dict[str, Any]] = []

            for name in request.retrievers:
                candidate = found[name].get(item.chunk_id)

                if candidate is None:
                    continue

                if name == "dense":
                    distance = candidate.distance
                    evidence["dense"] = {"distance": candidate.distance}

                if name in candidate.evidence:
                    evidence[name] = candidate.evidence[name]

                if name == "graph":
                    graph_paths = candidate.graph_paths

            matches.append(
                RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    index_id=chunk.index_id,
                    filename=chunk.filename,
                    content_hash=chunk.content_hash,
                    start=chunk.start,
                    end=chunk.end,
                    text=chunk.text,
                    distance=distance,
                    fused_rank=position,
                    fused_score=item.score,
                    retriever_ranks=item.ranks,
                    evidence=evidence,
                    graph_paths=graph_paths,
                )
            )

        timings["total"] = round((time.perf_counter() - started) * 1000, 2)

        return RetrievalResponse(
            question=request.question,
            document_ids=snapshot.document_ids,
            top_k=request.top_k,
            matches=matches,
            retrievers=request.retrievers,
            candidate_depth=request.depth,
            rrf_k=request.rrf_k,
            weights={name: (request.weights or {}).get(name, 1.0) for name in request.retrievers},
            candidate_counts={name: len(candidates[name]) for name in request.retrievers},
            timings_ms=timings,
            candidates=(
                {
                    name: [
                        CandidateRank(
                            chunk_id=c.chunk.chunk_id,
                            rank=rank,
                            distance=c.distance,
                            score=c.evidence.get(name, {}).get("score"),
                        )
                        for rank, c in enumerate(candidates[name], start=1)
                    ]
                    for name in request.retrievers
                }
                if request.include_candidates
                else None
            ),
        )

    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Retrieval failed")
        raise HTTPException(
            503,
            "Retrieval failed. Check the backend logs and index status.",
        ) from error
    finally:
        index_write_lock.release()


@router.post("/search", response_model=RetrievalResponse)
def search(request: RetrievalRequest) -> RetrievalResponse:
    return retrieve_chunks(request)
