# Managed AMD Runtime

Use this route for the optional AMD one-click profile only. The feature is a local
control plane for a pre-enrolled Private SSH target or a compatible Local Linux
Radeon host; it is not a hosted Xenix backend and Private SSH is not offline.

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

- Start from the guided setup surface. It accepts only `This computer` or an
  already enrolled Private SSH target and installs the fixed supported profile.
  It does not create hosts, start `sshd`, accept an unknown host key, select a
  model, tune GPU/cache/ports, or fall back to CPU or an API.
- The target must pass manifest compatibility, capacity, pinned trust, and
  authenticated-loopback preflight before acquisition. Failure is an admission
  result; do not repair it by manually changing product state.
- Installation/generation lifecycle is stored locally. Target processes, files,
  loopback forwards, URLs, ports, bearer secrets, and health are live session
  facts. Do not copy them into settings, diagnostics, or support tickets.
- Reconcile and repair are forward-only. A broken current user operation fails
  honestly; a later explicit operation may rematerialize the same verified
  generation. Do not use a PID file alone to stop a target process.

## Retirement and Feature Removal

Retire an installation from the guided surface. Remove immediately commits
durable desired absence and reports `retiring requested`; it does not wait for a
large model download, tunnel, or target cleanup. That commit revokes an
in-flight deployment through a memory-only signal and, where the placement can
prove the exact target-side recipe identity, an identity-fenced stop. Normal
install, repair, and resume never use this stop path.

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

Collect only redacted installation ID, generation/manifest digest, phase, typed
failure code, and local log/diagnostic bundle references. Never include private
keys, host keys, bearer secrets, live endpoint URLs, ports, PIDs, raw model paths,
or document/provider payloads.
