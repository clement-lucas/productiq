"""Collaboration Agent – kickoff meeting + project group chat via Microsoft Graph (delegated).

Uses the signed-in user's token from the bot OAuth connection (BOT_OAUTH_CONNECTION_NAME,
"graph-sso"). Read-only calls (resolve users, findMeetingTimes) run while building the
preview; every WRITE runs only after the user approves the card (approval.ApprovalGate).

Delegated Graph permissions: User.ReadBasic.All, Calendars.ReadWrite, Chat.Create,
ChatMember.ReadWrite, TeamsAppInstallation.ReadWriteSelfForChat, ChatMessage.Send.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from . import cards, telemetry
from .approval import ApprovalGate, PendingAction
from .memory import MemoryStore, ProjectMemory

GRAPH = "https://graph.microsoft.com/v1.0"
KIND = "collab.setup"


class GraphError(RuntimeError):
    def __init__(self, status: int, path: str, body: str) -> None:
        super().__init__(f"Graph {status} on {path}: {body[:300]}")
        self.status = status


class GraphClient:
    def __init__(self, token: str, http: Any = None) -> None:
        self._token = token
        self._http = http  # injectable httpx.AsyncClient (tests / connection reuse)

    async def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        import httpx  # lazy import

        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}
        client = self._http or httpx.AsyncClient(timeout=30)
        try:
            with telemetry.span("graph.call", method=method, path=path.split("?")[0]):
                resp = await client.request(method, GRAPH + path, headers=headers, json=body)
        finally:
            if self._http is None:
                await client.aclose()
        if resp.status_code >= 400:
            raise GraphError(resp.status_code, path, resp.text)
        return resp.json() if resp.content else {}


def chat_topic(project: ProjectMemory) -> str:
    return f"ProductIQ · {project.title}"[:250]


class CollaborationAgent:
    def __init__(self, store: MemoryStore, gate: ApprovalGate, teams_app_catalog_id: str,
                 graph_factory: Any = GraphClient) -> None:
        self.store = store
        self.gate = gate
        self.catalog_id = teams_app_catalog_id
        self.graph_factory = graph_factory

    # -- step 1: preview (read-only) -------------------------------------------------------
    async def propose(self, user_id: str, project: ProjectMemory, token: str, duration_min: int = 30,
                      window_days: int = 5, time_zone: str = "UTC") -> tuple[PendingAction, dict[str, Any]]:
        graph = self.graph_factory(token)
        # Resolve members added by email only (aadObjectId == "") – read-only.
        for m in project.members:
            if not m.get("aadObjectId") and m.get("email"):
                u = await graph.call("GET", f"/users/{m['email']}?$select=id,displayName,mail")
                m.update(aadObjectId=u["id"], name=m.get("name") or u.get("displayName", ""))
            elif m.get("aadObjectId") and not m.get("email"):
                u = await graph.call("GET", f"/users/{m['aadObjectId']}?$select=id,displayName,mail,userPrincipalName")
                m.update(email=u.get("mail") or u.get("userPrincipalName", ""), name=m.get("name") or u.get("displayName", ""))
        await self.store.save_project(project)
        attendees = [{"name": m.get("name", ""), "email": m["email"], "aadObjectId": m["aadObjectId"]}
                     for m in project.members if m.get("email")]
        if len({a["aadObjectId"] for a in attendees} | {user_id}) < 3:
            raise ValueError("A group chat needs at least 3 people – add teammates first, "
                             "e.g. `add ken@contoso.example as Design`.")

        start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        end = start + timedelta(days=window_days)
        fmt = "%Y-%m-%dT%H:%M:%S"
        suggestion = await graph.call("POST", "/me/findMeetingTimes", {
            "attendees": [{"type": "required", "emailAddress": {"address": a["email"], "name": a["name"]}}
                          for a in attendees if a["aadObjectId"] != user_id],
            "timeConstraint": {"activityDomain": "work", "timeSlots": [
                {"start": {"dateTime": start.strftime(fmt), "timeZone": "UTC"},
                 "end": {"dateTime": end.strftime(fmt), "timeZone": "UTC"}}]},
            "meetingDuration": f"PT{duration_min}M",
            "maxCandidates": 3,
            "returnSuggestionReasons": True,
        })
        slots = suggestion.get("meetingTimeSuggestions") or []
        if slots:
            slot = slots[0]["meetingTimeSlot"]
            s_dt, e_dt = slot["start"]["dateTime"][:19], slot["end"]["dateTime"][:19]
            tz = slot["start"].get("timeZone", "UTC")
        else:  # no common slot: propose next working hour, user can still reject
            s_dt, e_dt, tz = start.strftime(fmt), (start + timedelta(minutes=duration_min)).strftime(fmt), "UTC"

        payload = {
            "projectId": project.projectId,
            "subject": f"ProductIQ kickoff – {project.title}"[:255],
            "start": s_dt, "end": e_dt, "timeZone": tz,
            "attendees": attendees,
            "chatTopic": chat_topic(project),
            "emptySuggestionsReason": suggestion.get("emptySuggestionsReason", ""),
        }
        action = await self.gate.create(user_id, KIND, payload, project.projectId)
        return action, cards.approval_card(action.actionId, user_id, payload, action.expiresAt)

    # -- step 2: execute (only after approval) ----------------------------------------------
    async def execute(self, action: PendingAction, token: str) -> dict[str, Any]:
        if action.kind != KIND or action.status != "approved":
            raise PermissionError("action is not an approved collaboration request")
        p = action.payload
        graph = self.graph_factory(token)
        project = await self.store.get_project(p["projectId"])
        if project is None:
            raise KeyError(p["projectId"])
        out: dict[str, Any] = {"steps": {}}

        # 1) Group chat (requester + attendees as owners). Needs >= 3 members for chatType group.
        member_ids = list(dict.fromkeys([action.userId] + [a["aadObjectId"] for a in p["attendees"]]))
        chat = await graph.call("POST", "/chats", {
            "chatType": "group",
            "topic": p["chatTopic"],
            "members": [{"@odata.type": "#microsoft.graph.aadUserConversationMember", "roles": ["owner"],
                         "user@odata.bind": f"{GRAPH}/users('{uid}')"} for uid in member_ids],
        })
        chat_id = chat["id"]
        out["chatId"] = chat_id
        out["steps"]["chat"] = "ok"
        # 2) Bind BEFORE installing the app so the bot's installationUpdate can resolve the project.
        await self.store.bind_chat(chat_id, project.projectId, action.userId)

        # 3) Install the ProductIQ Teams app into the chat (non-fatal if it fails).
        try:
            await graph.call("POST", f"/chats/{chat_id}/installedApps", {
                "teamsApp@odata.bind": f"{GRAPH}/appCatalogs/teamsApps/{self.catalog_id}"})
            out["steps"]["installApp"] = "ok"
        except GraphError as exc:
            telemetry.log.warning("app install into chat failed: %s", exc)
            out["steps"]["installApp"] = f"failed ({exc.status})"

        # 4) Teams meeting on the requester's calendar.
        event = await graph.call("POST", "/me/events", {
            "subject": p["subject"],
            "body": {"contentType": "HTML",
                     "content": f"Kickoff for <b>{project.title}</b>. Created by ProductIQ after your approval."},
            "start": {"dateTime": p["start"], "timeZone": p["timeZone"]},
            "end": {"dateTime": p["end"], "timeZone": p["timeZone"]},
            "attendees": [{"type": "required", "emailAddress": {"address": a["email"], "name": a["name"]}}
                          for a in p["attendees"] if a["aadObjectId"] != action.userId],
            "isOnlineMeeting": True,
            "onlineMeetingProvider": "teamsForBusiness",
            "transactionId": action.actionId,  # idempotency on retries
        })
        join_url = (event.get("onlineMeeting") or {}).get("joinUrl")
        out.update(eventId=event.get("id"), joinUrl=join_url)
        out["steps"]["meeting"] = "ok"

        # 5) Summary card into the chat.
        latest = await self.store.latest_scorecard(project.projectId)
        project = await self.store.get_project(project.projectId) or project
        project.meetingId = event.get("id")
        await self.store.save_project(project)
        card = cards.project_summary_card(project.to_item(), latest, join_url)
        att_id = uuid.uuid4().hex
        await graph.call("POST", f"/chats/{chat_id}/messages", {
            "body": {"contentType": "html", "content": f'<attachment id="{att_id}"></attachment>'},
            "attachments": [{"id": att_id, "contentType": cards.CARD_CONTENT_TYPE,
                             "content": json.dumps(card, ensure_ascii=False)}],
        })
        out["steps"]["summary"] = "ok"
        project.actions.append({"type": KIND, "actionId": action.actionId, "chatId": chat_id,
                                "eventId": out["eventId"], "by": action.userId})
        await self.store.save_project(project)
        await self.store.audit(project.projectId, "collab.executed", action.userId, out)
        return out
