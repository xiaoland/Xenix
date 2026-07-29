# Online Activation Discussion Register

This register distinguishes Sir's decisions from candidate recommendations and
unresolved questions. A candidate is not implementation authority.

| ID | Concern or decision | State | Current disposition / next evidence |
| --- | --- | --- | --- |
| OA-D01 | Should activation reuse the existing Worker and D1? | Decided by Sir | Yes. One Worker, one D1 binding, one migration/deployment chain. Do not reopen this as a separate-service proposal. |
| OA-D02 | Are customer accounts, checkout, orders, and purchase flows in scope? | Decided by Sir | No. A bounded operator issuance path is still required so activation codes can exist. |
| OA-D03 | Does free trial become online, and must legacy local trial state migrate? | Decided by Sir | Trial authority becomes online. Do not import or translate legacy `trial_lock.json` state. Whether the inert file is merely ignored or later removed remains an implementation detail. |
| OA-D04 | What is authoritative after online activation? | Candidate | D1 owns grants, bindings, trial periods, and revocation. A server-signed local lease is a bounded projection used for startup and offline allowance. Confirm this exception to local product authority. |
| OA-D05 | How are download and activation separated inside the shared Worker/D1? | Open | Candidate: route modules, domain services, dedicated tables, scoped CORS, and secret access discipline. Any accepted design must record that these are logical boundaries only. |
| OA-D06 | What durable vocabulary should code and documents use? | Open | Candidate: `entitlement` names the durable grant; `activation` names activation-code exchange; UI continues to say “activation”. |
| OA-D07 | What does one activation code grant? | Decided by Sir | One high-entropy activation code represents one perpetual, revocable grant with at most one active device binding. Exact retries are idempotent; the already-bound device may recover without rebinding; another device is denied. Transfer requires an operator reset that invalidates the old binding and issues a new one-time code. |
| OA-D08 | What identifies a trial subject? | Open with recommendation | Use the proof-bearing installation key plus a domain-separated, server-peppered `SystemIdentification` projection for best-effort reinstall correlation. Never retain the raw system id; fail open when the signal is unavailable or weak. |
| OA-D09 | What is the offline policy? | Open | Decide whether initial use is always online, refresh cadence, offline allowance for trial and licensed grants, and behavior after allowance expires. |
| OA-D10 | How does the client authenticate a server decision? | Candidate | Standard TLS plus Ed25519-signed compact response with `kid`, audience, device binding, nonce, issue/refresh/expiry times, and policy revision. |
| OA-D11 | Should the client pin a Cloudflare TLS certificate or SPKI? | Open with recommendation | Current recommendation is no: Cloudflare rotates edge/backup certificates. Pin the Xenix response-signing public key instead. Confirm whether hostile trusted-root proxies are in scope. |
| OA-D12 | What D1 data shape and concurrency rule preserve correctness? | Open | Define grants, code digests, device bindings, trials, idempotency, revocation, and audit. Prefer unique constraints and atomic conditional writes; identify any case that truly needs stronger coordination. |
| OA-D13 | How are activation codes issued and administered without a user system? | Open | Candidate: an operator-only local CLI using Cloudflare credentials, printing a high-entropy code once and writing only its digest. No public admin API in the first release. |
| OA-D14 | May Preview Workers read or write production activation tables? | Open and release-blocking | Current workflow passes configured D1 identity to Preview. Choose isolated local/test data, read-only behavior, or a strict non-mutating Preview mode before activation code reaches that workflow. |
| OA-D15 | What device and network data may the service retain? | Open | Decide fields, hashing, purpose, retention, deletion, diagnostic exposure, audit access, and user-facing disclosure. Do not store raw hardware identifiers without an explicit need. |
| OA-D16 | Is the packaged Trial LLM provider part of online activation scope? | Open and security-relevant | Online activation does not protect an embedded provider key. Decide whether it is removed, separately proxied/metered, or explicitly outside the first activation release. |
| OA-D17 | Where and when does native startup evaluate entitlement? | Open | Preserve early gating without blocking the Qt UI thread. Define first-run activation UI, cached-lease fast path, background refresh, retry, and diagnosable failure copy. |
| OA-D18 | Which failures are durable product states? | Candidate | `trial_active`, `licensed`, `expired`, and `revoked` may be durable. Timeout, DNS failure, invalid signature, service error, and rate limit are operation outcomes, not entitlements. |
| OA-D19 | How are signing keys rotated? | Open | Define active and next public keys, `kid`, overlap order, maximum old-lease life, Worker secret update, client compatibility, and emergency compromise response. |
| OA-D20 | What does health prove in a shared service? | Open | Separate liveness from D1/migration/signing readiness. Health must not sign test grants, leak configuration, or hide a broken activation dependency behind the download URL check. |
| OA-D21 | How does shared deployment change rollback? | Open | D1 migrations precede Worker deployment and are not rolled back with code. Define expand/contract compatibility so old download and activation code remain safe during rollout and rollback. |
| OA-D22 | What does licensed “same device” mean? | Open with recommendation | Define it as proof of possession of the originally bound Ed25519 device key, protected at rest by user-scoped DPAPI. It identifies a retained Xenix user-profile identity, not a physical chassis or human. |
| OA-D23 | What happens when the device key is lost or the Windows user changes? | Open with recommendation | Treat runtime-home reset, clean Windows reinstall, unrecoverable DPAPI state, and another Windows user as a new device requiring operator reset. Never auto-rebind a paid grant from a spoofable machine signal. |
| OA-D24 | Is TPM-backed identity required in V1? | Open with recommendation | No. Defer Platform Crypto Provider ECDSA/attestation until abuse evidence justifies a second key-provider path, TPM lifecycle support, and its compatibility/privacy cost. |

## Discussion Rule

Update one row when new evidence changes a decision. If an answer changes the
approved infrastructure constraint, product scope, or intended security level, revise
the packet before producing an implementation handshake.
