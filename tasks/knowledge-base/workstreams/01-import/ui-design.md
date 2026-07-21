# Import Service UI Design

## Product Shape

Knowledge Base is a **Secondary Window** opened by a Knowledge button immediately to
the left of the existing Settings button in the main window header. It is modeless,
singleton/reusable (`show`, `raise`, `activateWindow`), and does not turn the chat
shell into a new navigation framework.

MVP has one global Library, so the window has no library list, selector, create,
rename, enable/disable controls, or chat scope chooser. The UI calls a service that
resolves the hidden stable global-library ID. This preserves a future multi-library
storage extension without exposing complexity that users cannot act on yet.

The persistent import queue lives in its own **modeless Import Queue Dialog**, not a
workspace tab and not a modal `QProgressDialog`. The dialog owns presentation only;
the service owns every task and status.

```text
MainWindow header
  [ ... ] [Knowledge] [Settings]
                 │
                 ▼
      Knowledge Workspace (Secondary Window)
       ┌─────────────────────────────────────────────┐
       │ Global Knowledge Library       [Import files]│
       │                                             │
       │ Documents             Details               │
       │ invoice.pdf  Canonical-ready   [Open source] │
       │ field.jpg   Needs OCR text     [Inspect]     │
       │                                             │
       │ [Open Import Queue]                          │
       └─────────────────────────────────────────────┘
                 │
                 ▼
      Import Queue Dialog (modeless)
       [Add files…] [Refresh]
       preflight rows -> persistent queue rows -> status/actions
```

## Import Queue Dialog Flow

1. **Add files** opens the normal multi-file chooser with exactly the allowlisted
   TXT/DOC/DOCX/PDF/JPEG/PNG filter; its drop zone accepts only local URLs.
2. The dialog locally removes duplicate selections while preserving user order and
   asks `preflight_imports` in a background service call. It never creates a source
   snapshot/artifact during preflight.
3. Rows show detection/routing facts: type, size, selected text encoding or DOC
   conversion candidate, PDF page-route summary when available, same-content duplicate
   status, encrypted/password requirement, OCR profile availability, and warnings.
4. The user enqueues eligible rows. A same-SHA-256 row defaults to **Open existing
   document** rather than enter a duplicate queue. An encrypted file requests a
   password only at the necessary execution/retry point and never displays/stores it.
5. Persistent rows show service status/phase/attempt/update time and actions. The
   dialog can close or be reopened without affecting imports.

The selection/preflight section can be a transient upper area of this same dialog;
do not multiply dialogs merely to show a queue. It is transparent routing feedback,
not a data-sharing consent prompt.

## Workspace and Queue States

| Service condition | Workspace/queue treatment | Permitted action |
| --- | --- | --- |
| No documents | Empty global-library state with Import files call to action | Open queue/add files |
| Preflight checking | Per-row spinner; no false aggregate percentage | Remove/cancel selection |
| Unsupported/Markdown/spoofed/unreadable | Per-row safe rejection reason | Remove/select another source |
| Duplicate SHA-256 | Existing document card + no duplicate enqueue by default | Open existing; future explicit revision is deferred |
| Queued/running | Actual phase and optional page count | Cancel |
| Needs attention | Password / Office converter reason and repair action | Enter transient password / configure capability / retry |
| Canonical-ready with warnings | Explicit IR/OCR/loss-note badge | Inspect details/open source; later re-enrich |
| Failed | Error code, translated summary, retryability, repair hint | Retry only when retryable |
| Cancel requested/cancelled | Clear lifecycle state | Retry creates a new attempt |

`ImportStatusView` is the sole durable-state projection: IDs, display name, source
type, canonical-generation ID if present, status, phase, attempt number, truthful
units, timestamps, capability label, safe error code/message, retryability, and
repair hint. UI does not derive a state from worker callbacks alone.

## Details, Source Opening, and Errors

The workspace document/detail view shows bounded information only: original source
artifact identity, canonical-ready state, Docling/parser/normalizer/OCR descriptor,
page/section or image locator, warnings, and attempts. It must not render arbitrary
raw provider payloads or the entire source document by default. **Open source** uses
`artifact://<id>` through LinkRouter; no widget assembles or receives an absolute
path. Preview assets must similarly be served through bounded service DTOs/artifact
identity.

All labels are translated through Qt and react to `LanguageChange`, including the new
Knowledge header button, workspace, queue phase/error text, and password guidance.

## Background and Window Lifetime Rules

- `KnowledgeImportService` owns work; it emits immutable DTOs through queued Qt
  signals. A 250–500 ms durable-status poll is a recovery/reopen fallback.
- Closing either secondary window stops its timers/observers only. It never cancels
  an import. Reopening refreshes durable status.
- Workers never touch widgets. The UI never claims a remote Paddle request is stopped
  before the runner records a safe cancellation boundary.
- Percentages appear only for trustworthy units (for example processed PDF pages);
  opaque remote calls show a phase/spinner.
- Settings remains the future location for document-AI configuration, but MVP does
  not add VLM setup. The queue can hand off an unavailable OCR/converter profile to
  Settings without embedding configuration in the import dialog.

## Existing Qt Surface and Verification Plan

The minimum-risk integration is a single header button left of `_settings_button`, a
cached secondary `KnowledgeWorkspace`, and a cached/one-at-a-time modeless
`KnowledgeImportQueueDialog`. It preserves the current history/chat layout and avoids
a `QStackedWidget` rewrite or a SettingsDialog navigation redesign.

Future UI tests must cover: header ordering and existing Settings behavior; singleton
window reuse; allowed-type chooser/drop and rejection; deterministic preflight/dedup;
per-page/route summaries; transient password behavior; durable queue refresh after
close/reopen; no false percent; cancel/retry; `artifact://` opening/no raw paths;
and English/Simplified-Chinese `LanguageChange` coverage.
