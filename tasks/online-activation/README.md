# Online Activation

**Status:** discussion packet open; no product implementation authorized
**Opened:** 2026-07-23
**Posture:** Explore and Solidify

## Objective

Define an online activation and online free-trial contract for Xenix Native that
reuses the existing website Hono Worker, existing D1 database, route, and deployment
chain. Produce an evidence-backed product policy, trust boundary, protocol, data
shape, failure model, and verification plan that Sir can approve before any durable
product, source, schema, workflow, or deployment mutation begins.

The first release does not introduce customer accounts, checkout, orders, a purchase
workflow, or migration of the legacy local trial state.

## Guardrails

- Sir has decided that activation reuses the current Worker and D1. A separate
  Worker, D1 database, route authority, or deployment pipeline is outside this task.
- Shared infrastructure must be described truthfully. Module and table boundaries
  may reduce coupling, but they are not independent security, deployment, storage,
  or failure domains.
- This packet is the only authorized mutation during the current discussion.
  Product requirements, technical contracts, source, schemas, workflows, tests, and
  deployment configuration remain unchanged until a scoped Impact Handshake is
  explicitly approved.
- The existing website download-contact behavior and data must not be reinterpreted
  as license or trial authority.
- Remote activation authority is limited to product entitlement. Local datasets,
  conversations, models, Knowledge content, artifacts, and canonical outputs remain
  locally authoritative.
- No server secret, signing private key, reusable shared HMAC secret, plaintext
  activation code, or provider credential may be embedded in the desktop client,
  stored in D1 as plaintext, or passed as a Wrangler plaintext variable.
- Standard TLS verification must remain enabled. A certificate-pinning proposal is
  not accepted merely because it is stricter; its rotation and outage behavior must
  be compared with application-level response signing.
- Trial fairness must be stated honestly. Without accounts, payment identity, or
  hardware attestation, reinstall, VM cloning, client patching, and device-identity
  spoofing cannot be eliminated.
- Online trial authority does not silently imply that every startup must be online.
  Initial online proof, refresh cadence, offline allowance, and fail-closed behavior
  remain explicit policy decisions.
- The packaged Trial LLM credential is an adjacent but separate exposure. Activation
  status must not be claimed to protect a credential still embedded in the client.
- Existing unrelated working-tree changes belong to the user and remain outside this
  packet and any later implementation scope.
- Commits, deployment, migration application, secret changes, and external side
  effects require their normal explicit authority.

## Verification

Discussion is ready for an implementation authorization only when:

- every open item in [the discussion register](discussion-register.md) is decided,
  explicitly deferred, or assigned a concrete evidence step;
- the product state machine distinguishes entitlement decisions from transport,
  security, and retry outcomes;
- the shared Worker/D1 authority, deployment blast radius, Preview behavior,
  privacy boundary, and migration ordering are explicit;
- the API version, request proof, signed response, device binding, activation-code
  lifecycle, trial rule, offline rule, revocation rule, and key-rotation procedure
  are coherent;
- an operator can issue, revoke, inspect, and reset activation state without adding
  a public customer or administrator system;
- [the verification plan](verification.md) proves both the new activation behavior
  and regression safety for the existing download API;
- an Impact Handshake names exact future addresses, state diffs, blast radius,
  invariants, and executable proof before code changes begin.

Packet integrity is checked through relative-link resolution, whitespace validation,
and a task-scoped diff review. No product test run is evidence for this discussion
packet because no product behavior is changed.

## Current Truth

- Sir decided on 2026-07-23 that activation must reuse the existing website Worker
  and existing D1 database. That decision supersedes the earlier separate-service
  recommendation.
- The current product truth explicitly says that trial builds do not provide online
  license activation and that hosted product authority is out of scope.
- The website currently has one Hono Worker entrypoint, one `DB` binding, one D1
  migration, one health route, and one download-contact route.
- CORS is currently installed globally and reflects arbitrary syntactically valid
  origins. That behavior cannot automatically apply to activation routes.
- Website CI type-checks and bundles the Worker but has no Worker/D1 API test suite.
- Production applies D1 migrations before deploying the Worker. A bad activation
  migration or Worker release therefore shares the download API's rollout and
  rollback boundary.
- Preview Workers currently receive the configured D1 database name and id. The
  repository does not prove that activation Preview traffic is isolated from
  production authorization data.
- Native trial enforcement is local, build-configured, HMAC-signed with an
  extractable packaged secret, and checked before the normal runtime is loaded.
- The native application has no activation client, server-signed lease, device-key
  owner, online failure states, revocation state, or post-start entitlement model.
- The packaged Trial LLM provider is independent of the local trial lock and loads a
  provider credential from frozen release configuration.
- Cloudflare Workers supports standard Ed25519 through Web Crypto, D1 transactional
  batches, Worker secret bindings, and advisory rate limiting. These capabilities do
  not by themselves decide the product policy.
- Sir decided that one code grants one perpetual, revocable, one-device entitlement:
  same-device recovery is allowed, another device is denied, and controlled transfer
  requires an operator reset and a new one-time code.
- The candidate licensed device identity is a per-user Ed25519 key protected with
  Windows DPAPI. A stable Windows system signal is considered separately and only
  for best-effort trial correlation.
- No source, product document, schema, workflow, test, secret, or deployment setting
  has been changed for online activation.

Detailed repository evidence is recorded in
[the current topology](evidence/current-worker-d1-topology.md). Candidate boundaries
and protocol ideas are discussion material, not accepted implementation.

## Next Step

Discuss and decide the product policy in this order:

1. whether licensed “same device” is the retained user-scoped device key and whether
   loss of that key always requires operator reset;
2. what identifies a trial subject and what level of reinstall resistance is an
   honest requirement without accounts;
3. whether trial and licensed use receive offline allowance, and for how long;
4. whether application-level Ed25519 signing is sufficient for the intended MITM
   threat or request confidentiality beyond normal TLS is also required;
5. how operators issue, revoke, unbind, and inspect grants before a purchase system
   exists.

These five decisions are the first discussion cohort, not the whole authorization
gate. After them, continue through every remaining release-blocking item in the
register. Only when the Verification section is satisfied may the packet prepare—but
not execute—the first implementation Impact Handshake.

## Packet Map

- [Discussion register](discussion-register.md)
- [Current Worker/D1 topology evidence](evidence/current-worker-d1-topology.md)
- [Candidate shared-Worker architecture](candidate-architecture.md)
- [Candidate protocol and policy model](protocol-and-policy.md)
- [Device identity and “same device”](device-identity.md)
- [Threat model](threat-model.md)
- [Verification plan](verification.md)
