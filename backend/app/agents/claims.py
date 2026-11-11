"""What a specialist that can PROPOSE a change is allowed to say (Step 8.5, D-109). Plain code, no model.

Found in a real run: the meal logger's tool calls failed, no proposal existed, and the model still said "I prepared a meal log, please confirm
it". A user could believe something was waiting for them. So the words about a proposal never come from the model alone:
- when a proposal WAS created, the reply is fixed text from here (it can never claim the meal is already saved);
- when none was created, an answer that CLAIMS one was prepared or saved is replaced by an honest fixed message.
A question the model asks (for example "which meal was that?") is left alone."""

import re

PREPARED = "I have prepared this for you. Please check it below and press Approve to save it, or Reject to cancel."
COULD_NOT_PREPARE = ("I could not prepare that one. Please tell me what you ate, how much and which meal, "
                     "for example: 2 rotis and a katori of dal for lunch.")
CLAIM = re.compile(r"\b(prepared|logged|saved|recorded|registered|added)\b|\bplease confirm\b|\bconfirm (it|this)\b", re.IGNORECASE)


def settle_answer(can_propose: bool, proposal_created: bool, answer: str | None) -> str | None:
    """The answer to show for a specialist run. Specialists that cannot propose anything are left exactly as they are."""
    if not can_propose or answer is None:
        return answer
    if proposal_created:
        return PREPARED
    if answer.strip().endswith("?"):
        return answer                      # a clarifying question, not a claim
    return COULD_NOT_PREPARE if CLAIM.search(answer) else answer
