# Chatbot EventList Design Notes

## Discussion Log

### 2026-05-18

- User expects tool icons to map to tool type.
- Summary text should include failure state explicitly, for example `Failed to ...`; success should read as a normal statement of completed work.
- MessageList should likely become Chatbot EventList.
- Pairing should be solved by a clear contract, not layered fallback heuristics.
- A tool-call item should be visible even before its result message exists.
- User questions whether `AgentToolCallRow` belongs to Agent Harness and whether its name or exposure mixes UI semantics.
- User notes that "streaming incremental rendering" may be too broad a label; only assistant messages stream, while tool-call messages are one-shot events.
- User does not see a need for `ChatbotTurnDividerEvent`; turn-end divider behavior should not be part of the EventList target.
- User agrees Chatbot UI should consume Chatbot Events instead of storage rows.
- User suggests Agent Harness should own the Chatbot Event projection.
- User expects tool-call success/failure descriptive text to stay in Agent Harness, because that text can also be part of the LLM-facing tool result.
- User confirmed adding the explicit-contract-over-fallback principle to `AGENTS.md`.
- User recommends GammaRay for Qt Widgets debugging because it works like a browser DevTools DOM inspector.

## Current Design Bias

- Use one Agent Harness-owned Chatbot EventList projection for both full snapshots and incremental message application.
- Keep the special streaming behavior limited to assistant message content updates, but make the EventList upsert path uniform enough that UI code does not fork into separate streaming and non-streaming renderers.
- Do not promote turn dividers into the new event model.
- Chatbot UI should treat tool event summary, status wording, icon key, and result detail as projected event data.
- Chatbot UI may own visual chrome such as chevron behavior and expanded/collapsed state.
- Target-state planning is recorded in `slice-plan.md`.

## Implementation Progress

- 2026-05-18: Started execution after user approval.
- 2026-05-18: Slice 0 updated durable TDD target language in `docs/30-unit-tdd/agent-harness.md` and `docs/30-unit-tdd/chatbot-ui.md`.
- 2026-05-18: Added Agent Harness-owned `ChatbotEvent` projection in `src/xenix/services/agent/chatbot_events.py`.
- 2026-05-18: Added Harness stream event `chatbot_event` / `chatbot_events` fields and switched MainWindow to prefer them.
- 2026-05-18: Migrated Chatbot UI rendering to EventList input and added compact expandable `ToolCallItem`.
- 2026-05-18: Removed automatic turn divider insertion from the Chatbot rendering path.
- 2026-05-19: Tightened `ToolCallItem` UI: full EventList column width, Qt native arrow button for chevron, and wheel events ignored by auto-height message text so the outer scroll area owns scrolling.
- 2026-05-19: Added GammaRay guidance to root `AGENTS.md` for Qt Widgets hierarchy/layout/property debugging.
- 2026-05-19: GammaRay was not installed in the current environment, so widget hierarchy/layout was checked through Qt runtime inspection. The check found stale `maximumWidth` on `ToolCallItem` after resize; removing the cap made tool items match the EventList column width.
- 2026-05-19: Replaced Qt filled arrow chevron with a custom thin-line chevron icon drawn into a `QToolButton`.
- 2026-05-19: Investigated Qt icon sources before further chevron/tool-icon changes. Local runtime is Qt 6.10.2 with `windowsvista` style. `QStyle.StandardPixmap` is broadly available, but arrow pixmaps render as filled triangles. `QIcon.fromTheme("go-next")` and `QIcon.fromTheme("go-down")` render as thin line arrows in this environment and better match the requested near-`>` chevron aesthetic. Contact sheet saved at `tasks/chatbot-event-list/qt-icon-contact-sheet.png`.
- 2026-05-19: Added QtAwesome and moved tool presentation ownership into `AgentToolRegistry` / `AgentTool`. `src/xenix/ui/icons.py` now maps semantic `icon_key` values to QtAwesome icon names, while Harness projection consumes registry presentation data for summaries and semantic icon keys.

## AGENTS.md Candidate Principle

- Prefer solving ambiguity by making the underlying contract explicit. Avoid stacking fallback heuristics when a durable invariant or projection boundary can be defined instead.

Status: promoted into root `AGENTS.md` on 2026-05-18 after user confirmation.
