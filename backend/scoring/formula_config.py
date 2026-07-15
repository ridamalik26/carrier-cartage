"""Weights + thresholds (Section 6/7).

These are the authoritative values reverse-engineered from the live formula
cells of Working_of_performance_evaluation.xlsx (Section 7's table), NOT the
"Revised Dev Req" weight sheet (Section 6) — that sheet is a category-naming
reference only and its numbers (e.g. Seal Tempering = 0.05) are superseded
here by the values actually implemented in the live spreadsheet
(Seal Tempering = 0.10, Accident = 0.15, Quality Failure = 0.15, etc.).

"Late Reporting" is out of scope (Section 6 decision) — the 10 categories
below already sum to 1.00 without it.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

DEFAULT_WEIGHTS: dict[str, float] = {
    "accident": 0.15,
    "ddt": 0.05,
    "medical_screening": 0.05,
    "ogra_fleet": 0.10,
    "hse": 0.10,
    "quality_fail": 0.15,
    "abnormal_shortage": 0.10,
    "fake_documents": 0.10,
    "seal_temp": 0.10,
    "other_omc": 0.10,
}

DEFAULT_THRESHOLDS: dict[str, float] = {
    "accident": 2_500_000,      # km
    "hse": 2_000,
    "quality_fail": 10_000,
    "abnormal_shortage": 5_000,
    "fake_documents": 5_000,
    "seal_temp": 2_000,
    "other_omc": 2_000,
}

FLAG_THRESHOLD = 0.80


@dataclass
class FormulaConfig:
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    thresholds: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_THRESHOLDS))
    flag_threshold: float = FLAG_THRESHOLD

    def with_threshold_overrides(self, overrides: dict[str, float]) -> "FormulaConfig":
        """Used by the frontend's manual-limits screen (Section 12 item 5) —
        weights are fixed by the formula sheet and are never editable, only
        the count-based thresholds."""
        merged_thresholds = {**self.thresholds, **{k: v for k, v in overrides.items() if v is not None}}
        return replace(self, thresholds=merged_thresholds)


def default_formula_config() -> FormulaConfig:
    return FormulaConfig()
