# ADR Index

ADRs preserve decision history. Later records supersede or clarify them; source and
tests own implementation mechanics.

| ADR | Date | Status | Relationship | Realization |
| --- | --- | --- | --- | --- |
| [0001 — Qt Widgets](0001-pyside6-qt-widgets.md) | 2026-03-09 | Accepted | — | Current |
| [0002 — SQLite metadata](0002-sqlite-for-local-state.md) | 2026-03-09 | Superseded | By 0006 | Historical |
| [0003 — Filesystem artifacts](0003-filesystem-for-datasets-models-results.md) | 2026-03-09 | Accepted | Complements 0006 | Current |
| [0004 — Native layering](0004-native-architecture-separate-from-web.md) | 2026-03-09 | Accepted | Clarified by 0007 | Current |
| [0005 — SSH workers](0005-ssh-ml-worker-pool.md) | 2026-05-23 | Accepted | Extends 0004; clarified by 0007 | Partial; gaps recorded |
| [0006 — SQLite application state](0006-bounded-sqlite-application-state.md) | 2026-07-11 | Accepted | Supersedes 0002; complements 0003 | Current |
| [0007 — Remote adapters](0007-remote-integrations-remain-adapters.md) | 2026-07-11 | Accepted | Clarifies 0004 and 0005 | Current |
| [0008 — Canonical LLM conversation boundary](0008-canonical-llm-conversation-boundary.md) | 2026-07-15 | Accepted | Relates to 0006 and 0007 | Current |
| [0009 — Native Paddle local OCR](0009-official-paddle-native-local-ocr.md) | 2026-07-22 | Accepted | Relates to 0003, 0006, and 0007 | Current |
| [0010 — Managed AMD ROCm deployments](0010-managed-amd-rocm-deployments.md) | 2026-07-28 | Accepted | Extends 0007; relates to 0006, 0008, and 0009 | Current |
| [0011 — KServe PAGE OCR provider boundary](0011-kserve-page-ocr-provider-boundary.md) | 2026-07-28 | Accepted | Relates to 0009 and 0010 | Current |
