# Security & Responsible AI checklist

## Security (lab defaults → production)

| Control | Lab (this repo) | Production / customer-zero |
|---|---|---|
| Authentication | Entra ID only: `disableLocalAuth` on Foundry and Cosmos DB, no shared keys on Storage | Same, plus Conditional Access for users |
| Secrets | None in code or repo. Bot uses a managed identity. The Graph app secret lives in Key Vault only | Federated credentials instead of a client secret; Key Vault purge protection ON |
| Authorisation | Least-privilege RBAC (`roles.bicep`); Cosmos DB data-plane RBAC | Separate identities per agent (Entra Agent ID); PIM for admins |
| Network | Public endpoints restricted by Entra auth | Private endpoints for Foundry (BYO VNet), AI Search, Cosmos DB, Storage, Key Vault; Container Apps in a VNet; Fabric private links |
| Data access | Fabric permissions enforced on the connection identity (user passthrough by default) | OneLake security / RLS in the semantic model; document-level ACLs in the knowledge base |
| Teams | Resource-specific consent (chat scope), admin-approved org app | Same, plus an app permission policy for the pilot group |
| Governance | Tags, synthetic data label | Microsoft Purview (sensitivity labels, DLP, Fabric data map), audit container in Cosmos DB |
| Supply chain | CI builds Bicep, lints PowerShell, runs tests | Dependabot, CodeQL, signed container images, branch protection |

## Responsible AI

- [ ] **Human in the loop:** meetings, chats and posts are created only after the user clicks **Approve** (`src/productiq/approval.py`).
- [ ] **Grounded numbers:** the scorecard is computed in code from cited specialist outputs. The model never invents figures, and a guardrail flags numbers without a source.
- [ ] **Citations** to Fabric queries, knowledge documents and web pages appear in every answer.
- [ ] **Prompt-injection defence:** retrieved text (reviews, documents, web pages) is treated as data. The red-team prompts in `eval/golden_qa.jsonl` include an injection hidden in a review.
- [ ] **Content safety:** Foundry guardrails (content filters, Prompt Shields) are on for all deployments.
- [ ] **Privacy:** feedback is aggregated with no customer PII, PII is redacted from logs, and users can view or clear their memory ("show my memory", "forget me").
- [ ] **Transparency:** the Copilot agent disclaimer says the content is AI-generated and the data is synthetic.
- [ ] **Evaluation gate:** numeric accuracy ≥ 90%, red-team pass rate 100%, groundedness ≥ 4/5 (Foundry evaluations) before a new agent version is promoted.
- [ ] **Data boundary:** Grounding with Bing and cross-geo Fabric AI processing send data outside the Azure compliance boundary. Both are documented and can be switched off (`enableBingGrounding=false`).
