"""Per-contractor scoring (Section 7), reverse-engineered from the live
Working_of_performance_evaluation.xlsx formula cells."""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.scoring.formula_config import FormulaConfig

CATEGORY_LABELS = {
    "accident": "Accident %",
    "ddt": "DDT %",
    "medical_screening": "Medical Screening %",
    "ogra_fleet": "OGRA fleet %",
    "hse": "HSE Observation",
    "quality_fail": "Quality Fail & Unauthorized Mod %",
    "abnormal_shortage": "Abnormal Shortage",
    "fake_documents": "Fake Documents",
    "seal_temp": "Seal Tempering",
    "other_omc": "Other OMC Loading",
}


def category_score(count, weight: float, denominator_metric: float, threshold: float, cap_at_weight: bool = True) -> float:
    """General pattern for count-based penalty categories (HSE, Quality Fail,
    Abnormal Shortage, Fake Documents, Seal Tempering, Other OMC).
    denominator_metric = total_loads for these categories."""
    if not count:
        return weight
    if not threshold:
        return 0.0
    raw = (denominator_metric / threshold) / count * weight
    return min(raw, weight) if cap_at_weight else raw


@dataclass
class ContractorScore:
    cc_number: int
    name: str
    category_scores: dict[str, float] = field(default_factory=dict)
    category_counts: dict[str, float] = field(default_factory=dict)
    overall_score: float = 0.0
    flagged: bool = False


def calculate_contractor_score(c: dict, config: FormulaConfig) -> ContractorScore:
    weights, thresholds = config.weights, config.thresholds
    scores: dict[str, float] = {}
    counts: dict[str, float] = {
        "accident": c.get("accident_count", 0) or 0,
        "hse": c.get("hse_count", 0) or 0,
        "quality_fail": c.get("quality_fail_count", 0) or 0,
        "abnormal_shortage": c.get("abnormal_shortage_count", 0) or 0,
        "fake_documents": c.get("fake_documents_count", 0) or 0,
        "seal_temp": c.get("seal_temp_count", 0) or 0,
        "other_omc": c.get("omc_count", 0) or 0,
    }

    # Accident % — capped at its own weight so Overall Score can never
    # mathematically exceed 100% (the legacy Excel formula was uncapped here).
    accident_count = counts["accident"]
    if not accident_count:
        scores["accident"] = weights["accident"]
    else:
        raw = (c.get("kms_travelled", 0) / thresholds["accident"]) / accident_count * weights["accident"]
        scores["accident"] = min(raw, weights["accident"])

    # DDT % and Medical Screening % — both derived from ATS Trained / Fleet
    # ratio (the reference sheet reuses the same computed value for both).
    fleet = c.get("fleet", 0) or 0
    ddt_ratio = (c.get("ats_trained", 0) / fleet) * weights["ddt"] if fleet else 0.0
    scores["ddt"] = ddt_ratio
    scores["medical_screening"] = ddt_ratio

    # OGRA fleet %
    scores["ogra_fleet"] = (c.get("ogra_fleet", 0) / fleet) * weights["ogra_fleet"] if fleet else 0.0

    total_loads = c.get("total_loads", 0) or 0
    scores["hse"] = category_score(counts["hse"], weights["hse"], total_loads, thresholds["hse"])
    scores["quality_fail"] = category_score(counts["quality_fail"], weights["quality_fail"], total_loads, thresholds["quality_fail"])
    scores["abnormal_shortage"] = category_score(counts["abnormal_shortage"], weights["abnormal_shortage"], total_loads, thresholds["abnormal_shortage"])
    scores["fake_documents"] = category_score(counts["fake_documents"], weights["fake_documents"], total_loads, thresholds["fake_documents"])
    scores["seal_temp"] = category_score(counts["seal_temp"], weights["seal_temp"], total_loads, thresholds["seal_temp"])
    scores["other_omc"] = category_score(counts["other_omc"], weights["other_omc"], total_loads, thresholds["other_omc"])

    overall_score = sum(scores.values())
    return ContractorScore(
        cc_number=c["cc_number"],
        name=c.get("name", str(c["cc_number"])),
        category_scores=scores,
        category_counts=counts,
        overall_score=overall_score,
        flagged=overall_score < config.flag_threshold,
    )


def score_all_contractors(contractor_rows: list[dict], config: FormulaConfig) -> list[ContractorScore]:
    results = [calculate_contractor_score(c, config) for c in contractor_rows]
    results.sort(key=lambda r: (not r.flagged, -r.overall_score))
    return results


def category_breakdown(score: ContractorScore) -> list[dict]:
    """List of {name, count, score} for the docx report table (Section 9)."""
    return [
        {
            "name": CATEGORY_LABELS[key],
            "count": score.category_counts.get(key),
            "score": round(value * 100, 2),
        }
        for key, value in score.category_scores.items()
    ]
