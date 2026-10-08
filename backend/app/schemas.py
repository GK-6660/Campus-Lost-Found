"""资源形状，与 docs/软件设计说明书.md 第 5 节一致。这里不写业务。"""

from typing import Literal

from pydantic import BaseModel, Field

Category = Literal[
    "earphones",
    "campus_card",
    "keys",
    "bottle",
    "book",
    "clothing",
    "electronics",
    "umbrella",
    "bag",
    "other",
    "unknown",
]
Color = Literal[
    "black",
    "white",
    "gray",
    "red",
    "orange",
    "yellow",
    "green",
    "blue",
    "purple",
    "pink",
    "brown",
    "multi",
    "unknown",
]
PlaceCode = Literal[
    "library",
    "teaching_a",
    "teaching_b",
    "canteen_1",
    "canteen_2",
    "dorm",
    "gym",
    "admin_building",
]
DayPart = Literal["morning", "afternoon", "evening"]
ItemType = Literal["lost", "found"]
ItemStatus = Literal["draft", "open", "returned", "closed"]
Role = Literal["user", "admin"]
TagKey = Literal["category", "color"]
TagSource = Literal["user", "model"]
JobStatus = Literal["processing", "succeeded", "failed"]
JobErrorCode = Literal["timeout", "no_model"]
ClaimResult = Literal["returned", "not_found"]
NotificationType = Literal["new_match", "found_returned", "item_taken_down"]
ReportStatus = Literal["open", "closed"]
ReasonCode = Literal["category", "color", "place", "time", "brand", "keyword"]


class User(BaseModel):
    id: str
    student_no: str
    nickname: str
    role: Role


class StoredFile(BaseModel):
    """已上传的涂黑图。"""

    id: str
    mime: str
    created_at: str


class Tag(BaseModel):
    key: TagKey
    value: str
    source: TagSource
    confirmed: bool


class Item(BaseModel):
    id: str
    owner_id: str = Field(exclude=True)
    type: ItemType
    status: ItemStatus
    version: int
    category: Category | None
    color: Color | None
    brand: str | None
    description: str | None
    occurred_on: str | None
    day_part: DayPart | None
    visited_places: list[PlaceCode] | None
    places_ordered: bool | None
    found_place: PlaceCode | None
    place_note: str | None
    subscribe_matches: bool | None
    image_id: str | None
    tags: list[Tag]
    job_id: str | None
    expires_on: str | None
    created_at: str
    updated_at: str


class PublicItem(BaseModel):
    item_id: str
    type: ItemType
    category: Category | None
    color: Color | None
    place_code: PlaceCode | None
    place_note: str | None
    occurred_on: str | None
    day_part: DayPart | None
    image_id: str | None


class Reason(BaseModel):
    code: ReasonCode
    points: int
    text: str


class ScorePart(BaseModel):
    points: int
    text: str
    conflict: bool = False


class Score(BaseModel):
    score: int
    score_max: int = 100
    reasons: list[Reason]
    conflicts: list[Reason]
    hard_conflict: bool


class Match(BaseModel):
    id: str
    lost_item_id: str
    found_item_id: str
    score: int
    score_max: int = 100
    notify: bool
    reasons: list[Reason]
    conflicts: list[Reason]
    counterpart: PublicItem


class Claim(BaseModel):
    id: str
    lost_item_id: str
    found_item_id: str
    result: ClaimResult
    created_at: str


class Notification(BaseModel):
    id: str
    type: NotificationType
    read: bool
    lost_item_id: str | None
    found_item_id: str | None
    title: str
    body: str
    created_at: str


class Job(BaseModel):
    id: str
    item_id: str
    status: JobStatus
    error_code: JobErrorCode | None
    prompt_version: str


class Report(BaseModel):
    id: str
    item_id: str
    reason: str
    created_at: str
    status: ReportStatus


class RegisterBody(BaseModel):
    student_no: str = Field(min_length=1, max_length=32)
    nickname: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=8, max_length=64)
    request_id: str


class LoginBody(BaseModel):
    student_no: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=8, max_length=64)
    request_id: str


class ItemCreate(BaseModel):
    type: ItemType
    request_id: str
    category: Category | None = None
    color: Color | None = None
    brand: str | None = Field(default=None, max_length=40)
    description: str | None = Field(default=None, max_length=500)
    occurred_on: str | None = None
    day_part: DayPart | None = None
    visited_places: list[PlaceCode] | None = None
    places_ordered: bool | None = None
    found_place: PlaceCode | None = None
    place_note: str | None = Field(default=None, max_length=80)
    subscribe_matches: bool | None = None
    image_id: str | None = None


class ItemPatch(BaseModel):
    version: int
    request_id: str
    confirm_tags: bool = False
    category: Category | None = None
    color: Color | None = None
    brand: str | None = Field(default=None, max_length=40)
    description: str | None = Field(default=None, max_length=500)
    occurred_on: str | None = None
    day_part: DayPart | None = None
    visited_places: list[PlaceCode] | None = None
    places_ordered: bool | None = None
    found_place: PlaceCode | None = None
    place_note: str | None = Field(default=None, max_length=80)
    subscribe_matches: bool | None = None
    image_id: str | None = None


class VersionedWrite(BaseModel):
    version: int
    request_id: str


class ClaimCreate(BaseModel):
    lost_item_id: str
    found_item_id: str
    result: ClaimResult
    request_id: str


class ReportCreate(BaseModel):
    item_id: str
    reason: str = Field(min_length=1, max_length=200)
    request_id: str


class TakedownBody(BaseModel):
    version: int
    request_id: str
    reason: str = Field(min_length=1, max_length=200)


class ItemList(BaseModel):
    items: list[Item]


class MatchList(BaseModel):
    item_id: str
    matches: list[Match]


class NotificationList(BaseModel):
    unread_count: int
    items: list[Notification]


class ClaimList(BaseModel):
    items: list[Claim]


class ReportList(BaseModel):
    items: list[Report]
