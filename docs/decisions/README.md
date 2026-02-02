# Decisions

This directory contains Architecture Decision Records (ADRs).

## Format

Each ADR follows this naming convention:

```
XXX-decision-title.md
```

Where `XXX` is a sequential number (001, 002, etc.).

## Template

```markdown
# ADR-XXX: Decision Title

## Status

- Proposed / Accepted / Deprecated / Superseded by ADR-YYY

## Context

What is the issue that we're seeing that is motivating this decision?

## Decision

What is the change that we're proposing or have agreed to implement?

## Consequences

What becomes easier or more difficult to do and any risks introduced?

## Related

- Links to related ADRs, PRDs, or external resources
```

## Active Decisions

| ADR | Title                               | Status   |
| --- | ----------------------------------- | -------- |
| 001 | Feature-Based Frontend Architecture | Accepted |
| 002 | TanStack Query for Server State     | Accepted |
| 003 | Hono RPC for Type-Safe APIs         | Accepted |

## Contributing

1. Create a new ADR with the next sequential number
2. Start with status "Proposed"
3. Discuss with team
4. Update status to "Accepted" or "Rejected"
5. If superseded, update status and reference new ADR
