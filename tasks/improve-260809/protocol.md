# Packet-Local Protocol

## Purpose

This directory is a program workspace. `README.md` is its small control surface; supporting files isolate decisions, evidence, execution history, authorization, and workstream context so a future turn does not need to load the whole program.

## Status Values

- `explore`: gather evidence without durable mutation.
- `solidify`: turn supported findings into a decision, contract, or proposed handshake.
- `ready`: scope and verification are clear, but mutation still needs approval.
- `executing`: work is inside an explicitly approved handshake.
- `verified`: the approved state diff has objective proof.
- `blocked`: progress requires a user decision or external state.
- `superseded`: historical context only; do not consume as current truth.

## File Authority

- `README.md`: current dashboard and exactly one next step.
- `decisions.md`: accepted and proposed normative decisions, with stable IDs.
- `open-questions.md`: unresolved choices, blocking level, impact, and next action.
- `program-plan.md`: dependency topology and execution sequence.
- `verification.md`: responsibility boundaries, acceptance policy, and proof matrix.
- `working-set.md`: file ownership, conflict hotspots, and context-loading rules.
- `cases/catalog.md`: case identity, subject/evaluator partition, and test profiles.
- `workstreams/*/packet.md`: one vertical's active scope and slice-level verification.
- `handshakes/`: the only packet location for detailed mutation authorization.
- `evidence/`: reusable observations and safe summaries; never normative by itself.
- `execution/`: bounded command/run history; never a second current-state owner.

## Workstream Packet Fields

Each active workstream packet keeps:

- Objective & Hypothesis
- Status
- Scope and Non-Goals
- Dependencies
- Durable Owners / Blast Radius
- Candidate State Diff
- Invariants
- Decisions Consumed
- Cases Consumed
- Verification Plan
- Current Evidence
- Next Action

## Working-Set Rule

Load the common packet core plus one active workstream. Add only its referenced cases, governing owner docs/local instructions, direct source files, and focused tests. Do not load all workstreams, the entire corpus, all runtime logs, or all benchmark output unless a cross-program review requires it.

## Evidence and Run Promotion

After a run:

1. Put bounded command and result metadata in `execution/`; raw logs, traces, DB copies, provider payloads, and transcripts go under ignored `execution/raw/`.
2. Promote only stable, reusable observations into `evidence/` with an Evidence ID.
3. If evidence changes a decision, add or supersede a Decision ID; do not silently rewrite history.
4. Update the active workstream and dashboard only with current status and the next action.
5. Never copy private oracle rows, labels, future windows, answer text, credentials, local paths, or unbounded payloads into tracked summaries.

## Mutation Rule

Task-packet maintenance is the only standing mutation exception. Every product/test/durable-doc change needs an Impact Handshake naming exact files or symbols, `From -> To`, blast radius, invariants, and verification. New evidence that changes the state diff returns the program to discussion.
