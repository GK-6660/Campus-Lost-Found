"""图片路由。E 实现。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Response, UploadFile

from app.api.deps import require_user
from app.files import read_image, save_redacted_image
from app.idempotency import replay_if_done, save
from app.schemas import StoredFile, User

router = APIRouter(tags=["files"])


@router.post("/files", status_code=201)
async def post_files(
    file: UploadFile,
    request_id: Annotated[str, Form()],
    user: Annotated[User, Depends(require_user)],
) -> StoredFile:
    replay = replay_if_done(user.id, request_id)
    if replay is not None:
        return replay
    saved = save_redacted_image(user.id, await file.read(), file.content_type or "")
    save(user.id, request_id, saved)
    return saved


@router.get("/files/{file_id}")
def get_file(file_id: str, user: Annotated[User, Depends(require_user)]) -> Response:
    data = read_image(file_id, user)
    return Response(content=data, media_type="application/octet-stream")
