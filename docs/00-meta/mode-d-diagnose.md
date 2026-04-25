# Diagnose Overlay

## Trigger

Use this overlay when the task is driven by a crash, anomaly, corruption risk, regression, migration failure, or other Reality-first problem whose cause is not yet justified.

## Preconditions

- The work has been recognized as primarily `Reality`.
- A task packet exists under `tasks/<task-slug>/`.

## Constraints

- Stay read-only until evidence justifies a fix.
- Keep telemetry, reproduction notes, state observations, and hypotheses in the task packet.
- Do not rewrite docs or code based on an unproven story.
- Promote only stable recurrence protection after the evidence is clear.

## Read-Do

1. Record `Objective & Hypothesis`, `Guardrails Touched`, and `Verification`.
2. Capture the symptom, impact, environment, and reproduction path.
3. Gather logs, traces, state snapshots, and other available evidence.
4. Narrow candidate causes and identify the next discriminating check.
5. Decide whether the next posture is `Execute` for a justified fix or `Solidify` for owner and scope confirmation.

## Exit

Leave this overlay only when the cause is supported well enough to justify a fix or a durable recurrence note.
