"""
Creates (or updates) and publishes the "ProductIQ Data Agent" with the Fabric data agent Python SDK (preview),
running OUTSIDE Fabric with your Azure CLI sign-in. If the SDK API in your installed version differs, run the
equivalent notebook fabric/notebooks/03_create_data_agent.ipynb inside the Fabric workspace instead.

Usage: python scripts/fabric/create_data_agent.py   (reads FABRIC_WORKSPACE_ID from config/outputs.json)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from piq_common import REPO_ROOT, credential, load_outputs, log, require, save_outputs  # noqa: E402

AGENT_NAME = "ProductIQ Data Agent"
LAKEHOUSE = "productiq_lakehouse"
GOLD_TABLES = ["dim_product", "dim_component", "dim_supplier", "dim_plant", "dim_region", "dim_date",
               "fact_feedback", "fact_sales", "fact_bom_cost", "fact_supplier_capacity", "fact_logistics",
               "fact_market_signal", "fact_warranty"]


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def _call_first(obj, names: list[str], *args, **kwargs):
    """Call the first method that exists on obj (the preview SDK has renamed a few methods between versions)."""
    for n in names:
        fn = getattr(obj, n, None)
        if callable(fn):
            return fn(*args, **kwargs)
    raise AttributeError(f"None of {names} found on {type(obj).__name__}")


def create_and_publish(workspace_id: str) -> str | None:
    from fabric.analytics.environment.credentials import SetFabricAnalyticsDefaultTokenCredentialsGlobally
    from fabric.dataagent.client import FabricDataAgentManagement, create_data_agent

    SetFabricAnalyticsDefaultTokenCredentialsGlobally(credential())

    try:
        agent = create_data_agent(data_agent_name=AGENT_NAME, workspace_id=workspace_id)
        log(f"Created data agent '{AGENT_NAME}'")
    except Exception:  # already exists
        agent = FabricDataAgentManagement(AGENT_NAME, workspace_id)
        log(f"Using existing data agent '{AGENT_NAME}'")

    instructions = _read("fabric/data-agent/instructions.md")
    try:
        _call_first(agent, ["update_settings"], ai_instructions=instructions)
    except (AttributeError, TypeError):
        _call_first(agent, ["update_configuration"], instructions=instructions)
    log("Agent instructions set")

    existing = agent.get_datasources() if hasattr(agent, "get_datasources") else []
    if not existing:
        try:
            _call_first(agent, ["add_staging_datasource"], artifact_name_or_id=LAKEHOUSE, workspace_id_or_name=workspace_id)
        except (AttributeError, TypeError):
            _call_first(agent, ["add_datasource"], LAKEHOUSE, workspace_id_or_name=workspace_id, type="lakehouse")
        existing = agent.get_datasources()
    ds = existing[0]
    for t in GOLD_TABLES:
        try:
            ds.select("dbo", t)
        except Exception as e:  # table missing -> the notebooks have not run yet
            log(f"  could not select dbo.{t}: {e}")
    log(f"Selected {len(GOLD_TABLES)} gold tables")

    ds_instr = _read("fabric/data-agent/datasource_instructions.md")
    try:
        _call_first(ds, ["update_configuration"], instructions=ds_instr)
        log("Data source instructions set")
    except Exception as e:
        log(f"  data source instructions not set via SDK ({e}); paste fabric/data-agent/datasource_instructions.md in the portal")

    examples = json.loads(_read("fabric/data-agent/example_queries.json"))
    try:
        _call_first(ds, ["add_fewshots", "add_few_shots"], {e["question"]: e["query"] for e in examples})
        log(f"{len(examples)} example queries added")
    except Exception as e:
        log(f"  example queries not added via SDK ({e}); add them in the portal from fabric/data-agent/example_queries.json")

    try:
        _call_first(agent, ["publish_staging"], description="ProductIQ initial publish")
    except (AttributeError, TypeError):
        _call_first(agent, ["publish"])
    log("Data agent published")

    agent_id = None
    for attr in ("id", "artifact_id", "_id"):
        agent_id = agent_id or getattr(agent, attr, None)
    if not agent_id and hasattr(agent, "get_configuration"):
        cfg = agent.get_configuration()
        agent_id = getattr(cfg, "id", None) or (cfg.get("id") if isinstance(cfg, dict) else None)
    return agent_id


if __name__ == "__main__":
    out = load_outputs()
    (ws,) = require(out, "FABRIC_WORKSPACE_ID")
    aid = create_and_publish(ws)
    if aid:
        save_outputs({"FABRIC_DATA_AGENT_ID": aid,
                      "FABRIC_DATA_AGENT_MCP_URL": f"https://api.fabric.microsoft.com/v1/mcp/workspaces/{ws}/dataagents/{aid}/agent"})
    print(f"Data agent id: {aid or '(look it up in the Fabric portal URL)'}")
