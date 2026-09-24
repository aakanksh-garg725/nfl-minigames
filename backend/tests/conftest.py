import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["AUTH_MODE"] = "demo"
os.environ["APP_ENV"] = "development"

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.auth import DEMO_USER  # noqa: E402
from app.core.db import Base  # noqa: E402
from app.services.demo import seed_demo  # noqa: E402


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        seed_demo(session)
        yield session
    engine.dispose()


@pytest.fixture
def user():
    return DEMO_USER
