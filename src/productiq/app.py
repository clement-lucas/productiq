"""aiohttp entry point: `python -m productiq.app`.

Routes
  POST /api/messages      Teams / M365 Copilot (Agents SDK, JWT-validated)
  POST /api/ask           web app  {userId, projectId?, question}
  GET  /api/projects/{id} web app  (membership enforced)
  GET  /healthz
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from aiohttp import web

from . import telemetry
from .approval import ApprovalGate
from .collaboration import CollaborationAgent
from .config import Settings
from .memory import FoundryMemoryHook, NotAMemberError, create_store
from .orchestrator import AgentRunner, ProductStrategist, RequestContext
from .scorecard import load_weights
from .specialists import SpecialistClient

log = logging.getLogger("productiq")
EASY_AUTH_HEADER = "X-MS-CLIENT-PRINCIPAL-ID"  # set by Container Apps built-in auth (Entra)


def _caller_id(request: web.Request, body_user: str | None = None) -> str:
    """Prefer the platform-authenticated identity; a body userId must match it when both exist.

    Without Easy Auth (local dev) the body/query userId is trusted – never expose that publicly.
    """
    principal = request.headers.get(EASY_AUTH_HEADER)
    if principal and body_user and body_user != principal:
        raise web.HTTPForbidden(text="userId does not match the signed-in user")
    user = principal or body_user or request.query.get("userId")
    if not user:
        raise web.HTTPUnauthorized(text="sign-in required")
    return user


async def healthz(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def ask(request: web.Request) -> web.Response:
    body = await request.json()
    question = (body.get("question") or "").strip()
    if not question:
        raise web.HTTPBadRequest(text="question is required")
    ctx = RequestContext(user_id=_caller_id(request, body.get("userId")), channel="web",
                         project_id=body.get("projectId"))
    reply = await request.app["strategist"].handle(ctx, question)
    out: dict[str, Any] = {"projectId": reply.project_id, "intent": reply.intent.value,
                           "markdown": reply.markdown, "card": reply.card, "data": reply.data}
    if reply.needs_collaboration:
        # Graph writes need the user's delegated token + card approval: done in Teams for the MVP.
        out["markdown"] += "\n\nOpen ProductIQ in Teams to approve the kickoff meeting and project chat."
    return web.json_response(out)


async def get_project(request: web.Request) -> web.Response:
    store = request.app["store"]
    try:
        project = await store.get_project_for_member(request.match_info["id"], _caller_id(request))
    except KeyError:
        raise web.HTTPNotFound()
    except NotAMemberError:
        raise web.HTTPForbidden(text="not a project member")
    return web.json_response({"project": project.to_item(),
                              "scorecard": await store.latest_scorecard(project.projectId)})


def build_app(settings: Settings | None = None) -> web.Application:
    settings = settings or Settings.from_env()
    telemetry.configure(settings.applicationinsights_connection_string)

    from azure.identity.aio import DefaultAzureCredential  # lazy: SDK only needed at runtime

    credential = DefaultAzureCredential(managed_identity_client_id=settings.managed_identity_client_id or None)
    store = create_store(settings, credential)
    gate = ApprovalGate(store, ttl=timedelta(minutes=settings.approval_ttl_minutes))
    strategist = ProductStrategist(
        store=store,
        specialists=SpecialistClient(settings.foundry_project_endpoint, credential),
        runner=AgentRunner(settings, credential),
        weights=load_weights(settings.scorecard_weights),
        memory_hook=FoundryMemoryHook(settings.use_foundry_memory),  # TODO: pass project client when wired
    )
    collab = CollaborationAgent(store, gate, settings.teams_app_catalog_id)

    middlewares: list[Any] = []
    app_routes = [web.get("/healthz", healthz), web.post("/api/ask", ask), web.get("/api/projects/{id}", get_project)]
    bot_parts = None
    if settings.bot_app_id:
        from microsoft_agents.hosting.aiohttp import jwt_authorization_middleware, start_agent_process

        from .bot import create_agent_app

        bot_parts = create_agent_app(settings, store, strategist, gate, collab)

        @web.middleware
        async def bot_jwt_only(request: web.Request, handler: Any) -> web.StreamResponse:
            # Bot Framework JWT validation applies to /api/messages only; web routes use Easy Auth.
            if request.path == "/api/messages":
                return await jwt_authorization_middleware(request, handler)
            return await handler(request)

        async def messages(request: web.Request) -> web.Response:
            return await start_agent_process(request, request.app["agent_app"], request.app["adapter"])

        middlewares.append(bot_jwt_only)
        app_routes.append(web.post("/api/messages", messages))
    else:
        log.warning("BOT_APP_ID not set – /api/messages disabled (web API only)")

    app = web.Application(middlewares=middlewares)
    app.add_routes(app_routes)
    app.update(settings=settings, store=store, strategist=strategist, gate=gate, collab=collab)
    if bot_parts:
        app["agent_app"], app["adapter"], app["agent_configuration"] = bot_parts

    async def _close(_: web.Application) -> None:
        if hasattr(store, "close"):
            await store.close()
        await credential.close()

    app.on_cleanup.append(_close)
    return app


def main() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    settings = Settings.from_env()
    web.run_app(build_app(settings), host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    main()
