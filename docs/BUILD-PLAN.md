# ProductIQ – Build plan (Hack to Build 2026)

**Build window:** Mon 9 Nov → Fri 27 Nov 2026 (the HTB build phase opened 2 Nov; this plan starts from 9 Nov)
**Judging:** 23 Nov – 11 Dec 2026 · **Badge:** 16 Dec 2026
**Owner:** Clement Lucas (PSA). Team members: _[add]_
**Environment:** M365 tenant `DIAx98389119.onmicrosoft.com` · Azure subscription `ME-DIAx98389119-cllucas-2` · region `eastus2` (change in `config/environment.json`)

> Judges start reviewing on **23 Nov**, so the MVP must be demo-ready by **Sun 22 Nov**. Week 3 is for collaboration features, hardening and storytelling, not core build.

## Milestones

| # | Date | Milestone | Exit criteria (definition of done) |
|---|------|-----------|------------------------------------|
| M0 | Mon 9 Nov | Repo & environment bootstrapped | `00`–`03` scripts run; resource group, Foundry project, models, AI Search, Cosmos DB, Key Vault, Container Apps, Bot Service, Fabric capacity deployed; ARM template compiled by CI |
| M1 | Fri 13 Nov | Data foundation live | 24 months of synthetic data in OneLake; bronze → silver → gold notebooks succeed; **ProductIQ Data Agent** published and answers 5 golden questions correctly; Foundry IQ knowledge base returns cited documents |
| M2 | Wed 18 Nov | Specialist agents grounded | 5 Foundry prompt agents with Fabric IQ, knowledge base and Bing tools pass the smoke test; tracing in Application Insights |
| M3 | Sun 22 Nov | **MVP demo-ready** (before judging starts) | Agent Framework orchestrator returns ranked options + weighted scorecard + citations in ≤ 90 s; reachable in Teams 1:1 and Microsoft 365 Copilot; project memory saved in Cosmos DB; evaluation baseline recorded |
| M4 | Wed 25 Nov | Collaboration + hardening | Approval card → Teams meeting + group chat created via Graph; ProductIQ installed in the chat and answers @mentions from project memory; RAI/security checklist complete; evaluation thresholds met |
| M5 | Fri 27 Nov | **Final submission** | Demo video, architecture, README, evaluation report and repo link submitted in the HTB portal; Fabric capacity paused |

## Week 1 – Foundation & data (9–15 Nov)

| Day | Work | Script / artefact | Done when |
|-----|------|-------------------|-----------|
| Mon 9 | Install tools; create GitHub repo; fill `config/environment.json`; sign in; deploy infrastructure (what-if first) | `00`, `01`, `02 -WhatIf`, `02` | Deployment succeeded; `.env` written |
| Mon 9 | Entra app for Graph + Teams SSO; redeploy to add bot OAuth connection | `03` | `graph-sso` connection visible on the Azure Bot |
| Tue 10 | Enable Fabric tenant settings; generate data; create workspace/lakehouse; upload bronze; run notebooks | `04`, `05` | Gold tables populated; row counts match `data/output/manifest.json` |
| Wed 11 | Create + publish Fabric data agent; tune instructions & example queries; run Fabric data agent evaluation (SDK) | `05`, `fabric/data-agent/*` | ≥ 80% of data golden questions correct |
| Thu 12 | Knowledge documents → Blob + SharePoint; knowledge source + knowledge base | `06`, `08` (docs only) | Retrieve returns cited docs for "pet hair tangling" |
| Fri 13 | Optional: Direct Lake semantic model + Fabric IQ ontology (preview) for business terms; **M1 review** | portal | M1 exit criteria met |
| Sat–Sun | Buffer / catch-up | | |

## Week 2 – Agents, orchestration and channels (16–22 Nov)

| Day | Work | Script / artefact | Done when |
|-----|------|-------------------|-----------|
| Mon 16 | Foundry connections (Fabric IQ, knowledge base MCP); create 5 specialist agents; smoke test | `07` | Each agent answers its scenario question with sources |
| Tue 17 | Agent Framework orchestrator: memory load → parallel specialists → Concept Designer → scorecard (Python-computed) | `src/productiq/orchestrator.py`, `scorecard.py` | `/api/ask` returns 3 options + scorecard locally |
| Wed 18 | Cosmos DB project memory + user memory commands; OpenTelemetry tracing; **M2 review** | `memory.py`, App Insights | Traces show one span per specialist |
| Thu 19 | Build image in ACR + deploy to Container Apps; Teams app package; publish to org catalog | `11`, `09`, `10` | Bot answers in Teams 1:1 |
| Fri 20 | Microsoft 365 Copilot custom engine agent (same bot); answer card with scorecard & citations | manifest `copilotAgents` | Agent works in Copilot Chat for a demo user |
| Sat 21 | Golden evaluation run + fixes (groundedness, numeric accuracy) | `12`, `eval/` | Baseline report saved |
| Sun 22 | **M3: MVP demo-ready**; record a backup demo video of the MVP | | Demo script runs end-to-end twice |

