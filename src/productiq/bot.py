"""Teams / Microsoft 365 Copilot channel via the Microsoft 365 Agents SDK for Python.

Handles: message activities (1:1, group chat @mentions), Adaptive Card Action.Submit
(approvals, "set up kickoff"), installationUpdate (bot added to a chat -> welcome/summary)
and membersAdded. SDK imports are lazy so `strip_mentions` etc. are testable without it.

TODO(verify) against the pinned microsoft-agents-* version: Authorization/get_token API,
MessageFactory/CardFactory location, Activity attribute names (from_property, aad_object_id).
"""
from __future__ import annotations

import re
from typing import Any

from . import cards, telemetry
from .approval import ApprovalGate, ApprovalStatus
from .collaboration import CollaborationAgent, GraphError
from .memory import MemoryStore, NotAMemberError
from .orchestrator import ProductStrategist, RequestContext

GRAPH_HANDLER = "GRAPH"  # AGENTAPPLICATION__USERAUTHORIZATION__HANDLERS__GRAPH (-> graph-sso)
_AT_TAG = re.compile(r"<at[^>]*>.*?</at>", re.I | re.S)


def _get(obj: Any, *keys: str) -> Any:
    """Read nested attributes/dict keys from SDK models or plain dicts."""
    for key in keys:
        if obj is None:
            return None
        obj = obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)
    return obj


