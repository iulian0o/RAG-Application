# Kestrel Analytics product guide

Edition 2026.11, effective 1 November 2026. Kestrel Analytics is a fictional company used in this team's synthetic evaluation corpus. The products, identifiers, limits, policies, and incidents in this collection are invented. This document describes product behavior. Billing rules, operational recovery, service ownership, and security controls are maintained in the companion documents.

## Workspaces and projects

A workspace is the administrative boundary for membership, subscriptions, and encryption settings. Each workspace contains projects. A project groups datasets, saved views, report schedules, and import configurations. A person can belong to several workspaces without sharing permissions between them. Changing the selected workspace changes the visible project list. A project name is a display label and does not need to be unique across workspaces. The project identifier remains stable when the display label changes.

The workspace owner assigns administrators and approves operations with organization-wide consequences. Project editors can create views and import data into their assigned projects. Project viewers can inspect published reports but cannot change import schedules. A workspace administrator can invite members, while transferring ownership requires the existing owner's approval. Invitations expire after four days. Expired invitations can be issued again without creating a second membership record. Access is established only after the recipient accepts the invitation.

## Importing data

Harbor Import accepts UTF-8 CSV and newline-delimited JSON. Each import belongs to one project and stores the selected schema revision with the job. A header mismatch produces a validation report before any rows enter the destination dataset. The preview examines the first 250 records and therefore cannot prove that all later records match the schema. Operators should inspect the full validation report for failed jobs. Correcting a column name in the preview does not modify the source file.

A successful import receives a receipt with a job identifier, accepted-record count, rejected-record count, and source digest. Keep that receipt when investigating duplicate data. Uploading identical source bytes with the same idempotency key returns the existing receipt. A different key creates an independent request even when the file name is unchanged. Import cancellation prevents uncommitted batches from being published. Batches already included in a successful receipt remain visible and require an explicit dataset correction.

Harbor Import dispatches ingestion jobs to service SVC-MARSH. The service catalog defines its processing region, queue, and owner. The product name shown to customers can differ from the operational service name. Include the service identifier and job receipt in an internal escalation. This routing statement applies to ordinary ingestion jobs. A dashboard refresh after ingestion is a separate action with its own receipt and does not change the original import's completion status.

## Reports and schedules

Aurora Reports dispatches scheduled report jobs to service SVC-ORBIT. A scheduled job captures the published view revision at the instant execution begins. Editing a draft view while the job runs does not alter its result. A successful job writes a report artifact and a delivery receipt. Delivery can fail after rendering succeeds, so the two statuses are displayed separately. Re-running delivery uses the existing artifact while re-running the complete job renders a new artifact from the current published revision.

Schedules use the workspace time zone and retain that zone when an editor travels. The editor sees the next execution time together with its zone. A schedule changed during an execution affects the next execution only. Paused schedules preserve their saved view and recipients. The schedule history distinguishes a manual pause from an execution failure. A manual run can still be requested while the recurring schedule is paused, subject to the editor's ordinary project permissions.

## Large exports

Exports above 2 GiB require approval from the workspace owner before the export job is submitted. An administrator can prepare the export request but cannot substitute their approval for the owner's. The approval is bound to the dataset revision and export format. Changing either value invalidates the approval. Smaller exports still require the requesting user's read permission on every included dataset. The security handbook specifies the encryption requirement for exports above the same threshold.

Export manifests contain the dataset revision, row count, selected columns, format, and content digest. Filtering rows changes the manifest's row count but leaves the source dataset intact. A failed export creates a failure receipt and does not expose a partial artifact through the download screen. Retrying with the same request token resumes an unfinished job when possible. Retrying a completed export with a new request token produces a separate artifact whose retention timer begins when that artifact becomes ready.

## Download links

For export artifacts created on or after 1 August 2026, download links expire 36 hours after the artifact becomes ready. Link expiration prevents another download through that link. It does not delete the artifact or remove the export receipt. An authorized user can issue a replacement link while the artifact remains within its retention period. Replacement links receive their own expiration timestamp and remain subject to the user's current project access.

Historical behavior through 31 July 2026 used a 12-hour download-link lifetime. That value describes artifacts created under the earlier release and should not be used to calculate expiration for a newly created artifact. The migration did not extend links that had already expired. Support staff should check the artifact creation timestamp before comparing a reported expiration to the policy. Artifact retention and link lifetime are separate settings with separate audit events.

## Project archival and deletion

Archiving a project hides it from the default project list and pauses its schedules. Members with existing access can find it using the archived-project filter. Archival preserves datasets, receipts, and report artifacts according to their ordinary retention rules. Restoring a project does not automatically resume its schedules. An editor must inspect the destination recipients and resume each schedule explicitly. This avoids sending a delayed report to recipients whose responsibilities have changed.

Project deletion requires a workspace owner's confirmation and a 48-hour recovery window before erasure begins. During that window the owner can cancel the request from the audit screen. The security and billing documents describe holds that may prevent erasure. A deletion request should include the project identifier rather than just its display name. Creating a new project with the same name does not restore the deleted project's data or reuse its identifier.
