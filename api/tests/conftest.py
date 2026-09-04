import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test.db")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("TOOL_API_KEY", "test-tool-key")
os.environ.setdefault("TOOL_HMAC_SECRET", "test-hmac")

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.seed import seed_if_empty


@pytest.fixture
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    seed_if_empty(session)
    session.close()
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def client(db):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def tool_headers():
    return {"X-Tool-Key": os.environ["TOOL_API_KEY"]}


@pytest.fixture
def staff_token(client):
    from app.config import settings

    res = client.post(
        "/staff/login",
        json={"email": settings.seed_reception_email, "password": settings.seed_reception_password},
    )
    assert res.status_code == 200, res.text
    return res.json()["token"]
