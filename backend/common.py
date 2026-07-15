"""Shared helpers used across every ingestion adapter (Section 3 of the spec).

Every raw file uses a different column name for the same underlying contractor ID
(`C/C Number`, `Vendor code`, `Carrier`, `Carriage Code`, ...) and a different
fiscal-year string format (`FY-26`, `FY26`, `fy 26`). All ingestion adapters must
route through these two functions before grouping/filtering so that a contractor
is never silently split into two rows because of formatting drift between files.
"""
from __future__ import annotations


def normalize_cc_number(value) -> int:
    """Coerce any raw C/C Number / Vendor code / Carrier field to a clean int key."""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return int(text)


def normalize_fy(value) -> str:
    """Turn 'FY-26', 'FY26', 'fy 26' etc. into one canonical form, e.g. 'FY26'."""
    return str(value).upper().replace("-", "").replace(" ", "").strip()


def parse_numeric(text) -> float:
    """Parse comma-formatted numeric-looking text fields (e.g. '48,000.000') to float."""
    return float(str(text).replace(",", "").strip())
