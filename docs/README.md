# Native Docs

This repository follows a local single-repo application of SVC v9.8.
This `docs/` tree stores only project-local durable knowledge. It does not vendor or mirror the upstream SVC framework text.
Routing starts in the repository root `AGENTS.md`, which sends each truth to its correct local owner.

Canonical durable owners:

- `00-meta/`
- `10-prd/`
- `15-alignment/`
- `20-product-tdd/`
- `30-unit-tdd/`
- `40-deployment/`

Volatile planning, investigation, evidence, artifacts, and collaboration state live in agent-owned task workspaces under `tasks/`.
