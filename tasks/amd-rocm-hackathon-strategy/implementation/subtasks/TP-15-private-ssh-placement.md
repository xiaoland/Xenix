# TP-15 — Private SSH Placement

## Outcome

Implement a placement-neutral long-lived inference target over OpenSSH without
depending on the existing batch ML worker lifecycle.

## Owned Mutation

- add `src/xenix/services/amd/placements/ssh.py`;
- add `src/xenix/services/amd/remote_supervisor.py`;
- add `tests/test_amd_ssh_placement.py`.

`services/ml/worker_pool.py`, `ml/execution.py`, `ml/ssh_worker_setup.py`, and ADR
0005 remain unchanged.

## Target Contract

- operator supplies a pre-enrolled reachable supported SSH target plus an explicit
  opaque public-key credential reference and isolated pinned host-trust reference;
- v1 supports no password, TOFU, changed-key continuation, or implicit global SSH
  config/agent fallback; no private-key material/path is copied to target or
  installation state;
- generation-owned target roots and controller owner/incarnation fencing;
- exact process group, executable, start identity, command fingerprint,
  generation, manifest, and runtime incarnation;
- remote-loopback services and local-loopback forwarding only;
- keepalive/disconnect detection, occupied-port retry, deadline, reap, and bounded
  orphan policy;
- PID files are observations, never stop/delete authority.

Xenix does not provision the cloud instance, start its initial sshd, upgrade its
OS, expand its storage, or improvise a Python toolchain. Missing prerequisites are
typed unsupported-target failures before acquisition.

Enrollment is a separate safety action before one-click deployment. It records an
immutable AMD-private target ID over host/user/port, pinned host-key identity, and
an explicit local identity-file reference. Changing any of those facts creates a
new target/installation; deployment never silently edits trust.

The captured cloud has no active systemd manager, so the placement owns process
supervision. Clean shutdown stops verified live runtime processes/forwards while
retaining installed generations; crash recovery fences verified orphans.

## Acceptance

- fake SSH server covers trust change, auth failure, disconnect, target reboot,
  occupied port, stale callback, PID/port reuse, second controller, and cleanup
  mismatch;
- controller loss cannot let an old owner stop a new incarnation;
- no remote endpoint is publicly exposed;
- target cleanup refuses unknown/adjacent files and processes;
- application secrets and business content are redacted.
- each runtime incarnation uses a generated bearer secret via protected handoff;
  unauthenticated requests are rejected and the secret never appears in persisted
  command summaries, settings, logs, diagnostics, or evidence.

## Verification

- focused deterministic SSH placement tests;
- OpenSSH command/quoting review on Windows and Linux;
- `pdm run check`.
