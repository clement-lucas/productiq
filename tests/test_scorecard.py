import copy
import json
import unittest

from productiq.scorecard import (CRITERIA, DEFAULT_WEIGHTS, Scorecard, ScorecardError, as_percent, load_weights,
                                 parse_options, validate_weights, weighted_total)
from tests.fixtures import DEMO_OPTIONS


class TestWeights(unittest.TestCase):
    def test_default_weights_match_contract(self):
        self.assertEqual(DEFAULT_WEIGHTS, {"customer_value": 25, "market_fit": 20, "cost": 15, "supplier_risk": 15,
                                           "logistics": 10, "time_to_market": 10, "sustainability": 5})
        self.assertEqual(sum(DEFAULT_WEIGHTS.values()), 100)

    def test_validate_rejects_bad_sum_missing_and_negative(self):
        bad = dict(DEFAULT_WEIGHTS, cost=20)
        with self.assertRaises(ScorecardError):
            validate_weights(bad)
        missing = {k: v for k, v in DEFAULT_WEIGHTS.items() if k != "logistics"}
        with self.assertRaises(ScorecardError):
            validate_weights(missing)
        with self.assertRaises(ScorecardError):
            validate_weights(dict(DEFAULT_WEIGHTS, cost=-15, customer_value=55))

    def test_load_weights_from_json_and_default(self):
        self.assertEqual(load_weights(""), DEFAULT_WEIGHTS)
        custom = dict(DEFAULT_WEIGHTS, customer_value=20, sustainability=10)
        self.assertEqual(load_weights(json.dumps(custom)), custom)
        with self.assertRaises(ScorecardError):
            load_weights(json.dumps(dict(DEFAULT_WEIGHTS, cost=99)))


class TestScoring(unittest.TestCase):
    def setUp(self):
        self.options = parse_options(copy.deepcopy(DEMO_OPTIONS))

    def test_weighted_total_computed_in_python(self):
        totals = {o.option_id: weighted_total(o, DEFAULT_WEIGHTS) for o in self.options}
        self.assertEqual(totals, {"A": 3.6, "B": 3.25, "C": 3.75})  # model's 9.99 ignored

    def test_ranking(self):
        sc = Scorecard("prj-1", self.options)
        self.assertEqual([o.option_id for o, _ in sc.ranked()], ["C", "A", "B"])
        self.assertEqual(sc.to_dict()["ranking"], ["C", "A", "B"])

    def test_tie_break_on_highest_weight_criterion(self):
        flat = {c: {"score": 3} for c in CRITERIA}
        # Exact tie: +1 customer_value (25), -1 market_fit (20), -1 sustainability (5) -> tie at 3.00.
        b = {**flat, "customer_value": {"score": 4}, "market_fit": {"score": 2}, "sustainability": {"score": 2}}
        sc = Scorecard("p", parse_options([{"id": "A", "name": "a", "scores": flat},
                                           {"id": "B", "name": "b", "scores": b}]))
        ranked = sc.ranked()
        self.assertEqual(ranked[0][1], ranked[1][1])
        self.assertEqual(ranked[0][0].option_id, "B")  # wins on customer_value (highest weight)

    def test_invalid_scores_rejected(self):
        raw = copy.deepcopy(DEMO_OPTIONS)
        raw[0]["scores"]["cost"]["score"] = 6
        with self.assertRaises(ScorecardError):
            parse_options(raw)
        raw = copy.deepcopy(DEMO_OPTIONS)
        del raw[1]["scores"]["logistics"]
        with self.assertRaises(ScorecardError):
            parse_options(raw)
        raw = copy.deepcopy(DEMO_OPTIONS)
        raw[0]["scores"]["cost"]["score"] = 3.5
        with self.assertRaises(ScorecardError):
            parse_options(raw)

    def test_rescore_creates_new_version_without_mutating_old(self):
        v1 = Scorecard("prj-1", self.options)
        # "re-score option C using the current motor platform"
        v2 = v1.rescore("C", {"supplier_risk": {"score": 3, "rationale": "reuse BLM-200 platform",
                                                 "citations": ["Cost & Supplier – fact_supplier_capacity"]},
                              "time_to_market": {"score": 4, "rationale": "no new motor qualification"}},
                        note="current motor platform")
        self.assertEqual(v2.version, 2)
        totals_v1 = {o.option_id: t for o, t in v1.ranked()}
        totals_v2 = {o.option_id: t for o, t in v2.ranked()}
        self.assertEqual(totals_v1["C"], 3.75)
        self.assertEqual(totals_v2["C"], 4.0)
        self.assertEqual(totals_v2["A"], totals_v1["A"])
        with self.assertRaises(ScorecardError):
            v1.rescore("Z", {"cost": {"score": 3}})
        with self.assertRaises(ScorecardError):
            v1.rescore("C", {"vibes": {"score": 3}})

    def test_round_trip_and_percent(self):
        sc = Scorecard("prj-1", self.options)
        again = Scorecard.from_dict(json.loads(json.dumps(sc.to_dict())))
        self.assertEqual(again.to_dict()["options"], sc.to_dict()["options"])
        self.assertEqual(as_percent(1), 0)
        self.assertEqual(as_percent(5), 100)
        self.assertEqual(as_percent(3.75), 69)


if __name__ == "__main__":
    unittest.main()
