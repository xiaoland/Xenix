# Beta Diagnostic Question Matrix

## Purpose

List candidate public-beta diagnostic questions before deciding the final
instrumentation scope.

Priority meaning:

- P0: beta feedback is likely not diagnosable without this signal.
- P1: materially shortens diagnosis or helps find recurring beta problems.
- P2: useful for analysis, but not required for the first beta telemetry slice.

Signal meaning:

- Trace: causal workflow boundary or nested operation.
- Metric: aggregate count, duration, distribution, or status rate.
- Log/Event: structured local diagnostic fact.

## Matrix

| Priority | Diagnostic Question | Workflow / Owner | Primary Signals | Safe Attributes | Forbidden / Notes |
| --- | --- | --- | --- | --- | --- |
| P0 | Did the app start far enough to initialize runtime paths, logging, settings, and storage? | `app.startup` | Trace, metric, log/event | `service.version`, `xenix.build.commit`, `xenix.package_mode`, `os.type`, `python.version_bucket`, `storage.schema_version`, `status`, `error.type` | No local absolute paths in remote/exported attributes. Local JSON log may include redacted runtime path class only. |
| P0 | Did storage bootstrap or migration fail, and at which schema transition? | `storage.bootstrap` | Trace, metric, log/event | `storage.schema_version.from`, `storage.schema_version.to`, `status`, `error.type`, `duration_ms` | No SQL values, row payloads, dataset values, or full exception message by default. |
| P0 | Which build/install population is producing failures? | `app.resource` | Resource attrs, metric dimensions | `service.version`, `xenix.build.commit`, `xenix.install.id`, `xenix.package_mode`, `os.type`, `python.version_bucket` | `install.id` must be random-generated, persistent, anonymous, and not derived from machine fingerprint. |
| P0 | Did an Agent turn start, complete, fail, cancel, or hit step budget? | `agent.turn` | Trace, metric, log/event | `agent.turn.status`, `agent.step_budget.outcome`, `duration_ms`, `error.type` | No prompt text, message content, tool result body, raw model output. |
| P0 | Did an LLM provider request fail or hang, and which provider/request class was involved? | `agent.provider_request` | Trace, metric, log/event | `agent.provider.key`, `agent.request.kind`, `agent.model.family_or_hash`, `status`, `duration_ms`, `error.type`, `http.status_code` if available | No API key, request body, prompt, response text, full provider error body. Model key should be bounded or hashed if user-configurable. |
| P0 | Did a tool call fail because of validation, service error, provider mismatch, cancellation, or timeout? | `agent.tool_call` | Trace, metric, log/event | `agent.tool.name`, `agent.tool.status`, `agent.tool.failure_class`, `duration_ms`, `error.type` | No tool arguments by default. Only registered safe summaries like dataset shape bucket may be considered later. |
| P0 | Did ML task execution progress from enqueue to worker dispatch to finalization? | `ml.task` | Trace, metric, log/event | `ml.task.kind`, `ml.task.status`, `ml.worker.kind`, `duration_ms`, `queue_wait_ms`, `error.type` | No dataset path, column names, cell values, model file path, raw traceback in exported attributes. |
| P0 | Did local or SSH worker dispatch fail before the ML operation could run? | `ml.worker_dispatch` | Trace, metric, log/event | `ml.worker.kind`, `ml.worker.selection_status`, `status`, `duration_ms`, `error.type` | No SSH hostname, username, remote path, key path, command line with secrets. |
| P0 | Did artifact finalization/registering fail after work succeeded? | `artifact.register` | Trace, metric, log/event | `artifact.kind`, `artifact.owner`, `status`, `error.type`, `duration_ms` | No absolute artifact paths remotely. Local logs may include redacted/path-class info only. |
| P1 | Are provider calls slow by provider/model family/request kind? | `agent.provider_request` | Metric, trace | `agent.provider.key`, `agent.request.kind`, `agent.model.family_or_hash`, `duration_ms` | Keep cardinality bounded; avoid full model names if user-defined. |
| P1 | Are tool failures concentrated in specific tools? | `agent.tool_call` | Metric, log/event | `agent.tool.name`, `agent.tool.failure_class`, `status` | Do not log raw args/results. |
| P1 | Are data operations failing due to file format, validation, SQL validation, or artifact write failures? | `data.*`, `analysis.*` | Trace, metric, log/event | `data.operation`, `analysis.operation`, `status`, `error.type`, `row_count_bucket`, `column_count_bucket`, `file_format` | No column names, cell values, SQL text, file paths, or generated chart contents. |
| P1 | Are ML task failures model-family specific or worker-kind specific? | `ml.task` | Metric, log/event | `ml.task.kind`, `ml.model.family`, `ml.model.task_kind`, `ml.worker.kind`, `error.type` | Model key may be bounded catalog key if from built-in registry; user-provided names need hashing/bucketing. |
| P1 | Did cancellation propagate correctly through Agent turn, tool execution, and ML task boundaries? | `agent.turn`, `agent.tool_call`, `ml.task` | Trace, metric, log/event | `owner`, `status=cancelled`, `duration_ms`, `cancellation.source` | No user message content explaining cancellation. |
| P1 | Are failures recoverable or user-actionable? | cross-owner | Metric, log/event | `error.type`, `error.recoverability`, `owner`, `status` | Avoid raw exception messages; map to normalized domain errors when possible. |
| P1 | Did runtime configuration load correctly and choose expected provider/worker defaults? | `settings.load`, `llm.settings`, `ml.worker_config` | Trace, log/event | `settings.kind`, `status`, `configured_provider_count_bucket`, `worker_count_bucket`, `default_worker.kind` | No provider base URL, API key, SSH host/user/path. |
| P1 | Can support correlate a user-reported issue to all local evidence? | cross-owner | Resource attrs, trace, log/event | `xenix.install.id`, `trace_id`, `span_id`, `owner`, `service.version`, `xenix.build.commit` | Install id must be random anonymous id. No machine fingerprint. |
| P2 | Which workflows are most used during beta? | cross-owner | Metric | `owner`, `operation`, `status` | This approaches product analytics; keep internal workflow-level only, not UI event analytics. |
| P2 | How large are beta workloads in broad buckets? | `data.*`, `ml.task` | Metric, log/event | `row_count_bucket`, `column_count_bucket`, `file_size_bucket`, `ml.task.kind` | Buckets only; no raw sizes if that is deemed sensitive, no file names or data values. |
| P2 | How often do background tasks complete inside grace period versus require follow-up query? | `agent.tool_call`, `ml.task` | Metric | `agent.tool.name`, `ml.task.kind`, `completion_mode` | No tool payload/body. |
| P2 | Are optional dependencies or model families missing/failing on user machines? | `ml.registry`, `ml.task` | Metric, log/event | `ml.model.family`, `dependency.group`, `status`, `error.type` | No local package paths. |
| P2 | Are remote SSH workers useful enough to justify more investment? | `ml.worker_dispatch`, `ml.remote_stage` | Metric | `ml.worker.kind=ssh`, `status`, `duration_ms`, `stage` | No host/user/remote path. |

## Initial Cut Proposal

Recommended first discussion cut:

- Keep all P0 questions unless a privacy or implementation concern rejects them.
- Promote only selected P1 questions that directly support public beta feedback
  loops.
- Defer all P2 questions unless they are nearly free after P0/P1 spans exist.

Status: accepted by user on 2026-06-06.

## Open Selection Questions

- Should any P0 item be downgraded because local logs already cover it well
  enough?
- Should `xenix.install.id` be included in every signal as a resource attribute,
  or only in exported/diagnostic bundles?
- Should built-in model catalog keys be treated as safe attributes, or should
  they still be mapped to family/task-kind only?
- Should row/column/file-size buckets be allowed in beta v1?
- Should SQL operation telemetry include operation kind only, or also query
  validator failure class?
