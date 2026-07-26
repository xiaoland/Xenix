import sys
from pathlib import Path

from xenix.resources import package_resource_path


def test_package_resource_path_uses_frozen_meipass_root(monkeypatch, tmp_path: Path) -> None:
    resource_root = tmp_path / "xenix" / "resources"
    resource_root.mkdir(parents=True)
    resource_path = resource_root / "logo.png"
    resource_path.write_bytes(b"png")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert package_resource_path("logo.png") == resource_path
