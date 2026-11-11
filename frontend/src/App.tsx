import { useState } from "react"
import { DocumentPanel } from "@/components/document-panel"
import { EvaluationPanel } from "@/components/evaluation-panel"
import { Button } from "@/components/ui/button"

const views = ["Ask", "Words", "Evaluation"] as const
type View = (typeof views)[number]

export default function App() {
  const [view, setView] = useState<View>("Ask")
  const [documentMode, setDocumentMode] = useState<"ask" | "words">("ask")

  if (window.location.pathname.replace(/\/+$/, "") === "/about") {
    return (
      <main className="mx-auto max-w-4xl px-6 py-20">
        <p className="text-4xl leading-tight font-semibold sm:text-5xl">
          Denis Amselemovitch is an intriguing character who likes to make
          impromptu appearances in incongruous places.
        </p>
      </main>
    )
  }

  return (
    <main className="min-h-screen bg-background px-6 py-12 text-foreground">
      <div className="mx-auto max-w-4xl space-y-6">
        <h1 className="text-4xl font-semibold tracking-tight">RAG workspace</h1>

        <nav aria-label="Workspace views" className="flex flex-wrap gap-2">
          {views.map((item) => (
            <Button
              key={item}
              type="button"
              variant={view === item ? "default" : "outline"}
              aria-pressed={view === item}
              onClick={() => {
                setView(item)
                if (item !== "Evaluation") {
                  setDocumentMode(item === "Words" ? "words" : "ask")
                }
              }}
            >
              {item}
            </Button>
          ))}
        </nav>

        <div hidden={view === "Evaluation"}>
          <DocumentPanel mode={documentMode} />
        </div>
        <div hidden={view !== "Evaluation"}>
          <EvaluationPanel />
        </div>
      </div>
    </main>
  )
}