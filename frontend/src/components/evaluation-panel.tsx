import { useState } from "react"
import { Button } from "@/components/ui/button"
import { postJson, requestJson, type Dataset, type EvaluationRun } from "@/lib/v2-api"
import { useRequest } from "@/lib/use-request"

function percentage(value: number | null) {
  return value === null ? "—" : `${(value * 100).toFixed(1)}%`
}

function downloadRun(run: EvaluationRun) {
  const blob = new Blob([JSON.stringify(run, null, 2)], { type: "application/json" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = `${run.run_id}.json`
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function EvaluationPanel() {
  const datasets = useRequest<Dataset[]>()
  const evaluation = useRequest<EvaluationRun>()
  const [datasetId, setDatasetId] = useState("")
  const [generateAnswers, setGenerateAnswers] = useState(false)
  const [answerTopK, setAnswerTopK] = useState("5")
  const [savedRunId, setSavedRunId] = useState("")
  const run = evaluation.data
  const groups = run?.summary
    ? [["Overall", run.summary] as const, ...Object.entries(run.by_type ?? {})]
    : []

  return (
    <section className="space-y-5" aria-label="Evaluation">
      <h2 className="text-2xl font-semibold">Evaluation</h2>

      <Button type="button" variant="outline" disabled={datasets.busy || evaluation.busy}
        onClick={() => void datasets.run(() =>
          requestJson<Dataset[]>("/api/evaluation/datasets"))}>
        {datasets.busy ? "Loading corpora…" : "Load corpora"}
      </Button>
      {datasets.error && <p role="alert">{datasets.error}</p>}
      {datasets.data?.length === 0 && <p>No evaluation datasets are available.</p>}

      <form className="space-y-3" onSubmit={(event) => {
        event.preventDefault()
        void evaluation.run(() =>
          postJson<EvaluationRun>("/api/evaluation/runs", {
            dataset_id: datasetId,
            generate_answers: generateAnswers,
            answer_top_k: generateAnswers ? Number(answerTopK) : 5,
          }),
        )
      }}>
        <fieldset className="space-y-3" disabled={evaluation.busy}>
          <label className="grid gap-1">
            Corpus
            <select className="rounded-md border bg-background p-2" required
              value={datasetId} onChange={(event) => setDatasetId(event.target.value)}>
              <option value="">Choose a corpus</option>
              {datasets.data?.map((dataset) => (
                <option key={dataset.id} value={dataset.id}>
                  {dataset.name} ({dataset.questions.length} questions)
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={generateAnswers}
              onChange={(event) => setGenerateAnswers(event.target.checked)} />
            Generate answers
          </label>
          {generateAnswers && (
            <label className="flex items-center gap-2">
              Chunks supplied to generation
              <input className="w-20 rounded-md border p-2" type="number"
                min={1} max={10} step={1} required value={answerTopK}
                onChange={(event) => setAnswerTopK(event.target.value)} />
            </label>
          )}
          <Button type="submit" disabled={!datasetId || datasets.busy}>
            Run evaluation
          </Button>
        </fieldset>
      </form>

      <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => {
        event.preventDefault()
        const id = encodeURIComponent(savedRunId.trim())
        void evaluation.run(() => requestJson<EvaluationRun>(`/api/evaluation/runs/${id}`))
      }}>
        <label className="grid gap-1">
          Saved run ID
          <input className="rounded-md border p-2" required value={savedRunId}
            onChange={(event) => setSavedRunId(event.target.value)} />
        </label>
        <Button type="submit" variant="outline" disabled={evaluation.busy || !savedRunId.trim()}>
          Open saved run
        </Button>
      </form>

      {evaluation.busy && <p role="status">Waiting for the evaluation server…</p>}
      {evaluation.error && <p role="alert">{evaluation.error}</p>}

      {run && (
        <div className="space-y-4">
          <div>
            <h3 className="font-semibold">{run.dataset_name}</h3>
            <p className="break-all">Run ID: {run.run_id}</p>
            <p>Status: {run.status.replaceAll("_", " ")}</p>
            {run.error && <p role="alert">{run.error}</p>}
            {run.summary && (
              <p>
                {run.summary.answerable_questions} of {run.summary.questions} answerable
                {" · "}{run.summary.retrieval_errors} retrieval errors
                {" · "}{run.summary.generation_errors} generation errors
              </p>
            )}
          </div>
          <Button type="button" variant="outline" onClick={() => downloadRun(run)}>
            Download JSON
          </Button>

          <details>
            <summary className="cursor-pointer">Index settings</summary>
            <ul>
              {run.snapshot.indexes.map((index) => (
                <li key={index.document_id} className="break-words">
                  {index.document_id} · {index.chunk_size} characters · {index.overlap} overlap
                  {" · "}{index.model_name}
                </li>
              ))}
            </ul>
          </details>

          {groups.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left text-sm">
                <caption className="mb-2 text-left font-semibold">Retrieval metrics</caption>
                <thead>
                  <tr className="border-b">
                    <th scope="col">Group</th>
                    <th scope="col">k</th>
                    <th scope="col">Hit rate</th>
                    <th scope="col">Evidence recall</th>
                    <th scope="col">Complete evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {groups.flatMap(([group, summary]) =>
                    Object.entries(summary.metrics).map(([k, metric]) => (
                      <tr key={`${group}-${k}`} className="border-b">
                        <td className="py-2">{group}</td>
                        <td>{k}</td>
                        <td>{percentage(metric.hit_rate)}</td>
                        <td>{percentage(metric.evidence_recall)}</td>
                        <td>{percentage(metric.complete_evidence_rate)}</td>
                      </tr>
                    )),
                  )}
                </tbody>
              </table>
            </div>
          )}

          {run.results.map((item) => (
            <details key={item.id} className="space-y-2 rounded-md border p-3">
              <summary className="cursor-pointer">
                {item.id} · {item.type} · {item.question}
              </summary>
              <p>{item.answerable ? "Answerable" : "Unanswerable"}</p>
              {item.retrieval_error && <p>Retrieval error: {item.retrieval_error}</p>}
              {item.generation_error && <p>Generation error: {item.generation_error}</p>}
              {item.answer && (
                <>
                  <p className="whitespace-pre-wrap">{item.answer.answer}</p>
                  {item.answer.citation_ids.length > 0 && (
                    <p className="break-all">Citations: {item.answer.citation_ids.join(", ")}</p>
                  )}
                </>
              )}
              <h4 className="font-semibold">Retrieved chunks</h4>
              {item.retrieved.length === 0 && <p>No chunks retrieved.</p>}
              {item.retrieved.map((chunk, rank) => (
                <details key={chunk.chunk_id} className="rounded-md border p-2">
                  <summary className="cursor-pointer break-all">
                    {rank + 1}. {chunk.filename} · {chunk.start}–{chunk.end} · {chunk.chunk_id}
                  </summary>
                  <p className="whitespace-pre-wrap break-words">{chunk.text}</p>
                </details>
              ))}
            </details>
          ))}
        </div>
      )}
    </section>
  )
}