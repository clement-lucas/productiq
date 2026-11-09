# ProductIQ service (`src/`)

Agentic product-innovation copilot for the fictional **Contoso Home Appliances** (all data synthetic).
One Python service (Azure Container Apps) serves Microsoft 365 Copilot / Teams (custom engine agent via
Azure Bot Service, bot type **UserAssignedMSI**) and a web app. Shared names (env vars, Cosmos containers,
Foundry agent names, scorecard weights) come from [`docs/CONTRACT.md`](../docs/CONTRACT.md).

## Modules (`productiq/`)

| Module | Purpose |
|---|---|
| `app.py` | aiohttp server: `POST /api/messages` (Agents SDK, JWT), `POST /api/ask`, `GET /api/projects/{id}`, `GET /healthz` |
| `bot.py` | Microsoft 365 Agents SDK handlers: messages, @mention stripping, `installationUpdate`, `membersAdded`, Action.Submit (approvals) |
| `orchestrator.py` | **Product Strategist** + **Concept Designer** (Microsoft Agent Framework, isolated in `AgentRunner`), intents/commands |
| `specialists.py` | Parallel calls to the Foundry prompt agents via Responses API + `agent_reference` |
| `collaboration.py` | **Collaboration Agent**: Graph findMeetingTimes, Teams meeting, group chat, app install, summary card |
| `approval.py` | Human-in-the-loop gate: pending action (id, expiry, payload) executed only on the same user's Approve |
| `memory.py` | `MemoryStore` logic + `CosmosMemoryStore` / `InMemoryStore`; optional Foundry managed-memory hook |
| `scorecard.py` | Weights (validated to sum to 100), weighted totals, ranking, versioned re-scoring – all in Python |
| `guardrails.py` | Retrieved content as data (injection stripping), numeric-claim grounding, PII redaction, language detection |
| `cards.py` | Adaptive Cards 1.5: answer + scorecard bars, approval preview, project summary |
| `telemetry.py` | `configure_azure_monitor` when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set; spans per specialist / Graph call |
| `config.py` | `Settings` dataclass from CONTRACT env vars (+ app-local `PRODUCTIQ_*`) |
| `prompts/` | System prompts for the Strategist and Concept Designer |

App-local optional env vars: `PORT` (8000), `PRODUCTIQ_MEMORY_BACKEND` (`cosmos`|`memory`; defaults to
`memory` when `COSMOS_ENDPOINT` is empty), `PRODUCTIQ_USE_FOUNDRY_MEMORY` (false), `PRODUCTIQ_SCORECARD_WEIGHTS`
(JSON string or file path, must sum to 100), `PRODUCTIQ_APPROVAL_TTL_MINUTES` (30), `AZURE_CLIENT_ID`
(managed identity client id; falls back to `BOT_APP_ID`).

## Request flow

```
Teams / M365 Copilot ──► Azure Bot Service ──► POST /api/messages ─┐
Web app ───────────────────────────────────► POST /api/ask ───────┤
                                                                   ▼
                                     ProductStrategist.handle(ctx, text)
   1. classify intent (ask / re-score / decide / kickoff / memory commands)
   2. resolve project: group chat → chatBindings[chatId] → membership check; 1:1 → session.activeProjectId
   3. load user memory (Cosmos `memories`, or Foundry memory hook)
   4. asyncio.gather → productiq-voc-analyst | -market-scout | -cost-supplier | -logistics | -future-tech
   5. sanitise outputs (<data> envelope, injection stripping) → Concept Designer (JSON: 3 options, 1–5 scores)
   6. scorecard.py computes weighted totals + ranking → saved to `scorecards`, findings → `projects`
   7. Strategist writes the answer (user's language); unsupported numbers are flagged
   8. markdown + Adaptive Card returned
"set up a kickoff" → bot gets delegated Graph token (OAuth connection graph-sso) → findMeetingTimes (read)
   → pending action + approval card → user clicks Approve → chat, bind, install app, Teams meeting, summary card
```

Chat commands: `help`, `re-score option C using the current motor platform`, `decide option C because …`,
`set up a kickoff meeting`, `add ken@contoso.example as Design`, `link project prj-…`, `new project: …`,
`remember that …`, `show my memory`, `forget me` (deletes the user's session, pending approvals and personal
memories; shared project records stay with the team).

