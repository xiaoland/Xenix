from pathlib import Path, PurePath

from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info


hiddenimports, binaries, datas = add_qt6_dependencies(__file__)

# PyInstaller's stock QtQml hook collects every QML module shipped in the
# PySide wheel. Xenix only uses the base QtQuick scene for its startup splash.
qml_source_root = Path(pyside6_library_info.location["QmlImportsPath"])
qml_destination_root = PurePath(pyside6_library_info.qt_rel_dir) / "qml"
for relative_module in (
    PurePath("QtQml"),
    PurePath("QtQml/Models"),
    PurePath("QtQml/WorkerScript"),
    PurePath("QtQuick"),
):
    source_directory = qml_source_root.joinpath(*relative_module.parts)
    destination_directory = qml_destination_root / relative_module
    for source_file in source_directory.iterdir():
        if not source_file.is_file():
            continue
        entry = (str(source_file), str(destination_directory))
        if source_file.suffix.casefold() == ".dll":
            binaries.append(entry)
        else:
            datas.append(entry)
