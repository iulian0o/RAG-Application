import { type GraphPath } from "@/lib/questions-api"

type GraphPathPanelProps = {
  paths: GraphPath[]
}

export function GraphPathPanel({ paths }: GraphPathPanelProps) {
  if (paths.length === 0) return null

  return (
    <div className="mt-3 space-y-3">
      <p className="text-xs font-semibold">Concept Graph paths</p>

      {paths.map((path, pathIndex) => (
        <div key={pathIndex} className="space-y-2 rounded bg-muted p-3 text-xs">
          <p>
            Entity matched in the question:{" "}
            <strong>{path.matched_entity.name}</strong>
          </p>

          <ol className="list-decimal space-y-2 pl-4">
            {path.edges.map((edge, edgeIndex) => (
              <li key={edgeIndex} className="space-y-1">
                <p className="break-words">
                  {edge.subject.name} —{edge.relation}→ {edge.object.name}
                  {path.traversed_reverse[edgeIndex]
                    ? " (followed backwards)"
                    : ""}
                </p>

                {edge.sources.map((source) => (
                  <details key={`${source.chunk_id}-${source.start}`}>
                    <summary className="cursor-pointer break-all">
                      Source: {source.filename} · {source.chunk_id}
                    </summary>
                    <blockquote className="mt-1 whitespace-pre-wrap break-words border-l-2 pl-2">
                      {source.quote}
                    </blockquote>
                    <p className="mt-1 text-muted-foreground">
                      Source character range: [{source.start}, {source.end})
                    </p>
                  </details>
                ))}
              </li>
            ))}
          </ol>
        </div>
      ))}
    </div>
  )
}