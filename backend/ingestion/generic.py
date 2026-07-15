"""Generic, pluggable ingestion pattern (Section 5.5).

Every violation source file so far shares the same shape: a row-per-incident
sheet with a contractor ID column, sitting alongside sheets that must be
excluded (historical archives, rollup summaries, scratch/"wrong data" sheets).
Rather than one hardcoded parsing function per file, each source is declared
once as a `ViolationSource` and ingested through the same function. When the
remaining raw files (Accident, HSE, OMC Loading, ATS Trained) arrive, adding
each is a `ViolationSource(...)` entry, not new pipeline code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import pandas as pd

from backend.common import normalize_cc_number, normalize_fy


@dataclass
class ViolationSource:
    name: str                                   # e.g. "abnormal_shortage" -> output column becomes "<name>_count"
    file_path: str
    sheet_name: str                             # the one valid/current-cycle sheet to read
    id_column: str                              # whatever the file calls the contractor ID
    extra_filter: Optional[Callable[[pd.DataFrame], pd.DataFrame]] = None
    header_row: Optional[int] = 0               # 0-indexed row for pandas `header=`; None = auto-detect
    header_anchor: Optional[str] = None          # text to search for when auto-detecting the header row
    fy_column: Optional[str] = None              # column to filter on CURRENT_CYCLE_FY, if present
    current_cycle_fy: Optional[str] = None       # normalized FY string to filter to, e.g. "FY26"
    name_column: Optional[str] = None            # optional contractor-name column, opportunistically captured


def detect_header_row(file_path: str, sheet_name: str, anchor: str, scan_rows: int = 10) -> int:
    """Scan the first `scan_rows` rows of a sheet for the row containing `anchor`
    (e.g. "Sr. No.") and return its 0-indexed row number, for files with title/
    spacer rows above the real header (Section 5.2)."""
    preview = pd.read_excel(file_path, sheet_name=sheet_name, header=None, nrows=scan_rows)
    for idx, row in preview.iterrows():
        if row.astype(str).str.strip().eq(anchor).any():
            return idx
    raise ValueError(f"Could not find header anchor {anchor!r} in first {scan_rows} rows of "
                      f"{file_path!r} sheet {sheet_name!r}")


def ingest_violation_count(source: ViolationSource) -> tuple[pd.Series, dict[int, str]]:
    """Returns (Series indexed by cc_number -> incident count, {cc_number: name} map)."""
    header_row = source.header_row
    if header_row is None:
        if not source.header_anchor:
            raise ValueError(f"{source.name}: header_row=None requires header_anchor to auto-detect it")
        header_row = detect_header_row(source.file_path, source.sheet_name, source.header_anchor)

    df = pd.read_excel(source.file_path, sheet_name=source.sheet_name, header=header_row)
    df.columns = [str(c).strip() for c in df.columns]

    if source.fy_column and source.current_cycle_fy and source.fy_column.strip() in df.columns:
        fy_col = source.fy_column.strip()
        df = df[df[fy_col].apply(normalize_fy) == source.current_cycle_fy]

    if source.extra_filter:
        df = df[source.extra_filter(df)]

    df = df.dropna(subset=[source.id_column])
    df["cc_number"] = df[source.id_column].apply(normalize_cc_number)

    names: dict[int, str] = {}
    if source.name_column and source.name_column in df.columns:
        for cc, name in zip(df["cc_number"], df[source.name_column]):
            if pd.notna(name) and cc not in names:
                names[cc] = str(name).strip()

    counts = df.groupby("cc_number").size().rename(f"{source.name}_count")
    return counts, names
