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
- Dataset transformation as an LLM-driven capability that produces derived datasets from registered inputs
- Models as reusable analyzers, not only supervised estimators
- Model training, evaluation where applicable, and apply operations through service-backed tool calls
- Artifact-backed result viewing inside Chatbot messages
- Local artifacts for datasets, models, metrics, reports, and model apply outputs
- Local runtime logs and metadata
- Settings as the supporting entry for LLM provider and development mock configuration

## Removed Concepts

- Multi-user accounts and roles
- Remote ML backend deployment
- Browser-first routing or API boundary concerns from the web app
- Server-managed tenancy, sessions, and permissions
- Always-on online access assumptions
- Scenario-first screens as the product operator path
- Work item as the target workspace owner

## Design Implications

- The native app can optimize for one desktop session instead of concurrent users.
- Authentication and authorization are out of scope unless a future issue reintroduces them with an ADR.
- "Backend" logic in the native app means same-process local services.
- The default operator path is a persisted Chatbot thread inside a Chatbot-first shell.
- Chatbot owns the user-facing conversation, file drop intake, message timeline, and result preview path.
- Agent Harness owns Thread, Turn, Message, tool-call, and tool-result semantics.
- The LLM receives atomic tools and keeps planning freedom inside service and tool constraints.
- Storage provides persistence interfaces for service-owned records.
- Model apply outputs must remain reviewable through artifact links after the originating turn closes.
- First-slice working context is represented by Thread messages, tool-call records, tool-result records, and artifact metadata.
- Data cleaning tools operate on registered datasets and create new derived datasets; source datasets remain intact.
- Query tools read registered datasets and return bounded results without creating dataset artifacts by default.
- Transform tools operate on registered datasets and create new derived datasets; source datasets remain intact.
- Project is retained only as a storage compatibility detail while the AI-first product model centers on Chatbot threads, datasets, artifacts, and dataset lineage.
- Operations guidance focuses on local runtime recovery and packaging, not cloud deployment.
