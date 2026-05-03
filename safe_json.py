"""
Safe JSON encoder for numpy/pandas-rich objects.

Provides `SafeJSONEncoder` and a convenience `dumps` function that
serializes numpy scalars/arrays, pandas Series/DataFrame/Index, sets,
and datetimes.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd


class SafeJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:  # type: ignore[override]
        # numpy scalars
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.ndarray,)):
            return obj.tolist()

        # pandas objects
        if isinstance(obj, (pd.Series,)):
            return obj.tolist()
        if isinstance(obj, (pd.Index,)):
            return obj.tolist()
        if isinstance(obj, (pd.DataFrame,)):
            # Records is a good default for tabular JSON
            return obj.to_dict(orient="records")

        # datetimes/dates
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()

        # sets
        if isinstance(obj, set):
            return list(obj)

        return super().default(obj)


def dumps(obj: Any, **kwargs: Any) -> str:
    """json.dumps with SafeJSONEncoder by default."""
    kwargs.setdefault("cls", SafeJSONEncoder)
    return json.dumps(obj, **kwargs)

