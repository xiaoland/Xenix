# AMD One-click Hard Cut-off Contract

## Definition

AMD one-click is a removable composition slice, not a core dependency. A cut-off
build starts, imports, packages, and exercises the ordinary Xenix product without
initializing AMD installation state, registering AMD factories, rendering AMD
setup UI, loading AMD manifests, starting processes, opening forwards, or touching
the network.

Hard cut-off does not mean reversing a released SQLite migration or deleting
generic capability improvements. `SettingsStore`, capability-owned provider
catalogs/factories, engine-neutral OCR, ordinary KServe/PAGE support, static
OpenAI-compatible providers, and Paddle OCR remain usable product substrate.

## Completion Record

The mechanical proof was executed on 2026-07-28:

- the static AMD regression rejects every direct generic-to-AMD source import;
- a default AMD-enabled Windows package and packaged smoke passed;
- `XENIX_BUILD_AMD_ONE_CLICK=0` produced a package with no AMD service, resource,
  UI, or runtime-hook path;
- that AMD-absent package passed packaged smoke even when
  `XENIX_ENABLE_AMD_ONE_CLICK=1` was inherited by the process;
- generic tests, checks, and source smoke passed with the optional slice not
  required.

This proves the pre-release hard cut boundary. It does not replace the staged
decommission sequence for a release that has managed real target installations.

## Dependency Rule

Dependencies point one way:

```text
app composition
  -> removable AMD slice
      -> capability-owned ports and storage primitives

ordinary LLM / Embedding / OCR / Knowledge / Agent / Settings / Storage
  -X-> AMD
```

The rules are mechanical:

- no generic module imports `xenix.services.amd`, AMD status/error types, or AMD
  resources;
- capability factory registries are app-scoped instances with explicit built-in
  registrations; AMD contributes adapters only at the composition root;
- no import-time registration, global service locator, entry-point discovery, or
  `try/except ModuleNotFoundError` hides a missing AMD package;
- no core constructor requires `AmdAiDeploymentService`;
- generic startup, shutdown, diagnostics, smoke, and spawned Paddle OCR have zero
  AMD prerequisite;
- AMD-only Python dependencies stay in target manifests/on-demand acquisitions,
  not the desktop base dependency lock or unconditional PyInstaller imports.

## Cut-off Inventory

The removable slice is:

- `src/xenix/services/amd/**`;
- `src/xenix/resources/amd/**`;
- `src/xenix/ui/amd_setup.py` and
  `src/xenix/ui/amd_deployment_tasks.py`;
- AMD-only tests, acceptance harnesses, scripts, and packaged-smoke collector.

The only permitted integration anchors outside that slice are:

- one build-owned AMD feature gate and one composition helper call in
  `src/xenix/app.py`;
- one generic optional UI-action contribution seam in
  `src/xenix/ui/main_window.py`, with no AMD type/import;
- one optional AMD resource/hidden-import collector in `xenix.spec`;
- AMD-namespaced translation entries;
- the already released primitive SQLite schema/migration edge, which remains inert
  compatibility history.

`src/xenix/services/agent/composition.py`, capability modules, Knowledge, the
physical settings store, generic diagnostics, and generic packaged smoke are not
permitted anchors. If source removal requires edits outside this inventory, the
architecture has failed the cut-off constraint.

## Persisted Compatibility

Capability schemas own an owner-neutral `Managed*ProviderRef` with an opaque
`manager_id`, installation ID, and component-generation ID. They never import an
AMD type or branch on an AMD enum.

When the AMD factory contribution is absent:

- old AMD-managed entries still parse and display as read-only
  `provider_implementation_unavailable`;
- an active/default/historical reference is never rewritten and never falls back;
- attempting inference fails typed before dispatch;
- the capability owner can explicitly remove an unavailable managed entry subject
  to its ordinary selection/reference blockers;
- settings revisions, secrets, and unrelated providers are unchanged.

Released AMD tables and migrations are never rolled back. They have no foreign-key
or startup dependency from core product state. With the AMD module absent,
storage bootstrap ignores inert rows/tables and all forward migrations still run.

## Decommission Sequence

Source removal and managed-runtime cleanup are different operations.

For a released feature:

1. release N disables new AMD deployment/upgrade intent but retains the AMD owner;
2. release N retires every installation, closes admission, drains bounded
   operations, removes exact target realizations, and leaves managed projections
   absent or explicitly unavailable;
3. an ownership/process/listener/forward/settings/SQLite inventory proves no live
   AMD realization remains;
4. release N+1 removes the slice and its integration anchors.

Before public release, or when attestation proves no installation/projection/live
realization ever existed, the slice may be cut directly. A source cut is never
claimed to stop an unknown remote orphan after its cleanup owner has been deleted.

## Mechanical Proof

TP-24 must prove all of the following:

- an AST/import-graph gate rejects every generic-to-AMD edge and import-time
  registration;
- a temporary cutoff tree excludes the removable slice and deletes only the named
  integration anchors;
- a clean subprocess imports and constructs SettingsStore/SQLite, static Chat,
  static Embedding, Knowledge, Agent composition, and spawned Paddle OCR;
- a fixture containing inert AMD SQLite rows and owner-neutral managed references
  loads without AMD code; managed targets are unavailable without fallback;
- generic `test`, `check`, `smoke`, `package`, and `smoke-package` paths do not
  collect AMD resources or resolve AMD runtime wheels;
- startup creates no AMD thread, process, listener, forward, network request,
  settings write, or installation query;
- the cutoff diff deletes no generic LLM, Embedding, OCR, Knowledge, Agent,
  SettingsStore, or storage-bootstrap implementation.
