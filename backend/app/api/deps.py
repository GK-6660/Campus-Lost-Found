"""从 Cookie 取当前用户。"""

from typing import Annotated

from fastapi import Cookie, Depends

from app.auth import current_user, require_admin
from app.errors import Unauthenticated
from app.schemas import User

SESSION_COOKIE = "clf_session"


def require_user(clf_session: Annotated[str | None, Cookie()] = None) -> User:
    if not clf_session:
        raise Unauthenticated()
    return current_user(clf_session)


def require_admin_user(user: Annotated[User, Depends(require_user)]) -> User:
    require_admin(user)
    return user
