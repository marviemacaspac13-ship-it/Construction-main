"""Who is calling. Every route except /health needs a signed-in Supabase user.

The browser already holds a Supabase session, so it sends that session's
access token as `Authorization: Bearer <token>` and this module asks Supabase
whether it is genuine. Nothing here issues or stores credentials.

Until Sep 2026 every route was open (audit finding API-02): anyone who could
reach port 8000 could read the catalog, run scans and delete symbol crops,
signed in or not. The symbol library is still one shared library - a
signed-in user can change it for everyone - but a stranger no longer can.

Asking Supabase costs one network round trip per request. That is cheap next
to a scan, which takes seconds, and it means a revoked or signed-out session
stops working here at the same moment it stops working in the browser.
"""

from functools import lru_cache

from fastapi import Header, HTTPException
from supabase import Client
from supabase_auth.errors import AuthApiError, AuthInvalidJwtError, AuthSessionMissingError

from app.materials import _client

# The token was checked and is not a valid session: signed out, expired,
# forged, or from another project. A 401 tells the browser to sign in again.
_REJECTED = (AuthApiError, AuthInvalidJwtError, AuthSessionMissingError)


@lru_cache(maxsize=1)
def _auth_client() -> Client:
    return _client()


def current_user(authorization: str | None = Header(default=None)) -> str:
    """The Supabase user id behind the request, or a 401.

    Used as a FastAPI dependency. Tests replace it through
    `app.dependency_overrides`; see `tests/conftest.py`.
    """
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(401, "Sign in first - this request carried no session.")

    try:
        response = _auth_client().auth.get_user(token.strip())
    except _REJECTED:
        raise HTTPException(401, "Your session has expired or is not valid. Sign in again.")
    except Exception:
        # Supabase unreachable is not the caller's fault, and calling it a
        # 401 would sign a working user out for a network blip.
        raise HTTPException(503, "Could not reach Supabase to check your session. Try again.")

    if response is None or response.user is None:
        raise HTTPException(401, "Your session has expired or is not valid. Sign in again.")
    return response.user.id
