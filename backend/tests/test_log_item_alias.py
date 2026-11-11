"""Step 8.5 (D-109): the model sometimes writes "amount" for "quantity" (seen in a real run); that is accepted, and still validated. Offline."""

import pytest
from pydantic import ValidationError

from app.agents.log_tools import LogItem, LogMealArgs


def test_amount_is_accepted_as_quantity_and_both_spellings_give_the_same_item():
    a = LogItem(food_key="roti", quantity=2, unit="piece")
    b = LogItem.model_validate({"food_key": "roti", "amount": 2, "unit": "piece"})
    assert a == b and b.quantity == 2.0
    assert LogMealArgs.model_validate({"slot": "lunch", "items": [{"food_key": "roti", "amount": 2, "unit": "piece"}]}).items[0].quantity == 2.0


@pytest.mark.parametrize("bad", [{"food_key": "roti", "amount": "two pieces", "unit": "piece"}, {"food_key": "roti", "amount": 0, "unit": "piece"},
                                 {"food_key": "roti", "amount": 5000, "unit": "g"}, {"food_key": "roti", "unit": "piece"},
                                 {"food_key": "roti", "quantity": 2, "amount": 3, "unit": "piece", "kcal": 1}])
def test_a_bad_amount_is_still_refused(bad):
    with pytest.raises(ValidationError):
        LogItem.model_validate(bad)
