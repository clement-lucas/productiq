# ProductIQ repository contract (shared names – keep consistent)

Repo root: productiq/   Language: Python 3.11 for all scripts and app code. PowerShell 7 for orchestration scripts.
Demo company: fictional "Contoso Home Appliances" (CHA). All data synthetic. Never name a real partner/customer ("GSI partner", "customer-zero").
Supplier/company names must be clearly fictional (e.g. "Kitsune Motor Works", "Nordwind Components") – never real brands.

## Environment variables (.env written by scripts/03-deploy-infra.ps1 from deployment outputs)
AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP, AZURE_LOCATION
FOUNDRY_ACCOUNT_NAME, FOUNDRY_PROJECT_NAME
FOUNDRY_PROJECT_ENDPOINT          # https://<account>.services.ai.azure.com/api/projects/<project>
FOUNDRY_OPENAI_ENDPOINT           # https://<account>.openai.azure.com/
MODEL_REASONING_DEPLOYMENT=gpt-5.4        # synthesis / strategist
MODEL_ROUTER_DEPLOYMENT=gpt-5.4-mini      # specialists / routing
MODEL_EMBEDDING_DEPLOYMENT=text-embedding-3-large
SEARCH_ENDPOINT, SEARCH_KNOWLEDGE_BASE=productiq-kb
COSMOS_ENDPOINT, COSMOS_DATABASE=productiq
  containers (partition key in brackets): sessions[/userId], projects[/projectId], chatBindings[/chatId], memories[/scopeId], scorecards[/projectId], decisions[/projectId], audit[/projectId]
APPLICATIONINSIGHTS_CONNECTION_STRING
KEY_VAULT_URI
STORAGE_ACCOUNT_NAME (blob containers: knowledge, raw-landing)
BOT_APP_ID (= user-assigned managed identity client id, bot type UserAssignedMSI), BOT_APP_TENANT_ID, BOT_MSI_RESOURCE_ID
BOT_OAUTH_CONNECTION_NAME=graph-sso
GRAPH_APP_CLIENT_ID               # Entra app "ProductIQ-Graph" (delegated Graph perms via bot OAuth connection)
TEAMS_APP_CATALOG_ID              # id of the Teams app in the org catalog (for installing into chats)
FABRIC_WORKSPACE_ID, FABRIC_LAKEHOUSE_ID, FABRIC_DATA_AGENT_ID
FABRIC_IQ_CONNECTION_NAME=fabriciq-dataagent
KB_MCP_CONNECTION_NAME=foundryiq-kb
BING_CONNECTION_NAME=bing-grounding

## Foundry prompt agents (created by scripts/foundry/create_agents.py; instructions in scripts/foundry/agents/<name>.md)
productiq-voc-analyst        tools: fabric_iq_preview
productiq-market-scout       tools: bing_grounding + mcp(knowledge base)
productiq-cost-supplier      tools: fabric_iq_preview
productiq-logistics          tools: fabric_iq_preview
productiq-future-tech        tools: bing_grounding + mcp(knowledge base)
Orchestrator "Product Strategist" + "Concept Designer" + "Collaboration Agent" live in src/productiq (Microsoft Agent Framework) and call the prompt agents via the Foundry Responses API (agent_reference).

## Scorecard (default weights, configurable in src/productiq/scorecard.py)
customer_value 25, market_fit 20, cost 15, supplier_risk 15, logistics 10, time_to_market 10, sustainability 5. Scores 1–5.

## Fabric
Workspace "ProductIQ-<env>", lakehouse "productiq_lakehouse".
Bronze CSVs uploaded to Files/bronze/<source_table>/<source_table>.csv
Notebooks: fabric/notebooks/01_bronze_to_silver.ipynb, 02_silver_to_gold.ipynb, 03_create_data_agent.ipynb (fallback)
Gold tables (Delta, lakehouse dbo): dim_product, dim_component, dim_supplier, dim_plant, dim_region, dim_date,
  fact_feedback, fact_sales, fact_bom_cost, fact_supplier_capacity, fact_logistics, fact_market_signal, fact_warranty
Data agent name: "ProductIQ Data Agent"; instructions fabric/data-agent/instructions.md; examples fabric/data-agent/example_queries.json

## Scenario signals that MUST be present in the synthetic data (and validated by the generator)
- Window: 24 months, 2024-11-01 .. 2026-10-31.
- Pet-owner customers: "pet hair tangling on the brush roll" is the #1 complaint topic among pet-owner negative feedback; ~31% (28–34%) of negative pet-owner reviews in the last 18 months (2025-05-01..2026-10-31).
- Pet-care cleaning category demand +12% YoY (market signal; acceptable 10–14%).
- Component "BLM-200 brushless motor" single-sourced from one supplier ("Kitsune Motor Works") at ~85% capacity utilisation in the latest months; qualifying a second supplier adds ~6 weeks lead time (documented in supplier brief + capacity table alt-supplier qualification lead time 42 days).
- Three concept options used in the demo: A "Battery & filter upgrade", B "Modular & repairable", C "Pet-care robot vacuum with anti-tangle brush and self-emptying dock".
