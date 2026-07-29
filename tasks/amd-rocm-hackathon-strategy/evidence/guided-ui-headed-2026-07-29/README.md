# Guided AMD UI Headed Evidence

**Date:** 2026-07-29

**Result:** headed validation and real Private SSH failure-path acceptance passed.

The task-local headed helper opened the production `AmdGuidedSetupDialog` against
an isolated Xenix runtime home. It first clicked Install with an empty form, then
submitted one complete Private SSH command against the assigned Radeon Cloud
endpoint. The endpoint accepted TCP but reset during SSH key exchange, so this
run intentionally proves truthful typed failure rather than operational
deployment.

A synthetic, algorithm-valid host public key was supplied. If the endpoint had
advanced past key exchange, strict host-key verification would have stopped at a
trust mismatch before authentication or remote mutation. No TOFU or fallback was
used.

## Observed Contract

- the empty form produced `amd_ssh_host_required`, focused
  `amdSshHostInput`, and wrote zero Settings documents, targets, or
  installations;
- the dialog exposed no Save action and no Local Linux placement;
- one valid click persisted one exact target/installation intent and reached the
  real OpenSSH boundary;
- the reset projected `not_materialized` plus
  `amd_ssh_connection_failed`, not a false compatibility verdict;
- Repair and Remove became available because the durable installation exists;
- a newly constructed production dialog rediscovered that hidden durable
  identity and re-enabled Repair/Remove without asking for a technical ID;
- the task log contained no endpoint, user, port, identity path, host key, SSH
  stderr, or raw exception message.

## Files

| File | Purpose |
| --- | --- |
| `guided-ui-headed.json` | Machine-readable, redacted assertions and result |
| `guided-ui-headed.jsonl` | Redacted structured task log |
| `guided-ui-validation.png` | Empty-form validation and field-focus result |
| `guided-ui-result.png` | Typed SSH failure with all input values redacted |

The executable helper is
[`validate_guided_ui_headed.py`](../../spikes/radeon-cloud/validate_guided_ui_headed.py).
It requires an isolated `XENIX_APP_HOME` and explicit endpoint/identity arguments;
none of those values are retained in this packet.

The already-completed product-composition run proves operational Chat,
Embedding, OCR, and exact retirement on the captured Cloud cell. A fresh
visible-dialog operational install and Remove remain the one human acceptance
journey after the cloud endpoint is restored or replaced.
