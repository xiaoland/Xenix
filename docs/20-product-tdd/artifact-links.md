# Artifact Link Contract

## Purpose

Define the cross-unit result presentation contract for Chatbot-first analysis. Agent Harness tools and services produce local files and metadata; Chatbot presents those results through markdown links and previews.

## URI Shape

Artifact links use this form:

```text
artifact://<artifact_id>
```

Artifact links may include legacy `view` query hints, but Chatbot normalizes them out for rendered markdown links. Current default behavior is preview/open based on artifact kind and MIME type.

Examples:

```markdown
[Cleaned dataset](artifact://954b713407184267a9444a79e5150779)
[Model apply results](artifact://ab9c1f9e0d2a4f4ba80d6cf7c143a809)
![Amount distribution](artifact://f1d8d11c74d64ff8a62a600de64c940e)
```

Markdown image syntax is the contract for inline image artifact previews. The image target still uses `artifact://...`; Chatbot resolves it through `ArtifactService` as a markdown image resource before loading the local file. The rendered image is wrapped in an ordinary artifact link, so clicking it opens the same artifact file. Ordinary markdown artifact links and bare `artifact://...` text do not become inline image previews.

## Ownership

- `ArtifactService` registers artifacts and resolves `artifact://...` URIs.
- Artifact rows store the local absolute path, title, kind, MIME type, preview payload, metadata payload, readiness, and optional Thread/Turn/Message/ToolCall ownership ids.
- Agent Harness tool payloads return `artifact_id` when they create or expose user-openable outputs. The Thread system prompt tells the model how to reference those ids with `artifact://...` markdown links.
- Chatbot intercepts artifact links and asks services to resolve them before opening files or rendering previews.
- Chatbot renders image artifacts inline only when markdown uses image syntax such as `![alt](artifact://<artifact_id>)`, and only in normal message markdown. Tool detail markdown downgrades image syntax to a plain artifact link.
- File paths remain service-owned implementation details.
- Remote SSH worker paths are never artifact-link authorities. Remote outputs must be downloaded into local service-managed paths and registered through `ArtifactService` before Chatbot can link or preview them.

## Result Flow

```text
Tool handler
  -> service operation produces or references a local artifact
  -> ArtifactService.register_artifact(...)
  -> tool result payload stores artifact_id
  -> provider-facing tool result JSON exposes the artifact_id
  -> assistant Message may use [label](artifact://<artifact_id>) or ![alt](artifact://<artifact_id>)
  -> Chatbot renders assistant markdown
  -> user activates artifact:// link
  -> ArtifactService.resolve_uri(...)
  -> Chatbot opens or previews the resolved artifact
```

## View Hints

`view` is a legacy rendering hint. Supported hints can grow over time as Chatbot gains richer renderers, but message markdown should not require them.

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
- Tool result payloads must not expose `ssh:` URLs or remote filesystem paths as result links.
- A missing artifact row is a service error with a user-actionable message.
- A missing file behind a valid artifact row is rendered as an unavailable artifact state.
