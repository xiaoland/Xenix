# Solidify Overlay

## Trigger

Use this overlay when the request is becoming specific and the next step is to settle owner, scope, invariants, and exact mutation targets before execution.

## Preconditions

- Exploration has reduced ambiguity enough to propose a concrete change set.
- An agent-owned task packet exists under `tasks/<task-slug>/`.

## Constraints

- Route by owner before editing anything durable.
- Restate scope, invariants, likely affected files, and uncertainty before writing.
- Ask for confirmation when the destination or blast radius still needs human agreement.
- Keep temporary reasoning in the task packet until the owner map is clear.
- Prepare the verification shape as soon as the design or contract claim is stable enough to act on.

## Read-Do

1. Sort truths into the correct owners: `PRD`, `Alignment`, `Product TDD`, `Unit TDD`, local `AGENTS.md`, `Deployment`, or `Tasks`.
2. Restate the target, current state, operation, included scope, excluded scope, invariants, likely affected files, and uncertainty.
3. Identify the smallest unresolved decision that blocks execution.
4. Update the task packet with the current decision, verification shape, and next step.
5. Hand off to `Execute`, `Explore`, or `Diagnose` once the evidence state makes the next posture clear.

## Exit

Leave this overlay when the durable destination is clear and the next posture can proceed without owner ambiguity.
