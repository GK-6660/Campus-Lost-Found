"""共用异常。组长维护，其他组只 raise。路由把它翻译成软件设计说明书里的错误 JSON。"""

from dataclasses import dataclass


class Unauthenticated(Exception):
    def __init__(self, message: str = "未登录") -> None:
        super().__init__(message)


class Forbidden(Exception):
    def __init__(self, message: str = "无权限") -> None:
        super().__init__(message)


class NotFound(Exception):
    def __init__(self, message: str = "没有这条记录") -> None:
        super().__init__(message)


class VersionConflict(Exception):
    def __init__(self, current_version: int) -> None:
        super().__init__("物品已被更新，请刷新")
        self.current_version = current_version


class FoundAlreadyReturned(Exception):
    def __init__(self, message: str = "这条拾获已经被人标记已找回") -> None:
        super().__init__(message)


class InvalidState(Exception):
    def __init__(self, message: str = "当前状态不允许这个操作") -> None:
        super().__init__(message)


@dataclass(frozen=True)
class FieldError:
    name: str
    code: str


class ValidationError(Exception):
    def __init__(self, fields: list[FieldError], message: str = "字段不合法") -> None:
        super().__init__(message)
        self.fields = fields
