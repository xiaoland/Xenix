# Observability

## When to Use

Developers and support operators use this runbook to inspect local logs, enable or verify OTLP export, or keep a failing telemetry backend from affecting the desktop application. Observability failure must not make interactive startup depend on backend availability.

## Local Evidence

Xenix writes JSON Lines to `logs/xenix.log` under the active runtime home. The file rotates at approximately 1 MB and retains three backups. Logs may contain local paths and diagnostic context; handle them as sensitive support evidence.

`config/telemetry.json` stores a randomly generated persistent install id. It is not derived from machine identity, but it correlates activity across runs and therefore remains sensitive.

## OTLP Enablement

Standard OpenTelemetry endpoint, protocol, and header variables configure transport. Signal-specific values take precedence over global values.

- Traces and metrics enable when their signal endpoint is set, or when the global OTLP endpoint is set, unless their `XENIX_OTEL_EXPORT_*` override disables them.
- Remote log export is off by default. It requires both `XENIX_OTEL_EXPORT_LOGS=true` and a log or global endpoint.
- `OTEL_SDK_DISABLED=true` disables the SDK path.

Prefer signal-specific endpoints and headers when backends or credentials differ. Remote log export deserves separate review because it can transmit application diagnostic detail.

## Verify and Degrade

After enabling a signal, perform one identifiable application action and confirm its arrival in the configured backend. If nothing arrives, inspect the local log and process output for exporter, protocol, authentication, DNS, or connection failures. Xenix has no built-in telemetry health screen, so backend receipt plus local failure evidence is the health check.

Interactive startup uses batch processing and does not synchronously flush after showing the main window. A slow or unreachable backend should not block Qt input; process-exit smoke and diagnostics may flush for deterministic evidence.

If a signal causes noise or exporter failures, disable that signal with its Xenix override, or remove its endpoint. Disable remote logs independently before disabling traces or metrics. Restart, confirm normal interaction, confirm the failing exporter messages stop, and verify that intended remaining signals still arrive.
