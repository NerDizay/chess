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
