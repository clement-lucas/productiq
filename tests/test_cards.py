import json
import unittest

from productiq import cards
from productiq.memory import ProjectMemory
from productiq.scorecard import Scorecard, parse_options
from tests.fixtures import AIKO, DEMO_OPTIONS, KEN


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


class TestCards(unittest.TestCase):
    def setUp(self):
        self.sc = Scorecard("prj-1", parse_options(DEMO_OPTIONS)).to_dict()

    def test_bar(self):
        self.assertEqual(cards.bar(0), "░" * 10)
        self.assertEqual(cards.bar(100), "█" * 10)
        self.assertEqual(cards.bar(69), "███████░░░")

    def test_answer_card_with_scorecard(self):
        card = cards.answer_card("Pet-owner vacuum", "Option C leads.", self.sc,
                                 ["Problem & target users"], ["VoC – fact_feedback"], "prj-1", ["check"])
        self.assertEqual(card["type"], "AdaptiveCard")
        self.assertEqual(card["version"], "1.5")
        texts = [n.get("text", "") for n in _walk(card)]
        self.assertTrue(any("1. C – Pet-care robot vacuum" in t for t in texts))
        self.assertTrue(any("3.75" in t for t in texts))
        self.assertTrue(any("synthetic" in t for t in texts))
        submit = [a for a in card["actions"] if a["type"] == "Action.Submit"][0]
        self.assertEqual(submit["data"], {"verb": "collab.propose", "projectId": "prj-1"})
        toggle = [a for a in card["actions"] if a["type"] == "Action.ToggleVisibility"][0]
        self.assertEqual(toggle["targetElements"], ["detail-A", "detail-B"])
        json.dumps(card)  # serialisable

    def test_answer_card_without_scorecard(self):
        card = cards.answer_card("Q", "Findings only")
        self.assertNotIn("actions", card)

    def test_approval_card(self):
        payload = {"subject": "ProductIQ kickoff", "start": "2026-11-10T01:00:00", "end": "2026-11-10T01:30:00",
                   "timeZone": "UTC", "chatTopic": "ProductIQ · Pet vacuum",
                   "attendees": [{"name": "Ken Sato", "email": "ken@contoso.example"}]}
        card = cards.approval_card("act-1", "u-aiko", payload, "2026-11-09T10:00:00+00:00")
        data = {a["title"]: a["data"] for a in card["actions"]}
        self.assertEqual(data["Approve"], {"actionId": "act-1", "requesterId": "u-aiko", "verb": "approval",
                                           "decision": "approve"})
        self.assertEqual(data["Reject"]["decision"], "reject")
        text = json.dumps(card, ensure_ascii=False)
        for expected in ("ken@contoso.example", "ProductIQ · Pet vacuum", "2026-11-10T01:00:00"):
            self.assertIn(expected, text)

    def test_project_summary_card(self):
        p = ProjectMemory("prj-1", "Pet-care robot vacuum", "Pet hair tangling")
        p.add_member(AIKO)
        p.add_member(KEN)
        p.findings.append({"text": "Tangling is the #1 pet-owner complaint"})
        p.openQuestions.append("Second motor supplier?")
        card = cards.project_summary_card(p.to_item(), self.sc, "https://teams.example/join")
        text = json.dumps(card, ensure_ascii=False)
        self.assertIn("Aiko Tanaka (PM)", text)
        self.assertIn("Current leader: **C", text)
        self.assertEqual(card["actions"][0]["url"], "https://teams.example/join")

    def test_fit_trims_oversized_cards(self):
        huge = cards.answer_card("T", "x" * 100, None, ["y" * 5000] * 3, ["z" * 9000] * 8)
        self.assertLessEqual(len(json.dumps(huge, ensure_ascii=False).encode()), cards.MAX_CARD_BYTES)
        self.assertIn("synthetic", huge["body"][-1]["text"])  # footer kept

    def test_attachment(self):
        att = cards.attachment({"type": "AdaptiveCard"})
        self.assertEqual(att["contentType"], "application/vnd.microsoft.card.adaptive")


if __name__ == "__main__":
    unittest.main()
