# Artifact Link Contract

## Purpose

Define the cross-unit result presentation contract for Chatbot-first analysis. Agent Harness tools and services produce local files and metadata; Chatbot presents those results through markdown links and previews.

## URI Shape

Artifact links use this form:

```text
artifact://<artifact_id>
```

Dataset activation links use this form:

```text
dataset://<dataset_id>
```

Artifact links may include legacy `view` query hints, but Chatbot normalizes them out for rendered markdown links. Current artifact behavior is preview/open based on artifact kind and MIME type. Dataset links activate the registered dataset's default user-openable view; current behavior lazily materializes a workbook export artifact and delegates opening to `ArtifactService`.

Examples:

```markdown
[Cleaned dataset](dataset://954b713407184267a9444a79e5150779)
[Model apply results](artifact://ab9c1f9e0d2a4f4ba80d6cf7c143a809)
![Amount distribution](artifact://f1d8d11c74d64ff8a62a600de64c940e)
```

Markdown image syntax is the contract for inline image artifact previews. The image target still uses `artifact://...`; Chatbot resolves it through `ArtifactService` as a markdown image resource before loading the local file. The rendered image is wrapped in an ordinary artifact link, so clicking it opens the same artifact file. Ordinary markdown artifact links and bare `artifact://...` text do not become inline image previews.

## Ownership

- `LinkRouter` owns user link activation. Chatbot passes activated URIs to `LinkRouter`; UI does not resolve service-owned links or open local paths directly.
- UI surfaces may run `LinkRouter` activation on a background worker when activation can materialize files or call the OS. While activation is pending, the UI may show an indeterminate non-modal progress surface, but it must not block main-window interaction or take over artifact or dataset path resolution.
- `ArtifactService` registers artifacts, resolves `artifact://...` URIs, validates artifact readiness/file existence, and opens artifact files through the OS.
- `DatasetExportService` owns `dataset://...` activation. It resolves the dataset, materializes or reuses a workbook export artifact lazily, then delegates opening to `ArtifactService`.
- Artifact rows store the local absolute path, title, kind, MIME type, preview payload, metadata payload, readiness, and optional Thread/Turn/Message/ToolCall ownership ids.
- Agent Harness tool payloads return `dataset_id` and `dataset_uri` when they create registered datasets. `dataset_id` is a tool/input identity; `dataset_uri` is the user-openable activation link.
- Agent Harness tool payloads return `artifact_id` when they create or expose already materialized user-openable outputs. The Thread system prompt tells the model to reference only artifact ids with `artifact://...` markdown links and to use dataset URIs for datasets.
- Chatbot intercepts service-owned links and asks `LinkRouter` to activate them. Inline image preview resource loading may still resolve image artifacts through `ArtifactService` without opening the file.
- Chatbot renders image artifacts inline only when markdown uses image syntax such as `![alt](artifact://<artifact_id>)`, and only in normal message markdown. Tool detail markdown downgrades image syntax to a plain artifact link.
- File paths remain service-owned implementation details.
- Remote SSH worker paths are never artifact-link authorities. Remote outputs must be downloaded into local service-managed paths and registered through `ArtifactService` before Chatbot can link or preview them.

## Result Flow

```text
Tool handler
  -> service operation creates a registered dataset
  -> tool result payload stores dataset_id and dataset_uri
  -> provider-facing tool result JSON exposes dataset_uri
  -> assistant Message may use [label](dataset://<dataset_id>)
  -> Chatbot renders assistant markdown
  -> user activates dataset:// link
  -> Chatbot/UI asks LinkRouter to activate the URI
  -> UI may run LinkRouter activation in a background worker and show pending progress
  -> LinkRouter activates DatasetExportService
  -> DatasetExportService materializes/reuses workbook export artifact
  -> ArtifactService opens the export artifact
  -> UI closes pending progress after activation succeeds or fails
```

```text
Tool handler
  -> service operation produces a local user-openable artifact
  -> ArtifactService.register_artifact(...)
  -> tool result payload stores artifact_id
  -> provider-facing tool result JSON exposes artifact_id
  -> assistant Message may use [label](artifact://<artifact_id>) or ![alt](artifact://<artifact_id>)
  -> Chatbot renders assistant markdown
  -> user activates artifact:// link
  -> LinkRouter activates ArtifactService
  -> ArtifactService opens the artifact
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
- Dataset links carry dataset identity and activate the dataset's default user-openable export.
- Local paths are opened through service boundaries, not by Chatbot/UI.
- Tool result payloads include `dataset_uri` when a tool produces a registered dataset.
- Tool result payloads include `artifact_id` when a tool produces an already materialized user-facing artifact.
- `artifact://` is artifact-id authority only. It must not fall back to dataset lookup.
- `dataset://` is dataset-id authority only. Dataset activation may create/reuse an export artifact internally.
- Tool result payloads must not expose `ssh:` URLs or remote filesystem paths as result links.
- A missing artifact row is a service error with a user-actionable message.
- A missing file behind a valid artifact row is rendered as an unavailable artifact state.
