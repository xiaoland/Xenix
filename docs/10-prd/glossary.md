# Product Glossary

This glossary defines product-facing terms used by Xenix Native.

## Terms

- Native app: the desktop application running as a single local process.
- Chatbot-first: the product interaction shape where the user performs data analysis primarily through conversation with Xenix, assisted by file drag-and-drop and artifact previews.
- Chatbot: the primary native interaction surface where the user converses with the LLM, drops files, sees messages, and previews artifacts. It is the key usability layer for non-technical data analysis.
- Agent Harness: the service under `src/xenix/services/agent/` that owns Thread, Turn, Message, tool-call, tool-result, provider interaction, tool execution, and run recording.
- System prompt: hidden instructions persisted as the first system Message in the first Turn. It is included in provider requests and hidden from the Chatbot timeline.
- Thread: a persisted conversation workspace owned by Agent Harness. A Thread stores title, turns, messages, provider request records, tool records, and artifact references.
- Turn: a bounded group of messages that starts with one user message and ends when the provider response contains zero tool calls. Empty assistant text with zero tool calls is a valid turn ending.
- Message: the atomic conversation record shared by UI rendering and Agent Harness semantics.
- Provider request: one Agent Harness call to an LLM provider. It records the persisted input Messages, output Messages created from the provider response, provider kind, lifecycle status, and token usage when the provider reports it.
- Tool call: a persisted Agent Harness record for a single LLM-requested function call against a registered Xenix tool.
- Tool result: a structured record produced after Agent Harness executes a service-backed tool call.
- Artifact: a service-registered local output such as a dataset, model, metrics report, image, or model apply output, usually surfaced through an `artifact://...` link.
- Artifact link: a markdown link whose target uses the `artifact://<artifact_id>` scheme so Chatbot can resolve and preview service-owned outputs.
- Dataset registration: a metadata pointer to a user-managed source dataset.
- Model: a reusable analyzer, not only a supervised estimator. It is a service-owned artifact that can be trained from declared input roles and later applied to compatible input roles.
- Trained model: a canonical reusable analyzer artifact tracked by metadata and stored on the filesystem.
- Model family: the product taxonomy for a reusable analyzer, such as supervised, clustering, anomaly detection, association rules, or recommendation.
- Model task kind: the operational contract for what a reusable analyzer does when applied, such as predictor, segmenter, anomaly scorer, rule miner, or recommender.
- ML workload: a service-backed model operation such as training, hyperparameter tuning, follow-up evaluation, or model apply.
- ML worker pool: the local service-owned set of configured execution workers that can run ML workloads. Worker selection is an internal placement decision, not a user-facing Agent tool argument.
- Local ML worker: the built-in worker that runs ML tasks on the user's machine.
- Remote SSH worker: a configured SSH execution worker managed by Xenix setup guidance. It provides remote compute and cache space but is not a remote backend or artifact authority.
- Remote execution/cache state: files staged on a remote SSH worker for task execution, environment reuse, or transfer efficiency. This state can be recreated or cleaned and does not replace local metadata or local artifacts.
- Legacy work item: the previous persisted unit of ML work and selection state, removed from the target AI-first service topology.
