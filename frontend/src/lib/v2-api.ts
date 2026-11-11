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

export type EvaluationRun = {
  run_id: string
  dataset_name: string
  status: string
  error?: string
  settings: { generate_answers: boolean; answer_top_k: number }
  snapshot: {
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
    retrieved: Chunk[]
    retrieval_error: string | null
    generation_error: string | null
    answer: { status: string; answer: string; citation_ids: string[] } | null
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