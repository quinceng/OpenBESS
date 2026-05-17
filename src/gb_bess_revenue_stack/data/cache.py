from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from gb_bess_revenue_stack.schemas.base import ensure_aware_utc


@dataclass(frozen=True)
class RawCacheEntry:
    path: Path
    sha256: str
    byte_count: int


class RawCache:
    """Immutable, content-addressed raw source cache."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def write_bytes(
        self,
        *,
        source_id: str,
        dataset: str,
        content: bytes,
        suffix: str,
        retrieved_at_utc: datetime,
    ) -> RawCacheEntry:
        retrieved_at_utc = ensure_aware_utc(retrieved_at_utc)
        normalised_suffix = suffix if suffix.startswith(".") else f".{suffix}"
        digest = hashlib.sha256(content).hexdigest()
        directory = self.root / source_id / dataset / retrieved_at_utc.date().isoformat()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{digest}{normalised_suffix}"
        if not path.exists():
            path.write_bytes(content)
        return RawCacheEntry(path=path, sha256=digest, byte_count=len(content))