## Run locally

```bash
cd src
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp ../.env .env            # written by scripts/03-deploy-infra.ps1; `az login` for DefaultAzureCredential
python -m productiq.app    # http://localhost:8000/healthz
curl -s localhost:8000/api/ask -H 'content-type: application/json' \
  -d '{"userId":"local-aiko","question":"Propose three concepts for pet owners"}'
```

* Leave `BOT_APP_ID` empty to run the web API only (Cosmos falls back to the in-memory store when
  `COSMOS_ENDPOINT` is empty).
* Bot testing: **Microsoft 365 Agents Playground** (`teamsapptester`) against `http://localhost:8000/api/messages`,
  or expose the port with **Dev Tunnels** (`devtunnel host -p 8000 --allow-anonymous`) and set the Azure Bot
  messaging endpoint to `https://<tunnel>/api/messages`. A UserAssignedMSI bot cannot authenticate from a laptop –
  for local Teams testing use a separate SingleTenant dev bot with a client secret
  (`CONNECTIONS__SERVICE_CONNECTION__SETTINGS__AUTHTYPE=ClientSecret`, `…CLIENTSECRET`).
* Web routes trust `userId` from the body only when no `X-MS-CLIENT-PRINCIPAL-ID` header exists – enable
  Container Apps built-in auth (Entra) in Azure.

Tests (repo root, stdlib only – no Azure SDKs needed):

```bash
PYTHONPATH=src python -m unittest discover -s tests -t .
```

Container: `docker build -t productiq src` (python:3.12-slim, non-root, port 8000).

## Where to extend

* **MVP**: Strategist, Concept Designer, the five Foundry specialists, Collaboration Agent, Cosmos memory.
* **Stretch**: add a specialist → create the Foundry prompt agent, add it to `SPECIALIST_AGENTS` and
  `_SPECIALIST_KEYWORDS`; PRD writer to Word/Loop; web-app approvals via OBO token; Foundry managed memory
  (`FoundryMemoryHook`); LLM-based intent routing instead of regexes; streaming responses in Copilot;
  Action.Execute (Universal Actions) to refresh approval cards in place.

## Required Graph delegated permissions (Entra app `ProductIQ-Graph`, connection `graph-sso`)

`User.ReadBasic.All`, `Calendars.ReadWrite`, `Chat.Create`, `ChatMember.ReadWrite`,
`TeamsAppInstallation.ReadWriteSelfForChat`, `ChatMessage.Send` (+ `openid profile offline_access`).
The managed identity needs **Cosmos DB Built-in Data Contributor** and **Azure AI User** on the Foundry project.

## Preview / unverified APIs (search for `TODO(verify)`)

| Where | Assumption |
|---|---|
| `orchestrator.AgentRunner` | `from agent_framework import Agent`, `from agent_framework.foundry import FoundryChatClient(project_endpoint=, model=, credential=)`, `await agent.run(text)` → `.text`. Older builds: `ChatAgent(chat_client=…)`, `AzureAIAgentClient`. |
| `specialists.py` | `AIProjectClient(...).get_openai_client()` (sync on 2.x) and `responses.create(extra_body={"agent_reference": {"name", "type": "agent_reference"}})`; some previews used the key `"agent"` (`AGENT_REF_KEY`). Citations read from `output[].content[].annotations[].url`. |
| `bot.py` | Agents SDK: `Authorization(storage, connections, **config)`, `auth.get_token(context, "GRAPH")`, `auth.begin_or_continue_flow(...)`, `MessageFactory`/`CardFactory` in `microsoft_agents.hosting.core`, `@app.error`, activity fields `from_property.aad_object_id`. |
| `config.agents_sdk_env()` | Env names `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__AUTHTYPE=UserManagedIdentity` and `AGENTAPPLICATION__USERAUTHORIZATION__HANDLERS__GRAPH__SETTINGS__AZUREBOTOAUTHCONNECTIONNAME`. |
| `memory.FoundryMemoryHook` | Foundry managed memory is preview – stub returns `None` so Cosmos is used. |
| `collaboration.py` | Graph `POST /chats` group chat requires ≥ 3 members; installing an app into a chat needs the app published to the org catalog (`TEAMS_APP_CATALOG_ID`) and RSC/consent. |
