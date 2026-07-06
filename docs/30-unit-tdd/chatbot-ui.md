# Chatbot UI Unit TDD

## Purpose

Preserve the local invariants for the Chatbot-first Qt UI. This document governs `src/xenix/ui/main_window.py`, `src/xenix/ui/chatbot.py`, and nearby widgets that render conversation, files, tool progress, artifact links, and settings.

## Shell Contract

MainWindow hosts:

- left History sidebar with thread selection, create, rename, and delete actions
- central `ThreadDetailView` as the selected thread detail surface
- Settings entry for provider configuration and development AIMock controls
- Settings entry for ML worker pool summary and SSH worker setup

The central thread detail view stretches to consume remaining horizontal space. Message list and composer width come from the thread detail view parent.

## ThreadDetailView Contract

`ThreadDetailView` owns the selected thread's:

- EventList scroll area
- EventList column with 20 px horizontal padding
- composer
- attachment chips
- file drag hover overlay scoped to the full composer shell
- event-level in-progress rendering while Agent Harness is running
- stop control while provider or tool execution is running
- step-budget confirmation controls

The ThreadDetailView EventList renders projected Chatbot Events emitted by Agent Harness. System messages are hidden from the normal EventList unless Agent Harness exposes a dedicated control event.
Transient thinking state is a ThreadDetailView projection of Chatbot activity semantics. Agent Harness may emit Chatbot-domain `ACTIVITY` events to say the assistant turn is still advancing without exposing provider-loop internals, but it does not command thinking widget lifetime. ThreadDetailView reduces `ACTIVITY` plus subsequent visible text, tool, connection, usage, snapshot, and error events into local transient indicator state.

## Event Rendering

- User text events are right-aligned, at least about 60% of the EventList column width, and capped at about 80%.
- Assistant text events use the remaining readable width of the EventList column.
- Tool events render at full EventList column width as one compact row with tool-type icon, Harness-provided summary text, and chevron when result detail is available.
- A tool-call request without a result renders as a pending tool event.
- A paired tool-call request and result renders as one final tool event.
- Event height is determined by content.
- Sender names are hidden for user and assistant text events.
- Text event content is rendered from content blocks such as text, markdown, file attachment, and thinking.
- Tool event summary, status wording, icon key, and result detail come from Agent Harness projection.
- Tool event result detail stays collapsed until the user opens it with the chevron; image previews inside tool detail do not auto-expand the item.
- Tool event actions such as opening Tool Call Details come from Agent Harness projection; Tool Call Item renders those actions and emits UI signals without parsing tool result payloads. Tool Call Item does not expose per-task cancellation; active run cancellation is owned by the Composer stop control.
- Tool icons and chevrons use QtAwesome icons resolved in the Qt UI layer. The UI maps semantic `icon_key` values to concrete icon names; tool definitions and Harness projection do not depend on QtAwesome names.
- Artifact links inside markdown emit `artifact_link_activated` and are resolved by services.
- Markdown image artifact links using `![alt](artifact://<artifact_id>)` render inline inside normal message markdown. Chatbot renders them as linked images, resolves the `artifact://...` image resource through `ArtifactService`, and clicking the image opens the same artifact file. Ordinary markdown artifact links remain clickable/openable and do not become image previews. Tool detail markdown downgrades image syntax to an ordinary artifact link instead of rendering inline images.
- Tool Call Detail View is a standalone task-scoped window opened from a Tool Call Item. It may query service-owned ML task details, logs, and artifacts for the explicit task ids attached to task-producing tool calls. It is not a global ML task list. `model.task.query` Tool Call Items do not expose this action because their result is already the task detail surface.

## Styling Contract

Prefer native Qt Widgets styling unless the component needs an explicit product surface. When custom styling is needed, style the whole visual component rather than one isolated property. A message bubble, editor, list row, chip, or tool item includes its outer frame, layout container, text widget, viewport, document/editor area, icon labels, action buttons, and relevant interaction states.

