"""Applying the user's decision on a proposal from the chat (Step 7.5, D-077).

This is a thin wrapper over the SAME workflow the proposal cards in the UI use (`decide_proposal`): the ownership check under RLS,
the re-verification of the plan and the single transaction are all there. Nothing here applies a change by itself.
"""

from collections.abc import Callable
from uuid import UUID

from app.workflows import decide_proposal as workflow

APPROVE, REJECT = "approve", "reject"
Decide = Callable[[UUID, UUID, str], str]   # (user, proposal, choice) -> a message to show the user


def decide_with_workflow(user_id: UUID, proposal_id: UUID, choice: str) -> str:
    try:
        if choice == APPROVE:
            workflow.approve(user_id, proposal_id)
            return "Done. I saved that change."
        if choice == REJECT:
            workflow.reject(user_id, proposal_id)
            return "No problem. I did not change anything."
    except workflow.ProposalNotFound:
        return "I could not find that proposal any more."
    except workflow.ProposalNotPending:
        return "That proposal was already decided or has expired."
    except workflow.ProposalCannotBeApplied as e:
        return str(e)
    return "I left that proposal waiting. You can approve or reject it on the plan screen."
