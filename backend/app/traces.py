import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.database import database
from app.redaction import RedactionSummary


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/traces", tags=["traces"])

TRACE_RETENTION = timedelta(days=30)
Operation = Literal["question", "index_rebuild"]
Outcome = Literal[
    "running",
    "answered",
    "abstained",
    "indexed",
    "invalid_output",
    "blocked",
    "error",
    "interrupted",
]

TRACED_ROUTES: dict[str, Operation] = {
    "/api/questions": "question",
    "/api/indexes/rebuild": "index_rebuild",
}


class RankedChunk(BaseModel):
    chunk_id: str
    index_id: str
    fused_rank: int
    retriever_ranks: dict[str, int]


class RetrievalDetails(BaseModel):
    index_ids: list[str]
    retrievers: list[str]
    top_k: int
    candidate_depth: int
    rrf_k: int
    weights: dict[str, float]
    ranked_chunks: list[RankedChunk]


class IndexDetails(BaseModel):
    chunk_size: int
    overlap: int
    attempted_index_id: str | None = None
    published_index_id: str | None = None
    chunk_count: int | None = None


class TraceRecord(BaseModel):
    schema_version: Literal[1] = 1
    trace_id: UUID = Field(default_factory=uuid4)
    operation: Operation
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    outcome: Outcome = "running"
    error_code: str | None = None
    http_status: int | None = None
    timings_ms: dict[str, float] = Field(default_factory=dict)
    retrieval: RetrievalDetails | None = None
    indexing: IndexDetails | None = None
    model: str | None = None
    llm_calls: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    redaction: RedactionSummary | None = None


def initialize_traces() -> None:
    with database() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS operation_traces (
                trace_id TEXT PRIMARY KEY,
                expires_at TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS operation_trace_expiry
            ON operation_traces (expires_at)
            """
        )
        now = datetime.now(timezone.utc)
        connection.execute(
            "DELETE FROM operation_traces WHERE expires_at <= ?",
            (now.isoformat(),),
        )
        rows = connection.execute(
            """
            SELECT payload FROM operation_traces
            WHERE json_extract(payload, '$.outcome') = 'running'
            """
        )
        for row in rows:
            trace = TraceRecord.model_validate_json(row["payload"])
            trace.outcome = "interrupted"
            trace.error_code = "process_interrupted"
            trace.finished_at = now
            connection.execute(
                "UPDATE operation_traces SET payload = ? WHERE trace_id = ?",
                (trace.model_dump_json(), str(trace.trace_id)),
            )


def start_trace(trace: TraceRecord) -> None:
    expires_at = trace.started_at + TRACE_RETENTION
    with database() as connection:
        connection.execute(
            "DELETE FROM operation_traces WHERE expires_at <= ?",
            (trace.started_at.isoformat(),),
        )
        connection.execute(
            "INSERT INTO operation_traces VALUES (?, ?, ?)",
            (str(trace.trace_id), expires_at.isoformat(), trace.model_dump_json()),
        )


def finish_trace(trace: TraceRecord) -> None:
    with database() as connection:
        connection.execute(
            "UPDATE operation_traces SET payload = ? WHERE trace_id = ?",
            (trace.model_dump_json(), str(trace.trace_id)),
        )


@router.get("/{trace_id}", response_model=TraceRecord)
def get_trace(trace_id: UUID, response: Response) -> TraceRecord:
    with database() as connection:
        row = connection.execute(
            """
            SELECT payload FROM operation_traces
            WHERE trace_id = ? AND expires_at > ?
            """,
            (str(trace_id), datetime.now(timezone.utc).isoformat()),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Trace was not found or expired.")

    response.headers["Cache-Control"] = "no-store"
    return TraceRecord.model_validate_json(row["payload"])


async def trace_operation(request: Request, call_next):
    operation = TRACED_ROUTES.get(request.url.path)
    if request.method != "POST" or operation is None:
        return await call_next(request)

    trace = TraceRecord(operation=operation)
    started = perf_counter()

    try:
        await run_in_threadpool(start_trace, trace)
    except sqlite3.Error:
        logger.error("Could not start operation trace")
        return JSONResponse({"detail": "Trace storage is unavailable."}, status_code=503)

    request.state.trace = trace

    try:
        response = await call_next(request)
    except Exception as error:
        logger.error("Traced request failed with %s", type(error).__name__)
        response = JSONResponse({"detail": "The operation failed."}, status_code=500)

    trace.http_status = response.status_code
    if trace.outcome == "running":
        trace.outcome = "error"
        trace.error_code = {
            404: "resource_not_found",
            409: "operation_conflict",
            422: "validation_failed",
            503: "service_unavailable",
            504: "service_timeout",
        }.get(response.status_code, "operation_failed")

    trace.finished_at = datetime.now(timezone.utc)
    trace.timings_ms["total"] = round((perf_counter() - started) * 1000, 2)

    try:
        await run_in_threadpool(finish_trace, trace)
    except sqlite3.Error:
        logger.error("Could not finalize trace %s", trace.trace_id)

    response.headers["X-Trace-Id"] = str(trace.trace_id)
    response.headers["Cache-Control"] = "no-store"
    return response
