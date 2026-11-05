import pytest

from app.db import admin_transaction, user_transaction


def test_user_transaction_refuses_a_plain_string_id():
    # The user id must come from a verified JWT as a UUID, never as raw request text.
    with pytest.raises(TypeError):
        with user_transaction("7f3a-not-a-uuid"):
            pass


@pytest.mark.parametrize("reason", ["", "   "])
def test_admin_transaction_needs_a_reason(reason):
    with pytest.raises(ValueError):
        with admin_transaction(reason):
            pass
