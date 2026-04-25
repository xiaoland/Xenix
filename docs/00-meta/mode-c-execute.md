# Execute Overlay

## Trigger

Use this overlay when the task is bounded, causality is known, and the owning layer is already clear.

## Preconditions

- The owner has been identified.
- The change set has been restated in the task packet.
- The nearest local `AGENTS.md` and any relevant `docs/30-unit-tdd/` material are known.

## Constraints

- Edit only the owning layer for the truth being changed.
- Check the nearest local `AGENTS.md` before touching code or local seam docs.
- Keep the task packet aligned with the actual change set.
- Make the smallest correct change that satisfies the agreed scope.

## Read-Do

1. Load the nearest local guidance and any relevant unit-level design memory.
2. Restate the target, current state, included scope, excluded scope, invariants, affected files, and assumptions.
3. Implement the smallest correct change set.
4. Record verification results if checks are run for the task.
5. Promote only the stable truths that truly need durable memory.

## Exit

Leave this overlay when the bounded change is complete, or switch back to `Explore`, `Solidify`, or `Diagnose` if scope, ownership, or evidence shifts.
