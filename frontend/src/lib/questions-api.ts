import { z } from "zod"
import { ApiError, traceIdFrom } from "@/lib/api-error"

export type RetrieverName = "dense" | "bm25" | "graph"


const graphEntitySchema = z.object({
  name: z.string(),
})

const graphSourceSchema = z.object({
  chunk_id: z.string(),
  filename: z.string(),
  start: z.number().int().nonnegative(),
  end: z.number().int().nonnegative(),
  quote: z.string(),
})

const graphEdgeSchema = z.object({
  subject: graphEntitySchema,
  relation: z.string(),
  object: graphEntitySchema,
  sources: z.array(graphSourceSchema),
})

const graphPathSchema = z.object({
  matched_entity: graphEntitySchema,
  edges: z.array(graphEdgeSchema),
  traversed_reverse: z.array(z.boolean()),
})

export type GraphPath = z.infer<typeof graphPathSchema>

const citationSchema = z.object({
  chunk_id: z.string(),
  document_id: z.string(),
  index_id: z.string(),
  filename: z.string(),
  content_hash: z.string(),
  start: z.number().int().nonnegative(),
  end: z.number().int().positive(),
  text: z.string(),
  distance: z.number().finite().nullable().optional(),
  fused_rank: z.number().int().default(1),
  fused_score: z.number().optional(),
  retriever_ranks: z.record(z.string(), z.number()).default({}),
  graph_paths: z.array(graphPathSchema).default([]),
})

const questionResponseSchema = z.object({
  question: z.string(),
  status: z.enum(["answered", "insufficient_evidence"]),
  answer: z.string().min(1),
  citations: z.array(citationSchema).max(20),
  model: z.string().nullable(),
  trace_id: z.string().nullable().optional(),
  retrieval: z
    .object({
      retrievers: z.array(z.string()),
      candidate_depth: z.number(),
      rrf_k: z.number(),
    })
    .nullable()
    .optional(),
})

export type QuestionResponse = z.infer<typeof questionResponseSchema>

export type QuestionRequest = {
  question: string
  document_ids: string[]
  top_k: number
  retrievers: RetrieverName[]
}

export async function askQuestion(
  request: QuestionRequest,
): Promise<QuestionResponse> {
  let response: Response

  try {
    response = await fetch("/api/questions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
      signal: AbortSignal.timeout(180000),
    })
  } catch {
    throw new ApiError(
      "The server could not be reached or the answer timed out. " +
        "Check the backend before retrying.",
    )
  }

  const headerTraceId = traceIdFrom(response)
  const body: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    const error = z.object({ detail: z.string() }).safeParse(body)

    throw new ApiError(
      error.success
        ? error.data.detail
        : `The question failed (HTTP ${response.status}). Check your inputs.`,
      response.status,
      headerTraceId,
    )
  }

  const parsed = questionResponseSchema.safeParse(body)

  if (!parsed.success) {
    throw new ApiError(
      "The server returned an unexpected answer format.",
      response.status,
      headerTraceId,
    )
  }

  const result = parsed.data
  const citationIds = result.citations.map((citation) => citation.chunk_id)

  if (
    result.question !== request.question ||
    (result.status === "answered" && result.citations.length === 0) ||
    (result.status === "insufficient_evidence" &&
      result.citations.length !== 0) ||
    new Set(citationIds).size !== citationIds.length ||
    result.citations.some(
      (citation) =>
        !request.document_ids.includes(citation.document_id) ||
        citation.end <= citation.start,
    )
  ) {
    throw new ApiError(
      "The answer or its references are inconsistent.",
      response.status,
      headerTraceId,
    )
  }

  return { ...result, trace_id: result.trace_id ?? headerTraceId }
}