import unittest
from datetime import datetime, timedelta, timezone

from productiq.approval import ApprovalGate, ApprovalStatus
from productiq.collaboration import CollaborationAgent
from productiq.memory import InMemoryStore
from tests.fixtures import AIKO, KEN, MARIA, RAJ


class FakeClock:
    def __init__(self):
        self.now = datetime(2026, 11, 9, 9, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now


class TestApprovalGate(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = InMemoryStore()
        self.clock = FakeClock()
        self.gate = ApprovalGate(self.store, ttl=timedelta(minutes=30), clock=self.clock)
        self.action = await self.gate.create("u-aiko", "collab.setup", {"x": 1}, "prj-1")

    async def test_same_user_approves_once(self):
        r = await self.gate.resolve(self.action.actionId, "u-aiko", "approve", "u-aiko")
        self.assertTrue(r.approved)
        self.assertEqual(r.action.payload, {"x": 1})  # stored payload, not card data
        again = await self.gate.resolve(self.action.actionId, "u-aiko", "approve", "u-aiko")
        self.assertEqual(again.status, ApprovalStatus.ALREADY_RESOLVED)

    async def test_other_user_cannot_approve(self):
        r = await self.gate.resolve(self.action.actionId, "u-ken", "approve", "u-aiko")
        self.assertEqual(r.status, ApprovalStatus.WRONG_USER)
        # Even if the card data is forged to claim Ken requested it, Ken's partition has no such action.
        r = await self.gate.resolve(self.action.actionId, "u-ken", "approve", "u-ken")
        self.assertEqual(r.status, ApprovalStatus.NOT_FOUND)
        # Original requester can still approve afterwards.
        self.assertTrue((await self.gate.resolve(self.action.actionId, "u-aiko", "approve")).approved)

    async def test_expired(self):
        self.clock.now += timedelta(minutes=31)
        r = await self.gate.resolve(self.action.actionId, "u-aiko", "approve")
        self.assertEqual(r.status, ApprovalStatus.EXPIRED)

    async def test_reject_and_unknown(self):
        r = await self.gate.resolve(self.action.actionId, "u-aiko", "reject")
        self.assertEqual(r.status, ApprovalStatus.REJECTED)
        self.assertEqual((await self.gate.resolve("nope", "u-aiko", "approve")).status, ApprovalStatus.NOT_FOUND)

    async def test_audit_trail(self):
        await self.gate.resolve(self.action.actionId, "u-aiko", "approve")
        events = [i["event"] for i in await self.store._list("audit", "prj-1")]
        self.assertIn("approval.requested", events)
        self.assertIn("approval.approved", events)


class FakeGraph:
    """Records Graph calls; returns canned responses."""
    calls: list = []

    def __init__(self, token):
        self.token = token

    async def call(self, method, path, body=None):
        FakeGraph.calls.append((method, path.split("?")[0]))
        if path.startswith("/me/findMeetingTimes"):
            return {"meetingTimeSuggestions": [{"meetingTimeSlot": {
                "start": {"dateTime": "2026-11-10T01:00:00.0000000", "timeZone": "UTC"},
                "end": {"dateTime": "2026-11-10T01:30:00.0000000", "timeZone": "UTC"}}}]}
        if path == "/chats":
            return {"id": "19:new@thread.v2"}
        if path == "/me/events":
            return {"id": "evt-1", "onlineMeeting": {"joinUrl": "https://teams.example/join"}}
        return {}


class TestCollaborationGate(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        FakeGraph.calls = []
        self.store = InMemoryStore()
        self.gate = ApprovalGate(self.store)
        self.collab = CollaborationAgent(self.store, self.gate, "catalog-app-id", graph_factory=FakeGraph)
        self.project = await self.store.create_project("Pet-care robot vacuum", "", AIKO)
        for m in (KEN, MARIA, RAJ):
            self.project.add_member(m)
        await self.store.save_project(self.project)

    async def test_propose_is_read_only_and_execute_requires_approval(self):
        action, card = await self.collab.propose("u-aiko", self.project, "token")
        self.assertEqual([c for c in FakeGraph.calls if c[1] != "/me/findMeetingTimes"], [])
        self.assertEqual(action.payload["start"], "2026-11-10T01:00:00")
        self.assertEqual(len(action.payload["attendees"]), 4)
        self.assertIn("Approve", [a["title"] for a in card["actions"]])

        with self.assertRaises(PermissionError):  # still pending
            await self.collab.execute(action, "token")
        self.assertNotIn(("POST", "/chats"), FakeGraph.calls)

        result = await self.gate.resolve(action.actionId, "u-aiko", "approve")
        out = await self.collab.execute(result.action, "token")
        self.assertEqual(out["chatId"], "19:new@thread.v2")
        self.assertEqual([c[1] for c in FakeGraph.calls[1:]],
                         ["/chats", "/chats/19:new@thread.v2/installedApps", "/me/events",
                          "/chats/19:new@thread.v2/messages"])
        self.assertEqual(await self.store.project_id_for_chat("19:new@thread.v2"), self.project.projectId)
        project = await self.store.get_project(self.project.projectId)
        self.assertEqual(project.meetingId, "evt-1")

    async def test_rejected_action_never_executes(self):
        action, _ = await self.collab.propose("u-aiko", self.project, "token")
        result = await self.gate.resolve(action.actionId, "u-aiko", "reject")
        with self.assertRaises(PermissionError):
            await self.collab.execute(result.action, "token")

    async def test_group_chat_needs_three_people(self):
        small = await self.store.create_project("Solo", "", AIKO)
        with self.assertRaises(ValueError):
            await self.collab.propose("u-aiko", small, "token")


if __name__ == "__main__":
    unittest.main()
