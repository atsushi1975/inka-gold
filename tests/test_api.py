"""インカの黄金の Web API およびヘルスチェックのユニットテスト。"""
from __future__ import annotations

import json
from typing import Any
import unittest
from unittest.mock import patch

from gameplatform import realtime, rooms
from games.inca.engine import FINISHED
from health_app import create_health_app, inca_status
from web import create_app
from web.api import _health_version


class ApiTest(unittest.TestCase):
    def setUp(self):
        rooms.reset()
        realtime.reset()
        patcher = patch.object(rooms, "CPU_TURN_DELAY_SECONDS", 0)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app = create_app({"TESTING": True})

    def client(self):
        return self.app.test_client()

    def create_room(self, name: str):
        client = self.client()
        response = client.post("/api/rooms", json={"name": name, "game": "inca"})
        self.assertEqual(response.status_code, 201, response.get_json())
        data = response.get_json()
        return client, data

    def join_room(self, room_id: str, name: str):
        client = self.client()
        response = client.post(f"/api/rooms/{room_id}/join", json={"name": name})
        return client, response

    @staticmethod
    def headers(token: str) -> dict[str, str]:
        return {"X-Player-Token": token}

    def start(self, client, room_id: str, token: str, cpu_count: int = 0):
        response = client.post(
            f"/api/rooms/{room_id}/start",
            headers=self.headers(token),
            json={"cpuCount": cpu_count},
        )
        return response

    def state(self, client, room_id: str, token: str):
        response = client.get(
            f"/api/rooms/{room_id}/state", headers=self.headers(token)
        )
        return response

    def action(self, client, room_id: str, token: str, payload: dict[str, Any], expected_revision: int | None = None):
        body = dict(payload)
        if expected_revision is not None:
            body["expectedRevision"] = expected_revision
        response = client.post(
            f"/api/rooms/{room_id}/actions",
            headers=self.headers(token),
            json=body,
        )
        return response

    def three_players(self):
        host_client, host = self.create_room("ホスト")
        room_id = host["roomId"]
        client_b, res_b = self.join_room(room_id, "B")
        self.assertEqual(res_b.status_code, 200)
        player_b = res_b.get_json()

        client_c, res_c = self.join_room(room_id, "C")
        self.assertEqual(res_c.status_code, 200)
        player_c = res_c.get_json()

        tokens = {
            host["playerId"]: host["token"],
            player_b["playerId"]: player_b["token"],
            player_c["playerId"]: player_c["token"],
        }
        clients = {
            host["playerId"]: host_client,
            player_b["playerId"]: client_b,
            player_c["playerId"]: client_c,
        }
        return room_id, host_client, host, tokens, clients

    def test_room_lifecycle_and_choosing(self):
        room_id, host_client, host, tokens, clients = self.three_players()
        response = self.start(host_client, room_id, host["token"])
        self.assertEqual(response.status_code, 200, response.get_json())

        # Each player chooses "stay" or "leave"
        for player_id, token in tokens.items():
            st = self.state(clients[player_id], room_id, token).get_json()
            rev = st["game"]["revision"]
            res = self.action(clients[player_id], room_id, token, {"type": "choose", "choice": "stay"}, expected_revision=rev)
            self.assertEqual(res.status_code, 200, res.get_json())

    def test_non_host_cannot_start_and_minimum_players(self):
        host_client, host = self.create_room("ホスト")
        room_id = host["roomId"]
        client_b, res_b = self.join_room(room_id, "B")
        player_b = res_b.get_json()
        # Non-host cannot start
        self.assertEqual(self.start(client_b, room_id, player_b["token"]).status_code, 403)
        # Less than 3 players cannot start
        self.assertEqual(self.start(host_client, room_id, host["token"]).status_code, 400)

    def test_cpu_count_rejected(self):
        room_id, host_client, host, tokens, clients = self.three_players()
        response = self.start(host_client, room_id, host["token"], cpu_count=1)
        self.assertEqual(response.status_code, 400)

    def test_stale_revision_conflict(self):
        room_id, host_client, host, tokens, clients = self.three_players()
        self.start(host_client, room_id, host["token"])
        # Send wrong expectedRevision
        res = self.action(host_client, room_id, host["token"], {"type": "choose", "choice": "stay"}, expected_revision=999)
        self.assertEqual(res.status_code, 409)
        self.assertIn("game", res.get_json())

    def test_invalid_action_and_duplicate_choice(self):
        room_id, host_client, host, tokens, clients = self.three_players()
        self.start(host_client, room_id, host["token"])
        # Invalid choice value
        res = self.action(host_client, room_id, host["token"], {"type": "choose", "choice": "invalid_choice"})
        self.assertEqual(res.status_code, 400)
        # Valid choice
        res2 = self.action(host_client, room_id, host["token"], {"type": "choose", "choice": "stay"})
        self.assertEqual(res2.status_code, 200)
        # Duplicate choice from the same player
        res3 = self.action(host_client, room_id, host["token"], {"type": "choose", "choice": "leave"})
        self.assertEqual(res3.status_code, 400)

    def test_choices_secrecy(self):
        room_id, host_client, host, tokens, clients = self.three_players()
        self.start(host_client, room_id, host["token"])
        guest_id = next(pid for pid in tokens if pid != host["playerId"])
        
        # Host chooses "stay"
        host_rev = self.state(host_client, room_id, host["token"]).get_json()["game"]["revision"]
        self.action(host_client, room_id, host["token"], {"type": "choose", "choice": "stay"}, expected_revision=host_rev)

        # Guest views state before choosing
        guest_res = self.state(clients[guest_id], room_id, tokens[guest_id])
        guest_state = guest_res.get_json()
        host_info = next(p for p in guest_state["game"]["players"] if p["id"] == host["playerId"])
        self.assertTrue(host_info["hasChosen"])
        self.assertNotIn("choice", host_info)

        # In guest's full response JSON string, host's choice ("stay") does not appear for host
        # (check that "choice" field is not exposed for host in players list)
        for p in guest_state["game"]["players"]:
            if p["id"] == host["playerId"]:
                self.assertNotIn("choice", p)

    def test_join_after_start_and_token_validation(self):
        room_id, host_client, host, tokens, clients = self.three_players()
        self.start(host_client, room_id, host["token"])

        # Join after start rejected
        client_d, res_d = self.join_room(room_id, "D")
        self.assertEqual(res_d.status_code, 400)

        # Invalid token rejected
        res_invalid = self.state(client_d, room_id, "invalid-token-123")
        self.assertEqual(res_invalid.status_code, 403)

        # Token of another room rejected
        _, other_host = self.create_room("別ホスト")
        res_other_token = self.state(client_d, room_id, other_host["token"])
        self.assertEqual(res_other_token.status_code, 403)

    def test_health(self):
        response = self.client().get("/api/health")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertIn("inca", payload["games"])
        self.assertIn("playing_rooms", payload)
        self.assertIsInstance(payload["playing_rooms"], int)

    def test_health_status_lifecycle(self):
        response = self.client().get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "idle")
        self.assertEqual(payload["playing_rooms"], 0)

        room_id, host_client, host, tokens, clients = self.three_players()
        response = self.client().get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "waiting")

        self.start(host_client, room_id, host["token"])
        response = self.client().get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "playing")

        room = rooms.get_room(room_id)
        room.game.phase = FINISHED
        response = self.client().get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "idle")

    def test_health_and_api_health_return_the_same_content(self):
        root_response = self.client().get("/health")
        api_response = self.client().get("/api/health")
        self.assertEqual(root_response.status_code, 200)
        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(root_response.get_json(), api_response.get_json())
        payload = api_response.get_json()
        self.assertEqual(
            set(payload),
            {"ok", "games", "title", "version", "status", "playing_rooms"},
        )
        self.assertEqual(payload["status"], "idle")

    def test_standalone_health_app_returns_common_payload(self):
        standalone = create_health_app("インカの黄金", inca_status)
        client = standalone.test_client()
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(set(payload), {"title", "version", "status", "playing_rooms"})
        self.assertEqual(payload["title"], "インカの黄金")
        self.assertEqual(payload["status"], "idle")

    def test_pages(self):
        r1 = self.client().get("/")
        self.assertEqual(r1.status_code, 200)
        self.assertIn("インカの黄金", r1.get_data(as_text=True))

        r2 = self.client().get("/rooms/test-room")
        self.assertEqual(r2.status_code, 200)
        self.assertIn("インカの黄金", r2.get_data(as_text=True))

