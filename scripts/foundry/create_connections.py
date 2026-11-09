"""
Creates Foundry project connections that cannot be declared in Bicep yet (RemoteTool category, preview):
  - fabriciq-dataagent : Fabric IQ -> published Fabric data agent MCP endpoint (user identity passthrough by default)
  - foundryiq-kb       : Foundry IQ knowledge base MCP endpoint on Azure AI Search (project managed identity)
Bing grounding, AI Search, Storage, Cosmos DB and App Insights connections are created by infra/modules/foundry.bicep.

Usage: python scripts/foundry/create_connections.py [--fabric-auth user|project]
  user    (default) UserEntraToken: Fabric enforces the calling user's permissions (needs an Entra user in the call chain)
  project ProjectManagedIdentity: the Foundry project identity queries Fabric (add it to the Fabric workspace as Viewer)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from piq_common import SCOPE_ARM, Rest, load_outputs, log, require, save_outputs, step  # noqa: E402

CONN_API = "2025-10-01-preview"
KB_API = "2026-08-01-preview"
POWERBI_AUDIENCE = "https://analysis.windows.net/powerbi/api"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fabric-auth", choices=["user", "project"], default="user")
    args = ap.parse_args()
    out = load_outputs()
    sub, rg, acct, proj, search_ep, kb = require(out, "AZURE_SUBSCRIPTION_ID", "AZURE_RESOURCE_GROUP", "FOUNDRY_ACCOUNT_NAME",
                                                  "FOUNDRY_PROJECT_NAME", "SEARCH_ENDPOINT", "SEARCH_KNOWLEDGE_BASE")
    project_id = (f"/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices"
                  f"/accounts/{acct}/projects/{proj}")
    arm = Rest("https://management.azure.com", SCOPE_ARM)
    values = {"FOUNDRY_PROJECT_RESOURCE_ID": project_id}

    step("Foundry IQ knowledge base connection")
    kb_conn = out.get("KB_MCP_CONNECTION_NAME", "foundryiq-kb")
    arm.put(f"{project_id}/connections/{kb_conn}?api-version={CONN_API}", {
        "properties": {"authType": "ProjectManagedIdentity", "category": "RemoteTool",
                       "target": f"{search_ep}/knowledgebases/{kb}/mcp?api-version={KB_API}",
                       "isSharedToAll": True, "audience": "https://search.azure.com/", "metadata": {"ApiType": "Azure"}}})
    log(f"{kb_conn} -> {kb}")
    values["KB_MCP_CONNECTION_ID"] = f"{project_id}/connections/{kb_conn}"

    mcp = out.get("FABRIC_DATA_AGENT_MCP_URL")
    if not mcp:
        log("FABRIC_DATA_AGENT_MCP_URL missing – run 05-setup-fabric.ps1 first. Skipping the Fabric IQ connection.")
    else:
        step(f"Fabric IQ connection ({args.fabric_auth} identity)")
        fab_conn = out.get("FABRIC_IQ_CONNECTION_NAME", "fabriciq-dataagent")
        props = {"category": "RemoteTool", "target": mcp, "audience": POWERBI_AUDIENCE, "isSharedToAll": True,
                 "authType": "UserEntraToken" if args.fabric_auth == "user" else "ProjectManagedIdentity",
                 "metadata": {"ApiType": "Azure", "type": "fabric_iq"}}
        arm.put(f"{project_id}/connections/{fab_conn}?api-version={CONN_API}", {"properties": props})
        log(f"{fab_conn} -> {mcp}")
        values["FABRIC_IQ_CONNECTION_ID"] = f"{project_id}/connections/{fab_conn}"
        log("Tip: you can also add the data agent in the Foundry portal: Tools > Add > Fabric IQ (OneLake Catalog).")

    bing = out.get("BING_CONNECTION_NAME")
    if bing:
        values["BING_CONNECTION_ID"] = f"{project_id}/connections/{bing}"
    save_outputs(values)
    print("\nConnections ready. Next: python scripts/foundry/create_agents.py")


if __name__ == "__main__":
    main()
