from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Iterable

import numpy as np


def prediction_digest(predictions: Iterable[Any]) -> str:
    """Return the one typed canonical digest for ordered model outputs."""

    values = [
        _canonical_prediction(value)
        for value in np.asarray(list(predictions), dtype=object).reshape(-1)
    ]
    serialized = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _canonical_prediction(value: Any) -> dict[str, Any]:
    if isinstance(value, np.generic):
        value = value.item()
    if value is None:
        return {"type": "null", "value": None}
    if isinstance(value, bool):
        return {"type": "bool", "value": value}
    if isinstance(value, int):
        return {"type": "int", "value": value}
    if isinstance(value, float):
        if math.isnan(value):
            rendered = "nan"
        elif math.isinf(value):
            rendered = "infinity" if value > 0 else "-infinity"
        else:
            rendered = value.hex()
        return {"type": "float", "value": rendered}
    return {"type": type(value).__name__, "value": str(value)}
