# Native AI First Exploration

## Objective & Hypothesis

- Objective: Redesign Xenix Native toward an AI-first interaction model while preserving the Qt Native application direction.
- Hypothesis: The product can replace existing functional screens with a Chatbot-based interface whose atomic UI element is `Message`; Xenix services become callable tools exposed through an Agent Harness so the LLM can invoke data loading, model training, prediction, and analysis workflows through function calling.

## Prompt

- User request on 2026-05-11: create branch `native-ai-first` from the current branch and establish a long-running task packet for the shift to an AI First Qt Native product.
- The named product direction keeps native Qt implementation.
- The interaction model changes fundamentally: the main interface becomes a Chatbot, and application workflows unfold through LLM dialogue plus file drag-and-drop.
- Existing functional screens are replaced by the Chatbot-based interface.
- A new functional area, Agent Harness, is introduced and requires design before implementation.
- User clarification on 2026-05-11:
  - Chatbot is the product surface, with `Message` as the atomic composition unit.
  - Command-center behavior means Xenix services are exposed as tools to the LLM through Harness Agent function calling.
  - Harness contracts should be exercised with independent integration tests around real services.
  - End-to-end AI behavior should use CopilotKit AIMock after feasibility is verified against official docs and current stack constraints.
  - Minimum acceptance: a user can complete basic data analysis inside Chatbot through pure conversation and file drag-and-drop.
- User clarification on Message and harness topology on 2026-05-11:
  - LLM function calling and Xenix service tools are part of Agent Harness.
  - Basic data analysis includes the full path from data intake to prediction.
  - UI and Harness share one persisted `Message` concept, with one UI Message corresponding to one Harness Message when visible.
  - UI focuses on whether a visible message is from user or assistant, and what content it contains.
  - Harness focuses on provider-facing kind such as assistant, user, system, tool call, and tool-call result.
  - Harness Message design must be informed by OpenAI Responses, OpenAI Chat Completions, OpenAI legacy Completions, Anthropic Messages, and Google Gemini Generative API contracts.
  - `ScenarioWorkflowService` is removed in the target topology.
  - Conversation thread and message persistence are part of the first phase.
  - CopilotKit AIMock attaches at the LLM provider boundary.
- User clarification on harness boundaries on 2026-05-11:
  - Reference LangGraph, Vercel AI SDK, and the Pydantic team AI library while keeping Xenix-owned contracts.
  - HarnessCore works against a canonical function-calling contract.
  - LLM providers implement that canonical contract and own provider request assembly.
  - HarnessCore emits events; assistant/tool-call/tool-result persistence belongs to recorder/store boundaries.
  - Most-needed provider dialects are OpenAI-compatible `/v1/chat/completions` and DeepSeek API.
  - Tool design needs further discussion.
  - `WorkItem` was part of the workspace discussion and later moved out of the first-slice LLM-facing contract.
- User clarification on turns and HarnessCore on 2026-05-11:
  - `FunctionCallingLoop` should be renamed to `HarnessCore`.
  - HarnessCore also owns user-message intake.
  - A thread is composed of turns.
  - A turn is a group of messages that starts with a user message and ends when the provider response has no tool calls.
  - CopilotKit AIMock belongs at the LLM provider boundary.
  - Workspace context injection required further design.
- User clarification on WorkItem on 2026-05-11:
  - WorkItem was considered as the LLM workspace inside a thread.
  - This was superseded by the later thread-as-workspace first-slice clarification.
- User clarification on context naming on 2026-05-11:
  - Remove the older analysis-context entity name completely.
  - Workspace context terms were explored before the first-slice thread-as-workspace decision.
  - Clarify the training tool shape before solidifying the tool registry.
- User clarification on thread workspace on 2026-05-12:
  - First-slice flow does not need WorkItem as a separate workspace.
  - Thread as conversation history can carry the current workspace duties.
  - A separate workspace outside thread may become useful only after task complexity grows.
- User clarification on Harness control on 2026-05-11:
  - Harness control should be split into concrete responsibilities.
  - Side-effect tracking and modeling decisions are separate concerns.
  - Data-aware and goal-aware training choices belong to `ModelingPlanner`.
- User clarification on first-slice control on 2026-05-12:
  - First-slice user control is cancellation: send button becomes stop button during provider inference or tool execution.
