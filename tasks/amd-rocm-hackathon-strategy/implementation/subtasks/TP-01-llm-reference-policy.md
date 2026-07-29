# TP-01 — LLM Managed-reference Policy

## Outcome

Make deletion and reinstallation behavior unambiguous for default, guard, title,
current, and historical Thread model references. The policy below is accepted;
this task records it.

## Owned Mutation

- update `docs/20-product-tdd/llm-conversation-boundary.md`.

ADR 0008 remains unchanged because this policy specializes provider-reference
lifecycle without changing its canonical conversation authority. No
implementation file is changed.

## Policy to Record

- default, turn-completion guard, and thread-title references block removal of
  their exact managed provider;
- any currently executing conversation operation blocks through its operation
  permit;
- an old Thread's persisted `selected_fq_model_key` does not keep remote compute
  installed forever, but reopening it after exact provider removal returns typed
  `llm_model_reference_stale`;
- deployment never rewrites Threads or selects a fallback;
- a generation-specific provider key is never reused, so G2 cannot satisfy a G1
  reference;
- retirement may remain `REMOVAL_BLOCKED` until live/default/guard/title blockers
  are explicitly resolved.
- removal of the entire manager implementation leaves historical exact refs typed
  `provider_implementation_unavailable`; it never rewrites a Thread or lets G2,
  static, trial, or another manager satisfy the reference.

## Acceptance

- G1 selected, G2 registered, G1 retired, and G1 reinstalled sequences have one
  deterministic result;
- no validator silently selects the first remaining provider;
- the LLM domain, not AMD deployment, owns stale-reference semantics;
- the policy names the exact repository query needed by TP-04.

## Verification

- document review against current conversation persistence and selection fields;
- link and terminology check.
