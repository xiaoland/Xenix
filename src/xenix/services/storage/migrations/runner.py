from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel

from ....exceptions import ValidationError
from .. import models  # noqa: F401
from ._helpers import get_user_version, set_user_version
from .legacy import (
    migrate_v1_to_v2,
    migrate_v2_to_v3,
    migrate_v3_to_v4,
    migrate_v4_to_v5,
    migrate_v5_to_v6,
    migrate_v6_to_v7,
    migrate_v7_to_v8,
    migrate_v8_to_v9,
    migrate_v9_to_v10,
    migrate_v10_to_v11,
    migrate_v11_to_v12,
    migrate_v12_to_v13,
    migrate_v13_to_v14,
)
from .v15_conversation import _ensure_v15_triggers, migrate_v14_to_v15
from .v16_to_v27 import (
    _ensure_v16_knowledge_fts,
    migrate_v15_to_v16,
    migrate_v16_to_v17,
    migrate_v17_to_v18,
    migrate_v18_to_v19,
    migrate_v19_to_v20,
    migrate_v20_to_v21,
    migrate_v21_to_v22,
    migrate_v22_to_v23,
    migrate_v23_to_v24,
    migrate_v24_to_v25,
    migrate_v25_to_v26,
    migrate_v26_to_v27,
)
from .v28 import migrate_v27_to_v28
from .v29 import migrate_v28_to_v29

CURRENT_SCHEMA_VERSION = 29

_MIGRATION_STEPS: dict[int, Callable[[Engine], int]] = {
    1: migrate_v1_to_v2,
    2: migrate_v2_to_v3,
    3: migrate_v3_to_v4,
    4: migrate_v4_to_v5,
    5: migrate_v5_to_v6,
    6: migrate_v6_to_v7,
    7: migrate_v7_to_v8,
    8: migrate_v8_to_v9,
    9: migrate_v9_to_v10,
    10: migrate_v10_to_v11,
    11: migrate_v11_to_v12,
    12: migrate_v12_to_v13,
    13: migrate_v13_to_v14,
    14: migrate_v14_to_v15,
    15: migrate_v15_to_v16,
    16: migrate_v16_to_v17,
    17: migrate_v17_to_v18,
    18: migrate_v18_to_v19,
    19: migrate_v19_to_v20,
    20: migrate_v20_to_v21,
    21: migrate_v21_to_v22,
    22: migrate_v22_to_v23,
    23: migrate_v23_to_v24,
    24: migrate_v24_to_v25,
    25: migrate_v25_to_v26,
    26: migrate_v26_to_v27,
    27: migrate_v27_to_v28,
    28: migrate_v28_to_v29,
}


def bootstrap_current_schema(engine: Engine) -> int:
    SQLModel.metadata.create_all(engine)
    _ensure_v15_triggers(engine)
    _ensure_v16_knowledge_fts(engine)
    set_user_version(engine, CURRENT_SCHEMA_VERSION)
    return CURRENT_SCHEMA_VERSION


def run_migrations(engine: Engine) -> int:
    current_version = get_user_version(engine)
    if current_version == 0:
        return bootstrap_current_schema(engine)
    while current_version in _MIGRATION_STEPS:
        current_version = _MIGRATION_STEPS[current_version](engine)
    if current_version == CURRENT_SCHEMA_VERSION:
        return current_version
    raise ValidationError(
        f"Local schema version {current_version} cannot be upgraded automatically to "
        f"schema v{CURRENT_SCHEMA_VERSION}. Preserve the runtime state and use the "
        "documented storage recovery flow."
    )
