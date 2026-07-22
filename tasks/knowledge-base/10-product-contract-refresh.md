# Product Contract Refresh — reconciled 2026-07-22

## Outcome

One global Knowledge Library helps a non-technical user apply their own business
definitions, operating rules, and experience while an Agent performs data-mining
work. Internal identities retain a `library_id` seam for future multiple libraries;
MVP exposes no Libraries management UI.

## MVP Promise

- Inputs: TXT, DOCX, DOC, PDF, JPEG, and PNG.
- Content IR: DoclingDocument JSON, wrapped by a Xenix-owned lifecycle envelope.
- Legacy DOC: normalize to DOCX through a separately probed LibreOffice capability;
  never pretend Docling natively parses it. The repeatable PDF-vs-DOCX spike selected
  DOCX for picture retention while preserving body/table recall.
- OCR: local PaddleOCR models, installed and health-checked through a one-click private
  deployment flow. The OCR runtime may use an isolated Python 3.12/3.13 sidecar so the
  desktop remains compatible with Python 3.14.
- Retrieval: keyword is available once text derivation is ready; semantic/hybrid are
  real selectable modes when independent Embedding settings and a current vector
  generation are usable. Explicit unavailable modes fail honestly.
- Agent surface: one small `knowledge.lookup` Tool; Knowledge method is integrated
  into the three data Skills. Skill activation is guidance, not authorization.
- UI: Knowledge Workspace is a secondary window; Import Queue is modeless.

## Non-goals

Markdown, PPT/PPTX, VLM, multi-library UX, general knowledge graphs, elaborate audit
history, and recovery dashboards are outside MVP.

## Success Gate

The executable goal gate is one typical rule-plus-data Agent case prepared through
production Import→Canonical→Derivation and judged by its final answer plus exact
Dataset. Local implementation/delivery evidence is complete. Two live cells created
the exact Dataset and passed integrity but failed grounded final-answer wording, so
Phase B remains open for repair and rerun.
