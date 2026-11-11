import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  postJson,
  requestJson,
  type Chunk,
  type Dataset,
  type QuestionWords,
  type Vocabulary,
  type WordMatches,
} from "@/lib/v2-api"
import { useRequest } from "@/lib/use-request"

type Result =
  | { kind: "vocabulary"; value: Vocabulary }
  | { kind: "word"; value: WordMatches }
  | { kind: "question"; value: QuestionWords }

const fieldClass = "rounded-md border bg-background px-3 py-2"

function ChunkDetail({ chunk, count }: { chunk: Chunk; count: number }) {
  return (
    <details className="rounded-md border p-3">
      <summary className="cursor-pointer break-words">
        {chunk.filename} · characters {chunk.start}–{chunk.end} · {count} occurrences
      </summary>
      <p className="mt-2 whitespace-pre-wrap break-words text-sm">{chunk.text}</p>
    </details>
  )
}

export function WordsPanel({ documentIds }: { documentIds: string[] }) {
  const [mode, setMode] = useState<"corpus" | "question">("corpus")
  const [word, setWord] = useState("")
  const [question, setQuestion] = useState("")
  const result = useRequest<Result>()
  const datasets = useRequest<Dataset[]>()
  const value = result.data
  const selection = { document_ids: documentIds }

  function loadVocabulary(offset = 0) {
    return result.run(async () => ({
      kind: "vocabulary",
      value: await postJson<Vocabulary>("/api/words/vocabulary", {
        ...selection, offset, limit: 25,
      }),
    }))
  }

  function loadWord(input: string, offset = 0) {
    setWord(input)
    return result.run(async () => ({
      kind: "word",
      value: await postJson<WordMatches>("/api/words/chunks", {
        ...selection, word: input, offset, limit: 10,
      }),
    }))
  }

  function analyzeQuestion() {
    return result.run(async () => ({
      kind: "question",
      value: await postJson<QuestionWords>("/api/words/question", {
        ...selection, question,
      }),
    }))
  }

  if (documentIds.length === 0) {
    return <p>Select indexed documents to explore their words.</p>
  }

  const page = value?.kind === "vocabulary" || value?.kind === "word" ? value : null
  const total = page?.kind === "vocabulary"
    ? page.value.total_words
    : (page?.value.chunk_count ?? 0)
  const chunksById = new Map(
    value?.kind === "question"
      ? value.value.chunks.map((chunk) => [chunk.chunk_id, chunk] as const)
      : [],
  )

  function changePage(offset: number) {
    if (page?.kind === "word") void loadWord(page.value.word, offset)
    if (page?.kind === "vocabulary") void loadVocabulary(offset)
  }

  return (
    <section className="space-y-4" aria-label="Words analytics">
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" aria-pressed={mode === "corpus"}
          disabled={result.busy} onClick={() => setMode("corpus")}>
          Corpus mode
        </Button>
        <Button type="button" variant="outline" aria-pressed={mode === "question"}
          disabled={result.busy} onClick={() => setMode("question")}>
          Question mode
        </Button>
      </div>

      {mode === "corpus" ? (
        <>
          <Button type="button" disabled={result.busy}
            onClick={() => void loadVocabulary()}>
            Load vocabulary
          </Button>
          <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => {
            event.preventDefault()
            void loadWord(word.trim())
          }}>
            <label className="grid gap-1">
              Word or identifier
              <input className={fieldClass} value={word} maxLength={200}
                onChange={(event) => setWord(event.target.value)} required />
            </label>
            <Button type="submit" disabled={result.busy || !word.trim()}>
              Find chunks
            </Button>
          </form>
        </>
      ) : (
        <form className="space-y-3" onSubmit={(event) => {
          event.preventDefault()
          void analyzeQuestion()
        }}>
          <Button type="button" variant="outline" disabled={datasets.busy || result.busy}
            onClick={() => void datasets.run(() =>
              requestJson<Dataset[]>("/api/evaluation/datasets"))}>
            {datasets.busy ? "Loading question sets…" : "Load question sets"}
          </Button>
          {datasets.error && <p role="alert">{datasets.error}</p>}
          {datasets.data && (
            <label className="grid gap-1">
              Pick a question
              <select className={fieldClass} value="" disabled={result.busy}
                onChange={(event) => setQuestion(event.target.value)}>
                <option value="">Choose a question</option>
                {datasets.data.map((dataset) => (
                  <optgroup key={dataset.id} label={dataset.name}>
                    {dataset.questions.map((item) => (
                      <option key={item.id} value={item.question}>{item.question}</option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </label>
          )}
          <label className="grid gap-1">
            Question
            <textarea className={fieldClass} value={question} maxLength={2000}
              onChange={(event) => setQuestion(event.target.value)} required />
          </label>
          <Button type="submit" disabled={result.busy || !question.trim()}>
            Analyze question
          </Button>
        </form>
      )}

      {result.busy && <p role="status">Analyzing indexed chunks…</p>}
      {result.error && <p role="alert">{result.error}</p>}

      {mode === "corpus" && value?.kind === "vocabulary" && (
        <div className="space-y-2">
          <p>{value.value.total_words} distinct words across {value.value.total_chunks} chunks.</p>
          <ul className="space-y-2">
            {value.value.words.map((entry) => (
              <li key={entry.word}>
                <button type="button" className="underline"
                  onClick={() => void loadWord(entry.word)}>{entry.word}</button>
                {" · "}{entry.occurrences} occurrences · {entry.chunk_count} chunks
              </li>
            ))}
          </ul>
        </div>
      )}

      {mode === "corpus" && value?.kind === "word" && (
        <div className="space-y-2">
          <p>{value.value.word} · {value.value.occurrences} occurrences in {value.value.chunk_count} chunks.</p>
          {value.value.matches.length === 0 && <p>No matching chunks.</p>}
          {value.value.matches.map((match) => (
            <ChunkDetail key={match.chunk.chunk_id}
              chunk={match.chunk} count={match.occurrences} />
          ))}
        </div>
      )}

      {mode === "corpus" && page && total > page.value.limit && (
        <div className="flex gap-2">
          <Button type="button" variant="outline" disabled={page.value.offset === 0}
            onClick={() => changePage(Math.max(0, page.value.offset - page.value.limit))}>
            Previous
          </Button>
          <Button type="button" variant="outline"
            disabled={page.value.offset + page.value.limit >= total}
            onClick={() => changePage(page.value.offset + page.value.limit)}>
            Next
          </Button>
        </div>
      )}

      {mode === "question" && value?.kind === "question" && (
        <div className="space-y-3">
          <p className="break-words">Analyzed question: {value.value.question}</p>
          <p>Absent words: {value.value.absent.join(", ") || "None"}</p>
          <h3 className="font-semibold">Present words</h3>
          {value.value.present.length === 0 && <p>No question words were found.</p>}
          {value.value.present.map((entry) => (
            <details key={entry.word} className="space-y-2 rounded-md border p-3">
              <summary className="cursor-pointer">
                {entry.word} · {entry.occurrences} occurrences in {entry.chunk_count} chunks
              </summary>
              {entry.chunk_counts.map((match) => {
                const chunk = chunksById.get(match.chunk_id)
                return chunk ? (
                  <ChunkDetail key={chunk.chunk_id}
                    chunk={chunk} count={match.occurrences} />
                ) : null
              })}
            </details>
          ))}
        </div>
      )}
    </section>
  )
}