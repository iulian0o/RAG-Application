# Custom corpus question set

These ten draft questions were generated with AI assistance from the actual uploaded got.md document on 10 November 2026. The team should review the questions and reference answers before treating the dataset as final. The document hash in custom.json identifies the stored, normalized extract. The extract ends during Jon's protection of Sam and contains corrupted punctuation inherited from the source conversion. Evidence preserves the exact stored characters and line breaks so that offsets resolve correctly.

The source JSONL uses the same locally defined substitute format as the synthetic Kestrel dataset. Both files contain identical question records. Eight questions are answerable and two ask for details absent from the provided extract. Reference quotes are verified against the actual application database. The questions use different vocabulary, split answer, and not in the corpus labels. This set does not meet the four-type condition for selecting the custom set for manual answer grading. Use the synthetic Kestrel set for that grading exercise.

Run the no-context baseline from backend, review each response, and fill correct_without_context and review_notes in the generated results file. A popular novel can produce correct answers from model memory. Preserve those observations and decide whether to retain or replace such questions before comparing retrieval configurations. The synthetic company material remains explicitly separate from this novel corpus.

```powershell
python -m app.evaluate_no_context custom
```

Freeze both custom.json and custom.source.jsonl during comparison runs. If you edit a question or repair the source text, record the revision and update both question files and any affected hashes or offsets before collecting new evaluation results. No baseline answers or grades have been generated as part of preparing these files.
