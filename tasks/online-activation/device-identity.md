# Device Identity and “Same Device”

**State:** candidate recommendation; OA-D22, OA-D23, and OA-D08 remain to be
decided

## Definition Before Mechanism

“Same device” is not one fact. The first release needs two deliberately separate
answers:

| Question | Candidate authority | Security level |
| --- | --- | --- |
| Is this the installation that already owns a licensed grant? | Proof of possession of the originally bound device private key | Cryptographic, subject to the limits of a patchable local client |
| Has this physical or virtual machine probably received a trial before? | A privacy-bounded stable Windows signal plus the installation key | Best-effort abuse correlation only |

A hardware serial, registry value, or hash of several properties does not prove
possession of a secret. Conversely, a random device key survives only while its
protected local state survives and cannot by itself detect a reinstall that deletes
that state.

## Recommended V1 Licensed Identity

Define a licensed “same device” as:

> the same Xenix runtime identity, under the same Windows user protection boundary,
> that can prove possession of the Ed25519 private key originally bound to the
> grant.

On the first online entitlement operation:

1. generate one Ed25519 key pair from the operating-system CSPRNG;
2. serialize the public key as the canonical 32-byte Ed25519 raw public key;
3. protect the private key using user-scoped Windows DPAPI
   `CryptProtectData` without `CRYPTPROTECT_LOCAL_MACHINE`;
4. publish the identity file atomically under Xenix config state;
5. send the public key and a signature over the canonical activation request;
6. let the Worker recompute
   `base64url(SHA-256("xenix-device-key/v1\0" || raw_public_key))`;
7. bind the grant to that digest and public key in the existing D1.

The client must never trust a client-supplied key digest when the Worker can derive
it from the supplied public key.

Every activation recovery and refresh request proves the same key possession by
signing its versioned canonical payload, including action, product, public-key
digest, request id, fresh nonce, and operation-specific fields. Exact replays are
made harmless by idempotency and return the same logical result. A separate
server-challenge round trip may be added only if a later threat requires proof of a
fresh server-selected nonce; it is not needed merely to make one-device binding
correct.

## Local Ownership and Storage

Candidate ownership:

```text
%LOCALAPPDATA%\Xenix\
  config\
    device_identity.json       long-lived identity; DPAPI ciphertext, never plaintext
  state\
    activation_state.json      replaceable signed lease and bounded refresh metadata
```

The exact filenames remain implementation detail, but the ownership split is not:

- the device identity changes only when explicitly created or recovered;
- a lease can be replaced after each valid server decision;
- neither belongs in SQLite because the entitlement gate runs before SQLite
  bootstrap;
- neither reuses `config/telemetry.json`. The observability installation id is
  replaceable, exported in diagnostics/telemetry, and explicitly is not a machine
  identity;
- identity and lease publication use same-directory temporary files, flush/fsync,
  and atomic replace;
- private material, DPAPI ciphertext, activation codes, and full leases never enter
  logs or diagnostic bundles.

Candidate identity envelope:

```json
{
  "schema_version": 1,
  "algorithm": "Ed25519",
  "public_key": "<base64url raw 32-byte key>",
  "protected_private_key": "<base64url DPAPI blob>",
  "created_at": "<UTC timestamp>"
}
```

DPAPI is the at-rest protection boundary. The proof of possession comes from the
signature, not from the existence of the blob. On every startup that consumes a
cached lease, the client should decrypt the key, derive or verify its public key,
and complete a local random challenge/sign/verify check before accepting the lease.
Copying only the signed lease therefore does not copy usable startup permission.

## Why User-Scoped DPAPI

Xenix is currently a per-user Windows application with a per-user runtime home.
User-scoped DPAPI normally requires the same Windows logon credentials on the same
computer. That matches the existing installation and state boundary.

`CRYPTPROTECT_LOCAL_MACHINE` is not the default recommendation: Microsoft documents
that any user on that computer can decrypt data protected with that flag. It would
silently redefine the product from one Xenix user profile to all local users.

Credential Manager does not improve the identity proof. It can hold an
application-defined blob, but the signature still supplies proof of possession and
its persistence modes introduce additional roaming choices. A small explicit DPAPI
envelope has the narrower interface for V1.

## Lifecycle Matrix

| Event | V1 classification | Reason / recovery |
| --- | --- | --- |
| Normal Xenix update | Same device | Velopack package state and `%LOCALAPPDATA%\Xenix` are separate |
| Setup run again while runtime home is retained | Same device | Identity file and DPAPI user boundary remain |
| Same-machine backup restored to the same user profile | Same device if DPAPI decrypts | Verify key before accepting the cached lease |
| Activation lease deleted but identity retained | Same device | Refresh, or re-enter the same code and prove the bound key |
| Full Xenix runtime-home reset | New identity | Device key is intentionally lost; operator reset is required |
| Different `XENIX_APP_HOME` | Different identity state | The override deliberately selects an isolated runtime |
| Different Windows user on the same PC | Different identity under the recommendation | User-scoped DPAPI cannot be assumed readable |
| Clean Windows reinstall or user-profile loss | New identity | Do not auto-rebind a paid grant from a spoofable fingerprint |
| Copy identity/lease files to another PC | Not the same device in the normal case | The copied DPAPI blob normally cannot be decrypted there |
| Complete VM/profile clone | Indistinguishable from the same identity | Software-only V1 cannot reliably detect a copied DPAPI/key environment |
| Key extraction from the running process or patched client | Outside the enforceable boundary | A local inspectable client is not a trusted execution environment |

