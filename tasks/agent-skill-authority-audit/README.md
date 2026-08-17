# Agent Skill Prose→Wall Audit

**Status:** Solidify (evidence-backed audit; no durable mutation yet)
**Opened:** 2026-08-16

## Objective

Make the three Agent Skills (xenix-data-analysis, xenix-data-modeling,
xenix-data-preprocessing) measurably cheaper and more reliable by separating
prose that duplicates an existing Harness hard wall from prose that still
carries real load. Deliver a line-referenced classification and a probe
catalog that turns every "delete / move / compress" edit into a measurable
ablation. No Waza runtime is introduced; only its philosophy (adversarial /
fault-injection / ablation) is borrowed and mapped onto the existing
benchmarks/agent_harness/ and skill_catalog surfaces.

## Guardrails

- No durable mutation to src/, docs/, tests/, benchmarks/, or skills/ under
  this packet. Every proposed edit is recorded here and gated by a separate
  Impact Handshake before execution.
- The Harness hard walls are evidence, not a change target. This audit must
  not weaken any existing validator, fail-closed check, or the progressive
  disclosure gate.
- Skills keep their positive workflow and final-answer standards; this packet
  only classifies the negative ("do not / never / only") prose.
- This packet is independent. It may cite tasks/improve-260809/ (O4-A3, O4-A4,
  O4-E3, B0-GR) as prior evidence but does not extend or depend on that
  packet's program structure.

## Verification

- Every W-class rule is backed by a concrete enforcement location (file:line)
  in the audit table.
- Every probe in the catalog states its input, expected outcome, and an
  offline or paid judge-free criterion.
- "Higher success rate, lower consumption" is expressed as measurable deltas
  (activation correctness, tool-call count, token/latency), never as prose
  impressions.

## Current Truth

- Most negative prose in the three Skills already duplicates a hard wall that
  exists in the tool/service layer (DuckDbSqlValidator, Pydantic input models,
  the model-param schemas, the in-memory derivation architecture, and the
  skill-activation progressive-disclosure gate). See audit.md.
- The one category that cannot be hard-walled is semantic final-answer
  honesty (causality, invented numbers, automatic-decision claims). Per the
  prior B0-GR / O4-E3 decision, these belong to the Judge and should be
  compressed to a single positive standard, not kept as "do not X".
- Routing (which skill activates) is structurally observable: activation is an
  explicit agent.skill.activate tool call and the tool scope is gated by the
  activated skill, so a route probe is deterministic and judge-free.
- User decisions recorded:
  - D1: prefer Harness hard walls over "do not X" prose; negative prose raises
    cognitive load and hallucination rate without adding safety.
  - D2: no confirmation wall for destructive/export operations — all data
    operations are derived, never in-place, so no true destruction exists.
  - D3: the semantic-judgment class cannot be hard-walled; compress it and
    measure it with the Judge.
  - D4: routing probes and fault-injection/ablation probes are the valuable
    instrument; ablation is the optimization loop.
  - D5: do not introduce the Waza runtime; borrow the philosophy only.

## Next Step

Produce audit.md and probes.md, then hand the single highest-value W-class
deletion candidate back for an Impact Handshake before touching any SKILL.md
or catalog.json.

## Packet Map

- audit.md — prose→wall classification with line-level enforcement evidence
- probes.md — routing, fault-injection/ablation, and consumption probe catalog
