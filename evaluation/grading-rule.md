# Answer grading rules

Apply these rules to the saved answer, retrieved chunks, and reference answer.

## Correct

The answer provides all essential facts requested and its claims are supported
by the cited chunks.

For an unanswerable question, the application clearly states that the documents
do not provide the answer.

## Partial

The supported answer provides some required facts but omits an essential part.

## Wrong

The answer contradicts the reference facts or answers a different question.

Answering an unanswerable question with a factual claim is wrong.

## Unsupported

For an answerable question, the answer makes factual claims that its cited
chunks do not support, even if those claims happen to be true.

## Failure diagnosis

For each unsuccessful answer, inspect the chunks actually supplied to
generation, limited to answer_top_k.

Record retrieval when necessary evidence was missing.
Record generation when sufficient evidence was present but the answer failed.
Record both when both problems are visible.
Record operational for a request or provider failure.

Explain the decision in grading_notes.