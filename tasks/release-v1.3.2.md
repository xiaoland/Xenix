# v1.3.2 Release Packet

## Status

Implementing the content-addressed Knowledge OCR artifact correction before a new
`develop -> main` promotion.

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

## Next Step

Validate the producer and existing portfolio, then promote v1.3.2 through Native
CI before creating its immutable tag.
