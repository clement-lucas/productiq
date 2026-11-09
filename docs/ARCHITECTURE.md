# ProductIQ – Architecture notes for builders

See the README diagram for the big picture and `ProductIQ-Architecture.html` (project files) for the interactive version. This page maps the architecture to the code and IaC in this repo.

## Components → where they live

| Layer | Component | Repo location | Notes |
|---|---|---|---|
| Experience | Microsoft 365 Copilot (custom engine agent), Teams 1:1 + group chat | `teams-app/` | Manifest 1.22, `copilotAgents.customEngineAgents`, RSC for chats |
| Experience | Web app API | `src/productiq/app.py` (`/api/ask`, `/api/projects/{id}`) | Turn on Container Apps Entra sign-in before exposing it |
| Channel | Azure Bot Service (UserAssignedMSI) + `graph-sso` OAuth connection | `infra/modules/botservice.bicep` | Teams + Microsoft 365 channels |
| Orchestration | Microsoft Agent Framework – Product Strategist, Concept Designer, Collaboration Agent | `src/productiq/orchestrator.py`, `collaboration.py` | Parallel fan-out to specialists, scorecard computed in Python, human approval gate |
| Agents | Foundry prompt agents (VoC, Market, Cost & Supplier, Logistics, Future Tech) | `scripts/foundry/create_agents.py`, `scripts/foundry/agents/*.md` | Called via Responses API with `agent_reference` |
| Models | gpt-5.4, gpt-5.4-mini, text-embedding-3-large | `infra/modules/foundry.bicep` | Names configurable in `config/environment.json` |
| Knowledge | Foundry IQ knowledge base on Azure AI Search (blob knowledge source) | `scripts/foundry/setup_knowledge.py` | MCP tool `knowledge_base_retrieve` |
| Data | Fabric lakehouse (bronze/silver/gold), notebooks, data agent | `fabric/`, `scripts/fabric/` | Fabric IQ tool connects Foundry agents to the data agent |
| Web | Grounding with Bing Search | `infra/modules/bing.bicep` + connection in `foundry.bicep` | Optional; data leaves the Azure compliance boundary |
| Memory | Cosmos DB (sessions, projects, chatBindings, memories, scorecards, decisions, audit) | `infra/modules/cosmos.bicep`, `src/productiq/memory.py` | Foundry managed memory (preview) behind a flag |
| Security | Managed identity, Key Vault, RBAC, Entra ID only | `identity.bicep`, `keyvault.bicep`, `roles.bicep` | See `docs/SECURITY.md` |
| Ops | Application Insights / Log Analytics, GitHub Actions | `monitoring.bicep`, `.github/workflows/` | OpenTelemetry spans per specialist |

## Identity and connectivity

| From → To | Protocol | Identity |
|---|---|---|
| Teams / Copilot → Bot Service → API | Bot Framework activities (HTTPS) | Bot = user-assigned managed identity; JWT validated by Agents SDK |
| API → Foundry agents | Responses API (HTTPS) | App managed identity (Azure AI User); OBO with the user's token is the production path |
| Foundry agent → Fabric data agent | Fabric IQ tool → MCP | Connection `fabriciq-dataagent`: user identity passthrough (UserEntraToken) or project MI |
| Foundry agent → knowledge base | MCP (`knowledge_base_retrieve`) | Project managed identity (Search Index Data Reader) |
| AI Search → Blob / Foundry embeddings | Indexer + skillset | Search managed identity (Storage Blob Data Reader, Cognitive Services User) |
| API → Cosmos DB | SDK | App MI with Cosmos DB Built-in Data Contributor (data-plane RBAC) |
| API → Microsoft Graph | REST | User's delegated token from `graph-sso` (after Approve) |
| API → App Insights | OpenTelemetry | Connection string |

## Tenancy
Single tenant per customer: Foundry project, Fabric capacity/workspace, Cosmos DB, AI Search and the Teams app all live in the customer's Entra tenant and Azure subscription. The Foundry agent and the Fabric data agent **must be in the same tenant**. A GSI partner deploys with this IaC using delegated least-privilege access (optionally Azure Lighthouse).

## Agent setup mode
The lab uses **basic agent setup** (Microsoft-managed thread/file storage). For production, switch to **standard agent setup**:
- bring your own Cosmos DB, Storage and AI Search, connected through `accounts/projects/capabilityHosts`
- add a **BYO VNet** with private endpoints

Both are tracked as hardening items in the build plan.
