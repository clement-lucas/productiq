"""
Foundry IQ knowledge setup (Azure AI Search agentic retrieval):
  1. uploads the synthetic knowledge documents (data/output/knowledge/*.md) to the "knowledge" blob container
  2. creates blob knowledge source "productiq-docs-ks" (Search generates data source, skillset, index, indexer;
     chunks + vectorises with the Foundry embedding deployment via the search service managed identity)
  3. waits for the first ingestion, then creates knowledge base "productiq-kb"
  4. runs a test retrieval

Usage: python scripts/foundry/setup_knowledge.py [--skip-upload]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from piq_common import REPO_ROOT, SCOPE_SEARCH, Rest, credential, load_outputs, log, require, step  # noqa: E402

API = "2026-08-01-preview"   # preview: matches the knowledge base MCP endpoint used by Foundry Agent Service
KS_NAME = "productiq-docs-ks"


def upload_docs(account: str) -> int:
    from azure.storage.blob import BlobServiceClient, ContentSettings

    folder = REPO_ROOT / "data" / "output" / "knowledge"
    if not folder.exists():
        sys.exit("data/output/knowledge not found – run scripts/04-generate-data.ps1 first.")
    svc = BlobServiceClient(f"https://{account}.blob.core.windows.net", credential=credential())
    container = svc.get_container_client("knowledge")
    n = 0
    for f in sorted(folder.glob("*.md")):
        with f.open("rb") as fh:
            container.upload_blob(f.name, fh, overwrite=True,
                                  content_settings=ContentSettings(content_type="text/markdown"),
                                  metadata={"source": "synthetic-demo", "company": "Contoso Home Appliances"})
        n += 1
        log(f"uploaded {f.name}")
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-upload", action="store_true")
    args = ap.parse_args()
    out = load_outputs()
    search_ep, storage_name, storage_id, aoai, emb, router, kb_name = require(
        out, "SEARCH_ENDPOINT", "STORAGE_ACCOUNT_NAME", "STORAGE_ACCOUNT_ID", "FOUNDRY_OPENAI_ENDPOINT",
        "MODEL_EMBEDDING_DEPLOYMENT", "MODEL_ROUTER_DEPLOYMENT", "SEARCH_KNOWLEDGE_BASE")
    search = Rest(search_ep, SCOPE_SEARCH)

    if not args.skip_upload:
        step("Uploading knowledge documents to Blob Storage")
        log(f"{upload_docs(storage_name)} documents uploaded")

    step(f"Creating blob knowledge source {KS_NAME}")
    ks = {
        "name": KS_NAME,
        "kind": "azureBlob",
        "description": "Contoso Home Appliances market reports, design guidelines, PRDs, supplier briefs, technology radar (synthetic).",
        "azureBlobParameters": {
            "connectionString": f"ResourceId={storage_id};",
            "containerName": "knowledge",
            "isADLSGen2": False,
            "ingestionParameters": {
                "disableImageVerbalization": True,
                "contentExtractionMode": "minimal",
                "embeddingModel": {"kind": "azureOpenAI", "azureOpenAIParameters": {
                    "resourceUri": aoai, "deploymentId": emb, "modelName": emb}},
                "chatCompletionModel": {"kind": "azureOpenAI", "azureOpenAIParameters": {
                    "resourceUri": aoai, "deploymentId": router, "modelName": router}},
            },
        },
    }
    search.put(f"/knowledgesources/{KS_NAME}?api-version={API}", ks, lro=False)
    log("Knowledge source created – waiting for first ingestion (2–10 min)")
    for _ in range(90):
        time.sleep(10)
        st = search.get(f"/knowledgesources/{KS_NAME}/status?api-version={API}", lro=False)
        last = st.get("lastSynchronizationState") or {}
        if last.get("endTime"):
            log(f"Ingestion finished: processed={last.get('itemUpdatesProcessed')} failed={last.get('itemsUpdatesFailed')}")
            break
    else:
        log("Ingestion still running – the knowledge base is created anyway; check the indexer in the portal.")

    step(f"Creating knowledge base {kb_name}")
    kb = {
        "name": kb_name,
        "description": "ProductIQ knowledge base (Foundry IQ) over Contoso product documents.",
        "knowledgeSources": [{"name": KS_NAME}],
        "retrievalInstructions": "Use for market reports, design guidelines, past PRDs, supplier briefs and technology trends of Contoso Home Appliances.",
        "outputMode": "extractiveData",
        "retrievalReasoningEffort": {"kind": "minimal"},
    }
    search.put(f"/knowledgebases/{kb_name}?api-version={API}", kb, lro=False)
    log("Knowledge base created")

    step("Test retrieval")
    try:
        r = search.post(f"/knowledgebases/{kb_name}/retrieve?api-version={API}",
                        {"intents": [{"type": "semantic", "search": "pet hair tangling brush roll market demand"}]}, lro=False)
        refs = r.json().get("references", [])
        log(f"{len(refs)} references returned")
    except RuntimeError as e:
        log(f"Retrieve test skipped: {e}")
    print(f"\nKnowledge base MCP endpoint: {search_ep}/knowledgebases/{kb_name}/mcp?api-version={API}")
    print("Next: scripts/07-setup-foundry.ps1")


if __name__ == "__main__":
    main()
