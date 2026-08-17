# Online Activation Threat Model

**State:** discussion input

## Protected Assets

- authority to create, bind, refresh, revoke, or restore a grant;
- Worker signing private key and operator Cloudflare credentials;
- activation-code plaintext before redemption;
- correctness of trial start/end and device-limit accounting;
- device and network privacy data;
- availability of both activation and the existing download API;
- authenticity of native cached startup permission.

## Trust Boundaries

```text
user input / local machine
    -> native client and local protected state
    -> hostile or unreliable DNS/network/proxy
    -> Cloudflare edge and existing Worker
    -> existing D1
    -> operator-only issuance/revocation tooling
```

The packaged native client is inspectable and patchable. Worker code and D1 are
remote authorities, but a malicious or compromised Worker deployment can read every
binding available to the shared Worker and can sign false responses while it controls
the signing key.

## Threat Matrix

| Threat | Candidate control | Residual truth |
| --- | --- | --- |
| DNS response points to an attacker | HTTPS CA and hostname verification; DNSSEC as zone hygiene | Correct TLS fails closed. Pure blocking remains a denial of service. |
| Network attacker changes an allow/deny response | Ed25519 application signature, audience, nonce, device binding, time bounds | Attacker can block or replay within remaining bounds but cannot forge new claims without the signing key. |
| Host trusts a hostile enterprise/debug root | Application signature still protects response authenticity | Proxy may read the activation code unless request-layer encryption is added. |
| Old valid response is replayed | Request nonce echo, device binding, `jti`, expiry, policy revision, local max-seen state | Offline revocation is impossible before the existing lease boundary. |
| Activation code is guessed | At least 128 bits of randomness, bounded attempts, rate limiting, digest-only storage | A leaked plaintext code remains a bearer secret until bound/revoked. |
| Activation is submitted concurrently | D1 unique constraints, atomic conditional write/transaction, idempotency | A read-then-write implementation can still oversubscribe and is forbidden. |
| D1 contents leak | No plaintext codes or private keys; minimum device data; bounded audit | Grant metadata and hashed identifiers may still be sensitive. |
| Worker secret leaks | Secret binding, no logs/response/D1 copy, narrow code path, protected deployment | Same Worker is one security domain; any deployed code can potentially exfiltrate the binding. |
| Download change breaks activation or vice versa | Modular routes, Worker integration tests, staged compatible migrations, end-to-end smoke | Shared Worker/D1 intentionally retains one blast radius. |
| Preview mutates real grants | Explicit Preview policy and executable isolation proof | Current workflow passes configured D1 identity and is unsafe to assume isolated. |
| Local lease file is edited | Server signature and device binding; atomic storage | Client patching can bypass verification; local enforcement is never unbreakable. |
| Lease and identity files are copied to another PC/user | User-scoped DPAPI plus a local private-key proof before lease use | A complete VM/profile clone or key extracted from the running process can remain indistinguishable. |
| Device key is lost after reset, profile loss, or Windows reinstall | Explicit operator reset, binding-epoch increment, and a newly issued code | Automatic paid rebind from a spoofable machine signal is intentionally rejected. |
| User rolls back clock/state | Last verified server time, bounded lease, monotonic/backward checks | Reboot, backup restore, VM snapshot, and patched clients limit certainty. |
| User deletes state or reinstalls to repeat a trial | Domain-separated and server-peppered stable system signal when available | Without account/payment/attestation, repeat-trial prevention is best effort; weak/unavailable signals fail open under the recommendation. |
| Stable trial signal becomes a cross-product tracking id | Never upload/store the raw system id; Xenix domain separation, server pepper, purpose/retention limits | A persistent pseudonym remains device-related data and needs disclosure and deletion policy. |
| Worker or D1 is unavailable | Cached valid lease if policy permits; bounded retry and honest UX | First activation/trial cannot succeed offline. |
| Signing key rotates normally | `kid`, overlapping client key ring, bounded old leases | Removing a key before old clients update causes an outage. |

## Certificate Pinning Assessment

Cloudflare documents that it regularly rotates edge certificates and does not
support HPKP for its managed certificates. Backup certificates can use different
private keys and certificate authorities. Hard-pinning the current leaf certificate
or Cloudflare edge SPKI therefore converts normal renewal or disaster recovery into a
client outage.

Primary sources:

- [Cloudflare certificate pinning](https://developers.cloudflare.com/ssl/reference/certificate-pinning/)
- [Cloudflare backup certificates](https://developers.cloudflare.com/ssl/edge-certificates/backup-certificates/)
- [Cloudflare certificate validity and renewal](https://developers.cloudflare.com/ssl/reference/certificate-validity-periods/)

Current recommendation:

1. keep normal system CA and hostname validation;
2. never ignore TLS errors or follow an HTTPS-to-HTTP downgrade;
3. pin Xenix's Ed25519 application-signing public keys in the native client;
4. enable DNSSEC and Certificate Transparency monitoring as operational defenses;
5. use offline allowance only as an explicit availability policy.

This protects response authenticity even when a trusted-root proxy can terminate TLS.
It does not hide the activation code from that proxy. If request confidentiality
against hostile trusted roots is a requirement, evaluate a standard request-envelope
scheme separately; do not invent ad hoc cryptography or call response signing
encryption.

Relevant platform sources:

- [Workers Web Crypto](https://developers.cloudflare.com/workers/runtime-apis/web-crypto/)
- [Workers secrets](https://developers.cloudflare.com/workers/configuration/secrets/)
- [Cloudflare DNSSEC](https://developers.cloudflare.com/dns/dnssec/)
- [Certificate Transparency monitoring](https://developers.cloudflare.com/ssl/edge-certificates/additional-options/certificate-transparency-monitoring/)

## Shared Worker and D1 Risk Acceptance

Sir's infrastructure decision intentionally accepts:

- one deployable code artifact;
- one set of Worker bindings and their code-visible trust domain;
- one D1 availability and migration boundary;
- one rollback coordination problem;
- one Preview configuration surface;
- one operational credential family.

The design response is disciplined internal ownership and strong regression proof,
not a claim of isolation:

- route-specific middleware and CORS;
- activation modules that receive the smallest binding surface practical;
- dedicated tables and repositories;
- additive, backward-compatible migrations;
- tests that exercise download and activation together;
- protected secret injection and deploy approval;
- explicit Preview non-production behavior;
- logs and health that identify which domain is degraded.

## Out-of-Scope Adversaries and Claims

- A user who can patch the executable can bypass a local startup branch.
- No protocol can prove that two installations belong to the same human without
  another identity root.
- DNS security cannot guarantee network reachability.
- Application response signing does not protect against a malicious Worker holding
  the current private signing key.
- Code signing and binary integrity may raise tampering cost but do not turn a local
  client into a trusted enforcement environment.

These are limits to state honestly, not reasons to omit bounded abuse controls.
