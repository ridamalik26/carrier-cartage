"""Seal Tampering penalty ingestion (Section 5.4).

Only the "Detail" sheet is row-level and current. "Summary" is a pre-aggregated
monthly rollup (wrong grain), "Sheet1" is explicitly labeled "Wrong data"
inside the file, "Deleted ENTRIES" and "Sheet2" are scratch/removed rows —
all four are excluded.
"""
from __future__ import annotations

import pandas as pd

from backend.ingestion.generic import ViolationSource, ingest_violation_count


def ingest_seal_tempering(file_path: str, period_start=None, period_end=None) -> tuple[pd.Series, dict[int, str]]:
    def _in_period(df: pd.DataFrame) -> pd.Series:
        if period_start is None or period_end is None:
            return pd.Series(True, index=df.index)
        date_col = next((c for c in df.columns if "date" in c.strip().lower() or c.strip().lower() in ("dt", "doc. dt")), None)
        if date_col is None:
            return pd.Series(True, index=df.index)
        dates = pd.to_datetime(df[date_col], errors="coerce")
        return (dates >= pd.Timestamp(period_start)) & (dates <= pd.Timestamp(period_end))

    source = ViolationSource(
        name="seal_temp",
        file_path=file_path,
        sheet_name="Detail",
        id_column="Vendor code",
        header_row=0,
        extra_filter=_in_period if (period_start and period_end) else None,
    )
    return ingest_violation_count(source)
