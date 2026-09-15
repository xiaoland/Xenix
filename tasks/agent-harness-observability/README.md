# Agent Harness observability

- **Objective:** make a failing benchmark cell explain its lifecycle, timing,
  correlation, and exception context, and carry the same trace boundary into the
  production Agent Harness submission path.
- **Guardrails:** preserve case verdicts, provider behavior, isolation, budgets,
  and the distinction between subject and judge measurements.
- **Verification:** run focused infrastructure tests, offline benchmark checks,
  headless/headed collection, static checks, and inspect the changed dependency
  topology.
- **Current Truth:** v5 reports now carry case-agnostic lifecycle spans and
  recover completed child-process phases after a timeout; terminal output joins
  the cell to its trace and absolute report path. Production Agent submissions
  emit the matching OpenTelemetry GenAI operation/conversation vocabulary.
- **Next Step:** commit and push after final diff/status verification. Python
  3.14 telemetry tests, Ruff, compileall, report-policy smoke, diff checks, and
  import-topology review pass. Full pytest collection is unavailable in this
  Linux container because PySide6 requires the absent system `libEGL.so.1`.
