"""Asks each specialist agent one scenario question through the Foundry Responses API and prints the answer."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from piq_common import SCOPE_FOUNDRY, Rest, load_outputs, require, step  # noqa: E402

QUESTIONS = {
    "productiq-voc-analyst": "What are the top complaint topics among pet owners for robot vacuums in the last 18 months, and what share is hair tangling?",
    "productiq-market-scout": "How fast is demand for pet-care cleaning products growing year over year, and which needs are emerging?",
    "productiq-cost-supplier": "Which components of the RoboClean R7 are single-sourced, and what is the latest capacity utilisation of the BLM-200 motor supplier?",
    "productiq-logistics": "What is the freight cost and CO2e per unit trend for robot vacuums shipped to Japan over the last 12 months?",
    "productiq-future-tech": "Which technologies could prevent hair tangling in robot vacuums and how mature are they?",
}


def output_text(resp: dict) -> str:
    if resp.get("output_text"):
        return resp["output_text"]
    parts = []
    for item in resp.get("output", []):
        for c in item.get("content", []) or []:
            if c.get("type") in ("output_text", "text"):
                parts.append(c.get("text", ""))
    return "\n".join(parts) or str(resp)[:1500]


def main() -> None:
    out = load_outputs()
    (endpoint,) = require(out, "FOUNDRY_PROJECT_ENDPOINT")
    api = Rest(endpoint, SCOPE_FOUNDRY)
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for agent, q in QUESTIONS.items():
        if only and agent != only:
            continue
        step(f"{agent}: {q}")
        r = api.post("/openai/v1/responses", {"input": q, "agent_reference": {"type": "agent_reference", "name": agent}}, lro=False)
        print(output_text(r.json())[:3000])


if __name__ == "__main__":
    main()
