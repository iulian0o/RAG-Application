export type Dataset = {
  id: string
  name: string
  questions: { id: string; type: string; question: string }[]
}

export type Chunk = {
  chunk_id: string
  filename: string
  start: number
  end: number
  text: string
}

export type RetrievedItem = Omit<Chunk, "text"> & {
  text?: string
  fused_rank?: number
  retriever_ranks?: Record<string, number>
}

export type Word = {
  word: string
  occurrences: number
  chunk_count: number
}

type Page = { offset: number; limit: number }

export type Vocabulary = Page & {
  total_words: number
  total_chunks: number
  words: Word[]
}

export type WordMatches = Page & Word & {
  matches: { chunk: Chunk; occurrences: number }[]
}

export type QuestionWords = {
  question: string
  present: (Word & {
    question_occurrences: number
    chunk_counts: { chunk_id: string; occurrences: number }[]
  })[]
  absent: string[]
  chunks: Chunk[]
}

type Metric = {
  hit_rate: number | null
  evidence_recall: number | null
  complete_evidence_rate: number | null
}

type Summary = {
  questions: number
  answerable_questions: number
  retrieval_errors: number
  generation_errors: number
  metrics: Record<string, Metric>
}

export type RunConfiguration = {
  name?: string
  git_commit?: string | null
  retrievers?: string[]
  fusion?: string
  weights?: Record<string, number> | null
  rrf_k?: number
  candidate_depth?: number | null
  final_top_k?: number
}

export type EvaluationRun = RunConfiguration & {
  run_id: string
  dataset_name: string
  status: string
  kind?: string
  error?: string
  settings?: RunConfiguration & {
    generate_answers?: boolean
    answer_top_k?: number
  }
  retrieval_config?: RunConfiguration
  latency_ms?: { mean: number | null; max: number | null }
  snapshot?: {
    indexes: {
      document_id: string
      chunk_size: number
      overlap: number
      model_name: string
    }[]
  }
  summary?: Summary
  by_type?: Record<string, Summary>
  results: {
    id: string
    question: string
    type: string
    answerable: boolean
    retrieved: RetrievedItem[]
    retrieval_error: string | null
    generation_error: string | null
    answer: { status: string; answer: string; citation_ids: string[] } | null
    first_hit_rank?: number | null
    retrieval_latency_ms?: number | null
    end_to_end_latency_ms?: number | null
    llm_calls?: number | null
    input_tokens?: number | null
    output_tokens?: number | null
  }[]
}

export async function requestJson<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(path, { cache: "no-store", ...options })

  if (!response.ok) {
    const body: { detail?: unknown } = await response.json().catch(() => ({}))
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (HTTP ${response.status}).`,
    )
  }

  return response.json() as Promise<T>
}

export function postJson<T>(path: string, body: object): Promise<T> {
  return requestJson<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
}