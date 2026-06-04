"""Supabase clients used by the tool modules.

Two flavors:
- get_client():           service-role key, bypasses RLS. Admin/seed use only.
- get_anon_client():      anon key, unauthenticated. Doorway for login.
- get_test_user_client(): anon client signed in as the .env test user.
                          Queries run as that user, so RLS applies.
"""
import os
from functools import lru_cache
from supabase import create_client, Client
from dotenv import load_dotenv

_pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_repo_root = os.path.dirname(_pkg_root)
load_dotenv(os.path.join(_repo_root, ".env"))


@lru_cache(maxsize=1)
def get_client() -> Client:
    """Service-role client. Bypasses RLS — use only for admin/seed scripts."""
    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url:
        raise ValueError("SUPABASE_URL is not set")
    if not service_key:
        raise ValueError("SUPABASE_SERVICE_KEY is not set")
    return create_client(url, service_key)


@lru_cache(maxsize=1)
def get_anon_client() -> Client:
    """Anon-key client (unauthenticated). RLS applies; sign in to act as a user."""
    url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    if not url:
        raise ValueError("SUPABASE_URL is not set")
    if not anon_key:
        raise ValueError("SUPABASE_ANON_KEY is not set")
    return create_client(url, anon_key)


@lru_cache(maxsize=1)
def get_test_user_client() -> Client:
    """Anon client signed in as the test user from .env.

    Dev shortcut: every request runs as this single hardcoded user. Real
    multi-user auth needs a per-request client built from the user's JWT.
    """
    url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    email = os.getenv("TEST_USER_EMAIL")
    password = os.getenv("TEST_USER_PASSWORD")
    if not url or not anon_key:
        raise ValueError("SUPABASE_URL / SUPABASE_ANON_KEY is not set")
    if not email:
        raise ValueError("TEST_USER_EMAIL is not set")
    if not password:
        raise ValueError("TEST_USER_PASSWORD is not set")

    # Own client, not the shared get_anon_client(), so signing in here
    # doesn't turn the cached anon client into an authenticated one.
    client = create_client(url, anon_key)
    client.auth.sign_in_with_password({"email": email, "password": password})
    return client
