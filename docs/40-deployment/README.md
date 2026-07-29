# Deployment Operations

Use this layer when runtime or release operations fail, or when an action can destroy local state. Route by trigger:

- Build, packaged acceptance, distribution, packaged-only failure, or rollback: [Packaging](packaging.md)
- Build/publish an unsigned Velopack Setup or operate the Alibaba OSS feed: [Windows Distribution](windows-distribution.md)
- Locate active state, inspect evidence, back up, reset, restore, or create a support bundle: [Runtime State](runtime-state.md)
- Configure or diagnose logs, traces, metrics, or OTLP export: [Observability](observability.md)
- Understand automatic migration, unsupported state, or migration failure recovery: [Local State Evolution](local-state-evolution.md)
- Operate or retire the optional Radeon model profile, inspect its installation
  state, or recover an interrupted forward reconcile: [Managed AMD Runtime](managed-amd-runtime.md)

Source, configuration, scripts, and tests own exact paths, archive manifests, schema versions, fields, and automation behavior. These runbooks retain operator decisions, failure boundaries, and verification evidence.
