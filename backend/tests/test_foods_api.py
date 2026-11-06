"""Food search refuses bad requests before touching the database, and shapes results correctly."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.auth import CurrentUser, get_current_user
from app.main import app
from app.schemas.foods import to_food_out


@pytest.fixture
def client(monkeypatch):
    def no_db(*args, **kwargs):
        raise AssertionError("this request should have been refused before any database work")

    monkeypatch.setattr("app.api.foods.user_transaction", no_db)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=uuid.uuid4(), email=None)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_search_needs_a_login():
    assert TestClient(app).get("/foods/search", params={"q": "dal"}).status_code == 401


@pytest.mark.parametrize("params", [{}, {"q": "d"}, {"q": "x" * 61}, {"q": "dal", "limit": 0},
                                    {"q": "dal", "limit": 26}, {"q": "dal", "limit": "lots"}])
def test_bad_queries_get_422_without_touching_the_database(client, params):
    assert client.get("/foods/search", params=params).status_code == 422


def test_result_shape():
    row = dict(id=7, key="idli", name="Idli", category="dish_breakfast", diet_class="vegan", is_dish=True,
               kcal=145.3, protein_g=5.9, carbs_g=27.3, fat_g=0.5, fiber_g=None, review_status="review",
               source="computed", synonyms=["idly"], units=[{"unit": "piece", "grams": 40.0}])
    out = to_food_out(row)
    assert out.fiber_g_per_100g is None          # unknown stays unknown
    assert out.verified is False                 # still in review
    assert out.units[0].grams == 40 and out.local_names == ["idly"]
