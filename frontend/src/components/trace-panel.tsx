import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  fetchTrace,
  TraceNotFoundError,
  type TraceResult,
} from "@/lib/trace-api"

type State =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "ready"; result: TraceResult }
  | { phase: "missing" }
  | { phase: "error"; message: string }

function unavailable(value: number | null | undefined) {
  return value === null || value === undefined ? "unavailable" : String(value)
}

export function TracePanel({ traceId }: { traceId: string | null }) {
  const [state, setState] = useState<State>({ phase: "idle" })
  const controller = useRef<AbortController | null>(null)

  useEffect(() => () => controller.current?.abort(), [])

  if (!traceId) return null

  const id = traceId

  async function load() {
    controller.current?.abort()
    const current = new AbortController()
    controller.current = current
    setState({ phase: "loading" })

    try {
      const result = await fetchTrace(id, current.signal)
      if (!current.signal.aborted) setState({ phase: "ready", result })
    } catch (error) {
      if (current.signal.aborted) return

      if (error instanceof TraceNotFoundError) {
        setState({ phase: "missing" })
      } else {
        setState({
          phase: "error",
          message:
            error instanceof Error
              ? error.message
              : "The trace could not be loaded.",
        })
      }
    }
  }

  const ready = state.phase === "ready" ? state.result : null
  const trace = ready?.kind === "trace" ? ready.trace : null

  return (
    <section aria-label="Trace" className="space-y-2 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={state.phase === "loading"}
          onClick={() => void load()}
        >
          {state.phase === "idle" ? "View trace" : "Refresh trace"}
        </Button>
        <span className="break-all text-xs text-muted-foreground">
          Trace ID: {id}
        </span>
      </div>

      <div role="status" aria-live="polite">
        {state.phase === "loading" && "Loading trace…"}
        {trace?.status === "running" &&
          "This operation is still running. Refresh to update."}
      </div>

      {state.phase === "missing" && (
        <p role="alert">
          This trace is no longer available (expired or unknown). Your result
          is unchanged.
        </p>
      )}

      {state.phase === "error" && <p role="alert">{state.message}</p>}

      {ready?.kind === "unsupported" && (
        <p role="alert">
          This trace uses an unsupported schema version (
          {String(ready.version)}).
        </p>
      )}

      {trace && (
        <div className="space-y-3 rounded-md border p-3">
          <p>
            {trace.operation.replaceAll("_", " ")} · status:{" "}
            {trace.status.replaceAll("_", " ")} ·{" "}
            {trace.duration_ms == null
              ? "duration unavailable"
              : `${Math.round(trace.duration_ms)} ms`}
          </p>

          {trace.stages.length > 0 && (
            <ol className="list-decimal space-y-1 pl-5">
              {trace.stages.map((stage, position) => (
                <li key={`${stage.name}-${position}`}>
                  {stage.name}
                  {stage.status ? ` — ${stage.status}` : ""}
                  {stage.duration_ms != null
                    ? ` (${Math.round(stage.duration_ms)} ms)`
                    : ""}
                </li>
              ))}
            </ol>
          )}

          {trace.ranked_chunks && (
            <div>
              <h4 className="font-semibold">Ranked chunks</h4>
              {trace.ranked_chunks.length === 0 ? (
                <p>No chunks were retrieved.</p>
              ) : (
                <ul className="space-y-1">
                  {trace.ranked_chunks.map((chunk) => (
                    <li key={chunk.chunk_id} className="break-all">
                      #{chunk.rank} {chunk.chunk_id}
                      {chunk.retriever_ranks &&
                        ` — ${Object.entries(chunk.retriever_ranks)
                          .map(([name, rank]) => `${name}: ${rank}`)
                          .join(", ")}`}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {trace.usage && (
            <p>
              Provider calls: {unavailable(trace.usage.llm_calls)} · input
              tokens: {unavailable(trace.usage.input_tokens)} · output tokens:{" "}
              {unavailable(trace.usage.output_tokens)}
            </p>
          )}

          {trace.index && (
            <p className="break-all">
              Chunk size {unavailable(trace.index.chunk_size)} · overlap{" "}
              {unavailable(trace.index.overlap)} · chunks{" "}
              {unavailable(trace.index.chunk_count)} · attempted index{" "}
              {trace.index.attempted_index_id ?? "none"} · published index{" "}
              {trace.index.published_index_id ?? "none"}
            </p>
          )}
        </div>
      )}
    </section>
  )
}