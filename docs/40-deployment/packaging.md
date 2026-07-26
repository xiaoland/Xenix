# Packaging

## When to Use

Release operators and packaging engineers use this runbook to build or distribute Xenix, investigate a packaged-only failure, or roll back a bad bundle. A broken package blocks release even when source-mode tests pass.

## Release Gate

Run the release sequence from a clean, synchronized environment:

```text
pdm run package
pdm run smoke-package
pdm run dist
```

`package` produces the Windows bundle. `smoke-package` exercises the packaged executable and selected delayed native/data paths. `dist` creates the distributable archive. Do not distribute if any stage fails.

Packaging embeds build-time inputs: Git commit plus the Pydantic-validated release URL, trial provider, trial lock, purchase URL, and supplied OpenTelemetry settings. Formal release builds require the complete trial configuration; public releases also require HTTPS `RELEASES_OSS_PUBLIC_URL`. Treat embedded provider secrets, lock secrets, and OTLP headers as extractable release credentials. `xenix.release_config.ReleaseConfig` owns names and validation; `scripts/package_app.py` generates one temporary frozen projection and removes it after packaging.

Packaging success proves assembly, not usability. The smoke gate proves only the paths currently exercised by `scripts/verify_packaged_smoke.py`; it is not a guarantee for every optional dependency or workflow. Add the smallest meaningful packaged exercise when a first-party path begins depending on a new compiled extension, native library, metadata file, or package data file.

Record the build commit, build environment, commands, smoke result, and archive checksum as release evidence. Re-run the whole chain after dependency, spec, resource, translation, build-input, or packaging-script changes.

## Packaged-Only Failures

Start with the smoke gate and its failing boundary. Inspect PyInstaller analysis/collection evidence and the built `_internal` tree for missing native libraries, metadata, or data files; a successful analysis-time import does not prove delayed runtime loading.

- For Polars CPU-feature failures, verify the compatible runtime is packaged and dependency versions agree. Do not bypass the CPU check.
- For compiled ML/data libraries, exercise the public API Xenix uses, preferably with a tiny in-memory operation.
- For Vega-Lite or word-cloud failures in the windowed build, test those renderers separately: console availability, converter behavior, fonts, and native resources differ.
- For missing resources, compare the spec, source resource location, and packaged path before adding broad collection rules.

## Release Failure and Rollback

Block distribution, preserve the failed bundle and logs as evidence, fix the owning source/spec/script, then rebuild and re-run all three stages. If a distributed build is unsafe or unusable, withdraw it and restore the previous verified archive. Rollback means redistributing a known-good bundle; it does not roll back user databases. Verify the restored bundle with its recorded smoke evidence and a fresh runtime home before announcing recovery.
