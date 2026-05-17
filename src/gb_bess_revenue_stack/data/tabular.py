from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd
from pydantic import BaseModel


def records_to_dataframe(records: Sequence[BaseModel | dict[str, Any]]) -> pd.DataFrame:
    """Convert canonical records to a pandas DataFrame using JSON-safe values."""

    rows: list[dict[str, Any]] = []
    for record in records:
        if isinstance(record, BaseModel):
            rows.append(record.model_dump(mode="json"))
        else:
            rows.append(dict(record))
    return pd.DataFrame(rows)
