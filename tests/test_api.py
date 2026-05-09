import pytest
from fastapi.testclient import TestClient
from uuid_utils.compat import uuid4

from backend.auth.config import get_settings
from backend.auth.jwt_tokens import create_access_token
from backend.endpoints import API_PREFIX, app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient):
    response = client.get(f"{API_PREFIX}/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_and_get_game(client: TestClient):
    anon = client.post(f"{API_PREFIX}/auth/anonymous", json={})
    assert anon.status_code == 200

    with client.websocket_connect(f"{API_PREFIX}/ws") as ws:
        ws.send_json({"id": "c1", "action": "games.create"})
        msg = ws.receive_json()
        assert msg["ok"] is True
        body = msg["data"]
        assert "id" in body
        assert body["whose_move"] == "white"
        assert body["black_user"] is None
        assert body["white_user"]["name"] == "Guest"
        assert "id" in body["white_user"]

        game_id = body["id"]
        ws.send_json({"id": "g1", "action": "games.get", "game_id": game_id})
        msg2 = ws.receive_json()
        assert msg2["ok"] is True
        assert msg2["data"]["id"] == game_id


def test_create_game_user_not_found(client: TestClient):
    settings = get_settings()
    token = create_access_token(user_id=uuid4(), name="nobody")
    client.cookies.set(settings.cookie_name, token)
    with client.websocket_connect(f"{API_PREFIX}/ws") as ws:
        ws.send_json({"id": "1", "action": "games.create"})
        msg = ws.receive_json()
        assert msg["ok"] is False
        assert msg["error"]["code"] == 404


def test_create_game_requires_auth(client: TestClient):
    with client.websocket_connect(f"{API_PREFIX}/ws") as ws:
        ws.send_json({"id": "1", "action": "games.create"})
        msg = ws.receive_json()
        assert msg["ok"] is False
        assert msg["error"]["code"] == 401


def test_anonymous_sets_cookie(client: TestClient):
    response = client.post(f"{API_PREFIX}/auth/anonymous", json={"name": "anon1"})
    assert response.status_code == 200
    assert response.json()["is_anonymous"] is True


def test_auth_me_ok(client: TestClient):
    client.post(f"{API_PREFIX}/auth/anonymous", json={"name": "me"})
    with client.websocket_connect(f"{API_PREFIX}/ws") as ws:
        ws.send_json({"id": "m1", "action": "auth.me"})
        msg = ws.receive_json()
        assert msg["ok"] is True
        assert msg["data"]["name"] == "me"
        assert "user_id" in msg["data"]


def test_auth_me_unauthorized(client: TestClient):
    with client.websocket_connect(f"{API_PREFIX}/ws") as ws:
        ws.send_json({"id": "m1", "action": "auth.me"})
        msg = ws.receive_json()
        assert msg["ok"] is False
        assert msg["error"]["code"] == 401


def test_matchmaking_pair_two_clients():
    """Один «Играть» → waiting; второй на другой сессии → matched; первый получает push."""
    with TestClient(app) as c1, TestClient(app) as c2:
        assert c1.post(f"{API_PREFIX}/auth/anonymous", json={"name": "alpha"}).status_code == 200
        assert c2.post(f"{API_PREFIX}/auth/anonymous", json={"name": "beta"}).status_code == 200
        with (
            c1.websocket_connect(f"{API_PREFIX}/ws") as w1,
            c2.websocket_connect(f"{API_PREFIX}/ws") as w2,
        ):
            w1.send_json({"id": "p1", "action": "matchmaking.play"})
            r1 = w1.receive_json()
            assert r1["ok"] is True
            assert r1["data"]["status"] == "waiting"
            assert "queued_at" in r1["data"]

            w2.send_json({"id": "p2", "action": "matchmaking.play"})
            r2 = w2.receive_json()
            assert r2["ok"] is True
            assert r2["data"]["status"] == "matched"
            assert r2["data"]["game"]["white_user"]["name"] == "alpha"
            assert r2["data"]["game"]["black_user"]["name"] == "beta"

            push = w1.receive_json()
            assert push.get("type") == "push"
            assert push.get("event") == "matchmaking.matched"
            assert push["data"]["game"]["id"] == r2["data"]["game"]["id"]


def test_matchmaking_cancel(client: TestClient):
    client.post(f"{API_PREFIX}/auth/anonymous", json={"name": "solo"})
    with client.websocket_connect(f"{API_PREFIX}/ws") as ws:
        ws.send_json({"id": "m1", "action": "matchmaking.play"})
        r = ws.receive_json()
        assert r["data"]["status"] == "waiting"
        ws.send_json({"id": "m2", "action": "matchmaking.cancel"})
        r2 = ws.receive_json()
        assert r2["ok"] is True
        assert r2["data"]["status"] == "cancelled"
