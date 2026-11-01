"""インカの黄金のゲーム設定。"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from gameplatform.errors import ConfigurationError

@dataclass(frozen=True, slots=True)
class RuleConfig:
    rounds: int = 5
    hide_tent_totals: bool = True

_BOOL_FIELDS = {
    "hide_tent_totals",
}

_INT_FIELDS = {
    "rounds": (1, 5),
}

def normalize_config(raw: Any) -> dict[str, Any]:
    """外部入力の設定を検証し、保存してよい形にして返す。"""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigurationError("設定はオブジェクトで指定してください。")
    normalized: dict[str, Any] = {}
    for key, value in raw.items():
        if key in _BOOL_FIELDS:
            if not isinstance(value, bool):
                raise ConfigurationError(f"{key} は true / false で指定してください。")
            normalized[key] = value
        elif key in _INT_FIELDS:
            low, high = _INT_FIELDS[key]
            if isinstance(value, bool) or not isinstance(value, int):
                raise ConfigurationError(f"{key} は整数で指定してください。")
            if not low <= value <= high:
                raise ConfigurationError(f"{key} は {low}〜{high} の範囲で指定してください。")
            normalized[key] = value
        else:
            raise ConfigurationError(f"不明な設定です: {key}")
    return normalized