def strip_mentions(text: str | None, entities: list[Any] | None = None, recipient_id: str | None = None) -> str:
    """Remove the bot's @mention (and any <at>…</at> markup) from a group-chat message."""
    text = text or ""
    for e in entities or []:
        if _get(e, "type") != "mention":
            continue
        mentioned = _get(e, "mentioned", "id")
        mention_text = _get(e, "text")
        if mention_text and (recipient_id is None or mentioned == recipient_id):
            text = text.replace(mention_text, " ")
    text = _AT_TAG.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def create_agent_app(settings: Any, store: MemoryStore, strategist: ProductStrategist,
                     gate: ApprovalGate, collab: CollaborationAgent) -> tuple[Any, Any, Any]:
    """Build (AgentApplication, CloudAdapter, auth configuration) for /api/messages."""
    import os

    from microsoft_agents.activity import load_configuration_from_env
    from microsoft_agents.authentication.msal import MsalConnectionManager
    from microsoft_agents.hosting.aiohttp import CloudAdapter
    from microsoft_agents.hosting.core import (AgentApplication, Authorization, CardFactory, MemoryStorage,
                                               MessageFactory, TurnContext, TurnState)

    for k, v in settings.agents_sdk_env().items():  # derive SDK config from CONTRACT env vars
        if v:
            os.environ.setdefault(k, v)
    sdk_config = load_configuration_from_env(os.environ)
    storage = MemoryStorage()  # bot turn state only; ProductIQ state lives in Cosmos
    connections = MsalConnectionManager(**sdk_config)
    adapter = CloudAdapter(connection_manager=connections)
    authorization = Authorization(storage, connections, **sdk_config)
    app = AgentApplication[TurnState](storage=storage, adapter=adapter, authorization=authorization, **sdk_config)

    async def send(context: TurnContext, markdown: str | None = None, card: dict | None = None) -> None:
        if markdown:
            await context.send_activity(MessageFactory.text(markdown))
        if card:
            await context.send_activity(MessageFactory.attachment(CardFactory.adaptive_card(card)))

    def request_ctx(context: TurnContext, project_id: str | None = None) -> RequestContext:
        a = context.activity
        conv_type = _get(a, "conversation", "conversation_type") or "personal"
        return RequestContext(
            user_id=_get(a, "from_property", "aad_object_id") or _get(a, "from_property", "id"),
            user_name=_get(a, "from_property", "name") or "",
            channel="teams",
            chat_id=_get(a, "conversation", "id"),
            conversation_type=conv_type,
            project_id=project_id,
        )

    async def graph_token(context: TurnContext, state: TurnState) -> str | None:
        """User's delegated Graph token via the bot OAuth connection; starts sign-in if needed."""
        auth = getattr(app, "auth", None) or authorization
        resp = await auth.get_token(context, GRAPH_HANDLER)  # TODO(verify) signature
        token = _get(resp, "token")
        if not token:
            await auth.begin_or_continue_flow(context, state, GRAPH_HANDLER)  # TODO(verify)
            await send(context, "Please sign in, then click the button again.")
        return token

    async def propose_collab(context: TurnContext, state: TurnState, ctx: RequestContext, project_id: str) -> None:
        token = await graph_token(context, state)
        if not token:
            return
        try:
            project = await store.get_project_for_member(project_id, ctx.user_id)
            _, card = await collab.propose(ctx.user_id, project, token)
        except (NotAMemberError, KeyError):
            return await send(context, "You're not a member of that project.")
        except (ValueError, GraphError) as exc:
            return await send(context, f"I couldn't prepare the kickoff: {exc}")
        await send(context, "Here's what I'd set up. Nothing happens until you approve.", card)

    async def on_submit(context: TurnContext, state: TurnState, data: dict[str, Any]) -> None:
        ctx = request_ctx(context)
        verb = data.get("verb")
        if verb == "collab.propose":
            return await propose_collab(context, state, ctx, data.get("projectId", ""))
        if verb != "approval":
            return await send(context, "Sorry, I didn't recognise that action.")
        token = None
        if data.get("decision") == "approve":  # obtain the token first so approval isn't consumed without it
            token = await graph_token(context, state)
            if not token:
                return
        result = await gate.resolve(data.get("actionId", ""), ctx.user_id, data.get("decision", ""),
                                    data.get("requesterId"))
        if result.status is not ApprovalStatus.APPROVED:
            return await send(context, result.message)
        try:
            out = await collab.execute(result.action, token)
        except GraphError as exc:
            telemetry.log.error("collaboration failed: %s", exc)
            return await send(context, f"Approved, but Microsoft Graph returned an error: {exc}")
        steps = ", ".join(f"{k}: {v}" for k, v in out["steps"].items())
        link = f"\n\n[Join the kickoff meeting]({out['joinUrl']})" if out.get("joinUrl") else ""
        await send(context, f"Done ✅ – created the project chat and Teams meeting ({steps}).{link}")

    @app.activity("message")
    async def on_message(context: TurnContext, state: TurnState) -> None:
        a = context.activity
        value = _get(a, "value")
        if isinstance(value, dict) and value.get("verb"):
            return await on_submit(context, state, value)
        text = strip_mentions(_get(a, "text"), _get(a, "entities"), _get(a, "recipient", "id"))
        if not text:
            return await send(context, "Hi! Ask me a product question or type `help`.")
        ctx = request_ctx(context)
        await context.send_activity(MessageFactory.text("Working on it – consulting the specialist agents…"))
        reply = await strategist.handle(ctx, text)
        await send(context, reply.markdown, reply.card)
        if reply.needs_collaboration and reply.project_id:
            await propose_collab(context, state, ctx, reply.project_id)

    @app.activity("installationUpdate")
    async def on_installation(context: TurnContext, _state: TurnState) -> None:
        a = context.activity
        if not str(_get(a, "action") or "").startswith("add"):
            return
        chat_id = _get(a, "conversation", "id")
        project_id = await store.project_id_for_chat(chat_id) if chat_id else None
        project = await store.get_project(project_id) if project_id else None
        if project:  # binding was created by an approved collaboration or a member's `link project`
            latest = await store.latest_scorecard(project.projectId)
            await send(context, None, cards.project_summary_card(project.to_item(), latest))
        else:
            await send(context, "Hi, I'm ProductIQ 👋 Mention me with a product question. A project member "
                                "can link this chat with `@ProductIQ link project <projectId>`.")

    @app.conversation_update("membersAdded")
    async def on_members_added(context: TurnContext, _state: TurnState) -> None:
        bot_id = _get(context.activity, "recipient", "id")
        for m in _get(context.activity, "members_added") or []:
            if _get(m, "id") != bot_id and _get(context.activity, "conversation", "conversation_type") == "personal":
                await send(context, "Welcome to ProductIQ – your product-innovation copilot for Contoso Home "
                                    "Appliances. Type `help` to see what I can do.")

    @app.error
    async def on_error(context: TurnContext, error: Exception) -> None:
        telemetry.log.exception("turn error: %s", error)
        await context.send_activity("Sorry – something went wrong. Please try again.")

    return app, adapter, connections.get_default_connection_configuration()
