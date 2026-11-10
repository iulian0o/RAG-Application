# Kestrel Analytics error runbook

Operational edition 2026.11 for the fictional evaluation environment. Error identifiers are exact strings. Similar digits do not imply the same recovery procedure. Begin an investigation by collecting the complete identifier, affected workspace, job receipt, and event timestamp. Preserve a concise record of each recovery action so that a later operator can distinguish the original failure from a failed retry.

## KST-427 checkpoint mismatch

KST-427 means the ingestion checkpoint digest disagrees with the signed ledger checkpoint. Freeze the affected ingestion stream, restore its last signed checkpoint, and verify the accepted-record count before replaying queued batches. Preserve the failed checkpoint digest in the incident record. Replaying first can make the discrepancy harder to reconstruct. The freeze applies to the affected stream; unrelated streams can continue when their checkpoint checks succeed.

The verification compares the restored checkpoint's accepted-record count with the last successful import receipt. A matching filename or source size is insufficient. If the receipt and restored checkpoint disagree, keep the stream frozen and escalate with both identifiers. After a successful replay, collect the new receipt and record its relationship to the interrupted job. Close the operational incident only after the stream resumes and its next checkpoint passes validation.

## KST-472 dispatch quota

KST-472 indicates that a workspace has exhausted its current dispatch allowance. Wait for the next dispatch window and retry with the original request token. This code does not require checkpoint restoration. Inspect the quota counter and job receipt before reducing concurrency. A second request token can create an additional pending job rather than accelerating the original request. Repeatedly submitting different tokens makes queue analysis harder and can prolong congestion.

The quota counter refreshes every minute. The user interface can briefly show a previous counter value while the service enforces the new one. Record both the counter sample timestamp and the rejection timestamp. An allowance increase requires an updated entitlement or an approved operational override. Editing a project display setting does not alter the dispatch allowance. If a valid override is present but the code persists, escalate to the service owner with the override receipt.

## KST-214 schema revision

KST-214 means the submitted import declares a schema revision that the project has retired. Obtain the current published schema and regenerate the mapping before submitting another import. Retired schemas remain in audit history and can still appear in old examples. A saved draft schema is not automatically eligible for ingestion. Confirm that the intended revision is published and belongs to the same project as the import request.

When a column was renamed, review transformations that refer to its earlier name. A successful preview of a small sample does not establish that all source records comply. Run full validation and inspect rejected-record reasons. Keep the original failed receipt for comparison. A new mapping should receive its own revision rather than overwriting the mapping attached to a completed import. Historical receipts continue to refer to the mapping used at their acceptance time.

## KST-318 artifact digest

KST-318 identifies an export artifact whose stored digest differs from the manifest digest. Disable delivery for the affected artifact and request regeneration from the recorded dataset revision. Do not patch individual bytes in the artifact to make a local download appear readable. Preserve the manifest and delivery receipt for diagnosis. The dataset itself may remain healthy, so the incident should distinguish artifact integrity from source-data integrity.

Regeneration creates a new artifact identifier and digest. Issue delivery links only after the new artifact passes verification. A previously issued link for the failed artifact should remain revoked. The user may need to replace a saved link in an external workflow. Include the replacement artifact identifier in the support response without embedding access credentials. If regeneration fails with the same code, escalate with both artifact identifiers and the source revision.

## KST-509 report delivery

KST-509 means report rendering completed but the configured delivery destination rejected the artifact. Inspect destination permissions and the delivery receipt. A report can therefore be rendered successfully while its scheduled delivery is marked failed. Re-rendering is unnecessary when the saved artifact remains valid and retained. Use the delivery retry action after correcting the destination configuration. A delivery retry preserves the rendered report's original dataset revision.

If the destination has been removed intentionally, pause the schedule while an editor chooses a replacement. Repeated delivery retries cannot restore an external destination that no longer exists. The incident record should distinguish revoked permission from an unavailable endpoint. Include the destination identifier rather than a credential-bearing URL in ordinary notes. Secret rotation, when required, follows the security handbook and should be recorded as a separate access-management event.

## KST-611 retention hold

KST-611 indicates that an erasure stage encountered an active retention hold. Inspect the project's retention panel to determine the hold type and issuing authority. The deletion request can remain pending while the hold is reviewed. An operator must not treat the code as a transient transport failure and repeatedly force the erasure stage. The billing policy and security handbook define distinct reasons for retaining records and distinct release authorities.

A hold-release receipt is necessary before the blocked erasure stage can proceed. Confirm that the receipt applies to the correct project and hold identifier. A release for another project is insufficient even when both projects share a workspace. Keep the original deletion request identifier in the recovery record. Recreating the request with a different display name does not remove the hold and can obscure the audit trail.
