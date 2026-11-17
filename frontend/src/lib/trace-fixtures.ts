export const FIXTURE_PREFIX = "fixture:"

const base = {
  schema_version: 1,
  started_at: "2026-11-16T10:00:00Z",
  finished_at: "2026-11-16T10:00:02Z",
  duration_ms: 1840,
}

export const fixtures: Record<string, unknown> = {
  answered: {
    ...base,
    trace_id: "fixture:answered",
    operation: "ask",
    status: "answered",
    stages: [
      { name: "retrieval", status: "ok", duration_ms: 120 },
      { name: "generation", status: "ok", duration_ms: 1650 },
    ],
    ranked_chunks: [
      { chunk_id: "idx-a:12", rank: 1, retriever_ranks: { dense: 3, bm25: 1 } },
      { chunk_id: "idx-a:13", rank: 2, retriever_ranks: { dense: 1 } },
    ],
    usage: { llm_calls: 1, input_tokens: 812, output_tokens: 64 },
  },
  abstained: {
    ...base,
    trace_id: "fixture:abstained",
    operation: "ask",
    status: "abstained",
    stages: [
      { name: "retrieval", status: "ok", duration_ms: 95 },
      { name: "generation", status: "ok", duration_ms: 1200 },
    ],
    ranked_chunks: [{ chunk_id: "idx-a:40", rank: 1, retriever_ranks: { dense: 1 } }],
    usage: { llm_calls: 1, input_tokens: null, output_tokens: null },
  },
  noRetrieval: {
    ...base,
    trace_id: "fixture:noRetrieval",
    operation: "ask",
    status: "abstained",
    stages: [{ name: "retrieval", status: "ok", duration_ms: 40 }],
    ranked_chunks: [],
    usage: { llm_calls: 0, input_tokens: 0, output_tokens: 0 },
  },
  failedRebuild: {
    ...base,
    trace_id: "fixture:failedRebuild",
    operation: "index_rebuild",
    status: "failed",
    stages: [
      { name: "chunking", status: "ok", duration_ms: 12 },
      { name: "embedding", status: "failed", duration_ms: 900 },
    ],
    index: {
      chunk_size: 800,
      overlap: 80,
      chunk_count: 412,
      attempted_index_id: "idx-new",
      published_index_id: null,
    },
  },
  running: {
    ...base,
    trace_id: "fixture:running",
    operation: "ask",
    status: "running",
    finished_at: null,
    duration_ms: null,
    stages: [{ name: "retrieval", status: "running" }],
  },
  unknownSchema: { schema_version: 99, trace_id: "fixture:unknownSchema" },
}