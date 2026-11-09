"""Weighted concept scorecard.

The model proposes per-criterion scores (1–5) with rationale and citations; all
arithmetic (weighted totals, ranking, re-scoring) happens here in Python, never in the model.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Mapping

# Default weights from docs/CONTRACT.md (percent, must sum to 100).
DEFAULT_WEIGHTS: dict[str, int] = {
    "customer_value": 25,
    "market_fit": 20,
    "cost": 15,
    "supplier_risk": 15,
    "logistics": 10,
    "time_to_market": 10,
    "sustainability": 5,
}
CRITERIA: tuple[str, ...] = tuple(DEFAULT_WEIGHTS)
CRITERION_LABELS = {
    "customer_value": "Customer value",
    "market_fit": "Market fit",
    "cost": "Cost",
    "supplier_risk": "Supplier risk",
    "logistics": "Logistics",
    "time_to_market": "Time to market",
    "sustainability": "Sustainability",
}
MIN_SCORE, MAX_SCORE = 1, 5


class ScorecardError(ValueError):
    pass


def validate_weights(weights: Mapping[str, float]) -> dict[str, float]:
    """Weights must cover exactly CRITERIA, be non-negative and sum to 100."""
    keys = set(weights)
    if keys != set(CRITERIA):
        missing, unknown = set(CRITERIA) - keys, keys - set(CRITERIA)
        raise ScorecardError(f"weights mismatch: missing={sorted(missing)} unknown={sorted(unknown)}")
    out: dict[str, float] = {}
    for k in CRITERIA:
        v = weights[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
            raise ScorecardError(f"weight for {k} must be a non-negative number, got {v!r}")
        out[k] = v
    total = sum(out.values())
    if abs(total - 100) > 1e-6:
        raise ScorecardError(f"weights must sum to 100, got {total}")
    return out


def load_weights(source: str | None = None) -> dict[str, float]:
    """Load weights from a JSON string or JSON file path (PRODUCTIQ_SCORECARD_WEIGHTS)."""
    src = (source if source is not None else os.environ.get("PRODUCTIQ_SCORECARD_WEIGHTS", "")).strip()
    if not src:
        return dict(DEFAULT_WEIGHTS)
    if not src.startswith("{"):
        with open(src, encoding="utf-8") as fh:
            src = fh.read()
    return validate_weights(json.loads(src))


@dataclass(frozen=True)
class CriterionScore:
    score: int
    rationale: str = ""
    citations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.score, bool) or not isinstance(self.score, int) or not MIN_SCORE <= self.score <= MAX_SCORE:
            raise ScorecardError(f"score must be an integer {MIN_SCORE}-{MAX_SCORE}, got {self.score!r}")


@dataclass(frozen=True)
class OptionScore:
    option_id: str  # "A", "B", "C"
    name: str
    scores: dict[str, CriterionScore]
    description: str = ""
    assumptions: tuple[str, ...] = ()

    def missing_criteria(self) -> list[str]:
        return [c for c in CRITERIA if c not in self.scores]


def weighted_total(option: OptionScore, weights: Mapping[str, float]) -> float:
    """Weighted average on the 1–5 scale (weights in percent). Missing criteria raise."""
    missing = option.missing_criteria()
    if missing:
        raise ScorecardError(f"option {option.option_id} missing scores for {missing}")
    return round(sum(weights[c] * option.scores[c].score for c in CRITERIA) / 100.0, 2)


def as_percent(total: float) -> int:
    """Map a 1–5 weighted total to 0–100 for display bars."""
    return round((total - MIN_SCORE) / (MAX_SCORE - MIN_SCORE) * 100)


def rank(options: list[OptionScore], weights: Mapping[str, float]) -> list[tuple[OptionScore, float]]:
    """Sort by weighted total desc; ties broken by the highest-weighted criterion, then option id."""
    top = max(CRITERIA, key=lambda c: weights[c])
    scored = [(o, weighted_total(o, weights)) for o in options]
    return sorted(scored, key=lambda t: (-t[1], -t[0].scores[top].score, t[0].option_id))


def apply_overrides(option: OptionScore, overrides: Mapping[str, Mapping[str, Any]]) -> OptionScore:
    """Return a copy with some criteria re-scored, e.g. {"supplier_risk": {"score": 4, "rationale": ...}}."""
    new_scores = dict(option.scores)
    for crit, ov in overrides.items():
        if crit not in CRITERIA:
            raise ScorecardError(f"unknown criterion {crit!r}")
        new_scores[crit] = CriterionScore(
            score=int(ov["score"]),
            rationale=str(ov.get("rationale", "")),
            citations=tuple(ov.get("citations", ())),
        )
    return replace(option, scores=new_scores)


@dataclass
class Scorecard:
    project_id: str
    options: list[OptionScore]
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    version: int = 1
    note: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def ranked(self) -> list[tuple[OptionScore, float]]:
        return rank(self.options, self.weights)

    def rescore(self, option_id: str, overrides: Mapping[str, Mapping[str, Any]], note: str = "") -> "Scorecard":
        """New version with one option re-scored; previous versions stay immutable in memory."""
        ids = [o.option_id for o in self.options]
        if option_id not in ids:
            raise ScorecardError(f"unknown option {option_id!r}; known {ids}")
        options = [apply_overrides(o, overrides) if o.option_id == option_id else o for o in self.options]
        return Scorecard(self.project_id, options, dict(self.weights), self.version + 1, note)

    def to_dict(self) -> dict[str, Any]:
        ranked = self.ranked()
        return {
            "id": f"{self.project_id}:v{self.version}",
            "projectId": self.project_id,
            "version": self.version,
            "note": self.note,
            "createdAt": self.created_at,
            "weights": self.weights,
            "ranking": [o.option_id for o, _ in ranked],
            "options": [
                {
                    "id": o.option_id,
                    "name": o.name,
                    "description": o.description,
                    "assumptions": list(o.assumptions),
                    "weightedTotal": total,
                    "scores": {
                        c: {"score": s.score, "rationale": s.rationale, "citations": list(s.citations)}
                        for c, s in o.scores.items()
                    },
                }
                for o, total in ranked
            ],
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Scorecard":
        return cls(
            project_id=d["projectId"],
            options=parse_options(d["options"]),
            weights=validate_weights(d.get("weights", DEFAULT_WEIGHTS)),
            version=int(d.get("version", 1)),
            note=d.get("note", ""),
            created_at=d.get("createdAt", datetime.now(timezone.utc).isoformat()),
        )


def parse_options(raw: list[Mapping[str, Any]]) -> list[OptionScore]:
    """Parse model JSON ([{id,name,description,assumptions,scores:{crit:{score,rationale,citations}}}]).

    Any total the model may have produced is ignored; invalid scores raise ScorecardError.
    """
    options: list[OptionScore] = []
    for item in raw:
        scores = {}
        for crit, s in (item.get("scores") or {}).items():
            if crit not in CRITERIA:
                continue  # ignore criteria we don't weight
            if isinstance(s, (int, float)):
                s = {"score": s}
            score = s.get("score")
            if isinstance(score, float) and score.is_integer():
                score = int(score)
            scores[crit] = CriterionScore(score, str(s.get("rationale", "")), tuple(s.get("citations") or ()))
        opt = OptionScore(
            option_id=str(item.get("id") or item.get("option_id")).strip().upper(),
            name=str(item.get("name", "")),
            scores=scores,
            description=str(item.get("description", "")),
            assumptions=tuple(item.get("assumptions") or ()),
        )
        if opt.missing_criteria():
            raise ScorecardError(f"option {opt.option_id} missing scores for {opt.missing_criteria()}")
        options.append(opt)
    return options
