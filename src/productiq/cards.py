"""Adaptive Card (schema 1.5) builders for Teams / M365 Copilot and the web app.

All builders return plain dicts. Action.Submit data always carries a `verb` so the bot can
route submits; approval submits also carry `actionId` and `requesterId`.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

from .scorecard import CRITERIA, CRITERION_LABELS, as_percent

SCHEMA = "http://adaptivecards.io/schemas/adaptive-card.json"
CARD_CONTENT_TYPE = "application/vnd.microsoft.card.adaptive"
MAX_CARD_BYTES = 28_000  # Teams limit is ~28 KB per message


def _card(body: list[dict[str, Any]], actions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    card: dict[str, Any] = {"type": "AdaptiveCard", "$schema": SCHEMA, "version": "1.5", "body": body,
                            "msteams": {"width": "Full"}}
    if actions:
        card["actions"] = actions
    return card


def _text(text: str, **kw: Any) -> dict[str, Any]:
    return {"type": "TextBlock", "text": text, "wrap": True, **kw}


def _facts(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    return {"type": "FactSet", "facts": [{"title": k, "value": v} for k, v in pairs]}


def bar(percent: int, width: int = 10) -> str:
    """Text bar that renders in every Adaptive Card host, e.g. ███████░░░."""
    filled = max(0, min(width, round(percent / 100 * width)))
    return "█" * filled + "░" * (width - filled)


def scorecard_table(scorecard: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Ranked options with weighted total + bar, then per-criterion scores per option."""
    rows: list[dict[str, Any]] = []
    for rank_no, opt in enumerate(scorecard["options"], start=1):
        total = opt["weightedTotal"]
        rows.append({
            "type": "ColumnSet",
            "separator": rank_no > 1,
            "columns": [
                {"type": "Column", "width": "stretch",
                 "items": [_text(f"**{rank_no}. {opt['id']} – {opt['name']}**")]},
                {"type": "Column", "width": "auto",
                 "items": [_text(f"{bar(as_percent(total))} **{total:.2f}** / 5", fontType="Monospace")]},
            ],
        })
        detail = [(f"{CRITERION_LABELS[c]} ({scorecard['weights'][c]:g}%)",
                   f"{opt['scores'][c]['score']}/5 – {opt['scores'][c]['rationale']}"[:160])
                  for c in CRITERIA if c in opt["scores"]]
        rows.append({"type": "Container", "isVisible": rank_no == 1, "id": f"detail-{opt['id']}",
                     "items": [_facts(detail)]})
    return rows


def answer_card(title: str, summary: str, scorecard: Mapping[str, Any] | None = None,
                prd_outline: list[str] | None = None, citations: list[str] | None = None,
                project_id: str = "", warnings: list[str] | None = None) -> dict[str, Any]:
    body: list[dict[str, Any]] = [
        _text(title, size="Large", weight="Bolder"),
        _text(summary),
    ]
    actions: list[dict[str, Any]] = []
    if scorecard:
        body.append(_text(f"Weighted scorecard (v{scorecard['version']}) – totals computed by ProductIQ, "
                          "not the model", weight="Bolder", spacing="Medium"))
        body.extend(scorecard_table(scorecard))
        actions.append({"type": "Action.ToggleVisibility", "title": "Show all criteria",
                        "targetElements": [f"detail-{o['id']}" for o in scorecard["options"][1:]]})
    if prd_outline:
        body.append(_text("PRD outline", weight="Bolder", spacing="Medium"))
        body.append(_text("\n".join(f"- {line}" for line in prd_outline[:10])))
    if citations:
        body.append(_text("Sources", weight="Bolder", spacing="Medium", size="Small"))
        body.append(_text("\n".join(f"{i}. {c}" for i, c in enumerate(citations[:8], 1)), size="Small",
                          isSubtle=True))
    for w in warnings or []:
        body.append(_text(f"⚠️ {w}", color="Warning", size="Small"))
    body.append(_text("AI-generated from synthetic demo data – verify before decisions.", size="Small",
                      isSubtle=True))
    if project_id:
        actions.append({"type": "Action.Submit", "title": "Set up kickoff meeting & chat",
                        "data": {"verb": "collab.propose", "projectId": project_id}})
    return fit(_card(body, actions))