- User clarification on atomic tools and script runtime on 2026-05-12:
  - LLM should receive more atomic tools.
  - LLM-authored scripts were considered during exploration for preprocessing, model training, and inference.
  - This is similar to giving the LLM a Python interpreter inside a managed Xenix runtime.
  - Scripts must produce declared outputs such as trained models, metrics, predictions, datasets, tables, charts, or reports.
  - Outputs must be registered through Xenix-provided APIs.
- User clarification on minimal first-slice tools on 2026-05-12:
  - The previous tool registry was too complex.
  - First slice should not support LLM-authored custom training or prediction scripts.
  - LLM tools should start with `data.peek`, `data.integrate`, `data.clean`, `data.transform`, `data.feature.select`, `model.train`, `model.hyper_train`, and `model.inference`.
  - Charts, tables, images, and prediction results should be returned as markdown artifact links, and Chatbot should auto-preview them.
  - Generic script runtime is deferred.
- User clarification on first-slice scope and service direction on 2026-05-12:
  - First slice excludes `data_transform`.
  - First-slice LLM tools are `data.peek`, `data.integrate`, `data.clean`, `data.feature.select`, `model.train`, `model.hyper_train`, and `model.inference`.
  - Service implementation direction changes to refactor-first.
  - Old UI exits the target path immediately.
  - `WorkItemService` can be removed from the target service topology.
  - First-slice working context needs further high-level design.
- User clarification on model tool discovery on 2026-05-16:
  - Add `model.metadata` so the LLM can inspect canonical model keys, capabilities, and parameter schemas.
  - `model.train` and `model.hyper_train` keep lightweight model-key string inputs.
  - `model.metadata.model_keys.items.enum` is the model catalog discovery point.
- User clarification on Agent autonomy and ownership on 2026-05-12:
  - The first-slice flow is an acceptance scenario.
  - System/developer prompts expose tools and boundaries while planning and tool ordering remain model-owned.
  - LLM planning and tool ordering should remain model-owned.
  - Agent Harness is a service under `src/xenix/services/agent/`.
  - Agent Harness owns Thread, Turn, Message, tool-call, and tool-result semantics.
  - Storage provides standardized persistence interfaces.
  - First slice does not add structured domain state for derived dataset, feature selection, best model, or prediction refs.

## Classification

- Intent: new product interaction direction and architecture-level workflow shape.
- Current mode: Explore.
- Durable owner candidates:
  - Product behavior and user workflow: `docs/10-prd/`
  - Cross-unit technical realization: `docs/20-product-tdd/`
  - Qt Widgets UI execution: `src/xenix/ui/`
  - Service and orchestration boundaries: `src/xenix/services/`
  - ML execution surface exposed to agents: `src/xenix/services/ml/`
  - Storage and audit/state persistence: `src/xenix/services/storage/`

## Guardrails Touched

- Native Qt Widgets application remains the implementation target.
- Existing ML workbench behavior and business vocabulary should survive through the Chatbot and tool-call model unless later product alignment explicitly changes them.
- Non-technical user friendliness remains a product invariant.
- Agent-driven actions need explicit boundaries, recoverability, and evidence of side effects.
- Durable docs and code stay unchanged during the initial exploration until scope, ownership, and invariants are restated.
- Provider-specific message contracts constrain the Agent Harness canonical Message design.

## Current Facts

- New branch requested: `native-ai-first`.
- Workstream is large and long-running.
- User explicitly asked for branch creation and task packet creation before deeper discussion and design.
- Existing repository structure separates UI, services, ML adapters, and storage.
- The current task starts from a native Qt product.
- The target UI removes current functional screens from the primary interaction model.
- The first acceptance target is basic data analysis through Chatbot conversation and file drag-and-drop.
- CopilotKit AIMock official materials describe deterministic mock infrastructure for AI apps, with support areas including LLM calls, MCP, vector stores, and agent-to-UI event streams. Source checked: https://aimock.copilotkit.dev/ and https://www.copilotkit.ai/blog/aimock-one-tool-to-mock-your-entire-ai-stack.
- Initial code topology draft exists at `tasks/native-ai-first/code-topology.md`.
- Provider message contract research exists at `tasks/native-ai-first/provider-message-contract-research.md`.
- Agent Harness design notes exist at `tasks/native-ai-first/agent-harness-design-notes.md`.
- Framework reference research exists at `tasks/native-ai-first/framework-reference-research.md`.
- Tool design notes exist at `tasks/native-ai-first/tool-design-notes.md`.
- LLM tool inventory exists at `tasks/native-ai-first/llm-tool-inventory.md`.
- Thread workspace design exists at `tasks/native-ai-first/thread-workspace-design.md`.
- Managed script runtime design exists at `tasks/native-ai-first/script-runtime-design.md`.
- Data transform DSL design exists at `tasks/native-ai-first/data-transform-dsl.md`.
- Artifact link contract exists at `tasks/native-ai-first/artifact-link-contract.md`.
- AIMock integration notes exist at `tasks/native-ai-first/aimock-integration.md`.
- Migration plan exists at `tasks/native-ai-first/migration-plan.md`.
- Global design review exists at `tasks/native-ai-first/global-review.md`.
- High-level decision agenda exists at `tasks/native-ai-first/high-level-design-decisions.md`.
- Implementation plan exists at `tasks/native-ai-first/implementation-plan.md`.
- Phase 0 impact map exists at `tasks/native-ai-first/phase-0-impact-map.md`.

