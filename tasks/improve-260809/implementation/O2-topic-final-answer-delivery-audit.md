# O2 Implementation Plan — Topic Final-Answer Delivery Audit

**Status:** Implemented, offline-verified, and paid-characterized on 2026-08-10; the final-grounding outcome improved in some samples but is not reliably closed.

## Outcome

Before answering a multilingual topic-discovery request, the Agent reconciles the user's requested public deliveries with authoritative Evaluate and completed FIT/APPLY facts, then states the evidence and decision limits without inventing paths or private content.

## Working Set

- [IH-O2](../handshakes/IH-O2-topic-final-answer-delivery-audit.md);
- `src/xenix/services/agent/skills/xenix-data-modeling/SKILL.md`;
- ignored generated Skill catalog as a derived runtime surface;
- the topic benchmark's business-prompt length contract only;
- existing Skill scope, catalog, Harness offline, and exact-collection checks.

No Tool, service, finalizer, sanitizer, semantic benchmark oracle/rubric, or other product source belongs to this slice.

## State Diff

- Bump the Modeling Skill from `0.9.0` to `0.10.0`.
- Replace the distributed topic final-answer reminder with one canonical pre-finalization audit.
- Require realized topic count and permutation boundary; Tool-returned perplexity, coherence, stability, connected/template isolation, and zero overlap; requested public Dataset IDs and Artifact links; exploratory/offline/non-causal/no-automatic-decision limits; and raw-content/local-path exclusion.
- When a requested public fact or identity is absent, report it unavailable instead of inventing it.
- After the first paid attempt exposed a measurement-only boundary failure, compress the semantically equivalent business prompt from 581 to 505 characters and enforce the `JudgeInput.task_intent` 512-character maximum at import time.

## Verification

- Skill catalog generated and checked.
- Focused Skill scope: 3 passed.
- `pdm run check`: passed.
- Direct `JudgeInput` boundary validation: passed; 505 characters with 7 characters headroom.
- Agent Harness offline checks: 33 passed.
- Exact topic collect-only: one item in headless and one item in headed mode.
- `git diff --check`: passed.

## Current Outcome

Run `75ad6132b189420bb0175bea0f6dc00e` was a `measurement_error` from the repaired `task_intent` boundary and is not Agent semantic evidence. Valid later runs `1143200b493149cf8c3aff77f52963a7` and `8ada4c4dd50349f0aeccdbdef9e06484` retained one or two final-grounding omissions despite all corresponding facts being available before finalization. The subsequent O3 adjacent-projection experiment did not improve that result and was rolled back. O2 remains retained as a sound general delivery audit, but it is not formal topic acceptance.
