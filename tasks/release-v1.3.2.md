# v1.3.2 Release Packet

## Status

Completed. v1.3.2 is publicly visible and verified from main promotion commit
`8fbaedd5`.

## Objective

Publish Xenix Native v1.3.2 without colliding with an earlier immutable OCR
runtime object that has the same logical runtime ID but different build bytes.

## Guardrails

- Preserve the immutable v1.3.0 and v1.3.1 tags and every uploaded object.
- Do not update the canonical feed until the full v1.3.2 publisher succeeds.
- Keep runtime ID, model pack ID, protocol, client installation, and catalog
  authority unchanged; change only the archive's public content identity.
- Use the existing 30-case portfolio and static checks; do not add a publication
  regression case.
- Preserve unrelated user worktree changes.

## Verification

- The producer catalog rejects an artifact name that does not equal
  `<runtime-id>-<complete archive SHA-256>.zip`.
- `pdm run test`, `pdm run check`, and `pdm run smoke` pass.
- Promotion Native CI passes on a `develop -> main` PR.
- Release identity binds `v1.3.2` to that main promotion and its PR.
- Native OCR build, packaged smoke, immutable upload, public SHA-256/Range checks,
  and canonical feed publication all pass.

## Current Truth

- v1.3.1 run `30258978782` safely failed before feed visibility.
- The existing OCR object is 205,199,984 bytes with SHA-256 beginning `50800E0C`;
  the v1.3.1 build is 205,199,982 bytes with SHA-256 beginning `5C8992F5`.
- ZIP entry metadata is normalized, but compiled native bytes are not assumed to
  be reproducible across rebuilds. Runtime ID alone is therefore not a complete
  immutable object identity.
- The embedded catalog already owns artifact name, byte count, and SHA-256; the
  client generation ID already incorporates the artifact SHA-256.
- Commit `ef04625` was promoted through PR #116; Native CI run `30263030953`
  passed in 5 minutes 17 seconds.
- `v1.3.2` resolves to main promotion commit `8fbaedd5`; local and remote release
  identity checks bound it to PR #116.
- Native Release run `30263473671` passed in 1 hour 3 minutes 13 seconds,
  including native OCR build/self-test and packaged smoke.
- The published OCR archive is 205,199,980 bytes. Its name and catalog both carry
  SHA-256 `3e76bae9cb17bbacac0174bcd3db80a6e10617afc2f9b98c913de7850b4b1322`.
- Publisher time was 961.25 seconds and visibility/final verification was 447.39
  seconds. The public OCR object returns HTTP 200, supports byte ranges, and
  returns 206 for `bytes=0-0`; Setup returns 200 with `no-cache`.
- The canonical stable feed now declares v1.3.2.

## Next Step

No release action remains. Retain the immutable tag, workflow evidence, manifest,
runtime catalog, publication timing, and rollback-history key.
