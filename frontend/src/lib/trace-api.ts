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

  const parsed = traceSchema.safeParse(body)

  if (!parsed.success) throw new Error("The trace has an unexpected shape.")

  return { kind: "trace", trace: parsed.data }
}