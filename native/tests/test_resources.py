from xenix.resources import package_resource_path


def test_app_icon_is_packaged() -> None:
    icon_path = package_resource_path("app-icon.svg")

    assert icon_path.is_file()
    assert icon_path.suffix == ".svg"
