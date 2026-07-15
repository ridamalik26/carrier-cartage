"""Per-contractor Word violation-summary report (Section 9)."""
from __future__ import annotations

import os

from docxtpl import DocxTemplate

from backend.reporting.build_template import TEMPLATE_PATH, build_template
from backend.scoring.scoring_engine import ContractorScore, category_breakdown


def ensure_template() -> str:
    if not os.path.exists(TEMPLATE_PATH):
        build_template()
    return TEMPLATE_PATH


def generate_report(cc_number: int, name: str, score: ContractorScore, period: str, output_dir: str,
                     template_path: str | None = None) -> str:
    template_path = template_path or ensure_template()
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"violation_report_{cc_number}.docx")

    doc = DocxTemplate(template_path)
    doc.render({
        "contractor_name": name,
        "cc_number": cc_number,
        "overall_score": round(score.overall_score * 100, 2),
        "categories": category_breakdown(score),
        "period": period,
    })
    doc.save(output_path)
    return output_path