Do not customize only foreground text, icon color, or one palette role while leaving the corresponding background, viewport, selection, disabled, focus, hover, link, and visited-link roles to platform defaults. Partial styling can leak native theme colors across nested Qt widgets, especially through `QAbstractScrollArea.viewport()` and text-document `Base` roles. Either keep the component native, or define the complete foreground/background contract for every child that participates in the same visual unit.

User text message bubbles own their black background as one custom-painted visual unit. Do not render the user-message black bubble through native `QFrame.StyledPanel`, `QTextBrowser`, or another `QAbstractScrollArea` stack; those layers can repaint independent platform backgrounds on Windows. User message rich text may use `QTextDocument` for layout, but the bubble background is painted by the user-message surface itself.

## Composer Contract

- The textarea defaults to one visual line.
- Enter submits the message.
- Shift+Enter inserts a newline.
- The textarea auto-grows up to its configured maximum line count.
- The composer stays in two rows: textarea row, then bottom controls row.
- The bottom controls row contains attach, flexible empty space, per-thread model picker, and send/stop.
- The model picker uses the same control height as attach and send/stop.
- The model picker shows LLM Service `fq_model_key` options and changes the selected thread's next-turn model only.
- Changing the model picker during a running turn must not change the provider already locked for that turn.
- ML worker setup belongs in Settings, not in Agent tool messages or Composer controls. The setup wizard may show connection, environment setup, and validation state, but Chatbot tools do not expose worker selection.
- Dragging local files over any child of the composer shell keeps the hover overlay visible.
- Attached dataset files are preflighted before send. Attachment chips show pending, ready, or failed state and expose removal. Pending or failed attachments block send; removing a pending attachment aborts its preflight logically and removing an unsent registered attachment discards the unreferenced dataset record.

## Streaming Contract

During a running turn:

- user message appears immediately
- when attachments are present, the user message appears only after all attached datasets are ready; pending or failed attachments remain in the Composer
- send button becomes stop
- non-final snapshots initialize or resume the running turn without releasing the composer
- Chatbot Events create, update, or finalize visible EventList items by event id
- assistant streaming updates one persisted assistant Message and one projected assistant text event; no provider-delta UI event or temporary assistant bubble is part of the Chatbot contract
- streamed provider tool-call argument deltas are progress-only and do not render raw JSON as assistant content
- Chatbot `ACTIVITY` events are UI-domain progress facts; ThreadDetailView projects them into a temporary thinking indicator until visible assistant text, tool progress, connection progress, final snapshot, cancellation, or error state supersedes them
- LLM retry connection events use a dedicated connection retry item. The item may look close to a tool call row, but it is not backed by tool-call state and disappears when a completed connection event reports recovery.
- tool-call events appear as soon as their request Message is created, and result Messages update the same logical tool event
- final snapshot replaces incremental state with the authoritative persisted timeline and releases the running state
- EventList follows the latest visible item only while the user is already at or near the bottom
- when the user scrolls away from the bottom during streaming, new EventList items and updates preserve the user's scroll position
- when the user is away from the bottom and more content exists below, EventList exposes a bottom-center floating icon button that scrolls back to the latest item and re-enables follow behavior

## Test Obligations

Qt boundary tests describe stable behavior themes, not a requirement to add a narrow regression test for each UI defect. Prefer folding coverage into golden, integrated, E2E, or existing boundary tests when a bug exposes a durable invariant. Avoid tests for incidental palette values, widget internals, or platform-specific rendering details unless those details are the documented component contract.

Qt boundary coverage should protect:

- new thread creation from History
- history selection, rename, and delete
- user text event rendering
- assistant text event rendering and update by event id
- request-only tool event rendering
- paired tool-call and tool-result rendering as one item
- tool event expand/collapse behavior
- Tool Call Item action rendering and signal propagation for task details
- Tool Call Detail View task refresh, log display, artifact opening, and timer shutdown
- artifact link activation and resolution
- inline image artifact resource rendering
- ML worker setup wizard validation states, language switching, and credential-boundary UI
- composer auto-grow layout switch
- Enter submit and Shift+Enter newline
- file drag hover overlay across the composer shell and textarea
- Chatbot Event create/update/finalize behavior for assistant streaming
- tool-call and tool-result Chatbot Events during open turns
- stop control propagation to Agent Harness
