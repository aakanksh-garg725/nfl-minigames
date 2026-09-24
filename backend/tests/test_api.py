from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.core.db import Base, get_db
from app.main import app, limited_user
from app.models import DealCase
from app.services import game
from app.services.demo import seed_demo
from app.services.rules import SLOTS, RuleError


@pytest.fixture
def client(db, user):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[current_user] = lambda: user
    app.dependency_overrides[limited_user] = lambda: user
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_api_no_hidden_fields_and_duplicate_action(client):
    created = client.post("/api/v1/deal-games", json={"slot": "RB1"})
    assert created.status_code == 200
    state = created.json()
    assert all(set(c) == {"case_number", "status", "is_user_case"} for c in state["cases"])
    url = f"/api/v1/deal-games/{state['id']}/select-case"
    chosen = client.post(url, json={"case_number": 1, "version": 0})
    assert chosen.status_code == 200
    assert client.post(url, json={"case_number": 2, "version": 0}).status_code == 409
    refreshed = client.get(f"/api/v1/deal-games/{state['id']}").json()
    assert refreshed["selected_case_number"] == 1
    assert refreshed["version"] == 1
    assert "seed" not in refreshed


def test_admin_is_protected(client):
    assert client.get("/api/v1/admin/health").status_code == 403


def test_invalid_body_and_slot_order(client):
    assert client.post("/api/v1/deal-games", json={"slot": "QB"}).status_code == 422
    assert client.post("/api/v1/deal-games", json={"slot": "WR1"}).status_code == 409


def test_duplicate_parallel_click_serializes(tmp_path, user):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'race.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        seed_demo(db)
        g = game.start_game(db, user, SLOTS[0])
        db.commit()
        gid = g.id
        game.act(db, user, gid, "select", 1, 0)
        db.commit()

    def click():
        with Session(engine, expire_on_commit=False) as db:
            try:
                result = game.act(db, user, gid, "open", 2, 1)
                db.commit()
                return result.status
            except RuleError:
                db.rollback()
                return "REJECTED"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: click(), range(2)))
    assert sorted(outcomes) == ["REJECTED", "ROUND_1"]
    with Session(engine) as db:
        assert (
            len(
                db.scalars(
                    select(DealCase).where(
                        DealCase.deal_game_id == gid, DealCase.status == "ELIMINATED"
                    )
                ).all()
            )
            == 1
        )
    engine.dispose()
