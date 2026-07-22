# Knowledge UI Visual QA — 2026-07-22

## Scope

The Slice 02 UI adds a logical-document Workspace, a separate modeless durable Import
Queue with content-free logs, one Knowledge-owned Settings tab for Embedding/OCR/
indexes, and a window-modal manual index rebuild sheet. Document detail/open/remove
and multimodal visual retrieval remain explicit later work.

## Repeatable Method

Run:

```powershell
pdm run python tasks/knowledge-base/evidence/capture_knowledge_ui.py
```

The offscreen harness loads the Windows Microsoft YaHei font explicitly, constructs
the production widgets with isolated services/settings, and writes PNGs under
`build/knowledge-ui-qa/`:

- `workspace-en.png`
- `workspace-zh.png`
- `queue-en.png`
- `queue-zh.png`
- `import-log-en.png`
- `import-log-zh.png`
- `settings-knowledge-en.png`
- `settings-knowledge-zh.png`
- `rebuild-index-en.png`
- `rebuild-index-zh.png`

## Review Result

- English and Chinese Workspace headings, logical-document columns/states, supported
  formats, index status, and toolbar actions are readable without clipping.
- The modeless Queue presents service-owned status and actions in both languages; it
  does not expose raw paths or exception text. Its modeless log shows only translated
  lifecycle phases/events.
- Embedding, OCR, and index controls occupy the Knowledge Base tab rather than AI;
  the API key is masked.
- The rebuild sheet offers only keyword and text semantic vector projections, with a
  unit/request estimate. It does not advertise multimodal vectors or extraction/OCR.

The captures are build evidence rather than shipped assets; the script is the durable
source of reproduction.
