# 30 Unit TDD

This layer preserves slow-moving logical structure for a complex unit.

Use it for cross-submodule constraints, architectural boundaries, and technology choices that should survive physical refactors.

Add a unit TDD only when:

- the unit has high local complexity
- repeated regressions suggest hidden invariants
- the behavior is expensive to rediscover from code history

Keep simple or stable modules in code and tests.

Current unit documents:

- `agent-harness.md`
- `chatbot-ui.md`
