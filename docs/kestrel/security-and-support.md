# Kestrel Analytics security and support handbook

Handbook edition 2026.11 for this fictional evaluation corpus. Workspace permissions, diagnostic access, and support entitlements are separate controls. A support representative's ability to inspect a case does not imply permission to inspect the customer's source records. Apply the documented approval path to each operation and preserve the relevant audit receipts.

## Suspended sign-in

After five unsuccessful credential submissions, sign-in is suspended for 18 minutes. A workspace administrator can end the suspension early by issuing a recovery challenge from the membership console. The affected member must complete that challenge before a new session is created. Repeated credential submissions during the suspension do not shorten its duration. An administrator's action is recorded with the affected member identifier and challenge issuance time.

A recovery challenge is valid for six minutes and can be used once. If it expires, the administrator must issue a replacement. Issuing a challenge does not change project roles or grant access to additional workspaces. A member who has been removed from the workspace requires a new invitation through the ordinary membership process. Investigators should distinguish a credential suspension from a revoked membership before suggesting a recovery action.

## Voice assistance

Voice callbacks are available only to Summit workspaces and must be requested through an authenticated support case. Cedar and trial workspaces use written case replies. A callback request includes the case identifier and the requesting member's preferred contact window. The support interface confirms that the request was received. It does not promise an immediate callback or bypass the queue for a case whose impact has not yet been assessed.

The support agent verifies the workspace association before discussing case details. A callback cannot authorize a membership change, reveal a stored credential, or override a retention hold. Those actions use their own documented approval processes. If the conversation identifies new evidence, the agent records a written summary in the case. Users can inspect that summary and correct factual mistakes without modifying the original operational receipts.

## Encryption for large exports

Exports above 2 GiB must be encrypted with a workspace-managed key before a download link is issued. The key identifier is recorded in the artifact manifest. A key alias alone is insufficient because an alias can later point to a different key revision. The export service verifies access to the recorded revision before marking delivery ready. Workspace-owner approval is a separate prerequisite defined in the product guide.

If the required key is unavailable, the export remains blocked and the interface displays a key-access failure. Generating an unencrypted replacement is not an approved recovery action. The workspace security administrator must restore access to the required revision or approve a new export using an eligible revision. A new export receives a new manifest. Keep the failed job receipt so that investigators can reconstruct the original encryption decision.

## Diagnostic collection

Diagnostic bundles must exclude raw customer records and expire after 72 hours. A bundle can contain job identifiers, error codes, aggregate counts, timestamps, and redacted configuration fields. Collect only the fields needed to reproduce or explain the observed failure. A support case identifier associates the bundle with an investigation but does not expand the permitted contents. The person preparing the bundle remains responsible for checking attachments before submission.

The expiration timer begins when the bundle is uploaded to the case. If an investigation requires a fresh bundle after expiration, collect a new one through the same review process. Re-uploading an old attachment without reviewing its contents is insufficient. The case retains a record that a bundle existed and when it expired. It does not retain unrestricted copies of the original attachment in ordinary case comments.

## Security-investigation holds

A security-investigation hold prevents project erasure until the security reviewer issues a release receipt. This hold is distinct from an invoice-dispute hold. The retention panel lists each active hold independently. Releasing one hold does not release another. A project whose owner has requested deletion can remain pending while either hold is active. The owner can inspect the hold category and request status without receiving restricted investigation notes.

The release receipt identifies the project, hold, reviewer, and release timestamp. Before resuming erasure, verify all active holds rather than assuming the most recently released hold was the only one. A completed recovery window does not override a hold. Renaming or archiving a project also leaves its holds intact. The runbook describes the operational error returned when an erasure stage encounters an active restriction.
