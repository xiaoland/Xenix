# Public Beta Runtime Telemetry

## Purpose

Design the minimum runtime telemetry slice needed before a small public beta.

This packet is intentionally exploratory. It should capture discussion state,
evidence, candidate designs, and confirmation checkpoints before any durable
docs or application code are changed.

## Files

- `exploration.md`: objective, constraints, facts, unknowns, candidate paths,
  and confirmation checkpoints.
- `working-design.md`: evolving topology, signal model, collection boundaries,
  and first-slice proposal.
- `discussion-axes.md`: separates the work into internal collection
  infrastructure, instrumentation design, and transport/export.
- `internal-infra-open-source-research.md`: research notes on mature open source
  options for the internal collection substrate.
- `beta-diagnostic-question-matrix.md`: candidate public-beta diagnostic
  questions for instrumentation strategy and tactical scoping.
- `model-as-observability-source.md`: strategy for projecting telemetry from
  existing domain models and lifecycle transitions rather than adding parallel
  telemetry entities.
- `implementation-slices.md`: proposed implementation slices, scope boundaries,
  model reuse, and verification anchors.
- `decision-log.md`: dated discussion decisions and rejected options.

## Current Mode

Explore.

Implementation is explicitly out of scope until the user confirms the
high-level direction and says to start.
