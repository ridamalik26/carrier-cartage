"""Quality Fail & Unauthorized Mod. ingestion (Section 5.3).

Combines two sources feeding the same scoring category:
  1. Un-Authorized_Modification.xlsx -> "Sheet1" only (Sheet1 (2)..(7) are
     historical archives from 2007-2012 and must be excluded).
  2. Reversal_Cases_Jul-Dec-25.xlsx -> "Data" only (Sheet2 is a 2012 archive),
     filtered to rows where Offense/Description == "Quality Issue".
"""
from __future__ import annotations

import pandas as pd

from backend.ingestion.generic import ViolationSource, ingest_violation_count


def _is_quality_issue(df: pd.DataFrame) -> pd.Series:
    cols = [c for c in ("Offense", "Description") if c in df.columns]
    if not cols:
        return pd.Series(False, index=df.index)
    mask = pd.Series(False, index=df.index)
    for c in cols:
        mask = mask | (df[c].astype(str).str.strip().str.casefold() == "quality issue")
    return mask


def ingest_quality_fail(
    unauthorized_mod_path: str,
    reversal_cases_path: str,
    current_cycle_fy: str,
) -> tuple[pd.Series, dict[int, str]]:
    unauth_source = ViolationSource(
        name="quality_fail_unauth",
        file_path=unauthorized_mod_path,
        sheet_name="Sheet1",
        id_column="C/C Number",
        header_row=0,
        fy_column="FY",
        current_cycle_fy=current_cycle_fy,
    )
    reversal_source = ViolationSource(
        name="quality_fail_reversal",
        file_path=reversal_cases_path,
        sheet_name="Data",
        id_column="C/C Number",
        header_row=0,
        extra_filter=_is_quality_issue,
    )

    unauth_counts, unauth_names = ingest_violation_count(unauth_source)
    reversal_counts, reversal_names = ingest_violation_count(reversal_source)

    combined = unauth_counts.reindex(
        unauth_counts.index.union(reversal_counts.index), fill_value=0
    ).add(
        reversal_counts.reindex(unauth_counts.index.union(reversal_counts.index), fill_value=0),
        fill_value=0,
    )
    combined = combined.rename("quality_fail_count").astype(int)

    names = {**reversal_names, **unauth_names}
    return combined, names
