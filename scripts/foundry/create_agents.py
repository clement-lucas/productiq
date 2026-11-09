"""
Creates / updates the ProductIQ specialist prompt agents in Foundry Agent Service (new agents API, api-version v1).
Each agent gets instructions from scripts/foundry/agents/<name>.md (+ _shared.md) and server-side tools:
  Fabric IQ (preview)  -> published Fabric data agent (structured data in OneLake)
  MCP knowledge base   -> Foundry IQ knowledge base (Azure AI Search agentic retrieval)
  Grounding with Bing  -> public web trends (optional)
The orchestrator (src/productiq, Microsoft Agent Framework) calls these agents via the Responses API (agent_reference).

Usage: python scripts/foundry/create_agents.py [--only productiq-voc-analyst]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from piq_common import SCOPE_FOUNDRY, Rest, load_outputs, log, require, step  # noqa: E402

HERE = Path(__file__).resolve().parent
KB_API = "2026-08-01-preview"

AGENTS = {
    "productiq-voc-analyst":   {"model": "router", "tools": ["fabric"]},
    "productiq-market-scout":  {"model": "router", "tools": ["kb", "bing"]},
    "productiq-cost-supplier": {"model": "router", "tools": ["fabric"]},
    "productiq-logistics":     {"model": "router", "tools": ["fabric"]},
    "productiq-future-tech":   {"model": "router", "tools": ["kb", "bing"]},
}


def tool_variants(kind: str, out: dict) -> list[dict]:
    """Return candidate JSON shapes for a tool (most complete first) – preview tool schemas evolve."""
    if kind == "fabric" and out.get("FABRIC_IQ_CONNECTION_ID"):
        full = {"type": "fabric_iq_preview", "project_connection_id": out["FABRIC_IQ_CONNECTION_ID"],
                "server_label": "productiq-data-agent", "server_url": out.get("FABRIC_DATA_AGENT_MCP_URL", ""),
                "require_approval": "never"}
        return [full, {"type": "fabric_iq_preview", "project_connection_id": out["FABRIC_IQ_CONNECTION_ID"],
                       "require_approval": "never"}]
    if kind == "kb" and out.get("KB_MCP_CONNECTION_ID"):
        return [{"type": "mcp", "server_label": "knowledge-base",
                 "server_url": f"{out['SEARCH_ENDPOINT']}/knowledgebases/{out['SEARCH_KNOWLEDGE_BASE']}/mcp?api-version={KB_API}",
                 "require_approval": "never", "allowed_tools": ["knowledge_base_retrieve"],
                 "project_connection_id": out.get("KB_MCP_CONNECTION_NAME", "foundryiq-kb")}]
    if kind == "bing" and out.get("BING_CONNECTION_ID"):
        return [{"type": "bing_grounding", "bing_grounding": {"search_configurations": [
            {"project_connection_id": out["BING_CONNECTION_ID"], "count": 5, "freshness": "Month"}]}}]
    return []


def upsert_agent(api: Rest, name: str, model: str, instructions: str, tools: list[dict]) -> str:
    body = {"definition": {"kind": "prompt", "model": model, "instructions": instructions, "tools": tools},
            "description": f"ProductIQ specialist: {name}", "metadata": {"solution": "productiq", "data": "synthetic"}}
    try:
        r = api.post(f"/agents/{name}/versions?api-version=v1", body, lro=False)
    except RuntimeError as e:
        if " 404 " not in str(e):
            raise
        r = api.post("/agents?api-version=v1", {"name": name, **body}, lro=False)
    data = r.json()
    return str(data.get("version") or data.get("versions", {}).get("latest", {}).get("version", "?"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="create a single agent")
    args = ap.parse_args()
    out = load_outputs()
    endpoint, reasoning, router = require(out, "FOUNDRY_PROJECT_ENDPOINT", "MODEL_REASONING_DEPLOYMENT", "MODEL_ROUTER_DEPLOYMENT")
    api = Rest(endpoint, SCOPE_FOUNDRY)
    shared = (HERE / "agents" / "_shared.md").read_text(encoding="utf-8")

    for name, spec in AGENTS.items():
        if args.only and name != args.only:
            continue
        step(f"Agent {name}")
        instructions = (HERE / "agents" / f"{name}.md").read_text(encoding="utf-8") + "\n\n" + shared
        model = reasoning if spec["model"] == "reasoning" else router
        # Try each tool's schema variants; fall back to the simpler shape on HTTP 400.
        chosen: list[dict] = []
        for kind in spec["tools"]:
            variants = tool_variants(kind, out)
            if not variants:
                log(f"  skipping {kind} tool (connection not configured)")
                continue
            for v in variants:
                try:
                    upsert_agent(api, name, model, instructions, chosen + [v])
                    chosen.append(v)
                    break
                except RuntimeError as e:
                    log(f"  {kind} tool shape rejected ({str(e)[:160]}) – trying next variant")
        version = upsert_agent(api, name, model, instructions, chosen)
        log(f"  version {version}; tools: {[t['type'] for t in chosen]}; model: {model}")
    print("\nAgents ready. Smoke test: python scripts/foundry/smoke_test.py")


if __name__ == "__main__":
    main()
