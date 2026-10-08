/** 与 docs/接口字段表.md 第 2、3 节一致。 */

export type Category =
  | "earphones"
  | "campus_card"
  | "keys"
  | "bottle"
  | "book"
  | "clothing"
  | "electronics"
  | "umbrella"
  | "bag"
  | "other"
  | "unknown";

export type Color =
  | "black"
  | "white"
  | "gray"
  | "red"
  | "orange"
  | "yellow"
  | "green"
  | "blue"
  | "purple"
  | "pink"
  | "brown"
  | "multi"
  | "unknown";

export type PlaceCode =
  | "library"
  | "teaching_a"
  | "teaching_b"
  | "canteen_1"
  | "canteen_2"
  | "dorm"
  | "gym"
  | "admin_building";

export type DayPart = "morning" | "afternoon" | "evening";
export type ItemType = "lost" | "found";
export type ItemStatus = "draft" | "open" | "returned" | "closed";
export type Role = "user" | "admin";
export type JobStatus = "processing" | "succeeded" | "failed";
export type ClaimResult = "returned" | "not_found";

export type User = {
  id: string;
  student_no: string;
  nickname: string;
  role: Role;
};

export type StoredFile = {
  id: string;
  mime: string;
  created_at: string;
};

export type Item = {
  id: string;
  type: ItemType;
  status: ItemStatus;
  version: number;
  category: Category | null;
  color: Color | null;
  brand: string | null;
  description: string | null;
  occurred_on: string | null;
  day_part: DayPart | null;
  visited_places: PlaceCode[] | null;
  places_ordered: boolean | null;
  found_place: PlaceCode | null;
  place_note: string | null;
  subscribe_matches: boolean | null;
  image_id: string | null;
  tags: {
    key: "category" | "color";
    value: string;
    source: "user" | "model";
    confirmed: boolean;
  }[];
  job_id: string | null;
  expires_on: string | null;
  created_at: string;
  updated_at: string;
};

export type Job = {
  id: string;
  item_id: string;
  status: JobStatus;
  error_code: "timeout" | "no_model" | null;
  prompt_version: string;
};

export type MatchList = {
  item_id: string;
  matches: unknown[];
};

export type NotificationList = {
  unread_count: number;
  items: unknown[];
};

export type ReportList = {
  items: unknown[];
};

export type Claim = {
  id: string;
  lost_item_id: string;
  found_item_id: string;
  result: ClaimResult;
  created_at: string;
};

export type ItemCreate = {
  type: ItemType;
  request_id?: string;
  category?: Category | null;
  color?: Color | null;
  brand?: string | null;
  description?: string | null;
  occurred_on?: string | null;
  day_part?: DayPart | null;
  visited_places?: PlaceCode[] | null;
  places_ordered?: boolean | null;
  found_place?: PlaceCode | null;
  place_note?: string | null;
  subscribe_matches?: boolean | null;
  image_id?: string | null;
};

export type ItemPatch = {
  confirm_tags?: boolean;
  category?: Category | null;
  color?: Color | null;
  brand?: string | null;
  description?: string | null;
  occurred_on?: string | null;
  day_part?: DayPart | null;
  visited_places?: PlaceCode[] | null;
  places_ordered?: boolean | null;
  found_place?: PlaceCode | null;
  place_note?: string | null;
  subscribe_matches?: boolean | null;
  image_id?: string | null;
};
