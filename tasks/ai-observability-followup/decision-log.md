# AI Observability Decision Log

## 2026-06-11

- Created follow-up task packet for AI observability upgrade.
- Classified current work as `Constraint + Explore`: no implementation yet; design and discussion only.
- Reframed the goal from general runtime telemetry to AI behavior observability for experience and token-consumption optimization.
- Accepted the recommended privacy posture: public-beta remote export should not include raw prompts, completions, tool arguments, tool results, or provider payloads by default.
- Accepted the recommended first token-attribution posture: begin with provider request, request kind, tool exposure, loop/retry/guard context, latency, status, and provider-reported usage.
- Recorded a maintainability hypothesis: AI telemetry boundaries should be owned by Agent Harness because it owns thread, turn, provider request, tool call, and agent-loop semantics.
- Recorded the complementary boundary: LLM Service should remain an LLM request router/provider-construction boundary, not the owner of AI telemetry semantics.
- Clarified `eval` in Xenix terms: structured judgment about agent behavior quality, not ordinary scikit-learn model evaluation.
- User corrected the layer boundary for `eval`: it is not collection-layer responsibility and should be treated as later analysis-layer work.
- Created collection-layer gap matrix to guide the next AI O11y implementation slices. The matrix separates existing Harness facts, direct OTel projections, missing collection facts, and analysis-layer exclusions.
- Created P0 implementation plan covering correlation, request shape, tool exposure, token usage projection, output shape, invalid tool call classification, tool call context, and semantic projection target.
- Implemented P0 AI observability projection in Agent Harness with GenAI/OpenInference-compatible metadata, safe request-shape summaries, token usage projection, invalid-tool-call classification, and targeted privacy tests.
- Split OTLP export configuration per signal so Phoenix can receive traces-only while metrics/logs remain routed through a Collector or stay local.

## Working Assumptions

- Existing Harness records should remain the source of truth.
- AI telemetry should be a projection, not a parallel state model.
- OpenTelemetry remains the backend-neutral export substrate.
- Phoenix is the strongest first backend candidate for local AI trace/eval verification, while OpenLIT remains a useful OTel-native instrumentation reference.
