"""インカの黄金のカード定義。"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

HAZARD_LABELS: dict[str, str] = {
    "fire": "火",
    "mummy": "ミイラ",
    "rocks": "落石",
    "snakes": "ヘビ",
    "spiders": "クモ",
}

TREASURE_VALUES = [1, 2, 3, 4, 5, 5, 7, 7, 9, 11, 11, 13, 14, 15, 17]

@dataclass(frozen=True, slots=True)
class Card:
    id: str
    type: str  # "treasure", "hazard", "relic"
    value: int | None = None
    hazard_type: str | None = None
    relic_index: int | None = None  # 1 to 5

    @property
    def label(self) -> str:
        if self.type == "treasure":
            return f"宝石: {self.value}"
        elif self.type == "hazard":
            return HAZARD_LABELS.get(self.hazard_type or "", self.hazard_type or "")
        elif self.type == "relic":
            return "遺物"
        return "カード"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "label": self.label,
        }
        if self.value is not None:
            d["value"] = self.value
        if self.hazard_type is not None:
            d["hazardType"] = self.hazard_type
        if self.relic_index is not None:
            d["relicIndex"] = self.relic_index
        return d

def full_treasures() -> list[Card]:
    return [
        Card(id=f"treasure-{i}", type="treasure", value=val)
        for i, val in enumerate(TREASURE_VALUES)
    ]

def full_hazards() -> list[Card]:
    cards: list[Card] = []
    idx = 0
    for h_type in ["fire", "mummy", "rocks", "snakes", "spiders"]:
        for _ in range(3):
            cards.append(Card(id=f"hazard-{h_type}-{idx}", type="hazard", hazard_type=h_type))
            idx += 1
    return cards

def full_relics() -> list[Card]:
    return [
        Card(id=f"relic-{i+1}", type="relic", relic_index=i+1)
        for i in range(5)
    ]
