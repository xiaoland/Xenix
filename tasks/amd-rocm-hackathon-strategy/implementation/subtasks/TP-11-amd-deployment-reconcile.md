# TP-11 — Deployment Coordinator and Forward Reconcile

## Outcome

Implement `AmdAiDeploymentService` as a deep control-plane facade over TP-08–10
and capability-owned managed-projection ports, using only fake placements in this
task.

## Owned Mutation

- add `src/xenix/services/amd/deployment.py`;
- add `src/xenix/services/amd/reconcile.py`;
- add `src/xenix/services/amd/status.py`;
- add `src/xenix/services/amd/participants.py`;
- add `tests/test_amd_deployment_service.py`.

It does not edit capability settings documents, build network clients, parse
OpenAI/KServe/PAGE, or contain SSH/Local branches.

## Public Use Cases

- prepare/install, inspect status, explicit repair, prepare upgrade, request
  retirement, and resume;
- immutable `InstallationSpec` chooses exactly one placement;
- private component participant collection submits exact owner-scoped ensure,
  mark-retiring, remove-if-unreferenced, and projection-status commands;
- status derives materialization, projection presence, live observation,
  selection/blockers, and timestamp without persisted `READY`.

## Forward-only Rules

- no before/after settings snapshot, compensation, or rollback;
- crash after any component/domain ensure only leaves forward-reconcilable partial
  progress;
- verified generation is required before projection ensure;
- G2 is a new provider identity and is never selected automatically;
- resource-blocked upgrade leaves selected G1 untouched;
- retirement closes the TP-09 gate and commits desired absence before domain
  reconcile; blockers yield `REMOVAL_BLOCKED`;
- normal ensure can never resurrect `RETIRING`.
- the fixed profile is product-usable only when Chat, Embedding, and OCR are all
  verified and projected, while each component/domain still reports its own
  failure and no aggregate `READY` is persisted.

## Acceptance

- idempotent prepare/repair/upgrade/retire with deterministic fake failures;
- crash after every phase/write restarts toward the same desired state;
- selection races become domain blockers/rejections without cross-domain lock;
- registration, reachability, selection, installed, and operational facts remain
  separate;
- adding a future fourth participant does not change lifecycle state logic.
- participants use owner-neutral capability ports; generic capability code never
  imports deployment/participant/status types;
- the facade can be omitted from composition without becoming a startup,
  shutdown, provider, settings, or diagnostics prerequisite.

## Verification

- state-machine/failpoint/property-style tests;
- fake managed owner conflict and partial-domain tests;
- `pdm run check`.
