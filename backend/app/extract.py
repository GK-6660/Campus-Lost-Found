"""拾获图抽类别和颜色。G 实现。不调用 match。"""

from app.files import read_image
from app.schemas import Item, Job, User
from app.tags import write_model_tags

_CALLEES = (read_image, write_model_tags)


def enqueue(item: Item) -> Job:
    raise NotImplementedError(f"extract.enqueue item={item.id} calls={len(_CALLEES)}")


def run_extract(job_id: str) -> None:
    raise NotImplementedError(f"extract.run_extract job={job_id}")


def extract_labels(image_bytes: bytes) -> tuple[str | None, str | None]:
    raise NotImplementedError(f"extract.extract_labels bytes={len(image_bytes)}")


def get_job(viewer: User, job_id: str) -> Job:
    raise NotImplementedError(f"extract.get_job viewer={viewer.id} job={job_id}")
