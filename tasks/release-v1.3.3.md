# v1.3.3 Release Packet

## Objective

Publish Xenix Native v1.3.3 with a self-contained native Knowledge OCR runtime,
so a released worker never resolves its pipeline configuration from a build
machine path, its current directory, or a companion `OCR.yaml` file.

## Guardrails

- Promote only the reviewed same-repository `develop -> main` result; do not
  merge or push `main` locally.
- The immutable `v1.3.3` tag must name that exact promotion merge commit and
  declare project version `1.3.3`.
- Leave unrelated local workflow, ignore-rule, task, and activation work out of
  this release commit.
- Publish only through the tag-triggered `Native Release` workflow; never
  replace or remove an immutable object or a pushed tag.

## Verification

- Focused native-runtime tests, repository checks, smoke tests, package, and
  packaged smoke pass before promotion.
- Promotion Native CI passes on the `develop -> main` pull request.
- Local release identity binds `v1.3.3` to the resulting `main` promotion
  commit before the tag is pushed.
- The tag-triggered Native Release workflow builds and verifies the isolated
  OCR runtime, packages the application, and publishes the canonical feed.

## Current Truth

- v1.3.2's native worker can fail when PaddleOCR's default configuration
  attempts to find source-tree `OCR.yaml` through a compile-time path.
- v1.3.3 passes an explicit compiled-in PaddleX configuration, disables the
  upstream default-config fallback, maps build paths deterministically, and
  verifies the archive from a foreign working directory after removing the
  builder checkout.
- Promotion PR #117 merged as `c84a06417cdc7072e90dc856a69aed3c41c283a3`.
  Its Native CI run `30338823462` passed, then local and remote identity checks
  bound immutable tag `v1.3.3` to that exact promotion result.
- Native Release run `30339319574` passed on its first attempt. It rebuilt the
  isolated native runtime, passed frozen-package smoke, published immutable
  objects, and updated `releases.win-x64-stable.json` last.
- The released OCR archive is 205,202,103 bytes:
  `xenix-knowledge-ocr-win-x64-paddle-inference-3.3.0-paddleocr-3.7.0-win-x64-55912b1496f9d3ee6f631070de192e892cee621a84304e41722b420d688a4092.zip`.
  Its full SHA-256 is
  `55912b1496f9d3ee6f631070de192e892cee621a84304e41722b420d688a4092`.
- Publisher time was 838.65 seconds and final visibility verification was
  387.05 seconds. The canonical stable feed now declares v1.3.3.

## Next Step

No release action remains. Retain the immutable tag, workflow evidence,
release manifest, OCR catalog, publication timing, and rollback-history key.
