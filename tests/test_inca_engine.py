"""インカの黄金エンジンのユニットテスト。"""
from __future__ import annotations
import json
import unittest
from gameplatform.errors import ConfigurationError, InvalidAction
from gameplatform.games import get as get_game_definition
from games.inca.cards import Card
from games.inca.config import RuleConfig, normalize_config
from games.inca.engine import CHOOSING, FINISHED, ROUND_END
from games.inca.views import player_view
from tests.helpers import choose, make_inca_game, next_round

class IncaRegistrationTest(unittest.TestCase):
    def test_game_definition_registered(self):
        defn = get_game_definition("inca")
        self.assertEqual(defn.key, "inca")
        self.assertEqual(defn.title, "インカの黄金")
        self.assertEqual(defn.min_players, 3)
        self.assertEqual(defn.max_players, 8)

class ConfigTest(unittest.TestCase):
    def test_normalize_config_valid(self):
        cfg = normalize_config({"rounds": 3, "hide_tent_totals": False})
        self.assertEqual(cfg, {"rounds": 3, "hide_tent_totals": False})

    def test_normalize_config_defaults(self):
        cfg = normalize_config(None)
        self.assertEqual(cfg, {})

    def test_normalize_config_errors(self):
        with self.assertRaises(ConfigurationError):
            normalize_config({"unknown": 123})
        with self.assertRaises(ConfigurationError):
            normalize_config({"rounds": 6})
        with self.assertRaises(ConfigurationError):
            normalize_config({"rounds": "3"})
        with self.assertRaises(ConfigurationError):
            normalize_config({"hide_tent_totals": "yes"})

class BurstAndDeckTest(unittest.TestCase):
    def test_hazard_burst_conditions(self):
        # A -> B safe, A -> B -> A burst
        c_fire = Card(id="f1", type="hazard", hazard_type="fire")
        c_mummy = Card(id="m1", type="hazard", hazard_type="mummy")
        c_fire2 = Card(id="f2", type="hazard", hazard_type="fire")
        c_treas = Card(id="t1", type="treasure", value=6)

        game = make_inca_game(3, deck=[c_treas, c_fire, c_mummy, c_fire2])
        game.start()

        # After treasure 6 -> 2 each, pool 0. Phase should be CHOOSING
        self.assertEqual(game.phase, CHOOSING)
        for p in game.players:
            self.assertEqual(p.carried, 2)

        # All stay
        choose(game, "p1", "stay")
        choose(game, "p2", "stay")
        choose(game, "p3", "stay")
        # Next card is fire (1st fire -> safe). Phase choosing again
        self.assertEqual(game.phase, CHOOSING)
        self.assertIn("fire", game.seen_hazards)

        # All stay
        choose(game, "p1", "stay")
        choose(game, "p2", "stay")
        choose(game, "p3", "stay")
        # Next card is mummy (safe, different type)
        self.assertEqual(game.phase, CHOOSING)
        self.assertIn("mummy", game.seen_hazards)

        # All stay
        choose(game, "p1", "stay")
        choose(game, "p2", "stay")
        choose(game, "p3", "stay")
        # Next card is fire2 -> Burst! Round ends -> phase ROUND_END (or FINISHED if rounds=1)
        self.assertEqual(game.phase, ROUND_END)
        # Carried lost
        for p in game.players:
            self.assertEqual(p.carried, 0)
        # fire is in excluded_hazards
        self.assertIn("fire", game.excluded_hazards)

