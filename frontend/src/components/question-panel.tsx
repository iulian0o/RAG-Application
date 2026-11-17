import { useState, type FormEvent } from "react"
import { GraphPathPanel } from "@/components/graph-path-panel"

import { Button } from "@/components/ui/button"
import { RetrieverControls } from "@/components/retriever-controls"
import { TracePanel } from "@/components/trace-panel"
import { ApiError } from "@/lib/api-error"
import { type StoredDocument } from "@/lib/documents-api"
import {
  askQuestion,
  type QuestionResponse,
  type RetrieverName,
} from "@/lib/questions-api"
import { compareRetrieval, type RetrievalComparison } from "@/lib/retrieval-api"

type QuestionPanelProps = {
  documents: StoredDocument[]
  disabled: boolean
  onBusyChange: (busy: boolean) => void
}

type AnswerSnapshot = {
  response: QuestionResponse
  filenames: string[]
  topK: number
}

type ComparisonSnapshot = {
  requestKey: string
  result: RetrievalComparison
}

export function QuestionPanel({
  documents,
  disabled,
  onBusyChange,
}: QuestionPanelProps) {
  const [question, setQuestion] = useState("")
  const [topK, setTopK] = useState("5")
  const [retrievers, setRetrievers] = useState<RetrieverName[]>(["dense"])
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState("")
  const [errorTraceId, setErrorTraceId] = useState<string | null>(null)
  const [snapshot, setSnapshot] = useState<AnswerSnapshot | null>(null)
  const [comparing, setComparing] = useState(false)
  const [comparison, setComparison] = useState<ComparisonSnapshot | null>(null)
  const [comparisonError, setComparisonError] = useState("")

  const locked = disabled || asking || comparing
  const noSelection = documents.length === 0
  const comparisonRequest = {
    question: question.trim(),
    document_ids: documents.map((document) => document.id),
    top_k: Number(topK),
  }
  const comparisonKey = JSON.stringify(comparisonRequest)
  const canCompare =
    !locked &&
    !noSelection &&
    comparisonRequest.question.length > 0 &&
    Number.isInteger(comparisonRequest.top_k) &&
    comparisonRequest.top_k >= 1 &&
    comparisonRequest.top_k <= 20
  const visibleComparison =
    comparison?.requestKey === comparisonKey ? comparison.result : null

  async function handleCompare() {
    if (!canCompare) return

    setComparison(null)
    setComparisonError("")
    setComparing(true)
    onBusyChange(true)
    try {
      const result = await compareRetrieval(comparisonRequest)
      setComparison({ requestKey: comparisonKey, result })
    } catch (reason) {
      setComparisonError(
        reason instanceof Error
          ? reason.message
          : "The retrieval comparison could not be completed.",
      )
    } finally {
      setComparing(false)
      onBusyChange(false)
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (locked) return

    const trimmedQuestion = question.trim()
    const count = Number(topK)

    setError("")
    setErrorTraceId(null)

    if (!trimmedQuestion) {
      setError("Enter a question.")
      return
    }

    if (noSelection) {
      setError("Select at least one document above.")
      return
    }

    if (retrievers.length === 0) {
      setError("Select at least one retriever.")
      return
    }

    if (
      topK.trim() === "" ||
      !Number.isInteger(count) ||
      count < 1 ||
      count > 20
    ) {
      setError("Top-k must be a whole number from 1 to 20.")
      return
    }

    const selectedDocuments = [...documents]

    setSnapshot(null)
    setAsking(true)
    onBusyChange(true)

    try {
      const response = await askQuestion({
        question: trimmedQuestion,
        document_ids: selectedDocuments.map((document) => document.id),
        top_k: count,
        retrievers,
      })

      setSnapshot({
        response,
        filenames: selectedDocuments.map((document) => document.filename),
        topK: count,
      })
    } catch (reason) {
      if (reason instanceof ApiError) setErrorTraceId(reason.traceId)

      setError(
        reason instanceof Error
          ? reason.message
          : "The question could not be completed.",
      )
    } finally {
      setAsking(false)
      onBusyChange(false)
    }
  }

  return (
    <section
      aria-labelledby="question-heading"
      className="space-y-5 border-t pt-6"
    >
      <div className="space-y-2">
        <h2 id="question-heading" className="text-xl font-semibold">
          Ask your chapters
        </h2>

        <p className="text-sm text-muted-foreground">
          {noSelection
            ? "Select at least one document using the checkboxes above."
            : `Selected: ${documents.map((document) => document.filename).join(", ")}`}
        </p>

        <p className="text-sm text-muted-foreground">
          Build an index for each selected document before asking.
          Questions use the saved index settings.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <label htmlFor="question" className="text-sm font-medium">
            Your question
          </label>

          <textarea
            id="question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="What happened when the message arrived?"
            rows={4}
            maxLength={2000}
            required
            disabled={locked}
            className="block w-full rounded-md border bg-background px-3 py-2 text-sm"
          />
        </div>

        <div className="max-w-xs space-y-2">
          <label htmlFor="top-k" className="text-sm font-medium">
            Maximum passages to retrieve (top-k)
          </label>

          <input
            id="top-k"
            type="number"
            min={1}
            max={20}
            step={1}
            required
            value={topK}
            onChange={(event) => setTopK(event.target.value)}
            disabled={locked}
            className="block w-full rounded-md border bg-background px-3 py-2"
          />

          <p className="text-xs text-muted-foreground">
            Applies to your next question. Changing this does not rebuild indexes.
          </p>
        </div>

        <RetrieverControls
          value={retrievers}
          onChange={setRetrievers}
          disabled={locked}
        />

        <div className="flex flex-wrap gap-2">
          <Button
            type="submit"
            disabled={locked || noSelection || retrievers.length === 0}
          >
            {asking ? "Finding an answer…" : "Ask question"}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={!canCompare}
            onClick={() => void handleCompare()}
          >
            {comparing ? "Comparing…" : "Compare retrieval"}
          </Button>
        </div>
      </form>

      {comparing && <p role="status">Comparing Dense and Dense + BM25…</p>}
      {comparisonError && (
        <p role="alert" className="text-sm text-destructive">{comparisonError}</p>
      )}
      {visibleComparison && <ComparisonResults result={visibleComparison} />}

      <p role="status" aria-live="polite" className="text-sm">
        {asking
          ? "Retrieving passages and preparing an answer…"
          : snapshot
            ? "Response ready."
            : ""}
      </p>

      {error && (
        <div className="space-y-2">
          <div role="alert" className="space-y-1 text-sm text-destructive">
            <p>{error}</p>
            {/Concept Graph/i.test(error) && (
              <p className="text-xs">
                The Concept Graph is built from the indexed Kestrel documents.
                Build or rebuild it (see the README), or uncheck Concept Graph
                to ask with Dense and BM25 only.
              </p>
            )}
          </div>
          <TracePanel key={errorTraceId ?? "none"} traceId={errorTraceId} />
        </div>
      )}

      {snapshot && (
        <article className="space-y-4 rounded-lg border p-5">
          <div className="space-y-1">
            <h3 className="font-semibold">
              {snapshot.response.status === "answered"
                ? "Answer"
                : "Insufficient evidence"}
            </h3>

            <p className="text-sm font-medium">
              {snapshot.response.question}
            </p>

            <p className="text-xs text-muted-foreground">
              Sources selected: {snapshot.filenames.join(", ")}
              {" · "}Top-k: {snapshot.topK}
            </p>

            {snapshot.response.retrieval && (
              <p className="text-xs text-muted-foreground">
                Retrievers: {snapshot.response.retrieval.retrievers.join(" + ")}
                {" · "}Candidate depth:{" "}
                {snapshot.response.retrieval.candidate_depth}
                {" · "}RRF k: {snapshot.response.retrieval.rrf_k}
              </p>
            )}
          </div>

          {snapshot.response.status === "insufficient_evidence" && (
            <p className="text-sm text-muted-foreground">
              The selected sources did not provide enough evidence.
            </p>
          )}

          <p className="text-xs text-muted-foreground">
            AI-generated. Verify against the passages below.
          </p>

          <p className="whitespace-pre-wrap break-words text-sm leading-7">
            {snapshot.response.answer}
          </p>

          <TracePanel
            key={snapshot.response.trace_id ?? "none"}
            traceId={snapshot.response.trace_id ?? null}
          />

          {snapshot.response.citations.length > 0 && (
            <div className="space-y-3">
              <h4 className="text-sm font-semibold">
                Supporting passages
              </h4>

              <p className="text-xs text-muted-foreground">
                Open a reference to inspect the exact passage supplied with
                this answer.
              </p>

              {snapshot.response.citations.map((citation, position) => (
                <details
                  key={citation.chunk_id}
                  className="rounded-md border p-3"
                >
                  <summary className="cursor-pointer break-words text-sm font-medium">
                    [{position + 1}] {citation.filename}
                  </summary>

                  <blockquote className="mt-3 whitespace-pre-wrap break-words border-l-2 pl-3 text-sm leading-6">
                    {citation.text}
                  </blockquote>

                  <p className="mt-3 break-all text-xs text-muted-foreground">
                    Chunk: {citation.chunk_id}
                  </p>

                  <p className="mt-1 text-xs text-muted-foreground">
                    Source character range: [{citation.start}, {citation.end})
                  </p>

                  <p className="mt-1 text-xs text-muted-foreground">
                    Fused rank: #{citation.fused_rank}
                    {Object.entries(citation.retriever_ranks).map(
                      ([name, rank]) => ` · ${name}: ${rank}`,
                    )}
                    {citation.distance != null &&
                      ` · distance ${citation.distance.toFixed(3)}`}
                  </p>

                  <GraphPathPanel paths={citation.graph_paths} />
                </details>
              ))}
            </div>
          )}
        </article>
      )}
    </section>
  )
}

function ComparisonResults({ result }: { result: RetrievalComparison }) {
  const columns = [
    { label: "Dense", search: result.dense, other: result.hybrid },
    { label: "Dense + BM25", search: result.hybrid, other: result.dense },
  ]

  return (
    <section aria-labelledby="comparison-heading" className="space-y-3">
      <h3 id="comparison-heading" className="font-semibold">Retrieval comparison</h3>
      <div className="grid gap-4 md:grid-cols-2">
        {columns.map(({ label, search, other }) => {
          const otherRanks = new Map(
            other.matches.map((chunk) => [chunk.chunk_id, chunk.fused_rank]),
          )
          return (
            <section key={label} className="min-w-0 space-y-2 rounded-md border p-3">
              <h4 className="text-sm font-semibold">{label}</h4>
              <p className="text-xs text-muted-foreground">
                {Math.round(search.timings_ms.total)} ms
              </p>
              {search.matches.length === 0 && <p className="text-sm">No passages retrieved.</p>}
              {search.matches.map((chunk) => {
                const otherRank = otherRanks.get(chunk.chunk_id)
                return (
                  <details key={chunk.chunk_id} className="rounded-md border p-2">
                    <summary className="cursor-pointer break-words text-sm">
                      #{chunk.fused_rank} {chunk.filename}
                    </summary>
                    <p className="mt-2 text-xs text-muted-foreground">
                      {otherRank === undefined
                        ? "Outside the other configuration’s top results"
                        : `Rank in the other configuration: #${otherRank}`}
                      {Object.entries(chunk.retriever_ranks).map(
                        ([name, rank]) => ` · ${name}: #${rank}`,
                      )}
                    </p>
                    <p className="mt-1 break-all text-xs text-muted-foreground">
                      Chunk {chunk.chunk_id} · characters [{chunk.start}, {chunk.end})
                    </p>
                    <blockquote className="mt-2 whitespace-pre-wrap break-words text-sm">
                      {chunk.text}
                    </blockquote>
                  </details>
                )
              })}
            </section>
          )
        })}
      </div>
    </section>
  )
}
