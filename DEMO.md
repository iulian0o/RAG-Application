# Demo script (about 5 minutes)

Setup: the five Kestrel documents of docs/kestrel uploaded and indexed (800 / 80), Concept Graph built.

1. **Identifier.** Ask "What does KST-427 mean?" with Dense only, then BM25 only. Compare the rank of the supporting passage.
2. **Two hops.** Ask "Which processing region and owning team handle scheduled jobs from Aurora Reports?" with Dense + BM25 + Concept Graph. Open the graph path and the source quote of each edge.
3. **Regression.** Show one question where adding a retriever worsens the rank of the supporting passage (see the benchmark comparison CSV in evaluation/results).
4. **Stale graph.** Rebuild one document index, ask again with Concept Graph: the error explains how to rebuild.
5. **No answer.** Ask for the founder's birth date: "Insufficient evidence".