def approval_card(action_id: str, requester_id: str, payload: Mapping[str, Any], expires_at: str) -> dict[str, Any]:
    """Preview of everything that will be created; nothing runs until Approve."""
    attendees = payload.get("attendees", [])
    body = [
        _text("Approval needed", size="Large", weight="Bolder"),
        _text("ProductIQ will do the following **on your behalf** only if you approve:"),
        _facts([
            ("Meeting", payload.get("subject", "")),
            ("When", f"{payload.get('start', '')} → {payload.get('end', '')} ({payload.get('timeZone', 'UTC')})"),
            ("Teams meeting", "Yes (online meeting link)"),
            ("Group chat", payload.get("chatTopic", "")),
            ("Install app in chat", "ProductIQ"),
            ("Post summary", "Project summary card in the new chat"),
        ]),
        _text(f"Attendees ({len(attendees)})", weight="Bolder"),
        _text("\n".join(f"- {a.get('name') or a.get('email')} ({a.get('email', '')})" for a in attendees)),
        _text(f"Expires {expires_at}", size="Small", isSubtle=True),
    ]
    base = {"actionId": action_id, "requesterId": requester_id}
    actions = [
        {"type": "Action.Submit", "title": "Approve", "style": "positive",
         "data": {**base, "verb": "approval", "decision": "approve"}},
        {"type": "Action.Submit", "title": "Reject", "style": "destructive",
         "data": {**base, "verb": "approval", "decision": "reject"}},
    ]
    return fit(_card(body, actions))


def project_summary_card(project: Mapping[str, Any], scorecard: Mapping[str, Any] | None = None,
                         join_url: str | None = None) -> dict[str, Any]:
    """Summary posted into the project group chat (and shown on installationUpdate)."""
    members = ", ".join(f"{m.get('name')} ({m.get('role')})" if m.get("role") else str(m.get("name"))
                        for m in project.get("members", []))
    body = [
        _text(f"ProductIQ project: {project.get('title', '')}", size="Large", weight="Bolder"),
        _text(project.get("problem", "")),
        _facts([("Project", project.get("projectId", "")), ("Members", members or "–")]),
    ]
    if scorecard and scorecard.get("options"):
        top = scorecard["options"][0]
        body.append(_text(f"Current leader: **{top['id']} – {top['name']}** ({top['weightedTotal']:.2f}/5, "
                          f"scorecard v{scorecard['version']})"))
    findings = project.get("findings", [])[-4:]
    if findings:
        body.append(_text("Key findings", weight="Bolder"))
        body.append(_text("\n".join(f"- {f.get('text', '')[:180]}" for f in findings)))
    if project.get("openQuestions"):
        body.append(_text("Open questions", weight="Bolder"))
        body.append(_text("\n".join(f"- {q}" for q in project["openQuestions"][:5])))
    actions = [{"type": "Action.OpenUrl", "title": "Join kickoff meeting", "url": join_url}] if join_url else []
    body.append(_text("Mention @ProductIQ in this chat to ask follow-ups.", size="Small", isSubtle=True))
    return fit(_card(body, actions))


def fit(card: dict[str, Any]) -> dict[str, Any]:
    """Drop trailing body elements (keeping the first two) until the card fits the size limit."""
    while len(json.dumps(card, ensure_ascii=False).encode()) > MAX_CARD_BYTES and len(card["body"]) > 2:
        card["body"].pop(-2)  # keep the final disclaimer/footer
    return card


def attachment(card: dict[str, Any]) -> dict[str, Any]:
    return {"contentType": CARD_CONTENT_TYPE, "content": card}
