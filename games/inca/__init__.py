"""インカの黄金のゲームプラットフォーム登録。"""
from __future__ import annotations
from typing import Any
from gameplatform.errors import InvalidAction
from gameplatform.games import GameDefinition, register
from .config import RuleConfig, normalize_config
from .engine import Game
from .views import player_view

def create_game(players: list[tuple[str, str]], config: dict[str, Any]) -> Game:
    return Game(players, config=RuleConfig(**config))

def act(game: Game, player_id: str, payload: dict[str, Any]) -> None:
    action_type = payload.get("type")
    if action_type == "choose":
        choice = payload.get("choice")
        game.act(player_id, {"type": "choose", "choice": choice})
    elif action_type == "next_round":
        game.act(player_id, {"type": "next_round"})
    else:
        raise InvalidAction(f"不明なアクションです: {action_type}")

GAME = GameDefinition(
    key="inca",
    title="インカの黄金",
    description="神殿の奥深くへと進み、危険を避けて多くの宝石と遺物を持ち帰る探索ゲーム。",
    min_players=3,
    max_players=8,
    create=create_game,
    view=player_view,
    act=act,
    normalize_config=normalize_config,
    cpu_driver=None,
)

register(GAME)
