# Product Contract Refresh — 2026-07-21

## Outcome

One global Knowledge Library helps a non-technical user apply their own business
definitions, operating rules, and experience while an Agent performs data-mining
work. Internal identities retain a `library_id` seam for future multiple libraries;
MVP exposes no Libraries management UI.

## MVP Promise

- Inputs: TXT, DOCX, DOC, PPTX, PPT, and PDF.
- Content IR: DoclingDocument JSON, wrapped by a Xenix-owned lifecycle envelope.
- Legacy DOC/PPT: normalize through a separately probed conversion capability before
  Docling; never pretend Docling natively parses them.
- OCR: local PaddleOCR models, installed and health-checked through a one-click private
  deployment flow. The OCR runtime may use an isolated Python 3.12/3.13 sidecar so the
  desktop remains compatible with Python 3.14.
- Retrieval: keyword is always available once a document is ready; semantic/hybrid is
  an internal enhancement when embeddings are configured and ready.
- Agent surface: one small `knowledge.lookup` tool and one restrained methodology
  Skill. Skill activation is guidance, not user authorization.
- UI: Knowledge Workspace is a secondary window; Import Queue is modeless.

## Non-goals

Markdown, standalone JPEG/PNG import, VLM, multi-library UX, user-selectable retrieval
algorithms, general knowledge graphs, elaborate audit history, and recovery dashboards
are outside MVP.

## Success Gate

The executable goal gate is one typical rule-plus-data Agent case running through
production services. A second multi-document evidence case is retained only as a
future candidate; it does not count as passed or as part of this goal until a typed
recommendation result can support an objective oracle.
