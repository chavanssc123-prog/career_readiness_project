"""JWT auth. Password hashing reuses utils.auth.hash_password / verify_password."""
from datetime import datetime, timedelta, timezone
from typing import Dict

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET
from database.db_utils import get_user_by_id

_bearer = HTTPBearer(auto_error=False)


def create_access_token(user: Dict) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user["id"]),
        "name": user.get("name"),
        "role": user.get("role", "user"),
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> Dict:
    """Equivalent of Streamlit's is_authenticated() + st.session_state.user_id."""
    if credentials is None or not credentials.credentials:
        raise _unauthorized("Please log in to continue.")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Your session has expired. Please log in again.")
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise _unauthorized("Invalid authentication token.")

    # Re-read the user so role changes / deleted users take effect immediately.
    user = get_user_by_id(user_id)
    if not user:
        raise _unauthorized("User no longer exists.")
    return user


def require_admin(user: Dict = Depends(get_current_user)) -> Dict:
    """Equivalent of Streamlit's is_admin() check."""
    if (user.get("role") or "user") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required. Please log in with an administrator account.",
        )
    return user
