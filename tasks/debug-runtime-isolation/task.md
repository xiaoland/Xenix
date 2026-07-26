# Debug Runtime Isolation

## Objective

Keep VS Code development and smoke runtime data inside the repository while preserving `%LOCALAPPDATA%\Xenix` as the installed application's default runtime authority. Move the current installed-home data into the development runtime home before removing the old source directory.

## Guardrails

- Do not change the application's production default path resolution.
- Do not merge with or overwrite a pre-existing destination runtime home.
- Delete `%LOCALAPPDATA%\Xenix` only after the copied tree is verified file-for-file.
- Preserve unrelated user changes, including the existing `.gitignore` edit.
- Do not change the ordinary GUI single-instance boundary.

## Verification

- VS Code Debug App resolves `XENIX_APP_HOME` to `.runtime/dev`.
- VS Code smoke resolves `XENIX_APP_HOME` to `.runtime/smoke`.
- `.runtime/` is ignored by Git.
- Source and destination inventories and SHA-256 hashes match before deletion.
- The AppData source no longer exists after verified deletion.

## Current Truth

- VS Code Debug App and `PDM: dev` select `.runtime/dev`.
- VS Code Debug Smoke Test and `PDM: smoke` select `.runtime/smoke`.
- `.runtime/` is ignored by Git.
- The migrated destination contains 1,410 files in 899 directories, totaling 7,527,283,115 bytes.
- Before source removal, all 1,410 source/destination file pairs matched by SHA-256 and the directory sets matched.
- The original `%LOCALAPPDATA%\Xenix` tree was removed to the Windows Recycle Bin after verification. A later installed-app launch may legitimately recreate that path as a new installed runtime home; that new state is distinct from the migrated source and remains the installed application's authority.

## Next Step

Run the installed `Xenix-Setup` version and development instance sequentially to perform the manual N-to-N+1 update acceptance. Launch the installed application without a user- or system-level `XENIX_APP_HOME` override.
