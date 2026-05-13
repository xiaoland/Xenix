# Product Glossary

This glossary defines product-facing terms used by Xenix Native.

## Terms

- Native app: the desktop application running as a single local process.
- ChatBox: the primary native interaction surface where the user converses with the LLM, drops files, sees messages, and previews artifacts.
- Agent Harness: the service under `src/xenix/services/agent/` that owns Thread, Turn, Message, tool-call, tool-result, provider interaction, tool execution, and run recording.
- Thread: a persisted conversation workspace owned by Agent Harness.
- Turn: a bounded group of messages that starts with a user message and ends with a `turn_end` tool result.
- Message: the atomic conversation record shared by UI rendering and Agent Harness semantics.
- Tool result: a structured record produced after Agent Harness executes a service-backed tool call.
- Artifact: a service-registered local output such as a dataset, model, metrics report, image, or prediction file, usually surfaced through an `artifact://...` link.
- Dataset registration: a metadata pointer to a user-managed source dataset.
- Trained model: a canonical model artifact tracked by metadata and stored on the filesystem.
- Legacy work item: the previous persisted unit of ML work and selection state, removed from the target AI-first service topology.
