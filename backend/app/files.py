"""保存浏览器导出的涂黑图，并在本模块内检查读取权限。

当前与 items.ITEMS 一样使用进程内表，重启后数据丢失。FILES 保存收到的
这一份字节，不生成或保留其他版本。MATCHES 是候选权限的临时读表，F 接入时
需与实际候选表共用；接入数据库后改为直接查询物品、文件和候选表，不调用 match。
服务端无法判断图片是否已经涂黑，这一步必须由浏览器在上传前完成。
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from app.errors import FieldError, NotFound, ValidationError
from app.schemas import Match, StoredFile, User

MAX_IMAGE_BYTES = 5 * 1024 * 1024
_ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp"}


@dataclass(frozen=True)
class _ImageRecord:
    metadata: StoredFile
    owner_id: str
    data: bytes


FILES: dict[str, _ImageRecord] = {}
MATCHES: dict[str, Match] = {}


def _image_mime(data: bytes) -> str:
    """识别实际文件头，不信任文件名或客户端声明的 Content-Type。"""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if (
        len(data) >= 20
        and data[:4] == b"RIFF"
        and data[8:12] == b"WEBP"
        and data[12:16] in (b"VP8 ", b"VP8L", b"VP8X")
        and int.from_bytes(data[4:8], "little") == len(data) - 8
    ):
        return "image/webp"
    raise ValidationError([FieldError("file", "invalid_file")], "只允许 JPEG、PNG、WebP 图片")


def _visible_in_candidates(file_id: str, viewer: User) -> bool:
    # 延迟导入物品读表以免 items -> files -> items 形成循环。不得调用匹配服务。
    from app.items import ITEMS

    today = datetime.now(timezone.utc).date().isoformat()
    for lost in ITEMS.values():
        if lost.owner_id != viewer.id or lost.type != "lost" or lost.status != "open":
            continue
        if lost.expires_on is not None and lost.expires_on < today:
            continue
        candidates = []
        for candidate in MATCHES.values():
            if candidate.lost_item_id != lost.id or candidate.score < 40:
                continue
            found = ITEMS.get(candidate.found_item_id)
            if (
                found is not None
                and found.type == "found"
                and found.status == "open"
                and found.owner_id != viewer.id
            ):
                candidates.append((candidate, found))
        candidates.sort(key=lambda row: row[0].score, reverse=True)
        if any(found.image_id == file_id for _, found in candidates[:5]):
            return True
    return False


def save_redacted_image(owner_id: str, data: bytes, mime: str) -> StoredFile:
    if not data or len(data) > MAX_IMAGE_BYTES or mime not in _ALLOWED_MIMES:
        raise ValidationError(
            [FieldError("file", "invalid_file")], "图片必须为 JPEG、PNG、WebP，且不超过 5MB"
        )
    actual_mime = _image_mime(data)
    if actual_mime != mime:
        raise ValidationError([FieldError("file", "invalid_file")], "图片类型与文件头不符")
    metadata = StoredFile(
        id=str(uuid4()),
        mime=actual_mime,
        created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    FILES[metadata.id] = _ImageRecord(metadata=metadata, owner_id=owner_id, data=data)
    return metadata.model_copy()


def read_image(file_id: str, viewer: User) -> bytes:
    record = FILES.get(file_id)
    if record is None:
        raise NotFound("没有这张图片")
    if (
        record.owner_id != viewer.id
        and viewer.role != "admin"
        and not _visible_in_candidates(file_id, viewer)
    ):
        raise NotFound("没有这张图片")
    return record.data


def get_own_file(file_id: str, owner_id: str) -> StoredFile:
    record = FILES.get(file_id)
    if record is None or record.owner_id != owner_id:
        raise NotFound("没有这张图片")
    return record.metadata.model_copy()
