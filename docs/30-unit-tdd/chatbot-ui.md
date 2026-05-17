# Chatbot UI Unit TDD

## Purpose

Preserve the local invariants for the Chatbot-first Qt UI. This document governs `src/xenix/ui/main_window.py`, `src/xenix/ui/chat_box.py`, and nearby widgets that render conversation, files, tool progress, artifact links, and settings.

## Shell Contract

MainWindow hosts:

- left History sidebar with thread selection, create, rename, and delete actions
- central `ThreadDetailView` as the ChatBox surface
- Settings entry for provider configuration and development AIMock controls

The central ChatBox stretches to consume remaining horizontal space. Message list and composer width come from the ChatBox parent.

## ThreadDetailView Contract

`ThreadDetailView` owns:

- message scroll area
- message column with 20 px horizontal padding
- composer
- attachment chips
- file drag hover overlay scoped to the full composer shell
- Thinking indicator while waiting for provider response
- stop control while provider or tool execution is running
- step-budget confirmation controls

Message list renders from `ThreadSnapshot.messages`. System messages are hidden from the normal timeline. Visible user messages after the first one receive a turn divider above them. The first user message starts the timeline directly.

## Message Rendering

- User messages are right-aligned and capped at about 60% of the message column width.
- Assistant messages use the remaining readable width of the message column.
- Tool-call and tool-result messages render as compact tool rows.
- Message height is determined by content.
- Sender names are hidden for user and assistant messages.
- Message content is rendered from content blocks such as text, markdown, file attachment, thinking, tool call, tool result, and step confirmation.
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
- Thinking indicator appears at the bottom while awaiting provider output
- assistant deltas stream into a temporary assistant bubble
- final snapshot replaces temporary streaming state with persisted messages
- message list scrolls to the latest visible item

## Test Obligations

Qt boundary tests should cover:

- new thread creation from History
- history selection, rename, and delete
- user message rendering with turn dividers only before later user messages
- tool-call and tool-result message rendering
- artifact link activation and resolution
- composer auto-grow layout switch
- Enter submit and Shift+Enter newline
- file drag hover overlay across the composer shell and textarea
- Thinking indicator and streaming assistant delta behavior
- stop control propagation to Agent Harness
