from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from PySide6.QtCore import QKeyCombination, Qt
from PySide6.QtGui import QKeySequence


SHORTCUT_SETTINGS_FILE = "shortcuts.json"
PORTABLE = QKeySequence.SequenceFormat.PortableText


def normalized_key(combination: QKeyCombination) -> QKeyCombination:
    key = combination.key()
    return QKeyCombination(
        combination.keyboardModifiers() & ~Qt.KeyboardModifier.KeypadModifier,
        Qt.Key.Key_Return if key == Qt.Key.Key_Enter else key,
    )


def shortcut_key(text: str) -> QKeyCombination:
    sequence = QKeySequence.fromString(text, PORTABLE)
    if sequence.count() != 1:
        raise ValueError("A shortcut must contain one key combination.")
    # PySide exposes sequence indexing at runtime, but omits it from its stub.
    combination = cast(Sequence[QKeyCombination], sequence)[0]
    if combination.key() == Qt.Key.Key_unknown:
        raise ValueError("A shortcut must contain one key combination.")
    return normalized_key(combination)


@dataclass(frozen=True)
class ConversationShortcuts:
    send: str = "Return"
    steer: str = "Ctrl+Return"

    def __post_init__(self) -> None:
        if shortcut_key(self.send) == shortcut_key(self.steer):
            raise ValueError("Conversation shortcuts must be distinct.")

    @classmethod
    def load(cls, path: Path) -> ConversationShortcuts:
        if not path.is_file():
            return cls()
        try:
            payload = json.loads(path.read_bytes())
            if isinstance(payload, dict) and isinstance(payload.get("send"), str) and isinstance(payload.get("steer"), str):
                return cls(send=payload["send"], steer=payload["steer"])
        except (OSError, ValueError):
            pass
        return cls()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=path.parent) as directory:
            temporary = Path(directory) / path.name
            temporary.write_text(json.dumps({"send": self.send, "steer": self.steer}, indent=2), encoding="utf-8")
            temporary.replace(path)
