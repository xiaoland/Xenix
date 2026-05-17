# Artifact Link Contract

## Purpose

Define the cross-unit result presentation contract for Chatbot-first analysis. Agent Harness tools and services produce local files and metadata; ChatBox presents those results through markdown links and previews.

## URI Shape

Artifact links use this form:

```text
artifact://<artifact_id>?view=<view>
```

Current default view is `preview`.

Examples:

```markdown
[Cleaned dataset](artifact://954b713407184267a9444a79e5150779?view=preview)
[Prediction results](artifact://ab9c1f9e0d2a4f4ba80d6cf7c143a809?view=preview)
```

## Ownership

- `ArtifactService` registers artifacts and resolves `artifact://...` URIs.
- Artifact rows store the local absolute path, title, kind, MIME type, preview payload, metadata payload, readiness, and optional Thread/Turn/Message/ToolCall ownership ids.
- Agent Harness tools return markdown summaries containing artifact links when they create or expose user-openable outputs.
- ChatBox intercepts artifact links and asks services to resolve them before opening files or rendering previews.
- File paths remain service-owned implementation details.

## Result Flow

```text
Tool handler
  -> service operation produces or references a local artifact
  -> ArtifactService.register_artifact(...)
  -> tool result payload stores artifact_id and artifact_link
  -> tool result Message stores markdown content
  -> ChatBox renders markdown
  -> user activates artifact:// link
  -> ArtifactService.resolve_uri(...)
  -> ChatBox opens or previews the resolved artifact
```

## View Hints

`view` is a rendering hint. Supported hints can grow over time as ChatBox gains richer renderers.

Current durable meanings:

- `preview`: choose the best available preview from artifact kind, MIME type, and preview payload.
- `table`: prefer tabular preview for CSV/XLSX-like outputs.
- `image`: prefer image preview.
- `report`: prefer text or markdown report preview.

Unknown views should fall back to a generic artifact chip or open action after successful resolution.

## Invariants

- Artifact links carry artifact identity and rendering preference.
- Local paths are resolved through `ArtifactService`.
- Tool result payloads include `artifact_id` when a tool produces a user-facing artifact.
- A missing artifact row is a service error with a user-actionable message.
- A missing file behind a valid artifact row is rendered as an unavailable artifact state.
