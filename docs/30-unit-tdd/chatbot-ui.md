# Chatbot UI Unit TDD

## Purpose

Preserve the local invariants for the Chatbot-first Qt UI. This document governs `src/xenix/ui/main_window.py`, `src/xenix/ui/chatbot.py`, and nearby widgets that render conversation, files, tool progress, artifact links, and settings.

## Shell Contract

MainWindow hosts:

- left History sidebar with thread selection, create, rename, and delete actions
- central `ThreadDetailView` as the selected thread detail surface
- Settings entry for provider configuration and development AIMock controls

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
Transient thinking state is also driven by Chatbot Events: `THINKING` with `IN_PROGRESS` inserts or updates the temporary thinking item, while a terminal `THINKING` event with the same id removes it. Thinking represents the interval from provider request send to the first provider stream event. MainWindow and ThreadDetailView must not infer thinking lifetime from snapshots or assistant message arrival.

## Event Rendering

- User text events are right-aligned and capped at about 60% of the EventList column width.
- Assistant text events use the remaining readable width of the EventList column.
- Tool events render at full EventList column width as one compact row with tool-type icon, Harness-provided summary text, and chevron when result detail is available.
- A tool-call request without a result renders as a pending tool event.
- A paired tool-call request and result renders as one final tool event.
- Event height is determined by content.
- Sender names are hidden for user and assistant text events.
- Text event content is rendered from content blocks such as text, markdown, file attachment, and thinking.
- Tool event summary, status wording, icon key, and result detail come from Agent Harness projection.
- Tool icons and chevrons use QtAwesome icons resolved in the Qt UI layer. The UI maps semantic `icon_key` values to concrete icon names; tool definitions and Harness projection do not depend on QtAwesome names.
- Artifact links inside markdown emit `artifact_link_activated` and are resolved by services.

## Composer Contract

- The textarea defaults to one visual line.
- Enter submits the message.
- Shift+Enter inserts a newline.
- The textarea auto-grows up to its configured maximum line count.
- The compact layout is attach button, textarea, send button in one row.
- When text wraps beyond one visual line, the layout switches to textarea row plus bottom controls row.
- The attach button and send button remain aligned with the textarea baseline in compact mode.
- Dragging local files over any child of the composer shell keeps the hover overlay visible.

## Streaming Contract

During a running turn:

- user message appears immediately
- send button becomes stop
- non-final snapshots initialize or resume the running turn without releasing the composer
- Chatbot Events create, update, or finalize visible EventList items by event id
- assistant streaming updates one persisted assistant Message and one projected assistant text event; no provider-delta UI event or temporary assistant bubble is part of the Chatbot contract
- tool-call events appear as soon as their request Message is created, and result Messages update the same logical tool event
- final snapshot replaces incremental state with the authoritative persisted timeline and releases the running state
- EventList scrolls to the latest visible item

## Test Obligations

Qt boundary tests should cover:

- new thread creation from History
- history selection, rename, and delete
- user text event rendering
- assistant text event rendering and update by event id
- request-only tool event rendering
- paired tool-call and tool-result rendering as one item
- tool event expand/collapse behavior
- artifact link activation and resolution
- composer auto-grow layout switch
- Enter submit and Shift+Enter newline
- file drag hover overlay across the composer shell and textarea
- Chatbot Event create/update/finalize behavior for assistant streaming
- tool-call and tool-result Chatbot Events during open turns
- stop control propagation to Agent Harness
