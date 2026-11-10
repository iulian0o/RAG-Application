# Kestrel Analytics service catalog

Catalog revision 2026.11 for the fictional Kestrel evaluation environment. Operational identifiers are stable routing keys. Product labels and team names can change independently. Region codes in this catalog describe the assigned processing region for the named service. They do not establish a separate contractual residency guarantee for every integration or downstream destination.

## SVC-ORBIT

SVC-ORBIT processes jobs in region EU-FR2 and is owned by Indigo Operations. Its operational queue is orbit-dispatch. Each accepted request receives a dispatch receipt before rendering begins. The service stores the published view revision with the job. Rendering completion and destination delivery are recorded as separate stages. The on-call handoff should include the stage that failed, the job identifier, and the last successful receipt.

The service permits up to eight active rendering jobs per workspace. Additional accepted jobs remain queued. A queue position is advisory and can change when a higher-priority recovery job is admitted. Cancelling a queued job releases its reservation. Cancelling an active rendering job takes effect at the next safe boundary and can leave a cancellation receipt without an artifact. The receipt is retained for investigation even when no export usage is posted.

## SVC-MARSH

SVC-MARSH processes ingestion jobs in region EU-DE3 and is owned by Reed Data Operations. Its operational queue is marsh-ingest. A worker validates schema compatibility before accepting a batch into a destination dataset. The receipt separates validation rejection from accepted-record counts. A retry with an existing request token consults the prior receipt before creating work. Operators should preserve the source digest when investigating a suspected duplicate ingestion.

The ingestion cancellation queue is marsh-abort. Cancellation prevents publication of uncommitted batches while preserving already accepted receipts. A cancellation acknowledgment does not imply that previously published records were removed. Dataset correction is a distinct operation requiring the appropriate editor permission. If a checkpoint mismatch interrupts cancellation, follow the exact error-code procedure in the runbook before replaying pending batches or submitting another cancellation token.

## SVC-GLINT

SVC-GLINT accepts at most 240 records per batch and requires a 45-second delay before retrying a rejected batch. Its processing region is EU-FR2 and its owner is Prism Integration. The retry must retain the original batch token. A caller that splits a rejected batch into smaller requests should assign a new token to each new batch and retain the original rejection receipt. The receipt records whether any records were accepted before rejection.

The service normalizes incoming event envelopes and emits validated events to downstream consumers. It does not calculate subscription invoices. An envelope with an unknown event revision is rejected before dispatch. Event payloads remain subject to workspace access controls. Diagnostic counters expose aggregate accepted and rejected counts without including event bodies. Investigators needing event bodies must follow the separate approved collection process described in the security handbook.

## SVC-GLIDE

SVC-GLIDE accepts at most 420 records per batch and recommends a 20-second delay after a temporary consumer pause. It is owned by Silver Connectors in region EU-NL1. The identifier resembles SVC-GLINT, but the two entries refer to different operational services. GLIDE publishes connector status events and uses the queue glide-status. Its receipt records the connector identifier, observed watermark, and event revision.

A temporary consumer pause leaves events in the service's queue until the consumer resumes or the queue retention period expires. The producer should inspect the receipt before submitting duplicates. Restarting a connector is a separate action and does not acknowledge queued status events. When a status event becomes stale, the next event can supersede its display value while the original receipt remains available for tracing the sequence of observations.

## SVC-LANTERN

SVC-LANTERN maintains the searchable receipt directory in region EU-DE3. Amber Reliability owns the service and monitors the lantern-receipts queue. Directory entries contain operation identifiers and permitted summary fields. Access checks are performed before returning matches. A partial identifier can return several suggestions, while a complete identifier targets one receipt. The directory does not grant access to the original datasets referenced by a receipt.

Directory updates normally appear within two minutes of receipt creation. A newly completed job may therefore be visible on its project page before appearing in global receipt search. Investigators should use the complete receipt identifier during that interval. Repeated creation of replacement jobs cannot accelerate directory indexing and may make the incident harder to understand. Report persistent indexing delay with both creation and search timestamps.

## SVC-VAULT

SVC-VAULT stores generated artifacts in region EU-FR2 and is owned by Cobalt Storage. Its queue is vault-artifacts. Artifact metadata contains a digest, dataset revision, creation timestamp, and retention deadline. A delivery link refers to an artifact identifier and has a separate lifetime. Revoking a link does not automatically erase its artifact. Artifact erasure is recorded with its own receipt after applicable retention controls permit it.

Integrity checks compare stored bytes against the manifest digest. A mismatch blocks ordinary delivery and triggers the appropriate artifact error in the runbook. The service retains diagnostic metadata about the failed artifact while a replacement is generated. It does not expose unverified bytes to make a delivery attempt appear successful. Owners should compare artifact identifiers when reviewing replacement deliveries because the regenerated artifact receives a new identity.
