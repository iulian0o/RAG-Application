import { z } from "zod"

export const retrieverNameSchema = z.enum(["dense", "bm25", "graph"])
export type RetrieverName = z.infer<typeof retrieverNameSchema>

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
  fused_rank: z.number().int().min(1).default(1),
  fused_score: z.number().finite().default(0),
  retriever_ranks: z.record(z.string(), z.number().int().min(1)).default({}),
  evidence: z.record(z.string(), z.record(z.string(), z.unknown())).default({}),
  graph_paths: z.array(z.record(z.string(), z.unknown())).default([]),
})

export type Citation = z.infer<typeof citationSchema>

const retrievalSummarySchema = z.object({
  retrievers: z.array(z.string()),
  candidate_depth: z.number().int(),
  top_k: z.number().int(),
  rrf_k: z.number().int(),
  weights: z.record(z.string(), z.number()),
})

const questionResponseSchema = z.object({
  question: z.string(),
  status: z.enum(["answered", "insufficient_evidence"]),
  answer: z.string().min(1),
  citations: z.array(citationSchema).max(20),
  model: z.string().nullable(),
  retrieval: retrievalSummarySchema.optional(),
})

export type QuestionResponse = z.infer<typeof questionResponseSchema>

export type QuestionRequest = {
  question: string
  document_ids: string[]
  top_k: number
  retrievers?: RetrieverName[]
  candidate_depth?: number
}