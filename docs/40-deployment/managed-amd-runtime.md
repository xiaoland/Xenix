# Managed AMD Runtime

Use this route for the optional AMD one-click profile only. The feature is a
Windows-desktop control plane for a Private SSH Linux Radeon target; it is not a
hosted Xenix backend, an ML Worker target, or an offline mode.

## Inclusion and Staged Cut-off

The AMD slice is included by the default desktop package and is disabled by
default for a source run unless explicitly enabled. Packaging owns the exact
build/runtime switches and the two-package proof in
[Packaging](packaging.md#optional-amd-one-click-slice).

For a released feature retirement, use a slice-containing build with new
deployment disabled (`retirement-only`) until every installation and exact target
realization is retired. Only then may a later package omit the slice. The build
switch controls local composition; it never grants authority to remove an
unverified remote path.

## Safe Operation

- Start from the AMD guided setup surface, not ML Worker settings. Enter the SSH
  host, user, port, local identity-file path, and one independently verified
  server host public key. `Install` validates the whole form, saves an immutable
  enrollment, and starts the fixed profile in one explicit action; there is no
  separate Save or pre-enrollment screen.
- The accepted host-key forms are one OpenSSH public-key line
  (`key-type base64 [comment]`) or the exact endpoint-matching, un-hashed
  `known_hosts` line. A fingerprint, private key, login public key, wildcard/
  hashed host pattern, mismatched endpoint prefix, multi-line scan, or
  algorithm/blob mismatch is rejected. Xenix does not discover or trust a host
  key through TOFU.
- The workflow does not create hosts, start `sshd`, select a model, tune
  GPU/cache/forward ports, or fall back to CPU, ML Worker, or an API.
- The target must pass manifest compatibility, capacity, pinned trust, and
  authenticated-loopback preflight before acquisition. Input failures start no
  worker and identify the affected field. Connectivity, compatibility, and
  component failures retain a stable support code and a durable installation
  handle only when one actually exists. An unreachable target is shown as not
  installed or degraded; `incompatible` is reserved for measured profile
  constraint failures.
- Installation/generation lifecycle is stored locally. Target processes, files,
  loopback forwards, URLs, ports, bearer secrets, and health are live session
  facts. Do not copy them into settings, diagnostics, or support tickets.
- Reconcile and repair are forward-only. A broken current user operation fails
  honestly; a later explicit operation may rematerialize the same verified
  generation. Exact retries preserve completed enrollment checkpoints; they do
  not delete or overwrite them as compensation. Do not use a PID file alone to
  stop a target process.
- Installation/target IDs are internal. On restart, the guided surface discovers
  every non-removed managed installation from SQLite and offers a stable,
  non-technical selector only when multiple identities need management. If SSH
  security setup stopped after that SQLite checkpoint, the immutable endpoint is
  restored and the user re-enters only the identity file and verified host key
  before choosing `Continue setup`. A status/security read error never converts
  unknown availability into absence; SQLite desired presence and lifecycle still
  fence Repair and Remove.

## Retirement and Feature Removal

Retire an installation from the guided surface. The control-plane request
immediately commits durable desired absence without waiting behind a large model
download or tunnel. The UI worker then observes exact cleanup through
`removed`, `retiring`, or a typed `removal_blocked` result; an older
Install/Repair completion cannot overwrite that newer Remove intent. The commit
revokes an in-flight deployment through a memory-only signal and, where the
placement can prove the exact target-side recipe identity, an identity-fenced
stop. Normal install, repair, and resume never use this stop path.

The target-side retirement operation first writes an exact generation tombstone
under that generation's control fence. Provisioning, asset transfer, and runtime
start all reject that tombstone. The service then closes new admission, removes
owner projections only after blockers are resolved, and cleans identity-matched
target realization. A stopped provisioning receipt may retain partial acquisition
until that cleanup can prove ownership and an empty process group; only that
identity-matched cleanup removes the tombstone. It never rewrites selections or
historical model references to make retirement succeed.

Manifest source locators define artifact identity. A recipe may use an explicitly
implemented transport mirror for availability, but it must verify the declared
byte size and SHA-256 before use and must not substitute a different source,
revision, model, or runtime when the mirror or official locator fails.

For a released feature cut-off, first ship a release that disables new deployment
and retires every installation. After inventory proves no live realization or
projection remains, a later release can omit the AMD composition slice. Do not
delete source to clean a remote target: removal of source is not authorization to
terminate an unknown process or delete an unverified path.

## Evidence and Support

The UI displays a localized explanation plus a stable support code. AMD guided
logs contain only the operation, success/installation-available and
security-checkpoint flags, derived condition/phase, optional input-field name,
stable error code, and (for an exceptional path) exception class name. They do
not contain host, user, port, identity path, host key, SSH output, request
representation, or exception message.

Collect only redacted installation ID, generation/manifest digest, phase, typed
failure code, and local log/diagnostic bundle references. Never include private
keys, host keys, bearer secrets, live endpoint URLs, ports, PIDs, raw model paths,
or document/provider payloads.
