"""Human-in-the-loop approval gate.

Side-effecting actions (calendar event, group chat, app install, chat post) are stored as a
*pending action* (id + expiry + exact payload) in the requester's `sessions` partition and
executed only when the SAME user submits "approve" for that id before it expires. The payload
executed is the stored one – never data echoed back from the card – so what the user
previewed is exactly what runs. Each action can be consumed once.
"""
from __future__ import annotations

import enum
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .memory import MemoryStore


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    NOT_FOUND = "not_found"
    WRONG_USER = "wrong_user"
    ALREADY_RESOLVED = "already_resolved"


@dataclass
class PendingAction:
    actionId: str
    userId: str
    kind: str  # e.g. "collab.setup"
    payload: dict[str, Any]
    projectId: str = ""
    status: str = ApprovalStatus.PENDING.value
    createdAt: str = ""
    expiresAt: str = ""
    resolvedAt: str | None = None

    def to_item(self) -> dict[str, Any]:
        d = asdict(self)
        d["id"] = f"pending-{self.actionId}"
        d["type"] = "pendingAction"
        return d

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> "PendingAction":
        known = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in item.items() if k in known})


@dataclass
class ApprovalResult:
    status: ApprovalStatus
    action: PendingAction | None = None
    message: str = ""

    @property
    def approved(self) -> bool:
        return self.status is ApprovalStatus.APPROVED


@dataclass
class ApprovalGate:
    store: MemoryStore
    ttl: timedelta = timedelta(minutes=30)
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(timezone.utc))

    async def create(self, user_id: str, kind: str, payload: dict[str, Any], project_id: str = "") -> PendingAction:
        now = self.clock()
        action = PendingAction(
            actionId=secrets.token_urlsafe(12),
            userId=user_id,
            kind=kind,
            payload=payload,
            projectId=project_id,
            createdAt=now.isoformat(),
            expiresAt=(now + self.ttl).isoformat(),
        )
        await self.store._upsert("sessions", action.to_item())
        await self.store.audit(project_id, "approval.requested", user_id, {"actionId": action.actionId, "kind": kind})
        return action

    async def resolve(self, action_id: str, submitter_id: str, decision: str,
                      requester_hint: str | None = None) -> ApprovalResult:
        """Resolve a card submit. `requester_hint` is the requesterId echoed in card data
        (used only for a friendlier error; authorisation relies on the submitter's partition)."""
        if requester_hint and requester_hint != submitter_id:
            return ApprovalResult(ApprovalStatus.WRONG_USER, message="Only the person who requested this can approve it.")
        item = await self.store._read("sessions", f"pending-{action_id}", submitter_id)
        if not item:
            return ApprovalResult(ApprovalStatus.NOT_FOUND, message="This request was not found (or isn't yours).")
        action = PendingAction.from_item(item)
        if action.userId != submitter_id:  # defence in depth
            return ApprovalResult(ApprovalStatus.WRONG_USER, action, "Only the requester can approve.")
        if action.status != ApprovalStatus.PENDING.value:
            return ApprovalResult(ApprovalStatus.ALREADY_RESOLVED, action, f"Already {action.status}.")
        now = self.clock()
        if now >= datetime.fromisoformat(action.expiresAt):
            action.status = ApprovalStatus.EXPIRED.value
            status, msg = ApprovalStatus.EXPIRED, "This approval request expired – ask me again to get a fresh one."
        elif decision == "approve":
            action.status = ApprovalStatus.APPROVED.value
            status, msg = ApprovalStatus.APPROVED, "Approved."
        else:
            action.status = ApprovalStatus.REJECTED.value
            status, msg = ApprovalStatus.REJECTED, "Cancelled – nothing was changed."
        action.resolvedAt = now.isoformat()
        # Persist the terminal state BEFORE executing so double-clicks can't run it twice.
        await self.store._upsert("sessions", action.to_item())
        await self.store.audit(action.projectId, f"approval.{action.status}", submitter_id, {"actionId": action_id})
        return ApprovalResult(status, action, msg)
