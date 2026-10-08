"""识别任务路由。G 实现。"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import require_user
from app.extract import get_job
from app.schemas import Job, User

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}")
def get_job_route(job_id: str, user: Annotated[User, Depends(require_user)]) -> Job:
    return get_job(user, job_id)
