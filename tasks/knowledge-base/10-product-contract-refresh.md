# Product Contract Refresh — reconciled 2026-07-22

## Outcome

One global Knowledge Library helps a non-technical user apply their own business
definitions, operating rules, and experience while an Agent performs data-mining
work. Internal identities retain a `library_id` seam for future multiple libraries;
MVP exposes no Libraries management UI.

## MVP Promise

- Inputs: TXT, DOCX, DOC, PPTX, PPT, PDF, JPEG, and PNG.
- Content IR: DoclingDocument JSON, wrapped by a Xenix-owned lifecycle envelope.
- Legacy DOC: normalize to DOCX through a separately probed LibreOffice capability;
  never pretend Docling natively parses it. The repeatable PDF-vs-DOCX spike selected
  DOCX for picture retention while preserving body/table recall.
- Presentations: parse PPTX directly through Docling; normalize legacy PPT to PPTX
  through the same explicitly probed, bounded LibreOffice capability class while
  retaining original-source provenance.
- OCR: an optional Xenix-owned native worker built on official Paddle Inference C++
  plus explicit model assets, installed and verified from one immutable archive.
  No runtime Python, pip, or global model cache is involved.
- Retrieval: keyword is available once text derivation is ready; semantic/hybrid are
  real selectable modes when independent Embedding settings and a current vector
  generation are usable. Explicit unavailable modes fail honestly.
- Agent surface: one small `knowledge.lookup` Tool; Knowledge method is integrated
  into the three data Skills. Skill activation is guidance, not authorization.
- UI: Knowledge Workspace is a secondary window; its `Task queue` is modeless;
  file picker and Workspace drag/drop feed the same import submission operation.

## Non-goals

Markdown, VLM, multi-library UX, general knowledge graphs, elaborate audit
history, and recovery dashboards are outside MVP.

## Success Gate

The executable goal gate is one typical rule-plus-data Agent case prepared through
production Import→Canonical→Derivation and judged by its final answer plus exact
Dataset. Local implementation/delivery evidence is complete. Two live cells created
the exact Dataset and passed integrity but failed grounded final-answer wording, so
Phase B remains open for repair and rerun.
