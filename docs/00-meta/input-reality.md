# Reality Route

## Trigger

Use for bugs, anomalies, crashes, corrupt state, regressions, migration failures, or any mismatch between expected and observed runtime behavior.

## Primary Owner

- `tasks/` for evidence gathering and hypothesis ranking
- nearest local `AGENTS.md` for recurrence tripwires after the fix

## Mode Relationship

- Common opening overlay: Diagnose.
- Explore, Solidify, or Execute may follow once evidence changes the posture.

## Forbidden

- No evidence, no modification.
- Do not jump straight from symptom to fix.

## Read-Do

1. Capture logs, traces, failing tests, state snapshots, environment, and reproduction path.
2. Define blast radius and timeline.
3. Build a diagnostics matrix when multiple causes remain plausible.
4. Rank hypotheses by evidence quality.
5. Only after validation, plan the fix and identify recurrence tripwires.
6. Promote stable operational or technical lessons into Deployment, Product TDD, Unit TDD, or local AGENTS only when justified.

## Exit

Leave this route when the likely cause is evidence-backed and the next action has an explicit verification path.