## Unknowns

- What exact data-to-prediction jobs the Chatbot must support in the first useful slice.
- What `content_blocks` are required inside one persisted `Message`: text, file attachment, tool call, tool result, cancellation, analysis summary, chart/table artifact, error recovery.
- Exact canonical function-calling request/event/result contract.
- Which LLM provider modes are acceptable beyond OpenAI-compatible `/v1/chat/completions`, DeepSeek API, and AIMock.
- What autonomy level is acceptable for agent actions across data import, model training, evaluation, export, and project mutation.
- Which existing UI capabilities become tools, message renderers, or supporting native widgets inside messages.
- Exact storage shape for conversation threads, messages, tool calls, tool results, artifacts, and cancellation state.
- High-level working-context projection from messages, tool results, and artifacts.
- Exact `Turn` schema and empty-tool-call ending behavior.
- Exact `ModelingPlanner` input/output contract.
- Exact minimal data/model tool schemas.
- Markdown artifact link contract for Chatbot preview rendering.
- What privacy, security, and cost constraints govern LLM use.
- How CopilotKit AIMock fits the Python/PySide6 native application at the LLM provider boundary.

## Constraints Observed

- Implementation should start only after sufficient discussion and design.
- High-level details require confirmation before implementation.
- Claims should be verified against current repository reality where possible.
- Work should proceed through task packet notes before promotion into durable docs.
- Harness service behavior should be covered by independent integration tests.
- End-to-end testing should use deterministic AI mocks where feasible, with CopilotKit AIMock as the named candidate.
- `ScenarioWorkflowService` should not remain in the target topology.
- Thread is the first-slice LLM workspace.

## Candidate Paths

1. Chatbot replacement path: build the native Chatbot surface around persisted `Message` as the atomic unit and migrate workflow output into message-rendered artifacts.
2. Agent Harness path: own LLM provider dialects, HarnessCore, Turn progression, minimal static tool registry, Xenix data/model tools, cancellation boundary, run recorder, and structured tool results.
3. Message contract path: derive the canonical Xenix Message from OpenAI, Anthropic, and Google provider contracts, then project it into UI view models.
4. Service integration path: add independent integration tests for service tools before wiring them into the LLM-facing harness.
5. Deterministic E2E path: use CopilotKit AIMock at the LLM provider boundary for repeatable end-to-end tests covering conversation, file drag-and-drop, tool calls, and data-to-prediction results.

## Verification Anchors

- Branch exists locally as `native-ai-first`.
- Task packet exists at `tasks/native-ai-first/exploration.md`.
- Product docs, source code, storage schema, and service contracts remain untouched during this initial setup.
- Next design pass should identify owner, blast radius, invariants, and smallest implementable slice before edits.
- Minimum acceptance proof should demonstrate a user completing data-to-prediction analysis inside Chatbot with conversation plus file drag-and-drop.
- Harness proof should include service integration tests for data loading, model training or analysis, and prediction or output generation once first-slice scope is finalized.
- E2E proof should include deterministic LLM/tool behavior through CopilotKit AIMock or a verified equivalent boundary.

## Smallest Confirmation Needed

- Define the first data-to-prediction workflow to design end to end.
- Define the first canonical `Message` contract and UI projection.
- Define Agent Harness responsibilities for the first slice.
- Decide LLM integration assumptions for the first slice.
- Decide exact LLM provider boundary contract for CopilotKit AIMock.
- Decide first-slice working-context projection.
- Decide the first tool contract set.
- Decide working-context projection and injection strategy.
- Decide provider empty-tool-call turn ending contract.
- Decide the first training preset contract.
- Decide markdown artifact link and preview contract.

## Promotion Candidate Truths

- Leave empty until stable after discussion and verification.
