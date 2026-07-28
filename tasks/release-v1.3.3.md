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
- The candidate native archive is
  `xenix-knowledge-ocr-win-x64-paddle-inference-3.3.0-paddleocr-3.7.0-win-x64-5f661643218c1028e5dc111321ced3e14bc82a9ce9774a31ff60f9e753a5b5ae.zip`.

## Next Step

Commit the bounded v1.3.3 candidate to `develop`, promote it to `main`, then
create and push the immutable tag after the promotion gate passes.
