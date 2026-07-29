# Diagnosis Evidence

Date: 2026-07-29

## Reproduction State

The active development runtime was copied into an isolated diagnostic runtime
without reusing its settings lock. The source state contained:

- SQLite size: `92,073,984` bytes
- Knowledge documents: `1`
- Knowledge units: `67`
- Knowledge index tasks: `3`
- Published vector generations: `1`
- AMD installations/component generations: `0 / 0`

The isolated copy was deleted after measurement because it contained copied
provider settings.

## Blocking Topology

```text
Settings button click
  -> MainWindow._open_settings
    -> SettingsDialog.__init__
      -> retranslate_ui
        -> _render_index_status
          -> KnowledgeIndexService.status
            -> KnowledgeSemanticService.inspect_index
              -> _usable_generation
                -> LanceKnowledgeVectorStore.generation_is_usable
                  -> import/open LanceDB
                  -> validate schema and row count
                  -> read and compare every unit ID
                  -> gc.collect
    -> SettingsDialog.show
      -> showEvent
        -> _render_index_status
          -> the same deep validation again
```

Source anchors:

- `src/xenix/ui/main_window.py:399`
- `src/xenix/ui/settings_dialog.py:344`
- `src/xenix/ui/settings_dialog.py:477`
- `src/xenix/ui/settings_dialog.py:667`
- `src/xenix/ui/settings_dialog.py:1021`
- `src/xenix/services/knowledge_index_service.py:168`
- `src/xenix/services/knowledge_semantic_service.py:88`
- `src/xenix/services/knowledge_semantic_service.py:344`
- `src/xenix/services/knowledge_vector_store.py:204`
- `src/xenix/services/knowledge_vector_store.py:614`

## Timings

One standalone Python 3.14.2 process used the real Qt signal path against the
isolated runtime:

| Segment | Elapsed |
| --- | ---: |
| First Settings click, total | `2.110632 s` |
| First `KnowledgeIndexService.status` | `1.859415 s` |
| Repeated status from `showEvent` | `0.217669 s` |
| First LLM settings snapshot | `0.000417 s` |
| First Embedding settings snapshot | `0.008625 s` |
| ML worker settings load | `0.000106 s` |
| Second click with cached dialog | `0.187622 s` |
| First click with index service absent | `0.016785 s` |

A separate service-only run measured the first
`KnowledgeSemanticService.inspect_index` at `1.929263 s`; warm calls were
approximately `0.085 s`.

Therefore the two synchronous status calls account for about `98%` of the
measured first-click time. Removing only that dependency reduces the same Qt
button-to-visible path to about `17 ms`.

The original diagnostic process did not reproduce the user's exact `5–8 s`
magnitude outside the attached debugger. A later isolated run against the same
real runtime, after moving the unchanged check off the GUI thread, measured that
check at `6.829751 s`. The magnitude is therefore now directly reproduced;
debugger hooks, native-module cache state, and endpoint protection may still
change it between runs but are no longer needed to establish the cause.

## Exclusions

- The AMD slice is not called by `MainWindow._open_settings`; its UI contribution
  attaches a separate header action.
- AMD was disabled in the isolated run and the active database held no AMD
  installation or component-generation rows.
- LLM, Embedding, and ML worker settings reads together were below `10 ms`.
- The eager index refresh and duplicate `showEvent` refresh predate the current
  AMD/settings changes. The new provider-catalog work did not introduce this
  blocking call.

## Repair Boundary

The Settings first paint must not own physical LanceDB integrity validation.
A suitable repair should:

1. render a cached or `checking` projection immediately;
2. schedule one asynchronous status refresh per activation;
3. publish the result only if the dialog lifecycle generation is still current;
4. remove the constructor/show-event duplicate;
5. retain an explicit deep integrity operation for rebuild/recovery decisions.

This is an architecture boundary issue, not a reason to weaken vector integrity
checks or add AMD-specific handling.