## Week 3 – Collaboration, Responsible AI, security, storytelling (23–27 Nov)

| Day | Work | Done when |
|-----|------|-----------|
| Mon 23 | Collaboration Agent: approval card → findMeetingTimes → Teams meeting → group chat → install app → summary card; bind projectId ↔ chatId | Meeting + chat created only after Approve |
| Tue 24 | @mention in group chat answered from project memory; re-score and decision logging; membership check | Maria's question answered without re-explaining |
| Wed 25 | RAI & security hardening: prompt-injection tests (review text, web), content filters/prompt shields, PII redaction in logs, least-privilege review, Key Vault only, optional private endpoints; **M4 review** | Checklist in `docs/SECURITY.md` ticked |
| Thu 26 | Final evaluation run (thresholds: groundedness ≥ 4/5, numeric accuracy ≥ 90%, red-team pass 100%); demo video (use the user-scenario storyboard); update deck and architecture | Video + report ready |
| Fri 27 | **M5: submit** in the HTB portal; tag release `v1.0-htb`; pause Fabric capacity | Submission confirmed |

## After the build phase
- 23 Nov – 11 Dec: answer judge questions; keep the environment available (resume Fabric capacity only for demos).
- 16 Dec: badge. Then: customer-zero pilot plan with a GSI partner; tear down or downsize (`scripts/99-teardown.ps1`).

## MVP vs stretch

| MVP (must) | Stretch (if time) |
|---|---|
| Product Strategist (orchestrator), Voice-of-Customer, Market & Trend Scout, Cost & Supplier, Collaboration Agent | Future Tech Explorer, Logistics Analyst as separate agents; Concept Designer PRD export to Word |
| Fabric data agent over gold lakehouse via Fabric IQ | Fabric IQ ontology, Direct Lake semantic model, Eventstream for live reviews |
| Cosmos DB project memory | Foundry managed memory (preview), hosted agent deployment |
| Teams 1:1 + group chat, Microsoft 365 Copilot | Web app (React) on Container Apps |
| Public endpoints + Entra-only auth | Private endpoints / BYO VNet, standard agent setup |

## Judging criteria → evidence

| Criterion | Evidence to show |
|---|---|
| Business impact | Time from question to ranked options (target ≥ 50% faster); fewer alignment meetings; risks found before design freeze |
| Architecture | `ProductIQ-Architecture.html`, IaC in `infra/`, Fabric medallion, Foundry IQ + Fabric IQ |
| Innovation | Multi-agent reasoning over Fabric + knowledge + web, memory that follows the project from Copilot into Teams |
| Responsible AI | Human approval before actions, citations, numbers only from Fabric, red-team set in `eval/`, content safety |
| Security | Managed identities, keyless (disableLocalAuth), Key Vault, RBAC least privilege, RSC in Teams |
| Build quality | CI (Bicep build/lint, unit tests), idempotent scripts, evaluation gate |
| Storytelling | Architecture walkthrough + user-scenario videos, live demo |

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Preview APIs change (Fabric IQ tool, knowledge base MCP, data agent SDK) | Scripts try alternative payloads and print portal fallbacks; pin SDK versions once working |
| Model not available in region / quota | Change model names/region in `config/environment.json`; GlobalStandard deployments |
| Fabric tenant settings or Teams admin policies block setup | Demo tenant admin enables settings on day 1 (checklist in README) |
| Fabric capacity cost | F2 default; `scripts/fabric-capacity.ps1 -Action Suspend` every evening |
| Graph permissions / consent for group chat install | Admin consent in `03`; RSC in manifest; fallback: bot posts proactive message |
| Time | MVP scope above; buffer weekends; record backup demo on 22 Nov |

## Daily routine
1. `fabric-capacity.ps1 -Action Resume` → work → `-Action Suspend`
2. Commit small changes; CI must be green
3. Log decisions in `docs/DECISIONS.md` (optional) and update this plan's status column
