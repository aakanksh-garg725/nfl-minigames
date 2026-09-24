import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.auth import current_user
from app.core.db import get_db
from app.main import app, limited_user
from app.models import Profile


@pytest.fixture
def client(db, user):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[current_user] = lambda: user
    app.dependency_overrides[limited_user] = lambda: user
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_profile_team_and_rename_preserve_identity(client, db, user):
    response = client.patch(
        "/api/v1/profile", json={"username": "New_Name", "favorite_team": "BAL"}
    )
    assert response.status_code == 200
    assert response.json()["username"] == "new_name"
    assert response.json()["profile_complete"] is True
    assert response.json()["user_id"] == user
    assert len(response.json()["teams"]) == 32
    assert len(list(db.scalars(select(Profile)))) == 1
    assert client.get("/api/v1/profile/username-availability?username=NEW_NAME").json()["available"]


def test_conflict_returns_available_suggestions_and_preserves_profile(client, db, user):
    db.add(Profile(user_id="other", username="taken", favorite_team="SEA"))
    db.add(Profile(user_id="other2", username="taken_nfl", favorite_team="SEA"))
    db.commit()
    response = client.patch("/api/v1/profile", json={"username": "TAKEN", "favorite_team": "GB"})
    assert response.status_code == 409
    assert "already taken" in response.json()["detail"]
    suggestions = response.json()["suggestions"]
    assert len(suggestions) == 3
    assert "taken_nfl" not in suggestions
    assert db.get(Profile, user).username == "local_player"
    for username in suggestions:
        assert client.get(f"/api/v1/profile/username-availability?username={username}").json()[
            "available"
        ]
    assert not client.get("/api/v1/profile/username-availability?username=TAKEN").json()[
        "available"
    ]


@pytest.mark.parametrize(
    "body",
    [
        {"username": "ab", "favorite_team": "BAL"},
        {"username": "has space", "favorite_team": "BAL"},
        {"username": "valid", "favorite_team": "NFL"},
        {"username": "valid"},
    ],
)
def test_invalid_profiles(client, body):
    assert client.patch("/api/v1/profile", json=body).status_code == 422


def test_incomplete_profile_cannot_start_game(client, db, user):
    db.get(Profile, user).favorite_team = None
    db.commit()
    assert not client.get("/api/v1/profile").json()["profile_complete"]
    assert client.post("/api/v1/deal-games", json={"slot": "RB1"}).status_code == 428
