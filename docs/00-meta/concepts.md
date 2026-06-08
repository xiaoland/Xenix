# Concepts

This file is the on-demand dictionary for SVC framework language used in Xenix Native. Load it only when routing, ownership, or boundary language is unclear.

## Unit

- Owned by layer: `docs/30-unit-tdd/`
- Definition: A logical technical boundary with internal contracts; it is not necessarily a folder.
- Common confusion: package, module, screen, service class.

## Durable Owner

- Owned by layer: `docs/00-meta/`
- Definition: The canonical place where a truth should live if it is stable and expensive to rediscover.
- Common confusion: the file currently being edited.

## Task Packet

- Owned by layer: `tasks/`
- Definition: An agent-owned task-local workspace for volatile reasoning, evidence, artifacts, collaboration state, and verification notes.
- Common confusion: append-only task log or durable architecture doc.

## Alignment Substrate

- Owned by layer: `docs/15-alignment/`
- Definition: Optional coordination grammar for repeated drift, ambiguous targeting, or risky mutation.
- Common confusion: general-purpose design doc storage.

## Implementation Taste

- Owned by layer: `docs/00-meta/implementation-taste.md`
- Definition: Framework-level judgment for non-trivial implementation structure, data shape, authority flow, semantic naming, and complexity budget.
- Common confusion: style guide, pattern catalog, or mandatory design phase.

## Maintenance Rules

- Keep entries short and orthogonal.
- Prefer ownership and boundary clarification over essays.
- Keep business glossary terms in `docs/10-prd/glossary.md` unless the term is also framework language.
