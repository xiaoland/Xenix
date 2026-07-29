# TP-04 — LLM Capability and Operation Seam

## Outcome

Make LLM settings and request lifecycle capable of representing a managed exact
generation without teaching the LLM domain about AMD, SSH, Local placement, or
dynamic endpoints.

## Owned Mutation

- add `src/xenix/services/llm/settings.py`;
- add `src/xenix/services/llm/provider_factory.py`;
- modify `src/xenix/services/llm/service.py`,
  `src/xenix/services/llm/providers.py`, and `src/xenix/services/llm/__init__.py`;
- modify only the necessary LLM conversation repository query for reference
  classification;
- add/extend LLM settings, provider factory, retry, stream, and conversation tests.

UI and `app.py` are not edited.

## Data and Ports

- explicit `StaticLlmTarget | ManagedLlmProviderRef`; the managed ref is
  capability-owned and contains an opaque `manager_id`, installation ID, and
  component-generation ID, never an AMD type;
- generation-specific immutable provider instance ID derived from owner,
  installation, and component generation;
- settings snapshot/read view, user command view, and managed-projection command
  view share one domain owner over TP-03;
- app-scoped factory registry owns construction only; built-ins register
  explicitly and optional managers contribute factories only through composition;
- `provider_scope()` owns one complete/stream semantic operation.

Managed projection data contains exact ref, display/model compatibility metadata,
and manifest digest—never URL, port, token, health, placement, or incarnation.

## P0 Retry Rule

The operation scope pins generation/incarnation around the entire outer retry loop.
Attempts known not to have dispatched may retry. Once dispatch may have happened,
connection/binding loss is non-retryable for that operation. Streaming releases
the scope in `finally`, including generator abandonment/close. Error text is
endpoint/token-redacted.

## Acceptance

- legacy, packaged-trial, and static OpenAI behavior remains compatible;
- G2 ensure creates a new entry and never changes G1/default/guard/title;
- same ID plus different exact ref is owner conflict;
- removal blockers and stale historical Thread behavior match TP-01;
- server-received-then-disconnect produces one request, not two;
- stream abandon releases one exact generation scope;
- inference service no longer exposes full-document save.
- an unknown/removed `manager_id` loads as
  `provider_implementation_unavailable`, dispatches nothing, changes no selection,
  and can be explicitly removed only through LLM-owned blockers;
- LLM modules have no AMD import, import-time registration, or ambient entry-point
  discovery.

## Verification

- focused LLM settings/provider/conversation tests;
- retry/stream black-box fixture;
- `pdm run check`.
