"""图片路由。E 实现。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Response, UploadFile

from app.api.deps import require_user
from app.files import MAX_IMAGE_BYTES, _image_mime, read_image, save_redacted_image
from app.idempotency import replay_if_done, save
from app.schemas import StoredFile, User

router = APIRouter(tags=["files"])


@router.post("/files", status_code=201)
async def post_files(
    file: UploadFile,
    request_id: Annotated[UUID, Form()],
    user: Annotated[User, Depends(require_user)],
) -> StoredFile:
    key = str(request_id)
    try:
        replay = replay_if_done(user.id, key)
        if replay is not None:
            return replay
        # 多读一个字节即可判定超限，避免把超大上传全部读入业务内存。
        saved = save_redacted_image(
            user.id, await file.read(MAX_IMAGE_BYTES + 1), file.content_type or ""
        )
        save(user.id, key, saved)
        return saved
    finally:
        await file.close()


@router.get("/files/{file_id}")
def get_file(file_id: str, user: Annotated[User, Depends(require_user)]) -> Response:
    data = read_image(file_id, user)
    return Response(content=data, media_type=_image_mime(data))
