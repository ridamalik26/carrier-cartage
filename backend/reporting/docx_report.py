"""Per-contractor Word violation-summary report (Section 9)."""
from __future__ import annotations

import io
import os

from docxtpl import DocxTemplate

from backend.reporting.build_template import TEMPLATE_PATH, build_template
from backend.scoring.scoring_engine import ContractorScore, category_breakdown


def ensure_template() -> str:
    if not os.path.exists(TEMPLATE_PATH):
        build_template()
    return TEMPLATE_PATH


def generate_report(cc_number: int, name: str, score: ContractorScore, period: str,
                     template_path: str | None = None) -> bytes:
    """Renders the report in memory and returns the .docx bytes — cheap enough
    to regenerate on every request instead of persisting it, so there's
    nothing to keep alive across serverless invocations."""
    template_path = template_path or ensure_template()

    doc = DocxTemplate(template_path)
    doc.render({
        "contractor_name": name,
        "cc_number": cc_number,
        "overall_score": round(score.overall_score * 100, 2),
        "categories": category_breakdown(score),
        "period": period,
    })
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
