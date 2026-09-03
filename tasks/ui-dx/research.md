# UI Agent DX and Maintainability — Ecosystem Research

## Component isolation

- [Storybook documentation](https://storybook.js.org/docs/9) defines stories as
  isolated component/page states that expose hard-to-reach cases without running
  the whole application.
- [Storybook component explorer guidance](https://storybook.js.org/tutorials/visual-testing-handbook/react/en/component-explorers/)
  emphasizes the reusable combination of a sandbox, named state variations,
  testing, and documentation.
- [Story reuse in tests](https://storybook.js.org/docs/9/writing-tests/integrations/stories-in-unit-tests)
  identifies duplicated fixture state across visual and unit tools as a
  maintenance cost.

Application: Xenix should adopt the state-specification pattern, not Storybook's
web stack. One Python scenario factory should serve interactive rendering,
contract tests, and capture.

## pytest-qt and Qt Test

- [pytest-qt 4.5.0 on PyPI](https://pypi.org/project/pytest-qt/) requires Python
  3.9+ and publishes classifiers through Python 3.13. Phase 0 therefore treated
  Python 3.14 as an empirical qualification, not a claimed support guarantee.

- [pytest-qt reference](https://pytest-qt.readthedocs.io/en/latest/reference.html)
  provides `qapp`, `qtbot.addWidget`, `waitSignal`, `waitUntil`, screenshots, and
  managed widget cleanup.
- [pytest-qt failure debugging](https://pytest-qt.readthedocs.io/en/stable/debugging.html)
  documents widget screenshots and notes that offscreen windows are not visibly
  inspectable.
- [pytest-qt Qt logging](https://pytest-qt.readthedocs.io/en/stable/logging.html)
  exposes captured Qt records and failure thresholds.
- [pytest-qt model tester](https://pytest-qt.readthedocs.io/en/latest/modeltester.html)
  wraps consistency checks for Qt item models.
- [Qt Test best practices](https://doc.qt.io/qt-6/qttest-best-practices.html)
  recommends signal/condition synchronization instead of hard-coded waits and
  warns that bitmap capture/comparison is highly environment-sensitive.
- [QSignalSpy](https://doc.qt.io/qt-6/qsignalspy.html) records signal emissions and
  arguments and can wait while the event loop runs.
- [QAbstractItemModelTester](https://doc.qt.io/qt-6/qabstractitemmodeltester.html)
  continuously checks model invariants as a model changes.

Application: migrate hand-rolled event pumping to pytest-qt, prefer public widget
APIs and signals, and use screenshots as evidence or narrow visual contracts.
Python 3.14.2 compatibility remains an explicit admission gate.

Phase 0 result: 4.5.0 passed `qapp`, managed widget cleanup, exposed-window wait,
signal wait, condition wait, screenshot, and Qt-log capture on Python 3.14.2,
PySide6 6.11.1, and pytest 9.1.1.

## Stable semantic IDs and accessibility

- [PySide6 QWidget accessibility properties](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html)
  state that `accessibleIdentifier` can identify a widget for automated tests.
- [QObject](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QObject.html) documents
  `objectName` and `findChild`, while Qt style sheets also commonly consume object
  names.
- [Qt accessibility for widgets](https://doc.qt.io/qt-6/accessible-qwidget.html)
  distinguishes accessibility semantics from the QObject implementation tree.

Application: stable automation IDs belong in `accessibleIdentifier`;
`accessibleName` stays localized/user-facing and `objectName` must not be renamed
casually because it can affect styling.

## Rendering and visual stability

- [Qt Widget Gallery](https://doc.qt.io/qtforpython-6/overviews/qtwidgets-gallery.html)
  shows that widget appearance varies by platform style and theme.
- [QWidget rendering/grab](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html)
  supports rendering a widget and its children into a pixmap without taking a
  desktop screenshot.
- [Qt High DPI overview](https://doc.qt.io/qt-6/highdpi.html) explains the
  distinction between device-independent geometry and physical pixels.
- [Playwright visual comparisons](https://playwright.dev/docs/next/test-snapshots)
  independently documents that OS, version, settings, hardware, power state, and
  headless mode can change screenshot rendering, and recommends generating and
  comparing baselines in the same environment.

Application: prefer `QWidget` capture, record style/font/DPI/viewport metadata,
and never share one golden across platform identities. Native Windows tests should
assert behavior and semantics rather than exact pixels.

## CI artifacts

- [GitHub workflow artifacts](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts)
  explicitly lists test results, failures, screenshots, logs, and core dumps as
  common persisted workflow outputs.
- [GitHub store/share artifact guide](https://docs.github.com/en/actions/tutorials/store-and-share-data)
  documents named uploads, retention, path allowlists, and post-failure debugging.
- [actions/upload-artifact](https://github.com/actions/upload-artifact/blob/main/README.md)
  documents `if-no-files-found`, retention, and hidden-file behavior.

Application: upload a known allowlisted `ui-artifacts/` directory with
`if: always()`; do not upload pytest's entire temp tree or runtime home.

## PySide typing

- [PySide fixing type hints](https://doc.qt.io/qtforpython-6.10/developer/fix_type_hints.html)
  acknowledges missing, broad, overload, and inheritance inaccuracies in generated
  Qt stubs while recommending static checking.
- [PySide mypy correctness](https://doc.qt.io/qtforpython-6/developer/mypy-correctness.html)
  describes Qt's own use of mypy to improve generated signatures.

Application: keep strict mypy for owned contracts and pure state, isolate dynamic
Qt edges in small adapters, and expand the existing allowlist incrementally.

## Synthesis

The sources converge on a layered design:

1. isolate named UI states with mocked/synthetic inputs;
2. identify controls semantically rather than structurally;
3. synchronize through signals/conditions, not sleeps;
4. use structure/state assertions for most tests;
5. keep pixels environment-specific and sparse;
6. persist bounded failure evidence in CI;
7. type-check owned seams even when framework stubs are imperfect.

This is the basis for the design and implementation ordering in this task packet.
