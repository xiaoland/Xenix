# Online Activation Verification Plan

**State:** candidate proof plan; no implementation commands authorized

## Discussion Gate

Before an implementation handshake:

- all `Decided by Sir` rows in the discussion register appear identically in the
  candidate architecture and protocol;
- every open product policy has a chosen rule or an explicit deferral that does not
  make the first release ambiguous;
- protocol examples can represent trial start, activation, refresh, expiry,
  revocation, device-limit denial, offline use, invalid signature, and service
  unavailability without collapsing them into one boolean;
- the D1 shape makes duplicate redemption and device-limit races invalid by
  constraint or atomic write;
- shared Worker/D1 deployment and Preview behavior have executable acceptance
  criteria;
- the native startup path has an observable, non-blocking recovery route;
- key provisioning and rotation have an operator sequence with no secret committed
  to the repository or embedded in the client.

## Future Worker Proof

Use Cloudflare's Workers Vitest integration with isolated local D1 migrations. Prove:

- existing health and `/api/xenix/download` success/failure contracts remain intact;
- CORS is present only for intended website origins/routes and absent from native
  activation routes unless explicitly required;
- request content type, size, shape, protocol version, and bounds are enforced;
- code plaintext and private key never enter D1, logs, response, analytics key, or
  thrown error;
- trial start is idempotent for the chosen subject;
- exact activation retry is idempotent;
- the bound key can recover with the consumed code while a different key receives
  `device_limit_reached`;
- idempotency-key reuse with different content is rejected;
- concurrent one-device redemption yields exactly one binding;
- expired, revoked, unknown, and device-limit decisions are distinct;
- D1 failure, signing-key absence, and malformed stored state fail safely;
- signed responses match native verification vectors;
- rate limiting returns a bounded retry outcome without becoming grant authority.

Cloudflare recommends its Vitest integration for Worker runtime and binding tests:
[Workers Vitest integration](https://developers.cloudflare.com/workers/testing/vitest-integration/).

## Future D1 and Migration Proof

- Apply all migrations to an empty local D1.
- Apply the activation migration to a fixture representing the current contact
  schema and prove contact rows are unchanged.
- Run the previously deployed Worker contract against the expanded schema.
- Run the updated Worker contract after migration.
- Inject a migration failure and prove Worker deployment is blocked without partial
  activation authority.
- Prove unique constraints and conditional writes under concurrent requests.
- Exercise D1 backup/restore or Time Travel procedure on test data.
- Prove no Preview test writes a production grant or contact row.

## Future Native Service Proof

Deterministic black-box tests must cover:

- device-key creation, DPAPI protection seam, reload, and wrong-user/corrupt-state
  failure;
- the Worker recomputes the canonical device-key digest and rejects a mismatched
  client claim;
- user-scoped DPAPI identity survives the packaged update path and a same-user
  reinstall that retains runtime home;
- a copied blob under another user/machine, a lost identity, and a full runtime-home
  reset produce explicit recovery-required outcomes and never silent key rotation;
- cached lease use requires a working local private-key proof, not only matching
  public JSON fields;
- known Ed25519 signing/verification vectors and explicit algorithm allow-list;
- signature, issuer, audience, protocol, nonce, device binding, time, and policy
  revision rejection independently;
- atomic lease publication and survival of interrupted writes;
- no legacy `trial_lock.json` import or fallback;
- cached valid lease startup without network;
- first trial/activation requiring a successful signed online decision;
- refresh success, transport timeout, DNS/TLS failure, rate limit, service error,
  signed denial, revocation, expiry, and clock rollback;
- request timeout, response size limit, redirect policy, and HTTPS-only endpoint;
- no activation code, private key, device raw signal, or signed lease in logs and
  diagnostic bundles.
- raw `SystemIdentification` never crosses the client boundary; unavailable/weak
  source behavior matches the accepted trial fail-open/fail-closed policy.

## Future UI and Startup Proof

- first run offers start-trial and enter-activation-code actions;
- network work never blocks the Qt UI thread;
- retry does not create duplicate activation or trial rows;
- offline allowance is explained separately from permanent license state;
- security error, service unavailable, invalid code, device limit, expiry, and
  revocation use distinct bilingual copy;
- a valid cached lease reaches MainWindow without avoidable network delay;
- a locked startup can retry or enter a new code without restarting the process;
- Settings/About, if added, consume a service read model rather than files or HTTP;
- `LanguageChange`, dialog shutdown, late callback suppression, and task cancellation
  follow local UI rules.

## Future Packaging and Operations Proof

- release configuration embeds only endpoint/protocol/public verification keys and
  no server secret;
- formal candidate requirements remove the local trial HMAC contract only in the
  authorized slice;
- packaged smoke uses a controlled service double or a local test execution of the
  same Worker contract with an isolated local D1 binding, never a separately deployed
  production service and never production grant state;
- Worker deployment verifies required secret presence before traffic;
- operator issue/revoke/unbind commands produce bounded audit events and never print
  an existing code after initial issue;
- operator transfer increments binding epoch and produces a new code; the old device
  and old code cannot win a new binding;
- normal and emergency signing-key rotation are rehearsed against old and new
  packaged clients;
- post-deploy smoke verifies download regression, D1 readiness, activation, refresh,
  signed response, and native acceptance;
- rollback rehearsal proves the old Worker remains compatible with the expanded D1
  schema.

## Security Review Proof

- dependency versions and relevant advisories are checked at implementation time;
- Hono/JWS verification uses an explicit asymmetric `EdDSA` allow-list;
- Worker secret is not configured through `vars`;
- Cloudflare rate limiting is treated as advisory and never exact accounting;
- certificate and DNS controls match the accepted threat model;
- privacy review approves every retained device/network field and retention period;
- shared Worker code review includes possible signing-key access from non-activation
  modules;
- abuse tests do not claim to solve client patching, VM cloning, or human identity.

## Initial Evidence Ledger

| Date | Evidence | Result |
| --- | --- | --- |
| 2026-07-23 | Repository and workflow inspection | Current shared Worker/D1 and native local-trial topology recorded; no product mutation or test run |

## Return-to-Discussion Triggers

Stop implementation and revise the packet if evidence requires:

- a second Worker or D1 despite OA-D01;
- accounts, orders, purchase, or administrator web UI;
- raw hardware identity retention beyond the accepted privacy policy;
- permanent offline activation;
- a cryptographic scheme not interoperable with standard Workers and Python
  libraries;
- a destructive D1 migration or Preview writes to production authorization data;
- proxying Trial LLM traffic as part of the activation authority;
- changing local product-data authority beyond the narrow entitlement exception.
