# L3 Plan 02: UI Flow

## 1. Main Window Refactor

Files:

- `src/xenix/ui/main_window.py`
- new `src/xenix/ui/dataset_workspace.py`

Changes:

- replace the placeholder summary shell with a two-part layout:
  - runtime info card can stay, but compressed
  - main content becomes `DatasetWorkspace`

Recommended `MainWindow` role:

- host top-level shell
- keep runtime-path card and log-opening action
- embed the dataset workspace

## 2. Dataset Workspace Structure

Files:

- new `src/xenix/ui/dataset_workspace.py`

Sections:

- project and work-item header
- import controls
- dataset summary card
- column-selection panel
- save/apply actions
- message/error area

Suggested widget composition:

```text
DatasetWorkspace
  Project selector
  WorkItem selector
  New WorkItem button
  DragDropFileWidget
  "Choose File" button
  DatasetSummaryWidget
  ColumnSelectionWidget
  Save button
  Status/Error label
```

## 3. Drag-And-Drop Widget

Files:

- new `src/xenix/ui/widgets/file_drop_zone.py`

Responsibilities:

- accept local file drops
- reject non-file URLs
- emit selected local path

Pseudo-code:

```python
class FileDropZone(QFrame):
    fileDropped = Signal(str)

    def dragEnterEvent(self, event):
        if any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.fileDropped.emit(url.toLocalFile())
                break
```

## 4. File Picker Flow

Files:

- `src/xenix/ui/dataset_workspace.py`

Behavior:

- use `QFileDialog.getOpenFileName`
- filter to:
  - `CSV Files (*.csv)`
  - `Excel Files (*.xlsx *.xls)`
  - `Supported Data Files (*.csv *.xlsx *.xls)`
- pass the selected path to the same inspection handler used by drag-and-drop

## 5. Dataset Summary Widget

Files:

- new `src/xenix/ui/widgets/dataset_summary.py`

Display fields:

- file name
- file path
- source format
- row count
- column count

This widget should be render-only and accept a `DatasetInspection` object.

## 6. Column Selection Widget

Files:

- new `src/xenix/ui/widgets/column_selection.py`

Responsibilities:

- display all columns with inferred kind
- allow choosing feature columns
- allow choosing target columns
- surface current selections to the workspace

V1 implementation choice:

- use two list widgets:
  - feature multi-select
  - target multi-select
- render inferred kind beside each column name

Maintainability rule:

- the widget should not know about datasets, projects, or persistence
- it only manages selection state over provided column metadata

## 7. Workspace Interaction Algorithm

When a file is selected:

1. call `DatasetService.inspect_source_file()`
2. if validation fails:
   - clear summary panel
   - clear column selection widget
   - show user-facing error
3. if inspection succeeds:
   - render summary
   - populate column selection widget
   - prefill dataset name from file stem if needed

When save is clicked:

1. ensure project and work item are selected
2. call `DatasetService.register_dataset()`
3. call `WorkItemService.attach_dataset_selection()`
4. refresh current work-item display
5. show success message

## 8. Work-Item Creation Shortcut

Files:

- `src/xenix/ui/dataset_workspace.py`

To keep the issue self-contained, add a minimal work-item creation shortcut:

- button: `New Work Item`
- prompt:
  - simple `QInputDialog` or small inline form
- action:
  - `WorkItemService.create_work_item()`
  - refresh work-item selector

This avoids blocking the import flow on absent navigation that does not exist yet.
