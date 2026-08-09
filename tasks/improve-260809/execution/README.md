# Execution Log Policy

## Purpose

Execution records bounded run history. They are chronological evidence inputs, not the current product contract.

## Run Record

Use one file or directory per meaningful run with a stable run ID. A safe summary should record:

- run, case, profile, and variant IDs;
- start time, repository revision/dirty identity, runtime and dependency-lock identity;
- input manifest, split, oracle, evaluator, subject, Judge, and policy versions;
- execution/persistence/integrity/Judge status;
- bounded quality metrics and gate verdicts;
- wall time, retries, Tool calls, input/output tokens, estimated cost, and optional peak memory;
- logical output Artifact/Dataset IDs or hashes;
- classified failure stage and a bounded error code.

## Raw Evidence

Put raw logs, traces, SQLite snapshots/queries, provider payloads, prompts, transcripts, and detailed errors under ignored `execution/raw/`. Summaries must redact local paths, credentials, raw rows, and unbounded content.

## Update Sequence

1. Record the run summary.
2. Promote reusable facts to an Evidence ID.
3. Add/supersede a Decision ID if the facts change direction.
4. Update the active workstream's Current Evidence and Next Action.
5. Update the dashboard only when overall status or the single next step changes.

No execution record exists yet beyond baseline E-001 and the private reference-script qualification summarized by E-006.
