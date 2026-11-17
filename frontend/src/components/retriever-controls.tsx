import { type RetrieverName } from "@/lib/questions-api"

const OPTIONS: { id: RetrieverName; label: string }[] = [
  { id: "dense", label: "Dense" },
  { id: "bm25", label: "BM25" },
  { id: "graph", label: "Concept Graph" },
]

type RetrieverControlsProps = {
  value: RetrieverName[]
  onChange: (value: RetrieverName[]) => void
  disabled: boolean
}

export function RetrieverControls({
  value,
  onChange,
  disabled,
}: RetrieverControlsProps) {
  function toggle(id: RetrieverName) {
    onChange(
      value.includes(id) ? value.filter((name) => name !== id) : [...value, id],
    )
  }

  return (
    <fieldset className="space-y-2" disabled={disabled}>
      <legend className="text-sm font-medium">Retrievers</legend>

      <div className="flex flex-wrap gap-4">
        {OPTIONS.map(({ id, label }) => (
          <label key={id} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={value.includes(id)}
              onChange={() => toggle(id)}
            />
            {label}
          </label>
        ))}
      </div>

      {value.length === 0 && (
        <p role="alert" className="text-xs text-destructive">
          Select at least one retriever.
        </p>
      )}

      <p className="text-xs text-muted-foreground">
        Several retrievers are combined with reciprocal rank fusion.
      </p>
    </fieldset>
  )
}