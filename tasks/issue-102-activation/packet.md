# Issue 102 - Software Activation

## Objective & Hypothesis

- Objective: explore how to implement online software activation for issue 102 before code changes.
- Hypothesis: activation should be modeled as an application entitlement boundary, not as UI-only enable/disable logic.

## Guardrails Touched

- Product behavior: locked/unlocked feature availability, activation/deactivation, language/settings exception.
- Service boundary: remote activation authority, local activation snapshot/cache, startup status resolution.
- UI boundary: activation entry near settings, global feature lock projection.
- Storage/deployment: local persisted expiry/status, package/runtime configuration for activation server.

## Verification

- Product claim can be stated in PRD without mechanism leakage.
- Technical owner for activation state is singular and testable.
- UI locked state is derived from activation status and does not duplicate authority.
- Offline-after-expiry behavior is covered by unit/boundary tests.

## Current Understanding

- GitHub issue 102 says: online activation through activation code/key; multiple devices allowed with a cap; activation can be cancelled; when not activated, all functionality except settings and language is locked; activation button is next to settings; local expiry time is saved; after local expiry, if activation status cannot be queried from the server, treat as unactivated.
- Current product docs intentionally removed authentication/authorization and always-on online assumptions from the native app. This issue reintroduces a narrow product entitlement boundary, not user accounts or remote app tenancy.
- `MainWindow` is the shell owner for Settings and Chatbot-first navigation. It can receive an activation status projection and lock the history/sidebar/thread/composer surfaces while leaving Settings, language, and activation reachable.
- Runtime config JSON services already exist for lightweight local settings. Activation needs a separate local snapshot/cache owner instead of mixing with LLM or worker settings.
- No existing license/activation implementation was found in source, durable docs, tests, or scripts.

## Unknowns

- Activation server API contract, authentication/signature model, and device identity strategy are not yet defined.
- Whether trial/grace behavior exists is not specified.
- Which UI surfaces count as settings/language and which existing flows must stay reachable while locked need confirmation.
- Whether activation state requires auditable history in SQLite or only the latest local snapshot in `config/activation.json` is a product/operations choice.
- Packaging/configuration for the activation server base URL and public verification material is not defined.

## Candidate Path

- Define product claims first, then introduce a small activation service with explicit remote authority and local snapshot semantics.
- Project activation status into app shell/navigation as a single locked-state input.
- Prefer server authority for activation/deactivation/device cap. Local state should only cache the latest accepted server assertion with expiry and device id.

## Next Step

- Discuss implementation shape, API contract, UI lock semantics, persistence choice, and verification before any durable code/doc change.
