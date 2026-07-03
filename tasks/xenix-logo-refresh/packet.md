# Xenix logo refresh task packet

## Objective & Hypothesis

Replace the current Xenix application logo with `F:\Hadream\DOWNLOAD\xenix-logo2.svg` and update the startup splash visual system to match the new orange/near-black mark.

Hypothesis: the durable product surface is mostly local to packaged resources and `src/xenix/ui/startup_splash.py`. The startup behavior, stage progression, and translated stage strings should remain unchanged unless explicitly requested.

## Guardrails Touched

- Root `AGENTS.md`: explicit user start is required before code/resource mutation.
- `src/xenix/ui/AGENTS.md`: changed user-visible UI strings require Qt translation extraction/compile and language-switch tests.
- `docs/00-meta/implementation-taste.md`: keep the visual refresh simple, with one clear resource authority and no broad UI architecture change.

## Current Understanding

- Current runtime window icon uses `package_resource_path("logo.png")`.
- Packaged executable icon uses root `logo.ico`.
- Resource bundle contains `src/xenix/resources/logo.png`, `src/xenix/resources/logo.ico`, and `src/xenix/resources/app-icon.svg`.
- Startup splash is custom-painted in `src/xenix/ui/startup_splash.py`; it currently draws a blue/steel dark shell, perspective grid, status bay, segmented pulse bar, and a hand-coded vector wordmark via `_xenix_vector_path()`.
- New SVG is a 320x320 mark with orange `#ED6609` and near-black `#242429`.

## Proposed Scope

- Replace resource logo outputs from the new SVG:
  - `src/xenix/resources/logo.png`
  - `src/xenix/resources/logo.ico`
  - `logo.ico`
  - likely `src/xenix/resources/app-icon.svg` as the vector source
- Update startup splash painting to use the new mark and a cleaner orange/near-black visual language.
- Keep startup stage enum, timing, stage text, and app startup flow unchanged.

## Verification

- Run focused tests covering resources and splash rendering:
  - `pdm run pytest tests/test_resources.py tests/test_i18n.py::test_startup_splash_renders_nonblank_canvas_offscreen`
- If startup text changes, also run i18n extraction/compile and affected language tests.
- If feasible, render/grab splash offscreen to inspect nonblank layout and logo visibility.

Result:

- `pdm run python -m compileall src\xenix\ui\startup_splash.py` passed.
- `pdm run pytest tests/test_resources.py tests/test_i18n.py::test_startup_splash_renders_nonblank_canvas_offscreen` passed: 3 tests.
- `tasks/xenix-logo-refresh/splash-preview.png` captured a 680x400 offscreen splash preview with bright background, orange logo/accent pixels, and nonblank content.
- ICO outputs contain sizes 16, 24, 32, 48, 64, 128, and 256 px.

## Next Step

Await user review. No commit has been made.
