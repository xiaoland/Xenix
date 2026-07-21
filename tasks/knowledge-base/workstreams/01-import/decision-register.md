# Import Decision Register

| ID | Decision / question | Position | Evidence and consequence | Status |
| --- | --- | --- | --- | --- |
| I-01 | Import completion boundary | Publish **canonical-ready** only; chunking, embedding, indexing, and tool exposure are later work. | Separates parser/OCR correctness and source trust from retrieval/storage decisions. | Accepted |
| I-02 | Source ownership | Copy/hash to a stable app-owned snapshot before `ArtifactService` registration. | The user file remains untouched; an artifact never points at movable staging. | Accepted |
| I-03 | Retry semantics | One logical document, immutable attempts, immutable canonical generations; retry never mutates ready output. | Preserves replayable provenance and makes crash recovery safe. | Accepted |
| I-04 | DOC conversion | Use a LibreOffice conversion capability; compare `DOC -> PDF` and `DOC -> DOCX` on a fidelity spike before choosing default/route classes. | Neither binary DOC-as-DOCX nor a premature conversion choice is safe. | Accepted direction; spike gate |
| I-05 | Same-content source | In the global library, same SHA-256 defaults to reuse/open-existing rather than duplicate import. | Prevents duplicate evidence from polluting later retrieval. | Accepted |
| I-06 | Encrypted document | Support in MVP; password is entered/held only for the active attempt and is never persisted. | Enables legitimate user documents without putting secrets in state/logs. | Accepted |
| I-07 | Content IR | `DoclingDocument` is the unified content IR; Xenix owns a separate immutable lifecycle envelope. | Avoids a competing document tree and keeps lifecycle authority out of provider IR. | Accepted |
| I-08 | Extensible pipeline | Keep `FileProbe -> FormatNormalizer -> ParserRouter -> ParseExecutor -> Canonicalizer` as distinct concepts. | Format additions become registered capabilities/fixtures, not a suffix switch. | Accepted |
| I-09 | PDF route granularity | Probe and route PDF per page; assemble one provenance-preserving DoclingDocument. | Born-digital, scan, OCR-layer, mixed, broken-font, and complex-layout pages need different treatments. | Accepted |
| I-10 | PDF preprocessor | Evaluate `pikepdf` as optional probe/repair support; never silently rewrite source. | It brings QPDF/native packaging and may make a derived input, so it needs spike evidence. | Provisional — spike required |
| I-11 | OCR MVP | Provide independent `OcrService` / `OcrCapability`; first remote adapter targets PaddleOCR Official API (AI Studio). | Keeps credentials, async polling, page mapping, and provider schema out of import orchestration/Docling/LLM Service. | Accepted direction; API contract spike |
| I-12 | Local Paddle structure | Defer PP-StructureV3; model it later as `StructuredDocumentCapability`, preferably sidecar/worker/self-hosted. | It is document-layout/table analysis, not merely OCR; local Paddle runtime/package/Python matrix is not proven. | Accepted deferral |
| I-13 | OCR availability | OCR is conditional; a missing/failed OCR projection does not invalidate a source image/scanned-page item. | File acceptance stays honest while UI distinguishes canonical-ready from text/search readiness. | Accepted |
| I-14 | VLM | No VLM service/profile/UI/projection in MVP. | Removes nondeterministic outbound enrichment from the first import contract. | Accepted |
| I-15 | Markdown | Do not accept Markdown in MVP. | External/local resource resolution needs separate authority and security design. | Accepted |
| I-16 | Library UX | Expose one global Library; retain a hidden stable library identity for future extension. | Avoids premature library management/scope UI while preserving migration path. | Accepted |
| I-17 | Window placement | Secondary Knowledge Workspace opens from a header button left of Settings; persistent import queue is a separate modeless dialog. | Lowest-impact Qt integration; chat shell and Settings tabs remain stable. | Accepted |
| I-18 | TXT detection | Use explicit decode policy plus `charset-normalizer` as candidate evidence; avoid making `python-magic` MVP authority. | Windows libmagic DLL/thread constraints do not justify an accepted-format dependency without a package spike. | Accepted direction; dependency spike |
| I-19 | Resource limits | Establish bytes/pages/pixels/ZIP expansion/subprocess/remote limits from fixtures and package measurements. | Unmeasured static limits would be theater; the import service still requires bounded policies. | Spike required |
| I-20 | Durable docs | Keep current reasoning in task packet; promote only accepted/evidenced claims through their owners in the approved implementation slice. | Prevents volatile research from becoming misleading durable truth. | Accepted |
