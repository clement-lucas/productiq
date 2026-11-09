"""
Sets up Microsoft Fabric for ProductIQ (idempotent):
  1. finds the Fabric capacity deployed by infra/main.bicep and makes sure it is Active
  2. creates workspace "ProductIQ-<env>" on that capacity and grants the app identity Viewer
  3. creates lakehouse "productiq_lakehouse"
  4. uploads the synthetic bronze CSVs (data/output/bronze) to OneLake Files/bronze/...
  5. imports notebooks 01 (bronze->silver), 02 (silver->gold), 03 (data agent, fallback) bound to the lakehouse
  6. runs notebooks 01 and 02 (Spark jobs) and waits
  7. creates + publishes the "ProductIQ Data Agent" (scripts/fabric/create_data_agent.py, Fabric data agent SDK – preview)
  8. writes FABRIC_* values to config/outputs.json/.env

Usage:  python scripts/fabric/setup_fabric.py [--env dev] [--skip-upload] [--skip-run] [--skip-agent]
Requires: Fabric tenant settings described in README (Fabric items, data agent, cross-geo AI processing, service principals can use Fabric APIs).
"""
from __future__ import annotations

import argparse
import base64
import copy
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from piq_common import (REPO_ROOT, SCOPE_ARM, SCOPE_FABRIC, Rest, credential, load_outputs, log,  # noqa: E402
                        require, save_outputs, step)

FABRIC_API = "https://api.fabric.microsoft.com/v1"
ONELAKE_DFS = "https://onelake.dfs.fabric.microsoft.com"
LAKEHOUSE = "productiq_lakehouse"
NOTEBOOKS = ["01_bronze_to_silver", "02_silver_to_gold", "03_create_data_agent"]
RUN_NOTEBOOKS = ["01_bronze_to_silver", "02_silver_to_gold"]


def ensure_capacity_active(arm: Rest, capacity_id: str) -> None:
    cap = arm.get(f"{capacity_id}?api-version=2023-11-01")
    state = cap.get("properties", {}).get("state")
    log(f"Capacity state: {state}")
    if state in ("Paused", "Suspended"):
        log("Resuming capacity …")
        arm.post(f"{capacity_id}/resume?api-version=2023-11-01")
        for _ in range(60):
            time.sleep(10)
            if arm.get(f"{capacity_id}?api-version=2023-11-01")["properties"]["state"] == "Active":
                break


def find_by_name(items: list[dict], name: str) -> dict | None:
    return next((i for i in items if i.get("displayName", "").lower() == name.lower()), None)


def list_all(fab: Rest, path: str) -> list[dict]:
    out, url = [], path
    while url:
        page = fab.get(url)
        out += page.get("value", [])
        url = page.get("continuationUri")
    return out


def notebook_payload(nb_path: Path, ws_id: str, lh_id: str) -> str:
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    nb = copy.deepcopy(nb)
    meta = nb.setdefault("metadata", {})
    meta.setdefault("kernel_info", {"name": "synapse_pyspark"})
    meta.setdefault("language_info", {"name": "python"})
    meta["dependencies"] = {"lakehouse": {"default_lakehouse": lh_id, "default_lakehouse_name": LAKEHOUSE,
                                          "default_lakehouse_workspace_id": ws_id}}
    return base64.b64encode(json.dumps(nb).encode("utf-8")).decode("ascii")


def upsert_notebook(fab: Rest, ws_id: str, lh_id: str, name: str) -> str:
    path = REPO_ROOT / "fabric" / "notebooks" / f"{name}.ipynb"
    definition = {"format": "ipynb", "parts": [{"path": "notebook-content.ipynb",
                                                 "payload": notebook_payload(path, ws_id, lh_id),
                                                 "payloadType": "InlineBase64"}]}
    existing = find_by_name(list_all(fab, f"/workspaces/{ws_id}/notebooks"), name)
    if existing:
        fab.post(f"/workspaces/{ws_id}/items/{existing['id']}/updateDefinition", {"definition": definition})
        log(f"Updated notebook {name}")
        return existing["id"]
    fab.post(f"/workspaces/{ws_id}/items", {"displayName": name, "type": "Notebook", "definition": definition})
    for _ in range(12):  # item list can lag a few seconds behind the create operation
        nb = find_by_name(list_all(fab, f"/workspaces/{ws_id}/notebooks"), name)
        if nb:
            log(f"Imported notebook {name}")
            return nb["id"]
        time.sleep(5)
    raise RuntimeError(f"Notebook {name} not found after import")


def run_notebook(fab: Rest, ws_id: str, nb_id: str, name: str, timeout_s: int = 3600) -> None:
    log(f"Running {name} (Spark session start can take 1–3 minutes) …")
    r = fab.post(f"/workspaces/{ws_id}/items/{nb_id}/jobs/instances?jobType=RunNotebook", {}, lro=False)
    location = r.headers.get("Location")
    if not location:
        raise RuntimeError("Job submission did not return a Location header")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(20)
        job = fab.get(location)
        status = job.get("status")
        if status in ("Completed", "Succeeded"):
            log(f"{name}: {status}")
            return
        if status in ("Failed", "Cancelled", "Deduped"):
            raise RuntimeError(f"{name} {status}: {json.dumps(job.get('failureReason'))}")
    raise TimeoutError(f"{name} did not finish in {timeout_s}s")


