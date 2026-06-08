# Constraint Route

## Trigger

Use when product behavior stays the same, but technical, dependency, performance, packaging, governance, or environment boundaries change.

## Primary Owner

- `docs/20-product-tdd/` or `docs/30-unit-tdd/`

## Mode Relationship

- Common overlays: Solidify, Execute, and Diagnose when observed reality diverges.
- Do not let mode selection blur whether the change is cross-unit or unit-local.

## Forbidden

- Do not rewrite product intent to justify an implementation decision.
- Do not hide cross-unit contract changes inside task packets only.

## Read-Do

1. Restate the constraint in technical terms.
2. Identify affected units, contracts, and authority paths.
3. Update Product TDD or Unit TDD where future drift would be expensive.
4. Define verification that proves the new contract still satisfies PRD commitments.
5. Escalate if the constraint changes a product promise.

## Exit

Leave this route when the updated technical contract is explicit, verification is defined, and PRD remains unchanged unless renegotiation is confirmed.
