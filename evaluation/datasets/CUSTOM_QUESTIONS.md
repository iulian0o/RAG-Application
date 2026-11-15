# Custom corpus question set

These ten draft questions were generated with AI assistance from the actual uploaded got.md document on 10 November 2026. The team should review the questions and reference answers before treating the dataset as final. The document hash in custom.json identifies the stored, normalized extract. The extract ends during Jon's protection of Sam and contains corrupted punctuation inherited from the source conversion. Evidence preserves the exact stored characters and line breaks so that offsets resolve correctly.

The source JSONL and JSON adapter contain the same records. V3 preserves `got-01` through `got-10` and appends one exact-identifier question and three two-hop questions with separate evidence spans. The set now has twelve answerable and two unanswerable questions. The new chains cover identifying a sword from its maker, resolving Littlefinger's account of a wager, and identifying the Kingslayer's twin. The twin question is a short chain whose hops can fit in one chunk. Keep the original ten-question subset when comparing to archived V2 results.

Run the no-context baseline from backend, review each response, and fill correct_without_context and review_notes in the generated results file. A popular novel can produce correct answers from model memory. Preserve those observations and decide whether to retain or replace such questions before comparing retrieval configurations. The synthetic company material remains explicitly separate from this novel corpus.

```powershell
python -m app.evaluate_no_context custom
```

Freeze both custom.json and custom.source.jsonl during comparison runs. If you edit a question or repair the source text, record the revision and update both question files and any affected hashes or offsets before collecting new evaluation results. No baseline answers or grades have been generated as part of preparing these files.
