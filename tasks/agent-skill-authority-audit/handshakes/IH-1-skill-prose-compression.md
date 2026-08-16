# IH-1 — Agent Skill Prose Compression (prose→wall)

**Status:** approved (direction authorized by direct user directive 2026-08-16;
details delegated, not individually reviewed)

## Address and Object

- src/xenix/services/agent/skills/xenix-data-analysis/SKILL.md (body)
- src/xenix/services/agent/skills/xenix-data-modeling/SKILL.md (body)
- src/xenix/services/agent/skills/xenix-data-preprocessing/SKILL.md (body)
- src/xenix/services/agent/skills/catalog.json (regenerated, not hand-edited)

Only the skill BODY changes. Frontmatter name / description / metadata are
untouched, so routing trigger words and tool-scope contracts are unchanged.

## State Diff (From → To)

Delete W-class prose that duplicates an existing hard wall; compress S-class
negative prose to positive one-liners; keep G/B routing and economy guidance in
positive form. Reference: packet audit.md.

- analysis: remove "do not invent tools/scripts/packages" (tool registry),
  "no destructive SQL" (DuckDbSqlValidator), "do not infer numbers" (final-answer
  standard already owns it); compress causality / knowledge-claim rules to
  positive form; keep the activate-narrower-skill routing rule; drop
  "overwrite/delete" from the ask-versus-act clause (derived-only per D2).
- modeling: remove "never invent params / SARIMA orders" (validate_params),
  "never inline word dumps / local paths" (resource + file-authority walls);
  convert "do not claim causality / automatic decision" and knowledge-claim
  rules to positive form; keep model-key selection and evidence-authority rules
  in positive form.
- preprocessing: remove "never overwrite source" (derived-only architecture),
  "only advertised tools / no script runtime" (tool registry), the
  index/name "never" clauses (tool_inputs + stale-index rejection); keep
  left-to-right and finalization-authority facts in positive form.

## Blast Radius

- Agent provider context projection (catalog.json body feeds
  agent_skill_context_messages). No Tool, service, schema, or harness change.
- tests/test_agent_skill_tool_scope.py depends on skill names and tool-scope
  mapping only — unaffected by body prose.
- No change to references/ or assets/ manifests.

## Invariants

- Skill names, descriptions (routing trigger words), tool lists, default
  workflow steps, reference/asset manifests, and final-answer standards are
  unchanged.
- Every existing hard wall (DuckDbSqlValidator, Pydantic input models,
  model-param schemas, in-memory derivation, skill-activation gate) is
  unchanged and not weakened.
- catalog.json must regenerate byte-stably from the edited SKILL.md files.

## Verification

- pdm run agent-skills-generate then pdm run agent-skills-check (sync).
- pdm run test -q and pdm run check (no regression).
- Benchmark A/B: same 4 cases (revenue_by_region_chart, rainy_season_restock,
  ml_cleaning, ml_clustering), same subject model, harness-variant baseline vs
  skill-prose-compressed. Success criterion: semantic pass held or improved,
  token/latency reduced.

## Return to discussion

- If the after-run shows semantic regression beyond single-sample noise, or
  token/latency does not decrease.
- If agent-skills-check or any ordinary test fails.
