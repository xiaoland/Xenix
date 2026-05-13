# Product Scope

## Purpose

Record which product concepts remain in the native edition and which are intentionally removed.

## Retained Concepts

- Simple and easy to use for teachers, students.
- Single local operator
- ChatBox-first native shell
- Conversation plus file drag-and-drop as the primary operator path
- Local dataset intake from user-selected CSV/XLSX files
- Agent Harness service exposing Xenix data and model capabilities as LLM tools
- Model training, evaluation, and inference through service-backed tool calls
- Artifact-backed result viewing inside ChatBox
- Local artifacts for datasets, models, metrics, reports, and predictions
- Local runtime logs and metadata

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
- "Backend" logic in the native app means local services, not a network service.
- The default operator path is a persisted ChatBox thread.
- Agent Harness owns Thread, Turn, Message, tool-call, and tool-result semantics.
- The LLM receives atomic tools and keeps planning freedom inside service and tool constraints.
- Storage provides persistence interfaces for service-owned records.
- Prediction outputs must remain reviewable through artifact links after the originating turn closes.
- Operations guidance focuses on local runtime recovery and packaging, not cloud deployment.