The repository structure supports update persistence, but uninstall/reinstall
retention still needs the planned Windows VM acceptance run. The protocol must
handle loss explicitly rather than assuming an installer guarantee.

## D1 Binding and Concurrency

The minimum invariant is one active binding per grant, not one grant per device:

```text
activation_devices
  device_key_hash PRIMARY KEY
  algorithm
  device_public_key
  first_seen_at / last_seen_at

activation_bindings
  grant_id PRIMARY KEY
  device_key_hash REFERENCES activation_devices
  binding_epoch
  bound_at
  refresh_seq
```

`device_key_hash` is not globally unique in the binding table because one
installation owning more than one grant has not been prohibited. `grant_id PRIMARY
KEY` makes two-device redemption invalid even under concurrency.

Activation behavior:

1. Worker verifies the request signature before attempting a binding.
2. A D1 atomic conditional write/batch consumes the issued code and creates the
   binding. An unguarded read followed by an insert is forbidden.
3. Two different keys racing for one code produce exactly one binding.
4. An exact request retry returns the stored logical result.
5. Re-entering the consumed code with the already-bound key is same-device recovery
   and may issue a fresh lease without changing the binding.
6. Re-entering it with another key returns `device_limit_reached`.

Operator transfer increments `binding_epoch`, invalidates the old binding, and
issues a new one-time activation code. Reopening the old code would let the old and
new devices race and is therefore not a controlled transfer. Leases include
`device_key_hash` and `binding_epoch`; an old device remains usable only until its
already-issued offline boundary.

## Trial Correlation

The installation key remains the proof-bearing identity for trial requests, but it
cannot prevent “delete state, start another trial.” The candidate supplemental
signal is `Windows.System.Profile.SystemIdentification.GetSystemIdForPublisher()`:

- it is an opaque, stable Windows system identifier whose source can be TPM, UEFI,
  or a weaker registry fallback;
- Microsoft states that it generally survives app reinstall, Windows upgrade, most
  hardware changes, and—except for the registry fallback—often a clean install;
- it is not a secret, cannot sign a challenge, can be spoofed by a modified client,
  and has undefined/weak behavior for VM cloning;
- for an unpackaged Win32 application without a publisher identity, Microsoft
  documents that other unpackaged applications receive the same raw identifier.

Therefore Xenix must never upload or store the raw identifier. Candidate projection:

```text
client_trial_signal =
  SHA-256("xenix-online-trial/v1\0" || source || "\0" || raw_system_id)

stored_trial_subject =
  HMAC-SHA-256(server_trial_pepper, client_trial_signal)
```

The client sends only its Xenix-domain-separated projection over HTTPS. The Worker
stores only the server-peppered value and a coarse source/confidence class if the
accepted policy needs it. The signal is a uniqueness/risk input, not an authority
for paid rebind, revocation, or private-key recovery.

If the API is unavailable or reports only a registry/unknown source, the product
must choose between:

- **fail open for trial** with rate limiting and an honest best-effort claim; or
- **fail closed for trial**, which excludes legitimate unsupported machines.

The recommendation is fail open for V1. Preventing every repeat trial is not worth
turning optional hardware/platform behavior into a product availability
requirement.

## TPM Option, Not V1 Default

The Windows Platform Crypto Provider can create a non-exportable TPM-backed signing
key, raising the cost of copying identity state. This is not the V1 default because:

- supported Platform Crypto Provider signing algorithms include ECDSA P-256 rather
  than the Ed25519 identity format above;
- it requires a second provider path, hardware/software fallback policy, packaging
  proof, and support for TPM clear/replacement;
- a signature alone does not attest that the key came from a TPM; attestation adds
  another protocol and privacy surface;
- a patchable client can still bypass local entitlement enforcement.

The service response-signing key and the device proof key are separate roles.
Future TPM support can use ECDSA P-256 behind a versioned device-key provider while
the Worker continues to sign leases with Ed25519.

## Decisions Requested

1. Accept licensed “same device” as the same user-scoped, DPAPI-protected Xenix
   device key, rather than a hardware fingerprint.
2. Accept key loss, a different Windows user, and clean Windows reinstall as a new
   device requiring operator reset; do not automatically rebind a paid grant from a
   machine signal.
3. Use `SystemIdentification` only as a best-effort, pseudonymized online-trial
   correlation signal and fail open when it is unavailable or weak.
4. Defer TPM-backed device keys and hardware attestation until abuse evidence
   justifies the compatibility and support cost.

## Primary Sources

- [Microsoft `CryptProtectData`](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)
- [Microsoft DPAPI example and scope notes](https://learn.microsoft.com/en-us/windows/win32/seccrypto/example-c-program-using-cryptprotectdata)
- [Microsoft `SystemIdentification`](https://learn.microsoft.com/en-us/uwp/api/windows.system.profile.systemidentification)
- [Microsoft `GetSystemIdForPublisher`](https://learn.microsoft.com/en-us/uwp/api/windows.system.profile.systemidentification.getsystemidforpublisher)
- [Microsoft CNG key storage providers](https://learn.microsoft.com/en-us/windows/win32/seccertenroll/cng-key-storage-providers)
- [Microsoft: how Windows uses the TPM](https://learn.microsoft.com/en-us/windows/security/hardware-security/tpm/how-windows-uses-the-tpm)
- [PyCA Ed25519](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/)
