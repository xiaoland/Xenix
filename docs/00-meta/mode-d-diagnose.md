# Mode D - Diagnose

## Trigger

Use this mode when the system is failing, the runtime is anomalous, or the cause is not yet established.

## Constraints

- Strictly read-only.
- Do not guess a fix.
- Do not modify code, durable docs, or runbooks while diagnosing.

## Read-Do

1. Read logs, traces, metrics, or failing output until the failure is grounded.
2. Write a diagnosis note in `tasks/` with likely causes and validation steps.
3. Pause and wait for human confirmation before switching to a fix or runbook execution.

## Exit

Leave this mode only after ground truth is established and a follow-up mode is approved.
