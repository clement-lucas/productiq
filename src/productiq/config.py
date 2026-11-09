"""Settings loaded from the environment variables defined in docs/CONTRACT.md.

App-local optional variables (not part of the shared contract) are prefixed PRODUCTIQ_.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping

# Cosmos containers and their partition keys (CONTRACT.md).
COSMOS_CONTAINERS: dict[str, str] = {
    "sessions": "/userId",
    "projects": "/projectId",
    "chatBindings": "/chatId",
    "memories": "/scopeId",
    "scorecards": "/projectId",
    "decisions": "/projectId",
    "audit": "/projectId",
}


def _flag(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # Azure
    azure_tenant_id: str = ""
    azure_subscription_id: str = ""
    azure_resource_group: str = ""
    azure_location: str = ""
    # Foundry
    foundry_account_name: str = ""
    foundry_project_name: str = ""
    foundry_project_endpoint: str = ""
    foundry_openai_endpoint: str = ""
    model_reasoning_deployment: str = "gpt-5.4"
    model_router_deployment: str = "gpt-5.4-mini"
    model_embedding_deployment: str = "text-embedding-3-large"
    search_endpoint: str = ""
    search_knowledge_base: str = "productiq-kb"
    # Cosmos
    cosmos_endpoint: str = ""
    cosmos_database: str = "productiq"
    # Observability / platform
    applicationinsights_connection_string: str = ""
    key_vault_uri: str = ""
    storage_account_name: str = ""
    # Bot / Graph / Teams
    bot_app_id: str = ""
    bot_app_tenant_id: str = ""
    bot_msi_resource_id: str = ""
    bot_oauth_connection_name: str = "graph-sso"
    graph_app_client_id: str = ""
    teams_app_catalog_id: str = ""
    # Foundry connections (used by the prompt agents, informational here)
    fabric_iq_connection_name: str = "fabriciq-dataagent"
    kb_mcp_connection_name: str = "foundryiq-kb"
    bing_connection_name: str = "bing-grounding"
    # App-local (PRODUCTIQ_*)
    port: int = 8000
    memory_backend: str = "cosmos"  # cosmos | memory
    use_foundry_memory: bool = False  # preview hook, Cosmos stays the fallback
    scorecard_weights: str = ""  # JSON string or path to JSON file
    approval_ttl_minutes: int = 30
    managed_identity_client_id: str = ""
    extra: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        e = os.environ if env is None else env
        g = lambda k, d="": (e.get(k) or d).strip()  # noqa: E731
        return cls(
            azure_tenant_id=g("AZURE_TENANT_ID"),
            azure_subscription_id=g("AZURE_SUBSCRIPTION_ID"),
            azure_resource_group=g("AZURE_RESOURCE_GROUP"),
            azure_location=g("AZURE_LOCATION"),
            foundry_account_name=g("FOUNDRY_ACCOUNT_NAME"),
            foundry_project_name=g("FOUNDRY_PROJECT_NAME"),
            foundry_project_endpoint=g("FOUNDRY_PROJECT_ENDPOINT"),
            foundry_openai_endpoint=g("FOUNDRY_OPENAI_ENDPOINT"),
            model_reasoning_deployment=g("MODEL_REASONING_DEPLOYMENT", "gpt-5.4"),
            model_router_deployment=g("MODEL_ROUTER_DEPLOYMENT", "gpt-5.4-mini"),
            model_embedding_deployment=g("MODEL_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"),
            search_endpoint=g("SEARCH_ENDPOINT"),
            search_knowledge_base=g("SEARCH_KNOWLEDGE_BASE", "productiq-kb"),
            cosmos_endpoint=g("COSMOS_ENDPOINT"),
            cosmos_database=g("COSMOS_DATABASE", "productiq"),
            applicationinsights_connection_string=g("APPLICATIONINSIGHTS_CONNECTION_STRING"),
            key_vault_uri=g("KEY_VAULT_URI"),
            storage_account_name=g("STORAGE_ACCOUNT_NAME"),
            bot_app_id=g("BOT_APP_ID"),
            bot_app_tenant_id=g("BOT_APP_TENANT_ID") or g("AZURE_TENANT_ID"),
            bot_msi_resource_id=g("BOT_MSI_RESOURCE_ID"),
            bot_oauth_connection_name=g("BOT_OAUTH_CONNECTION_NAME", "graph-sso"),
            graph_app_client_id=g("GRAPH_APP_CLIENT_ID"),
            teams_app_catalog_id=g("TEAMS_APP_CATALOG_ID"),
            fabric_iq_connection_name=g("FABRIC_IQ_CONNECTION_NAME", "fabriciq-dataagent"),
            kb_mcp_connection_name=g("KB_MCP_CONNECTION_NAME", "foundryiq-kb"),
            bing_connection_name=g("BING_CONNECTION_NAME", "bing-grounding"),
            port=int(g("PORT", "8000")),
            memory_backend=g("PRODUCTIQ_MEMORY_BACKEND", "cosmos" if g("COSMOS_ENDPOINT") else "memory").lower(),
            use_foundry_memory=_flag(e.get("PRODUCTIQ_USE_FOUNDRY_MEMORY")),
            scorecard_weights=g("PRODUCTIQ_SCORECARD_WEIGHTS"),
            approval_ttl_minutes=int(g("PRODUCTIQ_APPROVAL_TTL_MINUTES", "30")),
            # The Container App and the bot share the user-assigned MI (BOT_APP_ID = MI client id).
            managed_identity_client_id=g("AZURE_CLIENT_ID") or g("BOT_APP_ID"),
        )

    def agents_sdk_env(self) -> dict[str, str]:
        """Env vars expected by microsoft_agents load_configuration_from_env().

        TODO(verify): key names / AUTHTYPE literal against the pinned microsoft-agents-* version.
        """
        prefix = "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__"
        handler = "AGENTAPPLICATION__USERAUTHORIZATION__HANDLERS__GRAPH__SETTINGS__"
        return {
            prefix + "AUTHTYPE": "UserManagedIdentity",
            prefix + "CLIENTID": self.bot_app_id,
            prefix + "TENANTID": self.bot_app_tenant_id,
            handler + "AZUREBOTOAUTHCONNECTIONNAME": self.bot_oauth_connection_name,
            handler + "TITLE": "Sign in to Microsoft Graph",
            handler + "TEXT": "ProductIQ needs your consent to schedule meetings and create chats.",
        }
