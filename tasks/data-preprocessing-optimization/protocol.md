# Packet-Local Control Protocol

## Purpose

This task is now a program workspace, not a single scratch note. Each future sub-task should be small enough to review independently while still consuming the same durable decisions.

## Status Values

- `explore`: evidence is being gathered.
- `ready`: decision and verification shape are clear.
- `executing`: implementation is active.
- `verified`: code/docs change has concrete proof.
- `blocked`: progress needs user input or external state.
- `archived`: historical material; do not use as current design truth.

## Required Workstream Packet Fields

Every `workstreams/<nn-name>/packet.md` should keep these sections:

- Objective & Hypothesis
- Status
- Durable Owners / Blast Radius
- State Diff: `From -> To`
- Invariants
- Decisions Consumed
- Open Questions
- Verification Plan
- Verification Run Log
- Next Action

## Ledger Rules

- `README.md` is a dashboard only. It must not become an execution log.
- `ledger/decisions.md` is the current decision authority.
- `ledger/open-questions.md` owns unresolved issues. Each entry needs owner, blocking level, impact, and next step.
- `ledger/verification.md` owns current verification truth. Put the latest authoritative result at the top.
- `ledger/change-map.md` owns blast-radius and durable-owner mapping.
- Evidence files preserve facts; they do not define the current contract unless promoted into the ledger.
- Archive files are historical. They may contain obsolete terms such as active `data.peek`; current files must not depend on those claims without restating them in the ledger.

## Sub-Task Rules

- One sub-task gets one folder under `workstreams/`.
- Do not mix unrelated implementation notes into another workstream packet.
- If a sub-task changes durable docs, cite the doc owner in `Durable Owners / Blast Radius`.
- If a sub-task touches runtime behavior, record at least one concrete verification command or an explicit reason verification could not be run.
- If a user observation comes from the local runtime DB, put raw diagnosis in `evidence/` and only promote stable conclusions into `ledger/decisions.md` or a workstream packet.

## Naming

Use numeric prefixes for workstreams so discussion can reference stable names. Prefer product/contract names over implementation technique names.

Examples:

- `08-runtime-db-migration-policy`
- `09-workbook-group-export`
- `10-analysis-profile-replacement`

## Promotion Test

Promote a note from evidence/archive into the ledger only when it is:

- stable after verification or user confirmation;
- phrased as a durable contract, decision, or unresolved question;
- not merely a timestamped execution detail.
