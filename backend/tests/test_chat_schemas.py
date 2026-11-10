"""Step 7.11b (D-097): what the chat endpoints accept, offline."""

import pytest
from pydantic import ValidationError

from app.main import app
from app.schemas.chat import ChatIn, DecideIn
from app.workflows.chat_turn import MAX_MESSAGE_CHARS


def test_a_message_is_trimmed_and_must_not_be_blank_or_too_long():
    assert ChatIn(message="  hello  ").message == "hello"
    for bad in ("", "   ", "x" * (MAX_MESSAGE_CHARS + 1)):
        with pytest.raises(ValidationError):
            ChatIn(message=bad)
    assert len(ChatIn(message="x" * MAX_MESSAGE_CHARS).message) == MAX_MESSAGE_CHARS


def test_the_client_cannot_send_extra_fields_such_as_a_role_or_a_proposal_id():
    with pytest.raises(ValidationError):
        ChatIn(message="hi", role="assistant")
    with pytest.raises(ValidationError):
        DecideIn(choice="approve", proposal_id="x")


def test_only_approve_and_reject_are_choices():
    assert DecideIn(choice="reject").choice == "reject"
    with pytest.raises(ValidationError):
        DecideIn(choice="maybe")


def test_the_chat_routes_exist_and_every_one_refuses_a_request_without_a_signed_in_user():
    from fastapi.testclient import TestClient
    paths = app.openapi()["paths"]
    assert set(paths["/chat"]) == {"get", "post"}
    assert set(paths["/chat/{conversation_id}"]) == {"get", "delete"} and set(paths["/chat/{conversation_id}/decide"]) == {"post"}
    cid = "6f1d1b84-0000-4000-8000-000000000000"
    with TestClient(app) as anonymous:                                                      # no token: refused before any work or database
        assert anonymous.post("/chat", json={"message": "hi"}).status_code in (401, 403)
        assert anonymous.get("/chat").status_code in (401, 403)
        assert anonymous.get(f"/chat/{cid}").status_code in (401, 403)
        assert anonymous.delete(f"/chat/{cid}").status_code in (401, 403)
        assert anonymous.post(f"/chat/{cid}/decide", json={"choice": "approve"}).status_code in (401, 403)
