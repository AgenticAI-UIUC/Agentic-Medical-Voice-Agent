import pytest
from fastapi.testclient import TestClient

from app import crud
from app.main import app


@pytest.fixture(autouse=True)
def reset_mock_data():
    """
    Reset mock in-memory state before each test so tests don't affect each other.
    """
    crud.reset_mock_data()
    yield
    crud.reset_mock_data()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
