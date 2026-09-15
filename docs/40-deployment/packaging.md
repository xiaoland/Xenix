# Packaging

## When to Use

Release operators and packaging engineers use this runbook to build or distribute Xenix, investigate a packaged-only failure, or roll back a bad bundle. A broken package blocks release even when source-mode tests pass.

## Bundle Gate

Run the source bundle checks from a clean, synchronized environment:

```text
pdm sync --clean -G :all
pdm run package
pdm run smoke-package
```

`package` produces the PyInstaller Windows bundle. `smoke-package` exercises the packaged executable and selected delayed native/data paths; when a local Knowledge OCR release artifact is present, it restores the small locked golden image if the build cache has been cleaned before exercising that runtime. These commands validate the bundle but do not authorize or publish a release. The tag-driven Velopack, manifest, and OSS procedure is owned by [Windows Distribution](windows-distribution.md).

If a running bundle holds files under the default output directory, build into a separate root instead of interrupting that application: `pdm run package --dist-dir dist/review`, then `pdm run smoke-package --executable dist/review/xenix/xenix.exe`. The alternate root still uses the same clean build, runtime resources, and isolated DLL search path. Default release commands continue to use `dist/xenix`.

Packaging embeds build-time inputs: Git commit plus the Pydantic-validated release URL, trial provider, trial lock, purchase URL, and supplied OpenTelemetry settings. Formal release builds require the complete trial configuration; public releases also require HTTPS `RELEASES_OSS_PUBLIC_URL`. Treat embedded provider secrets, lock secrets, and OTLP headers as extractable release credentials. `xenix.release_config.ReleaseConfig` owns names and validation; `scripts/package_app.py` generates one temporary frozen projection and removes it after packaging.

On Windows, `scripts/package_app.py` runs PyInstaller in a child process whose `PATH` contains only the active Python environment, its base interpreter, and Windows system directories. PyInstaller otherwise uses the caller's ambient `PATH` as a fallback DLL source, which makes the bundle depend on unrelated tools installed in the invoking shell. A native dependency that needs another search directory must be collected by its package, hook, or `xenix.spec`; do not add machine-local directories to the packaging shell's `PATH` as a collection mechanism.

The tracked `.python-version`, `pdm.toml`, and `global.json` select the release Python environment and .NET SDK. Release automation installs the declared PDM version and restores the repository-local Velopack tool. The Knowledge OCR builder resolves an explicit `XENIX_CMAKE` override first, then Visual Studio's bundled CMake, and uses ambient `PATH` only as a fallback.

Packaging success proves assembly, not usability. The smoke gate proves only the paths currently exercised by `scripts/verify_packaged_smoke.py`; it is not a guarantee for every optional dependency or workflow. Add the smallest meaningful packaged exercise when a first-party path begins depending on a new compiled extension, native library, metadata file, or package data file.

Record the build commit, build environment, commands, and smoke result as bundle evidence. Re-run the gate after dependency, spec, resource, translation, build-input, or packaging-script changes.

The packaged splash intentionally collects only its base QML modules through `scripts/pyinstaller_hooks/hook-PySide6.QtQml.py`; add a module there when the scene begins importing it rather than restoring PyInstaller's full QML-tree collection.

## Packaged-Only Failures

Start with the smoke gate and its failing boundary. Inspect PyInstaller analysis/collection evidence and the built `_internal` tree for missing native libraries, metadata, or data files; a successful analysis-time import does not prove delayed runtime loading.

- For Polars CPU-feature failures, verify the compatible runtime is packaged and dependency versions agree. Do not bypass the CPU check.
- For compiled ML/data libraries, exercise the public API Xenix uses, preferably with a tiny in-memory operation.
- For Vega-Lite or word-cloud failures in the windowed build, test those renderers separately: console availability, converter behavior, fonts, and native resources differ.
- For missing resources, compare the spec, source resource location, and packaged path before adding broad collection rules.

## Release Failure and Rollback

Block distribution, preserve the failed bundle and logs as evidence, fix the owning source/spec/script, then rebuild and rerun the bundle gate. For an already published release, follow the rollback boundary in [Windows Distribution](windows-distribution.md); package rollback does not restore or downgrade user databases.
