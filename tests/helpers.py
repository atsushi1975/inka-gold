"""テスト用ヘルパー関数。"""
from __future__ import annotations
from games.inca.cards import Card, full_hazards, full_relics, full_treasures
from games.inca.config import RuleConfig
from games.inca.engine import Game

def make_inca_game(
    player_count: int = 3,
    config: RuleConfig | None = None,
    deck: list[Card] | None = None,
    decks: list[list[Card]] | None = None,
) -> Game:
    players = [(f"p{i+1}", f"P{i+1}") for i in range(player_count)]
    return Game(players, config=config, deck=deck, decks=decks)

def choose(game: Game, player_id: str, choice: str) -> None:
    game.act(player_id, {"type": "choose", "choice": choice})

def next_round(game: Game, player_id: str = "p1") -> None:
    game.act(player_id, {"type": "next_round"})
