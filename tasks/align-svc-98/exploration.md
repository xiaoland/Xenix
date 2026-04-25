# Exploration Task

## Objective & Hypothesis

- Objective: map the current Xenix Native repository against the requested SVC baseline, identify structural/documentation drift, and prepare the smallest confirmation needed before any durable-doc cleanup or implementation.
- Hypothesis: the repository already carries a partial SVC shape in docs, tasks, and local `AGENTS.md` files, but the applied baseline is inconsistent across versions and some enforcement artifacts are missing.

## Prompt

- Align Xenix Native to SVC `v9.8` without multi-repo and clean historical legacy documentation.
- First fully explore current code structure and existing docs.
- Use `tasks/align-svc-98/` as the reasoning and planning workspace.

## Guardrails Touched

- Current work is in Mode A exploration only.
- No durable docs or production code changes.
- Workspace for current thinking stays under `tasks/align-svc-98/`.
- Multi-repo is explicitly out of scope for the requested target state.

## Verification Anchors

- Confirm the true SVC upstream baseline to align against.
- Confirm current durable owner map in Xenix.
- Confirm current volatile task topology in Xenix.
- Confirm which existing documents are canonical, stale, or orphaned.

## Current Facts

- `docs/README.md` says the repository uses `SVC v9.3` canonical durable layers.
- `docs/SVC-LAYER-MAP.md` still says `SVC v9.1`.
- `docs/_SVC_v9_1.md` exists as an embedded framework snapshot and is likely a historical carry-over.
- `tasks/README.md` says the volatile workspace uses `tasks/active/`, `tasks/archive/`, and `tasks/templates/`.
- Actual `tasks/` contents currently include `issue-80/`, `v2_0_0/`, and `templates/`, so the declared topology and the real topology diverge.
- `README.md`, `pyproject.toml`, `CONTRIBUTING.md`, and `docs/40-deployment/development.md` reference `pdm run check-svc-docs`.
- `pyproject.toml` maps `check-svc-docs` to `python scripts/check_svc_docs.py`.
- `scripts/check_svc_docs.py` does not exist.
- Current code structure already reflects a layered native app:
  - core app entry: `src/xenix/main.py`, `src/xenix/app.py`
  - UI layer: `src/xenix/ui/`
  - service layer: `src/xenix/services/`
  - ML service subpackage: `src/xenix/services/ml/`
  - persistence-related code under `src/xenix/services/storage/`
- Current local `AGENTS.md` coverage already expresses important fast-moving boundaries:
  - `src/xenix/services/AGENTS.md`
  - `src/xenix/services/ml/AGENTS.md`
  - `src/xenix/ui/AGENTS.md`
- Current durable docs already separate several truth owners:
  - `docs/10-prd/`
  - `docs/15-alignment/`
  - `docs/20-product-tdd/`
  - `docs/30-unit-tdd/`
  - `docs/40-deployment/`

## SVC Upstream Facts

- Local reference repository: `F:/CODING/svc`
- Remote fetched on `2026-04-24`.
- Current fetched upstream `main` HEAD is commit `c5a120d4c764a0ff552cd4648c5abe2d94b1fa4d` dated `2026-04-06 21:01:33 +0800` with subject `v9.7: alignment substrate`.
- No remote tags were returned for `v9.*`.
- No `v9.8` string was found in the fetched local reference repository.
- Therefore, the requested `SVC v9.8` baseline is currently unverified from the accessible upstream source.

## Inferred SVC Target Shape

- This section is inference from the fetched upstream `v9.7` source, not a directly verified `v9.8` artifact.
- Routing starts with input type classification: `Intent / Constraint / Reality / Artifact`.
- Durable owner comes before mode selection.
- Mode behaves as a reusable posture overlay: `Explore / Solidify / Execute / Diagnose`.
- `tasks/` is the volatility buffer.
- Multi-repo is optional, pressure-driven, and not needed for this task.
- Alignment is a coordination grammar layer, not a catch-all dump for leftover docs.
- Promotion from task notes to durable docs should pass a stability / reuse / cost / owner test.

## Xenix Alignment Strengths

- The repository already has a recognisable durable-layer layout.
- Local `AGENTS.md` files are colocated near risky seams and already encode concrete boundaries.
- Service/UI ownership is materially present in both docs and code structure.
- `docs/15-alignment/` already holds glossary/taxonomy/target-map style coordination documents.

## Xenix Alignment Gaps

- Version baseline drift:
  - `v9.3` in `docs/README.md`
  - `v9.1` in `docs/SVC-LAYER-MAP.md`
  - old embedded framework snapshot in `docs/_SVC_v9_1.md`
- Task topology drift:
  - declared `tasks/active` and `tasks/archive`
  - actual ad hoc folders `tasks/issue-80` and `tasks/v2_0_0`
- Enforcement drift:
  - documented `check-svc-docs` command exists
  - referenced enforcement script is missing
- Possible durable-owner drift:
  - some legacy documentation may exist outside the clean owner boundaries implied by current SVC
- Possible naming/history drift:
  - UI and scenario naming suggest historical layers still coexist and may need documentation cleanup or explicit rationale

## Unknowns

- What concrete source should be treated as the authoritative definition of `SVC v9.8`?
- Should Xenix align to the latest accessible upstream (`v9.7` as of `2026-04-24`) if `v9.8` remains unavailable?
- Which historical docs should be deleted versus rewritten versus moved?
- Should old task records be migrated into `tasks/active/` and `tasks/archive/`, or preserved in place with a compatibility note?
- Should the missing `check-svc-docs` enforcement be restored, replaced, or removed from docs and command surfaces?

## Candidate Paths

1. Strict target confirmation path
   - First confirm what `v9.8` means in this project.
   - Then build an exact Xenix-to-SVC gap matrix against that verified baseline.
2. Latest-accessible baseline path
   - Use fetched upstream `v9.7` as the practical source baseline.
   - Note the version mismatch explicitly and align Xenix to that verified shape.
3. Hybrid path
   - Prepare the Xenix gap matrix against verified upstream `v9.7`.
   - Leave a narrow substitution point for any later `v9.8` delta once you provide the source.

## Smallest Confirmation Needed

- Confirm whether this task should align Xenix to:
  - the latest accessible upstream SVC baseline currently verifiable from `F:/CODING/svc` and GitHub (`v9.7` as of `2026-04-24`), or
  - another specific `v9.8` source that you want me to use.

## Promotion Candidate Truths

- Leave empty until scope and baseline are confirmed.
