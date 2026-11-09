"""User + project memory.

`MemoryStore` implements all business logic (project model, chat binding, membership,
"show my memory" / "forget me") on top of five storage primitives. `InMemoryStore`
(tests / local dev) and `CosmosMemoryStore` (Azure Cosmos DB NoSQL, Entra auth) only
implement those primitives. Containers and partition keys follow docs/CONTRACT.md.
"""
from __future__ import annotations

import copy
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .config import COSMOS_CONTAINERS


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class NotAMemberError(PermissionError):
    pass


@dataclass
class Member:
    aadObjectId: str
    name: str = ""
    email: str = ""
    role: str = ""  # e.g. "PM", "Design", "Sourcing", "Supply chain"


@dataclass
class ProjectMemory:
    projectId: str
    title: str
    problem: str = ""
    members: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)  # {specialist, text, citations, at}
    options: list[dict[str, Any]] = field(default_factory=list)
    scorecardVersions: list[int] = field(default_factory=list)  # versions stored in `scorecards`
    decisions: list[dict[str, Any]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    openQuestions: list[str] = field(default_factory=list)
    chatId: str | None = None
    meetingId: str | None = None
    createdAt: str = field(default_factory=utcnow)
    updatedAt: str = field(default_factory=utcnow)

    def member_ids(self) -> set[str]:
        return {m.get("aadObjectId", "") for m in self.members}

    def add_member(self, member: Member | dict[str, Any]) -> None:
        m = asdict(member) if isinstance(member, Member) else dict(member)
        if m["aadObjectId"] not in self.member_ids():
            self.members.append(m)

    def to_item(self) -> dict[str, Any]:
        d = asdict(self)
        d["id"] = self.projectId
        return d

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> "ProjectMemory":
        known = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in item.items() if k in known})


class MemoryStore:
    """Business logic over storage primitives. Subclasses implement the `_` methods."""

    # ---- primitives ---------------------------------------------------------------
    async def _read(self, container: str, item_id: str, pk: str) -> dict[str, Any] | None:
        raise NotImplementedError

    async def _upsert(self, container: str, item: dict[str, Any]) -> None:
        raise NotImplementedError

    async def _delete(self, container: str, item_id: str, pk: str) -> None:
        raise NotImplementedError

    async def _list(self, container: str, pk: str) -> list[dict[str, Any]]:
        """All items in one logical partition (single-partition query)."""
        raise NotImplementedError

    # ---- projects -----------------------------------------------------------------
    async def create_project(self, title: str, problem: str, owner: Member) -> ProjectMemory:
        project = ProjectMemory(projectId=f"prj-{uuid.uuid4().hex[:10]}", title=title[:120], problem=problem)
        project.add_member(owner)
        await self.save_project(project)
        return project

    async def get_project(self, project_id: str) -> ProjectMemory | None:
        item = await self._read("projects", project_id, project_id)
        return ProjectMemory.from_item(item) if item else None

    async def save_project(self, project: ProjectMemory) -> None:
        project.updatedAt = utcnow()
        await self._upsert("projects", project.to_item())

    async def get_project_for_member(self, project_id: str, user_id: str) -> ProjectMemory:
        """Load a project and enforce membership (raises NotAMemberError / KeyError)."""
        project = await self.get_project(project_id)
        if project is None:
            raise KeyError(project_id)
        if user_id not in project.member_ids():
            raise NotAMemberError(f"user is not a member of project {project_id}")
        return project

    # ---- chat binding -------------------------------------------------------------
    async def bind_chat(self, chat_id: str, project_id: str, bound_by: str) -> None:
        await self._upsert("chatBindings", {
            "id": chat_id, "chatId": chat_id, "projectId": project_id, "boundBy": bound_by, "at": utcnow(),
        })
        project = await self.get_project(project_id)
        if project:
            project.chatId = chat_id
            await self.save_project(project)

    async def project_id_for_chat(self, chat_id: str) -> str | None:
        item = await self._read("chatBindings", chat_id, chat_id)
        return item["projectId"] if item else None

    async def resolve_chat_project(self, chat_id: str, user_id: str) -> ProjectMemory | None:
        """chatId -> projectId, then membership check for the caller. None if unbound."""
        project_id = await self.project_id_for_chat(chat_id)
        if not project_id:
            return None
        return await self.get_project_for_member(project_id, user_id)

    # ---- sessions (partition /userId) ---------------------------------------------
    async def get_session(self, user_id: str) -> dict[str, Any]:
        return await self._read("sessions", "session", user_id) or {
            "id": "session", "userId": user_id, "activeProjectId": None, "createdAt": utcnow(),
        }

    async def save_session(self, session: dict[str, Any]) -> None:
        session["updatedAt"] = utcnow()
        await self._upsert("sessions", session)

    # ---- user / project memories (partition /scopeId) -----------------------------
    @staticmethod
    def user_scope(user_id: str) -> str:
        return f"user:{user_id}"

    async def remember(self, scope_id: str, text: str, kind: str = "preference") -> dict[str, Any]:
        item = {"id": uuid.uuid4().hex, "scopeId": scope_id, "kind": kind, "text": text, "at": utcnow()}
        await self._upsert("memories", item)
        return item

    async def recall(self, scope_id: str) -> list[dict[str, Any]]:
        return sorted(await self._list("memories", scope_id), key=lambda i: i.get("at", ""))

    async def show_user_memory(self, user_id: str) -> dict[str, Any]:
        """Everything ProductIQ remembers about the user ("show my memory")."""
        session = await self.get_session(user_id)
        return {
            "userId": user_id,
            "activeProjectId": session.get("activeProjectId"),
            "memories": [{"text": m["text"], "kind": m.get("kind"), "at": m.get("at")}
                         for m in await self.recall(self.user_scope(user_id))],
        }

    async def forget_user(self, user_id: str) -> int:
        """Delete the user's session, pending actions and personal memories ("forget me").

        Shared project records are kept (they belong to the team) – documented in README.
        """
        count = 0
        for item in await self._list("memories", self.user_scope(user_id)):
            await self._delete("memories", item["id"], item["scopeId"])
            count += 1
        for item in await self._list("sessions", user_id):
            await self._delete("sessions", item["id"], user_id)
            count += 1
        return count

    # ---- scorecards / decisions / audit -------------------------------------------
    async def save_scorecard(self, scorecard_dict: dict[str, Any]) -> None:
        await self._upsert("scorecards", scorecard_dict)
        project = await self.get_project(scorecard_dict["projectId"])
        if project and scorecard_dict["version"] not in project.scorecardVersions:
            project.scorecardVersions.append(scorecard_dict["version"])
            project.options = scorecard_dict["options"]
            await self.save_project(project)

    async def latest_scorecard(self, project_id: str) -> dict[str, Any] | None:
        items = await self._list("scorecards", project_id)
        return max(items, key=lambda i: i["version"]) if items else None

    async def add_decision(self, project_id: str, text: str, by: str) -> None:
        await self._upsert("decisions", {"id": uuid.uuid4().hex, "projectId": project_id,
                                         "text": text, "by": by, "at": utcnow()})

    async def audit(self, project_id: str, event: str, actor: str, data: dict[str, Any] | None = None) -> None:
        await self._upsert("audit", {"id": uuid.uuid4().hex, "projectId": project_id or "none",
                                     "event": event, "actor": actor, "data": data or {}, "at": utcnow()})


