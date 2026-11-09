import unittest

from productiq.memory import InMemoryStore, NotAMemberError, ProjectMemory
from productiq.scorecard import Scorecard, parse_options
from tests.fixtures import AIKO, DEMO_OPTIONS, KEN, RAJ


class TestProjectMemory(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = InMemoryStore()
        self.project = await self.store.create_project("Pet-owner vacuum refresh", "Pet hair tangling", AIKO)
        self.project.add_member(KEN)
        await self.store.save_project(self.project)

    async def test_create_and_round_trip(self):
        loaded = await self.store.get_project(self.project.projectId)
        self.assertIsInstance(loaded, ProjectMemory)
        self.assertEqual(loaded.member_ids(), {"u-aiko", "u-ken"})
        self.assertEqual(loaded.to_item()["id"], loaded.projectId)

    async def test_add_member_is_idempotent(self):
        self.project.add_member(KEN)
        self.assertEqual(len(self.project.members), 2)

    async def test_chat_binding_and_membership(self):
        chat = "19:abc@thread.v2"
        self.assertIsNone(await self.store.resolve_chat_project(chat, "u-aiko"))  # unbound
        await self.store.bind_chat(chat, self.project.projectId, "u-aiko")
        self.assertEqual(await self.store.project_id_for_chat(chat), self.project.projectId)
        project = await self.store.resolve_chat_project(chat, "u-ken")
        self.assertEqual(project.chatId, chat)
        with self.assertRaises(NotAMemberError):
            await self.store.resolve_chat_project(chat, RAJ.aadObjectId)
        with self.assertRaises(KeyError):
            await self.store.get_project_for_member("prj-missing", "u-aiko")

    async def test_show_and_forget_user_memory(self):
        scope = self.store.user_scope("u-aiko")
        await self.store.remember(scope, "Prefers answers in Japanese")
        await self.store.remember(self.store.user_scope("u-ken"), "Ken's note")
        session = await self.store.get_session("u-aiko")
        session["activeProjectId"] = self.project.projectId
        await self.store.save_session(session)

        mem = await self.store.show_user_memory("u-aiko")
        self.assertEqual(mem["activeProjectId"], self.project.projectId)
        self.assertEqual([m["text"] for m in mem["memories"]], ["Prefers answers in Japanese"])

        deleted = await self.store.forget_user("u-aiko")
        self.assertEqual(deleted, 2)  # 1 memory + 1 session
        mem = await self.store.show_user_memory("u-aiko")
        self.assertEqual(mem["memories"], [])
        self.assertIsNone(mem["activeProjectId"])
        # Other users and shared project data are untouched.
        self.assertEqual(len(await self.store.recall(self.store.user_scope("u-ken"))), 1)
        self.assertIsNotNone(await self.store.get_project(self.project.projectId))

    async def test_scorecard_versions(self):
        sc = Scorecard(self.project.projectId, parse_options(DEMO_OPTIONS))
        await self.store.save_scorecard(sc.to_dict())
        v2 = sc.rescore("C", {"supplier_risk": {"score": 3}})
        await self.store.save_scorecard(v2.to_dict())
        latest = await self.store.latest_scorecard(self.project.projectId)
        self.assertEqual(latest["version"], 2)
        project = await self.store.get_project(self.project.projectId)
        self.assertEqual(project.scorecardVersions, [1, 2])
        self.assertEqual(project.options[0]["id"], "C")

    async def test_store_returns_copies(self):
        loaded = await self.store.get_project(self.project.projectId)
        loaded.members.clear()
        again = await self.store.get_project(self.project.projectId)
        self.assertEqual(len(again.members), 2)


if __name__ == "__main__":
    unittest.main()
