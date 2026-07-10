# Implementation Taste

Implementation taste is the framework-level judgment surface for non-trivial code design and implementation changes.

It is language- and tech-stack-neutral. It is not a style guide, a pattern catalog, or a mandatory design phase.

## Role

Use this guidance when work shapes implementation structure, boundary shape, data shape, state flow, authority flow, durable naming, abstraction, dependency use, or complexity budget.

Do not load it for purely mechanical edits whose owner, surface, and verification are already obvious.

Implementation taste has two layers:

1. Design formation taste: asks what model, boundary, authority, naming, and complexity tradeoff should exist.
2. Implementation shape taste: projects those principles onto concrete code surfaces such as APIs, request/result objects, component props, commands, events, state shape, control flow, tests, assertions, and observability.

## Design Formation

### Preserve SSoT

Every durable fact, state, relationship, or decision should have one authority.

Replicas, caches, views, client state, derived data, and denormalized fields are references, projections, or performance artifacts unless explicitly promoted to authority.

When two surfaces appear to own the same truth, resolve authority before implementation.

### Respect Trust and Provenance

Values crossing a boundary must be classified by provenance:

- authority fact
- stable reference
- command or proposal
- user-authored value
- derived projection

Passing an id or command is often better than passing detail when the receiver can resolve authoritative state itself.

User-authored values are authoritative for user input, expression, preference, or intent, but not for application-owned facts such as permission, existing entity state, storage state, or computed model result state.

### Name Durable Semantics Directly

Durable model fields, cross-boundary fields, commands, events, and business operations should be direct, searchable, and consistent.

Use the same name for the same semantic unless an explicit boundary translation is being modeled.

### Shape Data Before Clever Flow

Data shape often determines implementation shape.

Before adding clever control flow, complex algorithms, or orchestration machinery, ask whether the data structure, authority boundary, ownership path, or state representation is wrong or underspecified.

Prefer data and boundary shapes that make valid behavior obvious and invalid behavior hard to express.

### Spend Complexity for Return

Complexity is an input. Useful behavior, reliability, clarity, maintainability, and evolvability are outputs.

Each abstraction, layer, state holder, protocol, configuration switch, indirection, dependency, and design pattern must explain what it earns.

Do not guess performance pressure. Measure before optimizing, and optimize only when the measured bottleneck is material enough to justify the added complexity.

Prefer simple algorithms and simple data structures until scale, evidence, or correctness pressure proves they are no longer enough.

## Implementation Shape

Use this guidance while editing concrete code surfaces to check:

- whether a boundary receives a fact, reference, command, proposal, or user-authored value
- whether names expose durable semantics instead of hiding them behind generic containers
- whether local structure matches real complexity
- whether assertions, tests, or observability can prove the intended authority, boundary, and behavior
- whether repository idioms are preserved unless the change intentionally renegotiates them

Implementation shape taste should stay close to the code surface being changed. When verified work changes a durable contract, update its single owning document in the same change instead of preserving a parallel summary.

## Application Path

1. Load this file through the root `AGENTS.md` entry point for non-trivial implementation work.
2. Use design formation taste to expose authority, trust, naming, and complexity pressure.
3. Use the root routing and working model for ownership, verification timing, and feedback loops.
4. Use implementation shape taste while editing concrete code surfaces.
5. If the change alters durable truth, update Product TDD, Unit TDD, Deployment, PRD, or local seam guidance according to the root owner map.
