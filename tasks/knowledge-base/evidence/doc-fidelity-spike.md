# Legacy DOC Fidelity Spike — 2026-07-22

## Question

Should the MVP normalize binary DOC to DOCX or PDF before Docling parsing?

## Repeatable Method

Run:

```powershell
pdm run python tasks/knowledge-base/evidence/run_doc_fidelity_spike.py
```

The script creates a representative Chinese Word fixture containing paragraphs, a
3×3 table, an embedded picture, header/footer text, a page break, and a reference
marker. LibreOffice first produces a genuine Word 97 DOC, then converts the same
source independently to DOCX and PDF. Each route is parsed through Xenix's Docling
worker and inspected for markers, table/picture labels, page anchors, and hashes.
The machine-readable report is regenerated at
`build/knowledge-doc-fidelity-spike/result.json`.

Runtime used for the recorded run:

- Python 3.14.0
- LibreOffice 26.2.2.2 (`1f77d10d6938fd34972958f64b2bcfa54f8b1ba5`)
- source DOC SHA-256:
  `38141a1a8007937520259ea00bc4b243ffad646a51cbfdc8c3ecdb977749d7cb`

## Result

| Signal | DOC→DOCX | DOC→PDF |
| --- | --- | --- |
| Body/rule/reference markers | all retained | all retained |
| Header marker | not surfaced by either Docling route | not surfaced by either Docling route |
| Table | 1; U100/R200 values retained | 1; U100/R200 values retained |
| Picture items | 1 | 0 |
| Page anchors | none | pages 1 and 2 |
| Parsed text characters | 204 | 208 |
| Output SHA-256 | `710d64420d95687efd1efbfde682f2b8709a3adbe76bbbfbc46975e2f9448136` | `3cbe28b4d1cf299a6f786f2693e6c38c875b53bb2b9cd7e41c9d5eb3436d2334` |

Both routes preserved the evidence needed by the representative retrieval case.
DOCX retained the embedded picture and document structure; PDF's only measured
advantage was physical page anchors.

## Decision

Use **DOC→DOCX** as the MVP normalization default. Retain DOC→PDF as an explicit
diagnostic alternative when page anchoring is materially more important than picture
retention. Always keep the original DOC as the source Artifact and record the
LibreOffice/intermediate descriptor and hashes in canonical provenance.

## Limits

This spike does not claim universal Office fidelity. It exposes one shared gap:
neither parsed route surfaced the header marker. Broader corpora should cover tracked
changes, text boxes, equations, nested/floating tables, rare fonts, and corrupted DOC
variants before changing the default or adding a per-document route heuristic.
