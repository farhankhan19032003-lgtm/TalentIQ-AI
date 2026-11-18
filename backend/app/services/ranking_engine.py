"""Transparent, configurable, reproducible scoring. Pure functions only (no I/O, no randomness)."""
from __future__ import annotations

from ..core.config import ALGORITHM_VERSION, COMPONENTS, COMPONENT_LABELS, DEFAULT_WEIGHTS, SCORING
from ..core.errors import AppError


def validate_weights(weights: dict | None) -> dict:
    w = dict(DEFAULT_WEIGHTS if not weights else weights)
    if set(w) != set(COMPONENTS):
        raise AppError(f"Weights must contain exactly: {', '.join(COMPONENTS)}", 422, "invalid_weights")
    if any((not isinstance(v, (int, float))) or v < 0 for v in w.values()):
        raise AppError("Weights must be non-negative numbers.", 422, "invalid_weights")
    total = sum(w.values())
    if abs(total - 1.0) > 1e-3:
        raise AppError(f"Weights must total 100% (currently {total * 100:.1f}%).", 422, "invalid_weights")
    return {k: float(w[k]) for k in COMPONENTS}


def compute_overall(components: dict, weights: dict) -> dict:
    """components: {key: {"score": float|None, "status": 'scored'|'unverified'|'not_required'}}.

    * Components the JD does not require are excluded and the remaining weights renormalised.
    * Components in SCORING["renormalise_unverified"] (default: project/domain) that have no resume evidence are also left
      out of the point estimate instead of counting as 0 (missing information is not a mismatch).
    * Every other unverified component scores 0.
    `score_low` = the score if every left-out component had scored 0, `score_high` = if every unverified component scored 100.
    Always score_low <= overall <= score_high."""
    skip_if_unverified = set(SCORING["renormalise_unverified"])
    active = [k for k in COMPONENTS if components[k]["status"] != "not_required" and weights[k] > 0]
    counted = [k for k in active if not (components[k]["status"] == "unverified" and k in skip_if_unverified)] or active
    tw_all, tw = sum(weights[k] for k in active), sum(weights[k] for k in counted)
    if tw <= 0:
        return {"overall": 0.0, "score_low": 0.0, "score_high": 0.0, "effective_weights": {}, "contributions": {}}
    eff = {k: (weights[k] / tw if k in counted else 0.0) for k in active}
    contrib = {k: eff[k] * (components[k]["score"] or 0.0) for k in active}
    overall = sum(contrib.values())
    low = sum(weights[k] / tw_all * (components[k]["score"] or 0.0) for k in counted)
    high = sum(weights[k] / tw_all * (100.0 if components[k]["status"] == "unverified" else (components[k]["score"] or 0.0)) for k in active)
    clamp = lambda x: round(max(0.0, min(100.0, x)), 2)
    return {"overall": clamp(overall), "score_low": clamp(low), "score_high": clamp(high),
            "effective_weights": {k: round(v, 6) for k, v in eff.items()},
            "contributions": {k: round(v, 4) for k, v in contrib.items()}}


def rank(items: list[dict]) -> list[dict]:
    """Deterministic: overall desc, technical desc, candidate id asc."""
    ordered = sorted(items, key=lambda r: (-r["overall"], -(r["components"]["technical_skills"]["score"] or 0), r["candidate_id"]))
    for i, r in enumerate(ordered, 1):
        r["rank"] = i
    return ordered


def sensitivity(items: list[dict], weights: dict, delta: float = 0.10) -> dict:
    """Re-rank under +/-10pp perturbations of each weight (others rescaled). Reports per-candidate rank range."""
    scenarios = [("baseline", weights)]
    for k in COMPONENTS:
        for sign in (+1, -1):
            w = dict(weights)
            w[k] = min(1.0, max(0.0, w[k] + sign * delta))
            rest = [x for x in COMPONENTS if x != k]
            rest_total = sum(weights[x] for x in rest)
            left = 1.0 - w[k]
            for x in rest:
                w[x] = (weights[x] / rest_total * left) if rest_total > 0 else left / len(rest)
            scenarios.append((f"{k}{'+' if sign > 0 else '-'}{int(delta * 100)}pp", w))
    ranks: dict[int, list[int]] = {r["candidate_id"]: [] for r in items}
    for _, w in scenarios:
        scored = []
        for r in items:
            o = compute_overall(r["components"], w)["overall"]
            scored.append((-o, -(r["components"]["technical_skills"]["score"] or 0), r["candidate_id"]))
        for pos, (_, _, cid) in enumerate(sorted(scored), 1):
            ranks[cid].append(pos)
    return {cid: {"rank_min": min(v), "rank_max": max(v), "stable": (max(v) - min(v)) <= 1, "scenarios": len(v)} for cid, v in ranks.items()}


def describe_formula(weights: dict) -> str:
    return "Overall = " + " + ".join(f"({COMPONENT_LABELS[k]} × {weights[k]:.2f})" for k in COMPONENTS) + f"   [algorithm v{ALGORITHM_VERSION}]"
