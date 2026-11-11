"""Step 8.9 (D-115): dizziness, fainting and chest symptoms are not "a body area": they must not get the exercise-pain wording. Offline."""

import pytest

from app.safety import messages
from app.safety.guards import check_input, check_output


@pytest.mark.parametrize("text", ["I feel dizzy when I fast, is that normal", "I felt dizzy and nearly fainted on the treadmill", "chest pain during my run",
                                  "I feel light headed after dieting", "I passed out yesterday", "feeling faint after my workout"])
def test_whole_body_symptoms_get_their_own_wording_in_the_same_category(text):
    v = check_input(text)
    assert v and v.category == "red_flag_pain" and v.reply == messages.RED_FLAG_SYMPTOMS
    assert "train that area" not in v.reply and "doctor" in v.reply


@pytest.mark.parametrize("text", ["sharp pain in my knee when I squat", "my fingers have numbness after deadlifts", "my knee swelling is getting worse", "my knee gives way on stairs"])
def test_pain_in_a_body_area_keeps_the_original_wording(text):
    v = check_input(text)
    assert v and v.category == "red_flag_pain" and v.reply == messages.RED_FLAG_PAIN


def test_the_new_wording_passes_the_output_guard_gives_no_medical_advice_and_names_a_doctor():
    assert check_output(messages.RED_FLAG_SYMPTOMS) is None
    assert "can't give medical advice" in messages.RED_FLAG_SYMPTOMS and "see a doctor" in messages.RED_FLAG_SYMPTOMS
    assert "diagnos" not in messages.RED_FLAG_SYMPTOMS.lower() and "should take" not in messages.RED_FLAG_SYMPTOMS.lower()


@pytest.mark.parametrize("text", ["I am light on protein today", "my heart is in this workout", "how many calories in a banana"])
def test_ordinary_sentences_are_not_caught(text):
    assert check_input(text) is None
