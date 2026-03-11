from __future__ import annotations

from pathlib import Path

import pandas as pd

from ...exceptions import ValidationError


def load_dataset(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    raise ValidationError(f"Unsupported dataset format '{path.suffix}'.")


def load_holdout_frame(path: Path) -> pd.DataFrame:
    return pd.read_pickle(path)
