# Product Scope

## Purpose

Record which product concepts remain in the native edition and which are intentionally removed.

## Retained Concepts

- Simple and easy to use for teachers, students.
- Single local operator
- Guided scenario-first home shell with localized scenario templates
- Local dataset selection and drag-and-drop import
- Scenario data preparation with checkbox-group input and target selection
- Fixed template-driven training plans with best-model tracking
- Scenario-first guided workflows as the primary operator path
- Inference against local data or manually entered values
- Prediction history review with result-file opening and export
- Local result viewing and export
- Local runtime logs and metadata

## Removed Concepts

- Multi-user accounts and roles
- Remote ML backend deployment
- Browser-first routing or API boundary concerns from the web app
- Server-managed tenancy, sessions, and permissions
- Always-on online access assumptions

## Design Implications

- The native app can optimize for one desktop session instead of concurrent users.
- Authentication and authorization are out of scope unless a future issue reintroduces them with an ADR.
- "Backend" logic in the native app means local services, not a network service.
- The default operator path can hide project management details behind guided scenario surfaces.
- Technical workspaces may remain in code as supporting or future surfaces, but they are not part of the current primary operator path unless explicitly exposed.
- Scenario mode may use application-managed local containers while continuing to rely on the shared service and storage layers.
- Prediction outputs must remain reviewable, openable, and exportable after the original prediction dialog closes.
- Operations guidance focuses on local runtime recovery and packaging, not cloud deployment.
