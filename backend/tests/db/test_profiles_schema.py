import pytest

pytestmark = pytest.mark.db


def test_profiles_table_exists_with_rls_enabled(admin_conn):
    row = admin_conn.execute(
        "select relrowsecurity from pg_class where oid = 'public.profiles'::regclass"
    ).fetchone()
    assert row == (True,)


def test_profiles_policies(admin_conn):
    rows = admin_conn.execute(
        "select policyname, cmd from pg_policies where schemaname = 'public' and tablename = 'profiles'"
    ).fetchall()
    assert set(rows) == {
        ("profiles_select_own", "SELECT"),
        ("profiles_insert_own", "INSERT"),
        ("profiles_update_own", "UPDATE"),
    }  # no DELETE policy on purpose


def test_signed_out_visitors_have_no_access(admin_conn):
    row = admin_conn.execute(
        "select has_table_privilege('anon', 'public.profiles', 'select'),"
        "       has_table_privilege('anon', 'public.profiles', 'insert')"
    ).fetchone()
    assert row == (False, False)


def test_updated_at_trigger_exists(admin_conn):
    row = admin_conn.execute(
        "select count(*) from pg_trigger where tgrelid = 'public.profiles'::regclass"
        " and tgname = 'profiles_set_updated_at'"
    ).fetchone()
    assert row == (1,)


def test_migration_is_recorded(admin_conn):
    row = admin_conn.execute(
        "select count(*) from supabase_migrations.schema_migrations where version = '20261105120000'"
    ).fetchone()
    assert row == (1,)
