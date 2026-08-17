# Impact Handshake F1 — Dataset Profile and Cleaning Evidence

**Status:** Consumed. Implementation and objective service acceptance completed on 2026-08-09; the single-sample paid cleaning characterization passed.
**Implementation plan:** [Foundation 1 — Dataset profile and cleaning evidence](../implementation/F1-dataset-profile-cleaning.md).
**Execution record:** [Foundation execution — 2026-08-09](../execution/foundations-2026-08-09.md).

## Evidence and Decisions Consumed

- Existing `AnalysisProfileService` is bounded but path-driven, dict-shaped, and not registered as an Agent Tool.
- `analysis.profile` has an orphaned Tool presentation while Skills currently begin with broader sample-oriented `data.query` calls.
- The supplied profile/cleaning cases demonstrate missingness, duplicates, type/range, outlier, frequency, date, and correlation risks, but supplied bytes and answers remain private.
- `D-002`, `D-003`, `D-006`, `D-008`, `D-011`, and `D-012`.

## Address and Object

Authorized objects are the profile service contract, Agent profile registration/projection, profile-first progressive-disclosure guidance, whole-Dataset cleaning scope guidance, a clean-room service fixture, and their direct tests.

Likely files are exactly those listed in the implementation plan. Any change to ML split/evaluation, storage schema, cleaning operation semantics, UI behavior, or benchmark executable assets is outside this handshake.

## State Diff

- **From:** profile accepts a path and returns an untyped dict/Markdown; the Agent has no profile Tool and begins with value-bearing queries; whole-Dataset cleaning can be mistaken for model-safe preparation.
- **To:** a registered Dataset ID produces typed, bounded, whole-Dataset quality facts through an atomic read-only Tool; provider-visible defaults contain no sample/category/group/identifier values; one focused bounded query resolves only material semantic ambiguity; cleaning and split-fitted model preparation are explicitly distinct; a clean-room service workflow proves the contract.

## Blast Radius

- Dataset inspection/profile callers and tests;
- Agent Tool catalog/composition and Tool presentation;
- data analysis/preprocessing Skill behavior;
- Tool result serialization and provider-visible privacy surface;
- ordinary test count and first paid cleaning characterization order.

## Invariants

- Source Dataset/files remain immutable and local authority remains unchanged.
- `analysis.profile` is read-only and creates no Dataset/Artifact by default.
- Dataset IDs and Artifact IDs remain non-interchangeable.
- `data.query` remains a separate atomic Tool and is never called implicitly by profile.
- No supplied corpus bytes, derivatives, answers, or Joblib files enter the repository.
- Service tests and Agent benchmarks remain physically and executably independent.
- No default provider-visible raw sample/category/group/identifier values.

## Acceptance

- The focused and repository commands in the implementation plan pass.
- Typed profile bounds and value non-disclosure are mechanically asserted.
- The clean-room case proves source immutability, expected profile/cleaning facts, derived lineage, and registered output identity through public service boundaries.
- The first paid cleaning run occurs only after service qualification and is recorded as single-sample characterization, not formal acceptance.

## Return to Discussion

Return to design when any stop condition in the implementation plan occurs or evidence requires changing cleaning semantics, persistence, UI, or the progressive-disclosure privacy default.