class InMemoryStore(MemoryStore):
    """Dict-backed store for unit tests and local runs without Cosmos."""

    def __init__(self) -> None:
        self.data: dict[str, dict[tuple[str, str], dict[str, Any]]] = {c: {} for c in COSMOS_CONTAINERS}

    @staticmethod
    def _pk_of(container: str, item: dict[str, Any]) -> str:
        return item[COSMOS_CONTAINERS[container].lstrip("/")]

    async def _read(self, container, item_id, pk):
        item = self.data[container].get((pk, item_id))
        return copy.deepcopy(item) if item else None

    async def _upsert(self, container, item):
        self.data[container][(self._pk_of(container, item), item["id"])] = copy.deepcopy(item)

    async def _delete(self, container, item_id, pk):
        self.data[container].pop((pk, item_id), None)

    async def _list(self, container, pk):
        return [copy.deepcopy(v) for (p, _), v in self.data[container].items() if p == pk]


class CosmosMemoryStore(MemoryStore):
    """Azure Cosmos DB NoSQL (async SDK) with Entra ID auth – no keys.

    The identity needs the Cosmos DB Built-in Data Contributor role (data plane RBAC).
    """

    def __init__(self, endpoint: str, database: str, credential: Any) -> None:
        from azure.cosmos.aio import CosmosClient  # lazy: keeps tests SDK-free

        self._client = CosmosClient(endpoint, credential=credential)
        self._db = self._client.get_database_client(database)
        self._containers = {name: self._db.get_container_client(name) for name in COSMOS_CONTAINERS}

    async def _read(self, container, item_id, pk):
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        try:
            return await self._containers[container].read_item(item=item_id, partition_key=pk)
        except CosmosResourceNotFoundError:
            return None

    async def _upsert(self, container, item):
        await self._containers[container].upsert_item(item)

    async def _delete(self, container, item_id, pk):
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        try:
            await self._containers[container].delete_item(item=item_id, partition_key=pk)
        except CosmosResourceNotFoundError:
            pass

    async def _list(self, container, pk):
        query = "SELECT * FROM c"
        return [i async for i in self._containers[container].query_items(query=query, partition_key=pk)]

    async def close(self) -> None:
        await self._client.close()


class FoundryMemoryHook:
    """Optional Foundry managed memory (preview) for *user* preferences, behind
    PRODUCTIQ_USE_FOUNDRY_MEMORY. Cosmos remains the system of record and fallback.

    TODO(verify): the Foundry memory-store API surface (azure-ai-projects memory_stores.*) is
    preview; wire `recall`/`remember` once the pinned SDK exposes it. Until then the hook
    returns None and callers fall back to Cosmos.
    """

    def __init__(self, enabled: bool, project_client: Any = None) -> None:
        self.enabled = enabled and project_client is not None
        self._client = project_client

    async def recall(self, user_id: str, query: str) -> list[str] | None:
        return None

    async def remember(self, user_id: str, text: str) -> bool:
        return False


def create_store(settings: Any, credential: Any = None) -> MemoryStore:
    if settings.memory_backend == "cosmos" and settings.cosmos_endpoint:
        return CosmosMemoryStore(settings.cosmos_endpoint, settings.cosmos_database, credential)
    return InMemoryStore()
