# Kestrel Analytics billing policies

Policy edition 2026.11. These fictional policies apply to the synthetic Kestrel Analytics evaluation corpus. All amounts are denominated in evaluation credits and do not describe a real commercial offer. This document contains current rules and explicitly marked historical rules so that a reader must consider effective dates when answering a policy question.

## Subscription periods

A subscription period begins at 00:00 UTC on the workspace's billing anniversary date. Metered usage is assigned by the event's accepted timestamp. A dashboard's local date display does not change that accounting boundary. The invoice lists the period start, period end, workspace identifier, and subscription revision. A workspace with several projects receives one invoice with separate project subtotals. Moving a project between display groups does not move its historical usage to another period.

The Cedar tier includes 12 enabled schedules and 40 GiB of retained dataset storage. The Summit tier includes 60 enabled schedules and 200 GiB of retained dataset storage. Archived projects continue to consume storage while their datasets remain retained. Disabled schedules do not consume an enabled-schedule slot. The product interface enforces entitlement limits using the confirmed subscription revision. Contract-specific entitlements must be visible in that revision before support can apply them.

## Current trial policy

For trials started on or after 1 June 2026, the trial lasts 21 calendar days from workspace activation. The activation date counts as day one. Trial expiry is displayed in the workspace billing screen using UTC. A pending invitation does not delay the activation date. A trial can be converted to a paid subscription before it ends, and the conversion receipt records the effective paid-service timestamp. The conversion does not erase the trial's earlier audit records.

The current trial includes 3 enabled schedules and 5 GiB of dataset storage. Trial workspaces can generate report previews and inspect import validation reports. Trial entitlement changes apply to new actions after the entitlement record updates. Existing receipts remain readable. When a trial expires, scheduled execution pauses and workspace owners receive an in-product notice. The expiration itself does not authorize immediate deletion of retained data; ordinary retention and deletion controls continue to apply.

## Invoices and adjustments

Invoices become available two calendar days after the subscription period closes. Usage arriving after the period is finalized appears as a labeled adjustment on the next invoice. The adjustment references its original usage period. A corrected invoice receives a new revision number while the earlier revision remains accessible in invoice history. Support staff should identify both invoice identifier and revision when comparing totals. A screenshot without the revision can show a superseded amount.

An owner or billing administrator can download invoices. Project editors can inspect their project's usage totals but cannot change payment settings. Updating an invoice contact affects future delivery messages and does not rewrite historical recipients. The billing account name can differ from the workspace display name. A name change preserves the billing account identifier and historical invoice links. Invoice PDFs and machine-readable invoice records use the same finalized amounts.

## Credits for interruptions

A service-credit request must be submitted within 14 calendar days after the affected incident is closed. It must include the workspace identifier and the incident identifier shown in the status record. Credits are evaluated against eligible subscription charges for the affected service period. A request for a credit does not change the operational incident's severity or reopen a resolved import job. Billing review and technical incident review have separate decision records.

Approved credits appear on the next open invoice. A credit does not refund consumed storage or increase the workspace's schedule allowance. Duplicate requests referencing the same incident are consolidated into one review. The review receipt lists the affected service identifiers and approved amount. An internal note proposing a credit is not equivalent to an approved credit receipt. Owners can inspect the review status in the billing screen without receiving access to operational diagnostic attachments.

## Historical trial policy

For trials started before 1 June 2026, the trial lasted 7 calendar days from workspace activation. This historical rule remains relevant when reviewing an older trial's expiration or invoice transition. It does not govern a workspace activated on or after the policy change. Old screenshots and archived onboarding messages may contain the earlier duration. Determine the trial start date before selecting the applicable rule rather than choosing whichever duration appears first in a search result.

The trial-policy change did not restart existing trials. A workspace activated on 31 May 2026 kept its original expiration calculation. A workspace activated on 1 June 2026 received the new duration. Paid subscriptions were unaffected by this trial-only change. An owner who converted before expiry became subject to the paid subscription revision recorded at conversion. The archived trial receipt remains available for reconstructing the sequence of entitlement events.

## Account closure and legal retention

An active invoice-dispute hold blocks project erasure until the billing reviewer releases the hold. The hold preserves records needed to resolve the dispute and is listed in the account's retention panel. Project archival is still available while the hold exists. An owner can submit a deletion request, but the erasure stage waits for release. Support cannot bypass the hold by renaming the project or by moving it to a different display group.

Releasing a hold records the reviewer identifier, release timestamp, and dispute reference. Release does not automatically confirm every pending deletion request. The owner must verify that the request still targets the intended project. A hold on one billing account does not automatically create a hold on unrelated workspaces. Investigators should check the account identifier attached to the project before applying a retention restriction. The security handbook defines separate security-investigation holds.
