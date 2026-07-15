"""In-memory state for the current evaluation run.

This is a single-run internal tool (Section 12: one upload -> process -> review
-> send flow at a time), so a process-wide singleton is sufficient for local
use. On Vercel, serverless invocations don't share memory, so main.py's
auth_gate middleware round-trips this same singleton through Vercel KV
(to_dict/load_dict below) on every request when KV/Blob env vars are present —
see backend/kv_store.py.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

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
    output_excel_path: str | None = None   # local-disk mode
    output_excel_url: str | None = None    # Vercel Blob mode

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

    def to_dict(self, include_emails: bool = True) -> dict:
        """JSON-safe snapshot for Vercel KV. Dict keys that are cc_numbers
        (ints) become strings, since JSON object keys must be strings."""
        return {
            "current_cycle_fy": self.current_cycle_fy,
            "period_label": self.period_label,
            "period_key": self.period_key,
            "master_table": {str(cc): row for cc, row in self.master_table.items()},
            "violation_counts": {
                cat: {str(cc): v for cc, v in counts.items()} for cat, counts in self.violation_counts.items()
            },
            "manual_counts": {
                cat: {str(cc): v for cc, v in counts.items()} for cat, counts in self.manual_counts.items()
            },
            "names": {str(cc): name for cc, name in self.names.items()},
            "contractor_emails": (
                {str(cc): email for cc, email in self.contractor_emails.items()} if include_emails else None
            ),
            "previous_scores": {str(cc): v for cc, v in self.previous_scores.items()},
            "formula_config": asdict(self.formula_config),
            "contractor_rows": self.contractor_rows,
            "scores": {str(cc): asdict(score) for cc, score in self.scores.items()},
            "output_excel_url": self.output_excel_url,
            "uploaded_sources": sorted(self.uploaded_sources),
        }

    def load_dict(self, data: dict) -> None:
        """Rehydrates this instance from a to_dict() snapshot. Missing/empty
        `data` (e.g. first request ever) leaves the freshly-constructed
        defaults in place."""
        if not data:
            return
        self.current_cycle_fy = data.get("current_cycle_fy", self.current_cycle_fy)
        self.period_label = data.get("period_label", self.period_label)
        self.period_key = data.get("period_key", self.period_key)
        self.master_table = {int(cc): row for cc, row in data.get("master_table", {}).items()}
        self.violation_counts = {
            cat: {int(cc): v for cc, v in counts.items()} for cat, counts in data.get("violation_counts", {}).items()
        }
        manual_counts = {
            cat: {int(cc): v for cc, v in counts.items()} for cat, counts in data.get("manual_counts", {}).items()
        }
        self.manual_counts = manual_counts or {c: {} for c in MANUAL_CATEGORIES}
        self.names = {int(cc): name for cc, name in data.get("names", {}).items()}
        if data.get("contractor_emails") is not None:
            self.contractor_emails = {int(cc): email for cc, email in data["contractor_emails"].items()}
        self.previous_scores = {int(cc): v for cc, v in data.get("previous_scores", {}).items()}
        formula_config = data.get("formula_config")
        if formula_config:
            self.formula_config = FormulaConfig(**formula_config)
        self.contractor_rows = data.get("contractor_rows", [])
        self.scores = {int(cc): ContractorScore(**s) for cc, s in data.get("scores", {}).items()}
        self.output_excel_url = data.get("output_excel_url")
        self.uploaded_sources = set(data.get("uploaded_sources", []))


state = AppState()
