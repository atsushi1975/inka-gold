"""プレイヤーごとの公開ビュー（情報フィルタ）。"""
from __future__ import annotations
from typing import Any
from .engine import CHOOSING, FINISHED, Game

def player_view(game: Game, player_id: str) -> dict[str, Any]:
    if player_id not in game.by_id:
        raise KeyError("このゲームのプレイヤーではありません")

    me = game.by_id[player_id]
    is_finished = game.phase == FINISHED
    hide_tents = game.config.hide_tent_totals and not is_finished

    players_view = []
    for p in game.players:
        is_me = p.id == player_id
        # hide tent totals and relics of other players if hide_tent_totals is True and not finished
        show_tent = is_me or not hide_tents
        show_relics = is_me or not hide_tents

        p_dict: dict[str, Any] = {
            "id": p.id,
            "name": p.name,
            "inTemple": p.in_temple,
            "carried": p.carried,
            "hasChosen": p.choice is not None,
            "isMe": is_me,
        }
        if show_tent:
            p_dict["tent"] = p.tent
        if show_relics:
            p_dict["relics"] = [r.to_dict() for r in p.relics]
            p_dict["relicCount"] = len(p.relics)
        players_view.append(p_dict)

    me_dict: dict[str, Any] = {
        "id": me.id,
        "name": me.name,
        "inTemple": me.in_temple,
        "carried": me.carried,
        "tent": me.tent,
        "relics": [r.to_dict() for r in me.relics],
        "choice": me.choice,
    }

    events_view = [
        {
            "seq": ev.seq,
            "kind": ev.kind,
            "message": ev.message,
            "data": ev.data,
        }
        for ev in game.events
    ]

    return {
        "revision": game.revision,
        "phase": game.phase,
        "round": game.round,
        "config": {
            "rounds": game.config.rounds,
            "hideTentTotals": game.config.hide_tent_totals,
        },
        "path": [c.to_dict() for c in game.path],
        "pool": game.pool,
        "seenHazards": list(game.seen_hazards),
        "deckCount": len(game.current_deck),
        "players": players_view,
        "me": me_dict,
        "events": events_view,
        "result": game.result,
    }
