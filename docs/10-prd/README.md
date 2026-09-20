# Xenix Product Truth

## Purpose and Pressure

Xenix is a local desktop workbench for non-technical business users, primarily
business and marketing staff. It turns tabular data into decision-ready analysis
through conversation, without requiring users to operate a data stack, choose
algorithms, or translate technical outputs on their own.

The product pressure is to preserve business meaning while reducing analytical
friction. Xenix should help users understand what the data says, what action it
supports, and what uncertainty remains.

## Claims and Evaluation

| Product claim | Rationale | Observable success | Expected evidence |
| --- | --- | --- | --- |
| Conversation is the primary work surface. | Business users should express goals in their own language. | A user can attach tabular data, ask a business question, and continue the work in one conversation. | Integrated conversation, attachment, and history coverage. |
| Data preparation preserves the source and produces explicit derived data. | Cleaning or reshaping must not silently destroy the original business record. | Prepared results are registered separately and remain available to later analysis. | Data-service and lineage contract coverage. |
| Results are explained in business terms and remain reviewable. | Metrics and model names alone do not support decisions. | The conversation explains meaning, actions, risks, and limitations; material outputs open as local artifacts. | Agent acceptance and artifact-activation coverage. |
| Reusable analyzers can be trained and applied without exposing algorithm plumbing. | Repeated business analysis should not require a notebook or ML interface. | A user can prepare roles, train or tune an analyzer, and apply the retained analyzer to compatible data. | Model-lifecycle integration coverage. |
| Product state and canonical outputs remain locally authoritative. | Optional remote capacity must not turn Xenix into a hosted backend. | Local services retain conversation, task, dataset, model, and artifact authority when remote ML execution is used. | Storage, worker, and artifact boundary coverage. |
| User knowledge can guide data analysis with source-linked evidence. | Business rules and operating experience often live outside datasets. | A user can import a supported document once and the Agent can retrieve a bounded, citable passage while analyzing data. | Knowledge import, lookup-tool, citation, and Agent benchmark coverage. |
| The interface supports English and Simplified Chinese. | Business users should work in the configured interface language. | The selected language persists and also guides the conversation language for new work. | Locale persistence and UI-switch coverage. |
| Background work is visible and controllable in one place. | Users should be able to see and stop long-running work without leaving the app. | The Jobs window lists ML and Knowledge background work with a shared status, and a queued or running job can be cancelled. | Job-layer scheduling and Job Center coverage. |

## Capabilities and Workflows

1. Start or reopen a conversation and attach a supported local CSV or Excel file.
2. Ask Xenix to inspect, combine, clean, prepare, summarize, or visualize the
   registered data.
3. When useful, define data roles and train, tune, or apply a reusable analyzer.
4. 在审计中心查看数据集、模型、训练和调参参数、图表、报告及应用结果；先阅读 Agent 的方法理由和结果解读，再按需检查来源与证据，并打开本地产出。解释缺失和证据缺失必须明确呈现。
5. Configure supported LLM providers and choose the LLM model used by the next
   assistant response without changing sampling already in progress.
6. Open the Knowledge Workspace, select or drop TXT, DOC/DOCX, PPT/PPTX, RTF, EPUB, ODT/ODP, PDF,
   JPEG, or PNG material, and let the Agent apply relevant saved knowledge through
   source-linked lookup.
7. Open About to review the installed Xenix version and manually check for
   software updates. A confirmed download reports percentage progress in a
   modeless window before the user explicitly chooses whether to restart and
   apply it.
8. Open the Jobs window to review background work — knowledge import and index
   builds, model training, evaluation, and apply runs — and cancel a queued or
   running job. Knowledge work resumes after a restart; model training is not
   automatically resumed.

## Rules and Scope

- Xenix serves one local operator. Accounts, roles, tenancy, and concurrent-user
  coordination are out of scope.
- Xenix does not mutate or delete user-selected source files. Cleaning,
  preparation, and transformation create derived registered data.
- Dataset identities are inputs to later work. User-openable outputs are
  service-registered artifacts.
- Local services, SQLite state, and local canonical artifacts remain authoritative.
  SSH workers provide execution and cache capacity only.
- External LLM-provider APIs are adapters, not a Xenix-owned remote backend.
- MVP exposes one global Knowledge Library. Its internal identity permits future
  multiple-library instances, but no library-management UI is promised.
- Knowledge import preserves the selected source and canonical content locally.
  Local OCR is installed explicitly through the Knowledge Workspace and supports
  standalone JPEG/PNG sources and scanned PDF pages. Documents and
  presentations use a bounded local Rust parser adapted into the canonical
  Docling content IR. Retrieval preserves heading hierarchy and bounded
  sentence-aware overlap. VLM and Markdown imports are outside MVP.
- Browser-first operation, an always-on Xenix server, and hosted product authority
  are out of scope.
- Trial builds may enforce a build-time expiry and direct the user to a purchase or
  licensed-download path. They do not provide online license activation.

## Business Language

- **Dataset**: registered tabular data available to Xenix analysis and model work.
- **Artifact**: a service-registered result that the user can open or preview.
- **LLM model**: the provider model selected for a conversation's next assistant
  response.
- **Trained analyzer**: a reusable analysis or ML result that can be applied to
  compatible data; UI copy may call it a trained model.
- **ML worker**: local or SSH-backed execution capacity selected by Xenix services;
  it does not own product state or canonical outputs.
- **Knowledge Library**: the global collection of imported business knowledge that
  the Agent may search; it is distinct from conversation attachments and Datasets.
- **Knowledge Unit**: a bounded, source-located passage derived from the current
  canonical document and used as the atomic retrieval result.

审计中心和任务中心均可选择当前会话或所有会话；任务中心集中呈现执行状态、日志与取消能力，审计中心集中呈现产出及解释，二者可按任务相互定位。训练工具消息不再提供专属详情窗口。
