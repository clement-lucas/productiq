"""Shared fictional demo data (Contoso Home Appliances – synthetic)."""
from productiq.memory import Member

AIKO = Member("u-aiko", "Aiko Tanaka", "aiko@contoso.example", "PM")
KEN = Member("u-ken", "Ken Sato", "ken@contoso.example", "Design")
MARIA = Member("u-maria", "Maria Garcia", "maria@contoso.example", "Sourcing")
RAJ = Member("u-raj", "Raj Patel", "raj@contoso.example", "Supply chain")


def _scores(cv, mf, cost, sr, log, ttm, sus):
    vals = dict(customer_value=cv, market_fit=mf, cost=cost, supplier_risk=sr, logistics=log,
                time_to_market=ttm, sustainability=sus)
    return {k: {"score": v, "rationale": f"{k} rationale", "citations": ["VoC – fact_feedback"]}
            for k, v in vals.items()}


# Weighted totals with default weights: A 3.60, B 3.25, C 3.75
DEMO_OPTIONS = [
    {"id": "A", "name": "Battery & filter upgrade", "scores": _scores(3, 3, 4, 4, 4, 5, 3)},
    {"id": "B", "name": "Modular & repairable", "scores": _scores(3, 3, 3, 4, 3, 3, 5)},
    {"id": "C", "name": "Pet-care robot vacuum with anti-tangle brush and self-emptying dock",
     "scores": _scores(5, 5, 3, 2, 3, 3, 3), "weightedTotal": 9.99},  # model total must be ignored
]
