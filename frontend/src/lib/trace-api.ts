import { z } from "zod"
import { fixtures, FIXTURE_PREFIX } from "@/lib/trace-fixtures"

export const SUPPORTED_SCHEMA = 1

export class TraceNotFoundError extends Error {}

const count = z.number().int().nonnegative().nullable().optional()

const traceSchema = z
  .object({
    schema_version: z.literal(SUPPORTED_SCHEMA),
    trace_id: z.string(),
    operation: z.string(),
    status: z.string(),
    started_at: z.string().nullable().optional(),
    finished_at: z.string().nullable().optional(),
    duration_ms: z.number().nullable().optional(),
    stages: z
      .array(
        z
          .object({
            name: z.string(),
            status: z.string().optional(),
            duration_ms: z.number().nullable().optional(),
          })
          .passthrough(),
      )
      .default([]),
    ranked_chunks: z
      .array(
        z.object({
          chunk_id: z.string(),
          rank: z.number().int(),
          retriever_ranks: z.record(z.string(), z.number()).optional(),
        }),
      )
      .optional(),
    usage: z
      .object({
        llm_calls: count,
        input_tokens: count,
        output_tokens: count,
      })
      .optional(),
    index: z
      .object({
        chunk_size: z.number().optional(),
        overlap: z.number().optional(),
        chunk_count: z.number().optional(),
        attempted_index_id: z.string().nullable().optional(),
        published_index_id: z.string().nullable().optional(),
      })
      .optional(),
  })
  .passthrough()

export type Trace = z.infer<typeof traceSchema>

export type TraceResult =
  | { kind: "trace"; trace: Trace }
  | { kind: "unsupported"; version: unknown }

async function readJson(traceId: string, signal: AbortSignal): Promise<unknown> {
  if (traceId.startsWith(FIXTURE_PREFIX)) {
    const fixture = fixtures[traceId.slice(FIXTURE_PREFIX.length)]
    if (fixture === undefined) throw new TraceNotFoundError()
    return fixture
  }

  let response: Response

  try {
    response = await fetch(`/api/traces/${encodeURIComponent(traceId)}`, {
      cache: "no-store",
      signal,
    })
    } catch (error) {
        if (signal.aborted) throw error

        throw new Error(
            "The trace could not be loaded. The server may be unreachable.",
            { cause: error },
        )
    }

  if (response.status === 404) throw new TraceNotFoundError()

  if (!response.ok) {
    throw new Error(`The trace request failed (HTTP ${response.status}).`)
  }

  return response.json().catch(() => {
    throw new Error("The trace response was not valid JSON.")
  })
}

export async function fetchTrace(
  traceId: string,
  signal: AbortSignal,
): Promise<TraceResult> {
  const body = await readJson(traceId, signal)
  const version = (body as { schema_version?: unknown } | null)?.schema_version

  if (version !== SUPPORTED_SCHEMA) return { kind: "unsupported", version }

  if (traceId.startsWith(FIXTURE_PREFIX)) {
    const parsed = traceSchema.safeParse(body)
    if (!parsed.success) throw new Error("The trace has an unexpected shape.")
    return { kind: "trace", trace: parsed.data }
  }

  const parsed = apiTraceSchema.safeParse(body)
  if (!parsed.success) throw new Error("The trace has an unexpected shape.")
  return { kind: "trace", trace: toPanelTrace(parsed.data) }
}

const apiTraceSchema = z.object({
  schema_version: z.literal(SUPPORTED_SCHEMA),
  trace_id: z.string(),
  operation: z.enum(["question", "index_rebuild"]),
  outcome: z.enum([
    "running", "answered", "abstained", "indexed",
    "invalid_output", "blocked", "error", "interrupted",
  ]),
  started_at: z.string(),
  finished_at: z.string().nullable(),
  timings_ms: z.record(z.string(), z.number().nonnegative()),
  retrieval: z.object({
    ranked_chunks: z.array(z.object({
      chunk_id: z.string(),
      fused_rank: z.number().int().positive(),
      retriever_ranks: z.record(z.string(), z.number()),
    })),
  }).nullable(),
  indexing: z.object({
    chunk_size: z.number(),
    overlap: z.number(),
    chunk_count: z.number().nullable(),
    attempted_index_id: z.string().nullable(),
    published_index_id: z.string().nullable(),
  }).nullable(),
  llm_calls: z.number().int().nonnegative(),
  input_tokens: z.number().int().nonnegative().nullable(),
  output_tokens: z.number().int().nonnegative().nullable(),
})

function toPanelTrace(record: z.infer<typeof apiTraceSchema>): Trace {
  const { total, ...stages } = record.timings_ms
  return {
    schema_version: record.schema_version,
    trace_id: record.trace_id,
    operation: record.operation,
    status: record.outcome,
    started_at: record.started_at,
    finished_at: record.finished_at,
    duration_ms: total ?? null,
    stages: Object.entries(stages).map(([name, duration_ms]) => ({
      name,
      duration_ms,
    })),
    ranked_chunks: record.retrieval?.ranked_chunks.map((chunk) => ({
      chunk_id: chunk.chunk_id,
      rank: chunk.fused_rank,
      retriever_ranks: chunk.retriever_ranks,
    })),
    usage: {
      llm_calls: record.llm_calls,
      input_tokens: record.input_tokens,
      output_tokens: record.output_tokens,
    },
    index: record.indexing
      ? { ...record.indexing, chunk_count: record.indexing.chunk_count ?? undefined }
      : undefined,
  }
}
