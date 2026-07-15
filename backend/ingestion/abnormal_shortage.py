"""Abnormal Shortages ingestion (Section 5.1)."""
from __future__ import annotations

import pandas as pd

from backend.ingestion.generic import ViolationSource, ingest_violation_count


def ingest_abnormal_shortage(file_path: str, current_cycle_fy: str) -> tuple[pd.Series, dict[int, str]]:
    source = ViolationSource(
        name="abnormal_shortage",
        file_path=file_path,
        sheet_name="Data",
        id_column="C/C Number",
        header_row=0,
        fy_column="FY",
        current_cycle_fy=current_cycle_fy,
    )
    return ingest_violation_count(source)
