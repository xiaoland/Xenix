# Product Scope

## Purpose

Record which product concepts remain in the native edition and which are intentionally removed.

## Retained Concepts

- Simple and easy to use for teachers, students.
- Single local operator
- Chatbot-first native experience
- Chatbot as the main surface that lets non-technical users complete data analysis through conversation
- Conversation plus file drag-and-drop as the primary operator path
- Local dataset intake from user-selected CSV/XLSX files
- Agent Harness service exposing Xenix data and model capabilities as LLM tools
- Basic data analysis from data intake through reusable model application
- Basic data cleaning as an LLM-driven capability that produces derived datasets
- Read-only dataset querying as an LLM-driven capability for inspection, validation, and analysis summaries
- Common descriptive dataset profiling as an LLM-driven analysis capability that returns bounded Markdown evidence without creating an artifact by default
- Dataset-scoped chart generation as an LLM-driven analysis capability that produces image artifacts
- One-off Agent-authored analysis functions as an LLM-driven capability for custom business analysis over registered datasets
- Dataset transformation as an LLM-driven capability that produces derived datasets from registered inputs
- Models as reusable analyzers, not only supervised estimators
- Model training, evaluation where applicable, and apply operations through service-backed tool calls
- Association-rule mining and item-similarity recommendation as reusable analyzer families available through the model lifecycle
- Artifact-backed result viewing inside Chatbot messages
- Local artifacts for datasets, models, metrics, reports, and model apply outputs
- Configurable ML worker pool for local and SSH-backed remote execution, where remote workers are execution/cache locations and not product data authorities
- Local runtime logs and metadata
- Settings as the supporting entry for multi-provider LLM configuration, model lists, global default model, and development mock configuration

## Removed Concepts

- Multi-user accounts and roles
- Remote ML backend deployment
- Browser-first routing or API boundary concerns from the web app
- Server-managed tenancy, sessions, and permissions
- Always-on online access assumptions
- Predefined workflow screens as the product operator path
- Work item as the target workspace owner

## Design Implications

- The native app can optimize for one desktop session instead of concurrent users.
- Authentication and authorization are out of scope unless a future issue reintroduces them with an ADR.
- "Backend" logic in the native app means same-process local services.
- Remote ML workers are not a remote backend deployment. The native app remains the task lifecycle, metadata, and artifact authority while SSH workers provide execution capacity.
- The default operator path is a persisted Chatbot thread inside a Chatbot-first shell.
- Chatbot owns the user-facing conversation, file drop intake, message timeline, and result preview path.
- Chatbot lets the user switch the selected LLM model per thread; the selection applies to the next turn and does not mutate the global default model.
- Agent Harness owns Thread, Turn, Message, tool-call, and tool-result semantics.
- The LLM receives atomic tools and keeps planning freedom inside service and tool constraints.
- Storage provides persistence interfaces for service-owned records.
- Model apply outputs must remain reviewable through artifact links after the originating turn closes.
- Agent tools express ML workload intent only. Worker selection is an internal service decision and is not exposed as a tool argument.
- First-slice working context is represented by Thread messages, tool-call records, tool-result records, and artifact metadata.
- Data cleaning tools operate on registered datasets and create new derived datasets when cleaning operations are applied; source datasets remain intact.
- Query tools read registered datasets and return bounded results without creating dataset artifacts by default.
- Analysis profiling tools read registered datasets and return bounded descriptive statistics directly in the tool result without creating artifacts by default.
- Analysis graph tools read registered datasets and produce service-managed image artifacts from Vega-Lite chart specifications.
- Analysis lambda tools run one-off Python analysis functions over registered datasets in a local subprocess, return any JSON-serializable dictionary through `result.output`, and may create service-managed artifacts through a constrained artifact API.
- Transform tools operate on registered datasets and create new derived datasets; source datasets remain intact.
- Project is retained only as a storage compatibility detail while the AI-first product model centers on Chatbot threads, datasets, artifacts, and dataset lineage.
- Operations guidance focuses on local runtime recovery and packaging, not cloud deployment.
