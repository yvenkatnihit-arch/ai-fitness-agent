"""Step 7.11e (D-100): the chat rate limit against the real database (fake model, no Gemini cost)."""

import pytest

from tests.db.test_chat_api_live import DECIDED, fake_graph, rows  # noqa: F401  (fixtures and helper shared with the chat tests)
from tests.db.test_onboarding_complete import client, onboard, users  # noqa: F401

pytestmark = pytest.mark.db


def total_messages(user):
    return rows("select count(*) from public.chat_messages where user_id = %s", user)[0][0]


def test_the_limit_stops_the_next_message_with_a_429_before_anything_is_saved(client, users, fake_graph, monkeypatch):
    onboard(client)
    monkeypatch.setattr("app.core.chat_limits.WINDOWS", ((600, 3),))
    cid = None
    for i in range(3):
        body = {"message": f"m{i}", **({"conversation_id": cid} if cid else {})}
        cid = client.post("/chat", json=body).json()["conversation_id"]
    before = total_messages(users[0])
    limited = client.post("/chat", json={"message": "one too many", "conversation_id": cid})
    assert limited.status_code == 429
    assert 1 <= int(limited.headers["Retry-After"]) <= 600
    assert "seconds" in limited.json()["detail"] or "minutes" in limited.json()["detail"]
    assert total_messages(users[0]) == before                                               # nothing was saved


def test_the_limit_counts_the_person_across_chats_and_not_other_people(client, users, fake_graph, monkeypatch):
    onboard(client)
    monkeypatch.setattr("app.core.chat_limits.WINDOWS", ((600, 2),))
    assert client.post("/chat", json={"message": "first chat"}).status_code == 200
    assert client.post("/chat", json={"message": "second chat"}).status_code == 200            # a NEW chat still counts
    assert client.post("/chat", json={"message": "third chat"}).status_code == 429
    client.session.user_id = users[1]
    onboard(client)
    assert client.post("/chat", json={"message": "someone else"}).status_code == 200           # their own allowance
    client.session.user_id = users[0]
    assert client.post("/chat", json={"message": "again"}).status_code == 429
    assert client.get("/chat").status_code == 200                                              # reading is never limited


def test_answering_a_proposal_is_not_limited(client, users, fake_graph, monkeypatch):
    onboard(client)
    fake_graph["propose"] = True
    cid = client.post("/chat", json={"message": "plan please"}).json()["conversation_id"]
    monkeypatch.setattr("app.core.chat_limits.WINDOWS", ((600, 1),))
    assert client.post("/chat", json={"message": "more", "conversation_id": cid}).status_code == 429
    assert client.post(f"/chat/{cid}/decide", json={"choice": "approve"}).status_code == 200   # the yes or no still works
