import { z } from "zod"
import { citationSchema, type QuestionRequest } from "@/lib/questions-api"

const retrievalResponseSchema = z.object({
  question: z.string(),
  document_ids: z.array(z.string()),
  index_ids: z.array(z.string()),
  matches: z.array(citationSchema).max(20),
  timings_ms: z.object({ total: z.number().nonnegative() }),
})

type ComparisonRequest = Omit<QuestionRequest, "retrievers">

export async function compareRetrieval(request: ComparisonRequest) {
  async function search(retrievers: ("dense" | "bm25")[]) {
    const response = await fetch("/api/retrieval/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...request, candidate_depth: 50, retrievers }),
      signal: AbortSignal.timeout(60000),
    })

    if (!response.ok) {
      throw new Error(`Retrieval failed (HTTP ${response.status}). Try again.`)
    }

    const parsed = retrievalResponseSchema.safeParse(await response.json())
    if (!parsed.success) {
      throw new Error("The server returned an unexpected retrieval response.")
    }

    const result = parsed.data
    const { document_ids: documentIds } = request
    if (
      result.question !== request.question ||
      result.document_ids.length !== documentIds.length ||
      documentIds.some((id, i) => id !== result.document_ids[i]) ||
      result.index_ids.length !== documentIds.length ||
      result.matches.some((chunk) => {
        const position = documentIds.indexOf(chunk.document_id)
        return position < 0 || chunk.index_id !== result.index_ids[position]
      })
    ) {
      throw new Error("The retrieval response does not match the selected sources.")
    }

    return result
  }

  // Retrieval and index updates share a non-blocking backend lock.
  const dense = await search(["dense"])
  const hybrid = await search(["dense", "bm25"])

  if (dense.index_ids.some((id, i) => id !== hybrid.index_ids[i])) {
    throw new Error("The active indexes changed during comparison. Try again.")
  }

  return { dense, hybrid }
}

export type RetrievalComparison = Awaited<ReturnType<typeof compareRetrieval>>
