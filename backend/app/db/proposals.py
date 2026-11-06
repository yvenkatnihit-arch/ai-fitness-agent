"""Plan proposals: the user reads their own (RLS); only the backend writes them (D-027)."""

from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

PROPOSAL_COLUMNS = "id, type, source, summary, status, payload, created_at"


def list_pending(conn: Connection, proposal_type: str | None = None) -> list[tuple]:
    """As the user: their pending proposals, newest first."""
    return conn.execute(
        f"""select {PROPOSAL_COLUMNS} from public.plan_proposals
            where status = 'pending' and (%s::text is null or type = %s)
            order by created_at desc""",
        (proposal_type, proposal_type),
    ).fetchall()


def recent_pending_workout(conn: Connection, split_key: str, within_seconds: int) -> tuple | None:
    """As the user: a pending workout proposal for this split made a moment ago (a double-tap must not call the LLM twice)."""
    return conn.execute(
        f"""select {PROPOSAL_COLUMNS} from public.plan_proposals
            where status = 'pending' and type = 'workout_change' and source = 'plan_generation'
              and payload ->> 'split_key' = %s and created_at > now() - make_interval(secs => %s)
            order by created_at desc limit 1""",
        (split_key, within_seconds),
    ).fetchone()


def replace_pending_workout(admin_conn: Connection, user_id: UUID, summary: str, payload: dict) -> tuple:
    """Admin: an older pending generated workout is no longer wanted (expired); save the new one as pending."""
    admin_conn.execute(
        """update public.plan_proposals set status = 'expired', decided_at = now()
           where user_id = %s and status = 'pending' and type = 'workout_change' and source = 'plan_generation'""",
        (user_id,),
    )
    return admin_conn.execute(
        f"""insert into public.plan_proposals (user_id, type, source, summary, payload)
            values (%s, 'workout_change', 'plan_generation', %s, %s)
            returning {PROPOSAL_COLUMNS}""",
        (user_id, summary, Jsonb(payload)),
    ).fetchone()
