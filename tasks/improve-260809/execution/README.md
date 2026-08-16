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

## Records

- [B0 offline implementation — 2026-08-09](B0-offline-implementation-260809.md)
- [Foundation execution — 2026-08-09](foundations-2026-08-09.md)
- [CF-C / CF-F execution — 2026-08-09](CF-2026-08-09.md)
- [Recommendation and text execution — 2026-08-10](RT-2026-08-10.md)
- [M1 private-material service characterization — 2026-08-10](M1-private-material-service-characterization-2026-08-10.md)
- [O1 topic final-answer diagnosis — 2026-08-10](O1-topic-final-answer-diagnosis-2026-08-10.md)
- [O2 topic final-answer delivery audit — 2026-08-10](O2-topic-final-answer-delivery-audit-2026-08-10.md)
- [O3 topic Apply delivery projection — 2026-08-10](O3-topic-apply-delivery-projection-2026-08-10.md)
- [O4 cleaning causal diagnosis — 2026-08-11](O4-cleaning-causal-diagnosis-2026-08-11.md)
- [O4-A1 cleaning service oracle audit — 2026-08-11](O4-A1-cleaning-service-oracle-audit-2026-08-11.md)
- [O4-A1 cleaning service correctness — 2026-08-11](O4-A1-cleaning-service-correctness-2026-08-11.md)
- [O4-A2 cleaning result projection audit — 2026-08-11](O4-A2-cleaning-result-projection-audit-2026-08-11.md)
- [O4-A2 bounded cleaning result facts — 2026-08-11](O4-A2-cleaning-result-facts-2026-08-11.md)
- [O4-A3 cleaning Tool/Skill authority audit — 2026-08-11](O4-A3-cleaning-tool-skill-authority-audit-2026-08-11.md)
- [O4-A3 cleaning Tool/Skill authority implementation and paid characterization — 2026-08-11](O4-A3-cleaning-tool-skill-authority-2026-08-11.md)
- [O4-E1 cleaning row-count matcher robustness — 2026-08-16](O4-E1-cleaning-row-count-matcher-robustness-2026-08-16.md)
- [A1 formal acceptance preflight — 2026-08-10](A1-preflight-2026-08-10.md)
- [A2 formal Agent Harness readiness — 2026-08-10](A2-harness-readiness-2026-08-10.md)
- [Final current-worktree verification — 2026-08-10](final-verification-2026-08-10.md)

The Foundation and CF records include paid single-sample characterization and bounded improvement/diagnosis series. Credentials, raw prompts/transcripts, provider responses, private material rows/answers, local paths exposed to the Agent, and unbounded logs remain excluded.