def upload_bronze(ws_id: str, lh_id: str) -> int:
    from azure.storage.filedatalake import DataLakeServiceClient

    bronze = REPO_ROOT / "data" / "output" / "bronze"
    if not bronze.exists():
        sys.exit("data/output/bronze not found – run scripts/04-generate-data.ps1 first.")
    svc = DataLakeServiceClient(account_url=ONELAKE_DFS, credential=credential())
    fs = svc.get_file_system_client(ws_id)
    count = 0
    for f in sorted(bronze.rglob("*.csv")):
        rel = f.relative_to(bronze).as_posix()
        target = f"{lh_id}/Files/bronze/{rel}"
        with f.open("rb") as fh:
            fs.get_file_client(target).upload_data(fh, overwrite=True)
        count += 1
        log(f"uploaded {rel} ({f.stat().st_size/1e6:.1f} MB)")
    return count


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="dev")
    ap.add_argument("--skip-upload", action="store_true")
    ap.add_argument("--skip-run", action="store_true")
    ap.add_argument("--skip-agent", action="store_true")
    args = ap.parse_args()

    out = load_outputs()
    (capacity_id, capacity_name) = require(out, "FABRIC_CAPACITY_ID", "FABRIC_CAPACITY_NAME")
    app_principal = out.get("APP_PRINCIPAL_ID")
    arm = Rest("https://management.azure.com", SCOPE_ARM)
    fab = Rest(FABRIC_API, SCOPE_FABRIC)

    step("Fabric capacity")
    ensure_capacity_active(arm, capacity_id)
    caps = fab.get("/capacities").get("value", [])
    cap = find_by_name(caps, capacity_name)
    if not cap:
        sys.exit(f"Capacity '{capacity_name}' is not visible to you in Fabric. Make sure you are a capacity admin "
                 "(fabricAdminUpn) and the capacity is Active.")
    log(f"Capacity {cap['displayName']} ({cap['sku']}, {cap['region']}) id={cap['id']}")

    step("Workspace")
    ws_name = f"ProductIQ-{args.env}"
    ws = find_by_name(list_all(fab, "/workspaces"), ws_name)
    if not ws:
        ws = fab.post("/workspaces", {"displayName": ws_name, "capacityId": cap["id"],
                                      "description": "ProductIQ – Contoso Home Appliances (synthetic data)"}).json()
        log(f"Created workspace {ws_name}")
    elif ws.get("capacityId") != cap["id"]:
        fab.post(f"/workspaces/{ws['id']}/assignToCapacity", {"capacityId": cap["id"]})
        log("Assigned workspace to capacity")
    ws_id = ws["id"]
    log(f"Workspace id {ws_id}")

    if app_principal:
        try:
            fab.post(f"/workspaces/{ws_id}/roleAssignments",
                     {"principal": {"id": app_principal, "type": "ServicePrincipal"}, "role": "Viewer"}, ok=(200, 201, 409))
            log("App managed identity granted Viewer on the workspace (for Fabric IQ calls without user passthrough)")
        except RuntimeError as e:  # tenant setting "Service principals can use Fabric APIs" may be off
            log(f"Could not add app identity to workspace (enable the tenant setting, then retry): {e}")

    step("Lakehouse")
    lh = find_by_name(list_all(fab, f"/workspaces/{ws_id}/lakehouses"), LAKEHOUSE)
    if not lh:
        fab.post(f"/workspaces/{ws_id}/lakehouses", {"displayName": LAKEHOUSE,
                                                     "description": "Medallion lakehouse (bronze/silver/gold)"})
        for _ in range(12):
            lh = find_by_name(list_all(fab, f"/workspaces/{ws_id}/lakehouses"), LAKEHOUSE)
            if lh:
                break
            time.sleep(5)
        log(f"Created lakehouse {LAKEHOUSE}")
    lh_id = lh["id"]
    log(f"Lakehouse id {lh_id}")
    save_outputs({"FABRIC_WORKSPACE_ID": ws_id, "FABRIC_WORKSPACE_NAME": ws_name, "FABRIC_LAKEHOUSE_ID": lh_id})

    if not args.skip_upload:
        step("Uploading bronze files to OneLake")
        n = upload_bronze(ws_id, lh_id)
        log(f"{n} files uploaded")

    step("Importing notebooks")
    nb_ids = {name: upsert_notebook(fab, ws_id, lh_id, name) for name in NOTEBOOKS}

    if not args.skip_run:
        step("Running the medallion pipeline (bronze -> silver -> gold)")
        for name in RUN_NOTEBOOKS:
            run_notebook(fab, ws_id, nb_ids[name], name)

    if not args.skip_agent:
        step("Creating and publishing the Fabric data agent")
        from create_data_agent import create_and_publish  # noqa: E402  (same folder)
        try:
            agent_id = create_and_publish(ws_id)
        except Exception as e:  # SDK is preview – fall back to the notebook
            log(f"SDK path failed ({e}). Open notebook '03_create_data_agent' in the workspace and run it, "
                "then re-run this script with --skip-upload --skip-run.")
            agent_id = None
        if not agent_id:
            agents = list_all(fab, f"/workspaces/{ws_id}/items?type=DataAgent")
            agent = find_by_name(agents, "ProductIQ Data Agent")
            agent_id = agent["id"] if agent else None
        if agent_id:
            mcp = f"https://api.fabric.microsoft.com/v1/mcp/workspaces/{ws_id}/dataagents/{agent_id}/agent"
            save_outputs({"FABRIC_DATA_AGENT_ID": agent_id, "FABRIC_DATA_AGENT_MCP_URL": mcp})
            log(f"Data agent {agent_id}\n    MCP endpoint: {mcp}")

    print("\nFabric setup complete. Next: scripts/06-setup-knowledge.ps1")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
