# Deployment Operations

Use this layer when runtime or release operations fail, or when an action can destroy local state. Route by trigger:

- Build, packaged acceptance, distribution, packaged-only failure, or rollback: [Packaging](packaging.md)
- Review 1.6.0 changes and upgrade implications: [Release preparation](release-1.6.md); prior release: [1.5](release-1.5.md)
- Reconcile local tooling, caches, evidence and task archives: [Development closeout](development-closeout.md)
- Build/publish an unsigned Velopack Setup or operate the Alibaba OSS feed: [Windows Distribution](windows-distribution.md)
- Locate active state, inspect evidence, back up, reset, restore, or create a support bundle: [Runtime State](runtime-state.md)
- Configure or diagnose logs, traces, metrics, or OTLP export: [Observability](observability.md)
- Understand automatic migration, unsupported state, or migration failure recovery: [Local State Evolution](local-state-evolution.md)

Source, configuration, scripts, and tests own exact paths, archive manifests, schema versions, fields, and automation behavior. These runbooks retain operator decisions, failure boundaries, and verification evidence.
