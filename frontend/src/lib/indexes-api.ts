import { z } from "zod"
import { ApiError, traceIdFrom } from "@/lib/api-error"

const indexSchema = z.object({
  document_id: z.string(),
  index_id: z.string(),
  content_hash: z.string(),
  model_name: z.string(),
  chunk_size: z.number().int().positive(),
  overlap: z.number().int().nonnegative(),
  chunk_count: z.number().int().positive(),
  created_at: z.string(),
  trace_id: z.string().nullable().optional(),
})

export type DocumentIndex = z.infer<typeof indexSchema>

export type IndexSettings = {
  chunk_size: number
  overlap: number
}

async function sendRequest(
  path: string,
  options: RequestInit = {},
  timeout = 15000,
): Promise<Response> {
  try {
    return await fetch(path, {
      ...options,
      cache: "no-store",
      signal: AbortSignal.timeout(timeout),
    })
  } catch {
    throw new ApiError(
      "The server could not be reached or the request timed out. " +
        "An index build may still be running. Refresh status before retrying.",
    )
  }
}

async function readIndexResponse(response: Response): Promise<DocumentIndex> {
  const headerTraceId = traceIdFrom(response)
  const body: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    const error = z.object({ detail: z.string() }).safeParse(body)

    throw new ApiError(
      error.success
        ? error.data.detail
        : `Index request failed (HTTP ${response.status}). Check your settings.`,
      response.status,
      headerTraceId,
    )
  }

  const parsed = indexSchema.safeParse(body)

  if (!parsed.success) {
    throw new ApiError(
      "Unexpected index response. Refresh status to check the result.",
      response.status,
      headerTraceId,
    )
  }

  return { ...parsed.data, trace_id: parsed.data.trace_id ?? headerTraceId }
}

export async function getDocumentIndex(
  documentId: string,
): Promise<DocumentIndex | null> {
  const response = await sendRequest(
    `/api/indexes/${encodeURIComponent(documentId)}`,
  )

  if (response.status === 409) {
    return null
  }

  return readIndexResponse(response)
}

export async function rebuildDocumentIndex(
  documentId: string,
  settings: IndexSettings,
): Promise<DocumentIndex> {
  const response = await sendRequest(
    "/api/indexes/rebuild",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        document_id: documentId,
        settings,
      }),
    },
    120000,
  )

  return readIndexResponse(response)
}