# Local Development Closeout

Use this guide to separate reproducible development output from durable evidence and application state before a release. [Contributor workflow](../../CONTRIBUTING.md) owns commands and pinned toolchain versions; [Runtime State](runtime-state.md) owns application data and recovery.

Compare the active Python/PDM and SVC versions with the repository declarations, then synchronize the existing lockfile with `pdm sync --clean -G :all`. A closeout does not need dependency upgrades or a new lock resolution. VSCode pre-launch should run `pdm run prepare`; dependency synchronization is an explicit setup task rather than a repeated launch prerequisite.

Lint/type-check caches and obsolete review bundles are reproducible output. Before removing them, identify exact workspace paths and running consumers; retain the latest useful verification evidence. Do not classify an entire build directory as disposable: it may contain benchmark reports, local provider settings, OCR outputs or diagnostics that historical task packets reference.

Local runtime homes, original mock data, managed artifacts, provider configuration, the active virtual environment and release manifests are separate from caches. Follow their owning lifecycle or backup procedure instead of deleting them during a generic workspace sweep. A dirty Git tree and disk usage measure different things; ignored local data can be large while a tracked checkout is clean.

Close task packets with an explicit stage status and preserve original evidence paths. Promote current principles into their durable document owner, retain uncertainty in the task archive and mark release notes as preparation until publication. Prior-version review bundles are evidence for tested functionality, not final release artifacts.
