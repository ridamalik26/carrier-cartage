"""In-memory state for the current evaluation run.

This is a single-run internal tool (Section 12: one upload -> process -> review
-> send flow at a time), so a process-wide singleton is sufficient — no DB
required per the spec's Section 11 models/ note ("if persisting between runs").
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.scoring.formula_config import FormulaConfig, default_formula_config
from backend.scoring.scoring_engine import ContractorScore

MANUAL_CATEGORIES = ("accident", "hse", "omc", "ats_trained")


@dataclass
class AppState:
    current_cycle_fy: str = "FY26"
    period_label: str = "Jul-Dec 2025"
    period_key: str = "H1-2026"

    master_table: dict[int, dict] = field(default_factory=dict)
    violation_counts: dict[str, dict[int, int]] = field(default_factory=dict)  # category -> {cc_number: count}
    manual_counts: dict[str, dict[int, int]] = field(default_factory=lambda: {c: {} for c in MANUAL_CATEGORIES})
    names: dict[int, str] = field(default_factory=dict)
    contractor_emails: dict[int, str] = field(default_factory=dict)
    previous_scores: dict[int, float] = field(default_factory=dict)

    formula_config: FormulaConfig = field(default_factory=default_formula_config)

    contractor_rows: list[dict] = field(default_factory=list)
    scores: dict[int, ContractorScore] = field(default_factory=dict)
    output_excel_path: str | None = None
    generated_reports: dict[int, str] = field(default_factory=dict)  # cc_number -> docx path

    uploaded_sources: set[str] = field(default_factory=set)  # tracks which of the 10 categories are logged

    def reset(self) -> None:
        self.__init__()

    def merge_names(self, new_names: dict[int, str]) -> None:
        for cc, name in new_names.items():
            self.names.setdefault(cc, name)

    def build_contractor_rows(self) -> list[dict]:
        cc_numbers = set(self.master_table) | {
            cc for counts in self.violation_counts.values() for cc in counts
        } | {
            cc for counts in self.manual_counts.values() for cc in counts
        }

        rows = []
        for cc in cc_numbers:
            base = self.master_table.get(cc, {"total_loads": 0, "kms_travelled": 0.0, "fleet": 0, "ogra_fleet": 0})
            row = {
                "cc_number": cc,
                "name": self.names.get(cc, str(cc)),
                **base,
                "abnormal_shortage_count": self.violation_counts.get("abnormal_shortage", {}).get(cc, 0),
                "fake_documents_count": self.violation_counts.get("fake_documents", {}).get(cc, 0),
                "quality_fail_count": self.violation_counts.get("quality_fail", {}).get(cc, 0),
                "seal_temp_count": self.violation_counts.get("seal_temp", {}).get(cc, 0),
                "accident_count": self.manual_counts["accident"].get(cc, 0),
                "hse_count": self.manual_counts["hse"].get(cc, 0),
                "omc_count": self.manual_counts["omc"].get(cc, 0),
                "ats_trained": self.manual_counts["ats_trained"].get(cc, 0),
            }
            rows.append(row)

        self.contractor_rows = rows
        return rows


state = AppState()