class GemSharingTest(unittest.TestCase):
    def test_gem_division_and_pool(self):
        # Treasure 7 shared among 3 players -> 2 each, pool 1
        c_treas = Card(id="t1", type="treasure", value=7)
        c_treas2 = Card(id="t2", type="treasure", value=4)
        game = make_inca_game(3, deck=[c_treas, c_treas2])
        game.start()

        for p in game.players:
            self.assertEqual(p.carried, 2)
        self.assertEqual(game.pool, 1)

        # p1 leaves, p2 & p3 stay
        # p1 gets pool (1) + carried (2) = 3 into tent. Pool becomes 0.
        choose(game, "p1", "leave")
        choose(game, "p2", "stay")
        choose(game, "p3", "stay")

        self.assertEqual(game.by_id["p1"].tent, 3)
        self.assertEqual(game.by_id["p1"].in_temple, False)
        self.assertEqual(game.pool, 0)

    def test_multiple_leavers_share_pool(self):
        c_treas1 = Card(id="t1", type="treasure", value=7) # 2 each, pool 1
        c_treas2 = Card(id="t2", type="treasure", value=5) # 1 each, pool 1 + 2 = 3
        game = make_inca_game(3, deck=[c_treas1, c_treas2])
        game.start()

        # Both p1 and p2 leave. Pool is 1. Divided by 2 -> 0 each, pool remains 1.
        choose(game, "p1", "leave")
        choose(game, "p2", "leave")
        choose(game, "p3", "stay")

        self.assertEqual(game.pool, 1)
        self.assertEqual(game.by_id["p1"].tent, 2) # carried 2 + 0
        self.assertEqual(game.by_id["p2"].tent, 2)

class RelicTest(unittest.TestCase):
    def test_relic_collection_single_leaver(self):
        c_treas = Card(id="t1", type="treasure", value=6)
        c_relic = Card(id="r1", type="relic", relic_index=1)
        game = make_inca_game(3, deck=[c_treas, c_relic])
        game.start()

        # Card 1: treasure. All stay.
        choose(game, "p1", "stay")
        choose(game, "p2", "stay")
        choose(game, "p3", "stay")

        # Card 2: relic. p1 leaves, p2 & p3 stay
        choose(game, "p1", "leave")
        choose(game, "p2", "stay")
        choose(game, "p3", "stay")

        p1 = game.by_id["p1"]
        self.assertEqual(len(p1.relics), 1)
        self.assertIn(c_relic, p1.relics)

class SimultaneousChoiceTest(unittest.TestCase):
    def test_choices_hidden_until_all_selected(self):
        c_treas = Card(id="t1", type="treasure", value=6)
        c_treas2 = Card(id="t2", type="treasure", value=6)
        game = make_inca_game(3, deck=[c_treas, c_treas2])
        game.start()

        choose(game, "p1", "stay")
        # p2 views before choosing
        view_p2 = player_view(game, "p2")
        # p2 should see that p1 has chosen (hasChosen=True), but NOT what p1 chose ("stay")
        p1_info = next(p for p in view_p2["players"] if p["id"] == "p1")
        self.assertTrue(p1_info["hasChosen"])
        self.assertNotIn("choice", p1_info)

        # Duplicate choice raises InvalidAction
        with self.assertRaises(InvalidAction):
            choose(game, "p1", "leave")

class InformationLeakageTest(unittest.TestCase):
    def test_hide_tent_totals(self):
        c_treas = Card(id="t1", type="treasure", value=6)
        game = make_inca_game(3, config=RuleConfig(hide_tent_totals=True), deck=[c_treas])
        game.start()
        choose(game, "p1", "leave")
        choose(game, "p2", "stay")
        choose(game, "p3", "stay")

        view_p2 = player_view(game, "p2")
        # p2 should not see p1's tent
        p1_info = next(p for p in view_p2["players"] if p["id"] == "p1")
        self.assertNotIn("tent", p1_info)
        # p2 should see own tent
        self.assertIn("tent", view_p2["me"])

class ScoringAndVictoryTest(unittest.TestCase):
    def test_game_finishes_and_scores(self):
        c_treas = Card(id="t1", type="treasure", value=3)
        game = make_inca_game(3, config=RuleConfig(rounds=1), deck=[c_treas])
        game.start()
        choose(game, "p1", "leave")
        choose(game, "p2", "leave")
        choose(game, "p3", "leave")

        self.assertEqual(game.phase, FINISHED)
        self.assertIsNotNone(game.result)
        self.assertIn("winners", game.result)
        self.assertIn("scores", game.result)

if __name__ == "__main__":
    unittest.main()
