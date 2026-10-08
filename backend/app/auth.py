"""账号。E 实现。"""

from app.schemas import User


def register(student_no: str, nickname: str, password: str) -> User:
    raise NotImplementedError(
        f"auth.register student_no={student_no} nickname={nickname} password_len={len(password)}"
    )


def login(student_no: str, password: str) -> User:
    raise NotImplementedError(f"auth.login student_no={student_no} password_len={len(password)}")


def logout(session_id: str) -> None:
    raise NotImplementedError(f"auth.logout session_id={session_id}")


def current_user(session_id: str) -> User:
    raise NotImplementedError(f"auth.current_user session_id={session_id}")


def require_admin(user: User) -> None:
    raise NotImplementedError(f"auth.require_admin user={user.id} role={user.role}")
