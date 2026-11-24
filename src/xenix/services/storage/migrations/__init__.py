from __future__ import annotations

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
from .runner import CURRENT_SCHEMA_VERSION, bootstrap_current_schema, run_migrations
from .v15_conversation import migrate_v14_to_v15
from .v16_to_v27 import (
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

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "bootstrap_current_schema",
    "get_user_version",
    "migrate_v1_to_v2",
    "migrate_v2_to_v3",
    "migrate_v3_to_v4",
    "migrate_v4_to_v5",
    "migrate_v5_to_v6",
    "migrate_v6_to_v7",
    "migrate_v7_to_v8",
    "migrate_v8_to_v9",
    "migrate_v9_to_v10",
    "migrate_v10_to_v11",
    "migrate_v11_to_v12",
    "migrate_v12_to_v13",
    "migrate_v13_to_v14",
    "migrate_v14_to_v15",
    "migrate_v15_to_v16",
    "migrate_v16_to_v17",
    "migrate_v17_to_v18",
    "migrate_v18_to_v19",
    "migrate_v19_to_v20",
    "migrate_v20_to_v21",
    "migrate_v21_to_v22",
    "migrate_v22_to_v23",
    "migrate_v23_to_v24",
    "migrate_v24_to_v25",
    "migrate_v25_to_v26",
    "migrate_v26_to_v27",
    "migrate_v27_to_v28",
    "migrate_v28_to_v29",
    "run_migrations",
    "set_user_version",
]
