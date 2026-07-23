# Slice 03 Evidence — Legacy Unit and PPTX Diagnostic

**Run:** 2026-07-22
**Runtime:** user Xenix home at `%LOCALAPPDATA%\Xenix`
**Fixture:** `tests/.mock-data/2026半年度工作汇报（品牌营销）.pptx`

## Purpose and boundary

Sir authorized deleting only local Knowledge-specific data and retesting current Unit
derivation with the named PPTX. The file is a diagnostic fixture: PPTX remains outside
the current TXT, DOC/DOCX, PDF, JPEG, and PNG MVP import promise, so the experiment
uses Docling conversion plus the current derivation function without persisting a
new unsupported Knowledge document.

## Pre-reset evidence

SQLite contained:

| State | Count |
| --- | ---: |
| logical Knowledge documents | 1 |
| import attempts | 1 |
| index tasks | 1 |
| current Units / FTS rows | 116 / 116 |
| total Unit characters | 86,591,045 |
| maximum Unit characters | 4,271,960 |

The largest rows began with `![Image](data:image/png;base64,...)` and had picture
locators. They were embedded image bytes serialized as Markdown data URIs, not
meaningful text chunks. This establishes the historical failure mode directly.

## Authorized reset

The reset:

- deleted all rows from Knowledge import, canonical, document, derivation, Unit/FTS,
  index-task, and vector-generation tables;
- deleted the one Artifact referenced only by those Knowledge rows;
- passed `PRAGMA foreign_key_check` with no violations;
- checkpointed and vacuumed SQLite from about 369 MB to about 92 MB;
- deleted the verified
  `%LOCALAPPDATA%\Xenix\artifacts\knowledge` tree: 2 files, 117,019,649 bytes; and
- did not delete `%LOCALAPPDATA%\Xenix\cache\knowledge-ocr`, AI settings, ML data,
  `%USERPROFILE%\.paddlex`, conversation data, datasets, or unrelated Artifacts.

Post-reset counts for every listed Knowledge authority/projection are zero.

## Current-code diagnostic

The 53,093,313-byte PPTX was converted by the current Docling runtime and passed to
the current `_knowledge_units`/`bound_knowledge_units` path.

| Measurement | Result |
| --- | ---: |
| Docling status | success |
| Docling conversion | 5.876 s |
| Unit derivation | 0.113 s |
| raw Docling items | 116 |
| picture items | 49 |
| derived text Units | 67 |
| total Unit characters | 1,509 |
| minimum / mean / maximum Unit characters | 2 / 22.52 / 377 |
| Units above the 8,000-character bound | 0 |
| Units containing embedded image Base64 | 0 |

## Conclusion

The current derivation behavior is bounded for the exact fixture that created the
legacy pathological corpus. The old rows were produced by an earlier projection that
exported picture items to Markdown and therefore indexed their Base64 data URI. The
present code skips picture Markdown and applies an 8,000-character normalized-text
bound.

The required Slice 03 fix is not another ad-hoc splitter. Retrieval projections need
an explicit schema/version or equivalent generation compatibility identity. When the
projection contract changes, documents with a legacy retrieval generation must be
marked for canonical re-derivation before keyword/vector rebuild; index status must
not infer compatibility by loading the old Unit bodies.

This diagnostic does not validate PPTX as a supported import, OCR quality, vector
quality, or Agent retrieval outcome. Those remain separate acceptance surfaces.
