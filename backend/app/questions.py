from time import perf_counter
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.answer_contract import INSUFFICIENT_EVIDENCE_MESSAGE
from app.generation import (
    GenerationMetadata,
    InvalidModelOutput,
    RedactionBlocked,
    generate_answer,
)
from app.retrieval import (
    RetrievalRequest,
    RetrievedChunk,
    retrieve_chunks,
)
from app.traces import RankedChunk, RetrievalDetails, TraceRecord


router = APIRouter(prefix="/api/questions", tags=["questions"])


class QuestionResponse(BaseModel):
    question: str
    status: Literal["answered", "insufficient_evidence"]
    answer: str
    citations: list[RetrievedChunk]
    model: str | None
    trace_id: UUID | None = None


@router.post("", response_model=QuestionResponse)
def ask_question(request: RetrievalRequest, http_request: Request) -> QuestionResponse:
    trace: TraceRecord = http_request.state.trace

    started = perf_counter()
    try:
        retrieval = retrieve_chunks(request)
    finally:
        trace.timings_ms["retrieval"] = round((perf_counter() - started) * 1000, 2)

    trace.retrieval = RetrievalDetails(
        index_ids=retrieval.index_ids,
        retrievers=retrieval.retrievers,
        top_k=retrieval.top_k,
        candidate_depth=retrieval.candidate_depth,
        rrf_k=retrieval.rrf_k,
        weights=retrieval.weights,
        ranked_chunks=[
            RankedChunk(
                chunk_id=chunk.chunk_id,
                index_id=chunk.index_id,
                fused_rank=chunk.fused_rank,
                retriever_ranks={
                    name: chunk.retriever_ranks[name]
                    for name in retrieval.retrievers
                    if name in chunk.retriever_ranks
                },
            )
            for chunk in retrieval.matches
        ],
    )

    if not retrieval.matches:
        trace.outcome = "abstained"
        return QuestionResponse(
            question=request.question,
            status="insufficient_evidence",
            answer=INSUFFICIENT_EVIDENCE_MESSAGE,
            citations=[],
            model=None,
            trace_id=trace.trace_id,
        )

    evidence = [
        {"chunk_id": chunk.chunk_id, "text": chunk.text}
        for chunk in retrieval.matches
    ]
    usage: dict[str, int | None] = {}
    metadata = GenerationMetadata()
    started = perf_counter()
    try:
        draft, model_name = generate_answer(
            question=request.question,
            evidence=evidence,
            usage=usage,
            metadata=metadata,
        )
    except RedactionBlocked:
        trace.outcome = "blocked"
        trace.error_code = "redaction_failed"
        raise
    except InvalidModelOutput:
        trace.outcome = "invalid_output"
        trace.error_code = "invalid_model_output"
        raise
    finally:
        trace.redaction = metadata.redaction
        trace.timings_ms["generation"] = round((perf_counter() - started) * 1000, 2)
        trace.llm_calls = usage.get("llm_calls") or 0
        trace.input_tokens = usage.get("input_tokens")
        trace.output_tokens = usage.get("output_tokens")

    trace.model = model_name
    if draft.status == "insufficient_evidence":
        trace.outcome = "abstained"
        return QuestionResponse(
            question=request.question,
            status=draft.status,
            answer=INSUFFICIENT_EVIDENCE_MESSAGE,
            citations=[],
            model=model_name,
            trace_id=trace.trace_id,
        )

    chunks_by_id = {chunk.chunk_id: chunk for chunk in retrieval.matches}
    response = QuestionResponse(
        question=request.question,
        status="answered",
        answer=draft.answer,
        citations=[chunks_by_id[chunk_id] for chunk_id in draft.citation_ids],
        model=model_name,
        trace_id=trace.trace_id,
    )
    trace.outcome = "answered"
    return response
