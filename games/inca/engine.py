"""インカの黄金のゲームエンジン。"""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Any
from gameplatform.errors import InvalidAction
from .cards import Card, HAZARD_LABELS, full_hazards, full_relics, full_treasures
from .config import RuleConfig

CHOOSING = "choosing"
ROUND_END = "round_end"
FINISHED = "finished"

__all__ = [
    "CHOOSING",
    "ROUND_END",
    "FINISHED",
    "Event",
    "Game",
    "Player",
]

@dataclass(slots=True)
class Player:
    id: str
    name: str
    in_temple: bool = True
    carried: int = 0
    tent: int = 0
    relics: list[Card] = field(default_factory=list)
    choice: str | None = None  # "stay" | "leave"

@dataclass(slots=True)
class Event:
    seq: int
    kind: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)

class Game:
    def __init__(
        self,
        players: list[tuple[str, str]],
        *,
        config: RuleConfig | None = None,
        rng: random.Random | None = None,
        decks: list[list[Card]] | None = None,
        deck: list[Card] | None = None,
    ) -> None:
        self.config = config or RuleConfig()
        if not (3 <= len(players) <= 8):
            raise ValueError(f"人数は 3〜8 人です: {len(players)}")
        ids = [pid for pid, _ in players]
        if len(set(ids)) != len(ids):
            raise ValueError("プレイヤー id が重複しています")

        self.rng = rng or random.Random()
        self.players = [Player(id=pid, name=name) for pid, name in players]
        self.by_id = {p.id: p for p in self.players}
        self.revision = 1
        self.phase = CHOOSING
        self.round = 1
        self.started_by = self.players[0].id

        self.decks = decks
        self.initial_deck_override = deck

        # Relics deck: 5 relics shuffled
        relics = full_relics()
        self.rng.shuffle(relics)
        self.relics_deck = relics

        self.excluded_hazards: set[str] = set()
        self.relics_brought_back_order: list[Card] = []

        self.path: list[Card] = []
        self.pool: int = 0
        self.seen_hazards: set[str] = set()
        self.current_deck: list[Card] = []

        self.events: list[Event] = []
        self._event_seq = 0
        self.result: dict[str, Any] | None = None

    def _log(self, kind: str, message: str, data: dict[str, Any] | None = None) -> None:
        self._event_seq += 1
        self.events.append(Event(seq=self._event_seq, kind=kind, message=message, data=data or {}))

    def start(self) -> None:
        if self.revision > 1 or self.events:
            raise InvalidAction("すでに開始しています。")
        self._log("start", f"ゲームが開始されました（全 {self.config.rounds} ラウンド）")
        self._start_round()

    def _start_round(self) -> None:
        for p in self.players:
            p.in_temple = True
            p.carried = 0
            p.choice = None

        self.pool = 0
        self.seen_hazards = set()
        self.path = []

        # Build round deck
        if self.decks and self.round - 1 < len(self.decks):
            deck = list(self.decks[self.round - 1])
        elif self.round == 1 and self.initial_deck_override is not None:
            deck = list(self.initial_deck_override)
        else:
            treasures = full_treasures()
            hazards = [h for h in full_hazards() if h.hazard_type not in self.excluded_hazards]
            if self.round - 1 < len(self.relics_deck):
                relic = self.relics_deck[self.round - 1]
                deck = treasures + hazards + [relic]
            else:
                deck = treasures + hazards
            self.rng.shuffle(deck)

        self.current_deck = deck
        self._log("round_start", f"第 {self.round} ラウンドが開始されました。")
        self._reveal_next_card()

    def _reveal_next_card(self) -> None:
        if not self.current_deck:
            self._end_round()
            return

        card = self.current_deck.pop(0)
        self.path.append(card)

        if card.type == "treasure":
            val = card.value or 0
            in_temple_players = [p for p in self.players if p.in_temple]
            n = len(in_temple_players)
            if n == 0:
                self.pool += val
                self._log("treasure", f"宝石 {val} が出ましたが、神殿内に誰もいないためプールに残りました。", {"card": card.to_dict(), "pool": self.pool})
                self._end_round()
            else:
                share = val // n
                remainder = val % n
                for p in in_temple_players:
                    p.carried += share
                self.pool += remainder
                self._log("treasure", f"宝石 {val} が出ました。神殿内の {n} 人で {share} ずつ分け合いました。", {"card": card.to_dict(), "share": share, "remainder": remainder, "pool": self.pool})
                self.phase = CHOOSING
                for p in in_temple_players:
                    p.choice = None

        elif card.type == "hazard":
            h_type = card.hazard_type or ""
            if h_type in self.seen_hazards:
                # Burst!
                self.excluded_hazards.add(h_type)
                label = HAZARD_LABELS.get(h_type, h_type)
                self._log("burst", f"{label}が再び発生してバースト！神殿内のプレイヤーは手持ちの宝石を失いました。", {"card": card.to_dict(), "hazardType": h_type})
                for p in self.players:
                    if p.in_temple:
                        p.carried = 0
                self._end_round()
            else:
                self.seen_hazards.add(h_type)
                label = HAZARD_LABELS.get(h_type, h_type)
                in_temple_players = [p for p in self.players if p.in_temple]
                self._log("hazard", f"{label}が出現しました。", {"card": card.to_dict(), "hazardType": h_type})
                if not in_temple_players:
                    self._end_round()
                else:
                    self.phase = CHOOSING
                    for p in in_temple_players:
                        p.choice = None

        elif card.type == "relic":
            in_temple_players = [p for p in self.players if p.in_temple]
            self._log("relic", f"遺物が現れました。", {"card": card.to_dict()})
            if not in_temple_players:
                self._end_round()
            else:
                self.phase = CHOOSING
                for p in in_temple_players:
                    p.choice = None

    def act(self, player_id: str, payload: dict[str, Any]) -> None:
        if player_id not in self.by_id:
            raise InvalidAction("プレイヤーではありません。")
        action_type = payload.get("type")

        if action_type == "choose":
            if self.phase != CHOOSING:
                raise InvalidAction("現在は選択フェーズではありません。")
            player = self.by_id[player_id]
            if not player.in_temple:
                raise InvalidAction("すでに神殿の外にいます。")
            if player.choice is not None:
                raise InvalidAction("すでに選択済みです。")
            choice = payload.get("choice")
            if choice not in ("stay", "leave"):
                raise InvalidAction("選択は 'stay' または 'leave' を指定してください。")

            player.choice = choice
            self.revision += 1

            # Check if all in-temple players have chosen
            in_temple_players = [p for p in self.players if p.in_temple]
            if all(p.choice is not None for p in in_temple_players):
                self._resolve_choices()

        elif action_type == "next_round":
            if self.phase != ROUND_END:
                raise InvalidAction("現在はラウンド終了フェーズではありません。")
            if self.round >= self.config.rounds:
                raise InvalidAction("すでに最終ラウンドが終了しています。")
            self.round += 1
            self.revision += 1
            self._start_round()

        else:
            raise InvalidAction(f"不明なアクションです: {action_type}")

    def _resolve_choices(self) -> None:
        leavers = [p for p in self.players if p.in_temple and p.choice == "leave"]
        stayers = [p for p in self.players if p.in_temple and p.choice == "stay"]

        if leavers:
            L = len(leavers)
            share = self.pool // L
            remainder = self.pool % L
            for p in leavers:
                p.carried += share
            self.pool = remainder

            relics_on_path = [c for c in self.path if c.type == "relic"]

            if L == 1:
                leaver = leavers[0]
                leaver.carried += self.pool
                self.pool = 0
                if relics_on_path:
                    for r_card in relics_on_path:
                        if r_card in self.path:
                            self.path.remove(r_card)
                        leaver.relics.append(r_card)
                        self.relics_brought_back_order.append(r_card)
                    self._log("leave_single", f"{leaver.name} が単独で帰還し、プール全額と遺物を持ち帰りました。", {"playerId": leaver.id, "relicsCount": len(relics_on_path)})
                else:
                    self._log("leave_single", f"{leaver.name} が単独で帰還し、プール全額を持ち帰りました。", {"playerId": leaver.id})
            else:
                names = ", ".join(p.name for p in leavers)
                self._log("leave_multiple", f"{names} の {L} 人が同時に帰還し、プールを均等に分け合いました（遺物は場に残ります）。", {"playerIds": [p.id for p in leavers]})

            for p in leavers:
                p.tent += p.carried
                p.carried = 0
                p.in_temple = False
                p.choice = None
        else:
            self._log("stay_all", "全員が神殿に残ることを選択しました。")

        for p in stayers:
            p.choice = None

        # Check if anyone is still in temple
        remaining_temple = [p for p in self.players if p.in_temple]
        if not remaining_temple:
            self._end_round()
        else:
            self._reveal_next_card()

    def _end_round(self) -> None:
        for p in self.players:
            p.carried = 0
            p.in_temple = False
            p.choice = None

        self._log("round_end", f"第 {self.round} ラウンドが終了しました。")

        if self.round >= self.config.rounds:
            self._finish_game()
        else:
            self.phase = ROUND_END

    def _finish_game(self) -> None:
        self.phase = FINISHED

        # Calculate scores and relic values
        # 1st-3rd relics brought back: 5 pts each, 4th-5th: 10 pts each.
        scores: dict[str, int] = {}
        relic_counts: dict[str, int] = {}

        for p in self.players:
            relic_counts[p.id] = len(p.relics)
            score = p.tent
            for r_card in p.relics:
                # Find position in global brought back order
                try:
                    idx = self.relics_brought_back_order.index(r_card) + 1
                except ValueError:
                    idx = 1
                val = 5 if idx <= 3 else 10
                score += val
            scores[p.id] = score

        max_score = max(scores.values()) if scores else 0
        top_scorers = [pid for pid, sc in scores.items() if sc == max_score]

        if len(top_scorers) == 1:
            winners = top_scorers
        else:
            # Tie breaker: most relics
            max_relics = max(relic_counts[pid] for pid in top_scorers)
            top_relics = [pid for pid in top_scorers if relic_counts[pid] == max_relics]
            winners = top_relics

        self.result = {
            "winners": winners,
            "scores": scores,
            "relicCounts": relic_counts,
        }
        self._log("game_finished", f"ゲームが終了しました！ 勝者: {', '.join(self.by_id[wid].name for wid in winners)}", {"winners": winners, "scores": scores})
