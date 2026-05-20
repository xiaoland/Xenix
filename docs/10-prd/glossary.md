# Product Glossary

This glossary defines product-facing terms used by Xenix Native.

## Terms

- Native app: the desktop application running as a single local process.
- Chatbot-first: the product interaction shape where the user performs data analysis primarily through conversation with Xenix, assisted by file drag-and-drop and artifact previews.
- Chatbot: the primary native interaction surface where the user converses with the LLM, drops files, sees messages, and previews artifacts. It is the key usability layer for non-technical data analysis.
- Agent Harness: the service under `src/xenix/services/agent/` that owns Thread, Turn, Message, tool-call, tool-result, provider interaction, tool execution, and run recording.
- System prompt: thread-level instructions projected as the first provider message when Agent Harness calls an LLM provider. It is stored on the Thread and hidden from the Chatbot timeline.
- Thread: a persisted conversation workspace owned by Agent Harness. A Thread stores title, system prompt, turns, messages, tool records, and artifact references.
- Turn: a bounded group of messages that starts with one user message and ends when the provider response contains zero tool calls. Empty assistant text with zero tool calls is a valid turn ending.
- Message: the atomic conversation record shared by UI rendering and Agent Harness semantics.
- Tool call: a persisted Agent Harness record for a single LLM-requested function call against a registered Xenix tool.
- Tool result: a structured record produced after Agent Harness executes a service-backed tool call.
- Artifact: a service-registered local output such as a dataset, model, metrics report, image, or model apply output, usually surfaced through an `artifact://...` link.
- Artifact link: a markdown link whose target uses the `artifact://<artifact_id>?view=<view>` scheme so Chatbot can resolve and preview service-owned outputs.
- Dataset registration: a metadata pointer to a user-managed source dataset.
- Model: a reusable analyzer, not only a supervised estimator. It is a service-owned artifact that can be trained from declared input roles and later applied to compatible input roles.
- Trained model: a canonical reusable analyzer artifact tracked by metadata and stored on the filesystem.
- Legacy work item: the previous persisted unit of ML work and selection state, removed from the target AI-first service topology.
