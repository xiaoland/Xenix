# Implementation Dependency Graph

This graph is the execution order, not the runtime topology.

```mermaid
flowchart TB
    S["TP-03 SettingsStore"]
    D0["TP-00 Managed AMD decision"] --> R["TP-08 Installation repository"]
    D0 --> M["TP-10 Manifest planner"]
    D1["TP-01 LLM reference policy"] --> L["TP-04 LLM capability seam"]
    S --> L
    S --> E["TP-05 Embedding catalog"]
    D2["TP-02 OCR product profile"] --> O1["TP-06 OCR neutral extraction"]
    S --> O2["TP-07 OCR KServe/spawn"]
    O1 --> O2

    R --> K["TP-09 AMD runtime kernel"]
    L --> C["TP-11 Deployment reconcile"]
    E --> C
    O2 --> C
    R --> C
    K --> C
    M --> C

    L --> G1["TP-12 AMD Chat adapter"]
    K --> G1
    E --> G2["TP-13 AMD Embedding adapter"]
    K --> G2
    O2 --> G3["TP-14 AMD OCR adapter"]
    K --> G3

    K --> P["TP-15 Private SSH placement"]
    M --> P
    P --> Q1["TP-16 Granite recipe"]
    P --> Q2["TP-17 BGE-M3 recipe"]
    P --> Q3["TP-18 RapidOCR recipe"]
    M --> Q1
    M --> Q2
    M --> Q3
    O2 --> Q3

    C --> V["TP-19 Private SSH vertical"]
    G1 --> V
    G2 --> V
    G3 --> V
    Q1 --> V
    Q2 --> V
    Q3 --> V

    V --> U["TP-20 Guided AMD UI"]
    U --> X["TP-21 Packaging/operations"]

    K --> A["TP-22 Local Linux Radeon"]
    G1 --> A
    G2 --> A
    G3 --> A
    Q1 --> A
    Q2 --> A
    Q3 --> A

    V --> Z["TP-23 Clean-room lifecycle"]
    X --> H["TP-24 AMD hard cut-off"]
    H --> Z
    A --> Z
```

## Runtime Topology Produced by the Plan

```mermaid
flowchart TB
    APP["App optional AMD composition anchor"] --> UI["AMD setup UI"]
    APP --> DS["AmdAiDeploymentService"]
    DS --> CO["Installation coordinator"]
    CO --> DB["AMD installation repository"]
    CO --> CM["Manifest/compatibility planner"]
    CO --> PP["Managed component participants"]
    CO --> PR["Private placement registry"]
    PR --> LP["LocalAmdPlacement"]
    PR --> SP["PrivateSshAmdPlacement"]

    PP --> LS["LLMSettingsService"]
    PP --> ES["EmbeddingSettingsService"]
    PP --> OS["OcrSettingsService"]
    LS --> SS["SettingsStore"]
    ES --> SS
    OS --> SS

    LLM["LLMService"] --> LF["ChatOperationFactory"]
    EMB["EmbeddingService"] --> EF["EmbeddingOperationFactory"]
    OCR["KnowledgeImportService"] --> OF["OcrAttemptFactory"]
    LF --> LA["AMD Chat adapter"]
    EF --> EA["AMD Embedding adapter"]
    OF --> OA["AMD OCR adapter"]
    LA --> RD["AMD-private runtime directory"]
    EA --> RD
    OA --> RD
    RD --> LE["Local execution session"]
    RD --> SE["Private SSH execution session"]
```

The deployment facade never appears in the inference path. The settings store
never emits domain payloads to UI. A spawned OCR worker receives an ephemeral
ordinary OCR spec and never imports the AMD module.

## AMD-absent Topology

```mermaid
flowchart TB
    APP["App composition without AMD contribution"] --> UI["Ordinary UI"]
    APP --> LLM["Static LLM factories"]
    APP --> EMB["Static Embedding factories"]
    APP --> OCR["Paddle / ordinary KServe OCR"]
    APP --> AG["Generic Agent composition"]
    UI --> CS["Capability settings owners"]
    CS --> SS["SettingsStore"]
    AG --> LLM
    AG --> EMB
    AG --> OCR
```

Only the bounded app composition anchor points toward AMD. Capability registries
are explicit app-scoped instances; capability modules, Agent composition, generic
startup/shutdown/diagnostics, and spawned OCR workers never import AMD or discover
it through ambient entry points. Removing the AMD contribution therefore removes a
leaf slice rather than breaking the graph.

## Shared Edit Hotspots

| Hotspot | Sole task owner |
| --- | --- |
| SQLite model/migration edge | TP-08 |
| `knowledge_pipeline.py` Paddle-neutral extraction | TP-06 |
| `knowledge_import_worker.py` ephemeral provider spawn | TP-07 after TP-06 |
| `llm/service.py` retry/stream scope | TP-04 |
| `embedding_service.py` schema/fingerprint | TP-05 |
| `app.py` composition | TP-19 |
| `settings_dialog.py` AMD/conflict UI | TP-20 |
| packaging and operational runbooks | TP-21 |
| cutoff verifier and negative build | TP-24 |

The existing `services/ml/worker_pool.py`, `ml/execution.py`, and
`ml/ssh_worker_setup.py` are outside ownership. They may be read for OpenSSH
experience but may not become dependencies of the long-lived AMD inference
lifecycle.
