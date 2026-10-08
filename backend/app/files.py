"""涂黑后的图片。E 实现。不导入 match，权限判断在本文件里查记录。"""

from app.schemas import StoredFile, User


def save_redacted_image(owner_id: str, data: bytes, mime: str) -> StoredFile:
    raise NotImplementedError(
        f"files.save_redacted_image owner={owner_id} mime={mime} bytes={len(data)}"
    )


def read_image(file_id: str, viewer: User) -> bytes:
    raise NotImplementedError(f"files.read_image file={file_id} viewer={viewer.id}")


def get_own_file(file_id: str, owner_id: str) -> StoredFile:
    raise NotImplementedError(f"files.get_own_file file={file_id} owner={owner_id}")
