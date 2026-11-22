/** B2：拾获登记。在浏览器里涂黑照片，只上传涂黑图，然后轮询识别进度。 */

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ChangeEvent, PointerEvent as ReactPointerEvent } from "react";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  ConfigProvider,
  Form,
  Input,
  Select,
  Space,
  Spin,
  Typography,
} from "antd";
import zhCN from "antd/locale/zh_CN";

import { ApiError, newRequestId, request } from "../api/client";
import { uploadFile } from "../api/files";
import { confirmTags, createItem, publishItem, updateItem } from "../api/items";
import { pollJob } from "../api/jobs";
import type {
  Category,
  Color,
  DayPart,
  Item,
  ItemCreate,
  ItemPatch,
  ItemStatus,
  JobStatus,
  PlaceCode,
} from "../api/types";
import { redactImage } from "../features/redact";
import type { Stroke } from "../features/redact";

type FoundFormValues = Pick<
  ItemPatch,
  | "category"
  | "color"
  | "brand"
  | "description"
  | "occurred_on"
  | "day_part"
  | "found_place"
  | "place_note"
>;
type DraftFields = Required<FoundFormValues>;
type Intent = "save" | "publish";
type Busy = Intent | "confirm" | "redact" | "upload" | "refresh" | null;
type Notice = { type: "success" | "error" | "warning"; text: string };
type Rect = { x: number; y: number; width: number; height: number };
type SourceImage = { file: File; url: string; width: number; height: number };
type RedactedImage = { blob: Blob; url: string };
type PendingWrite =
  | { kind: "create"; intent: Intent; request_id: string; payload: ItemCreate }
  | {
      kind: "update";
      intent: Intent;
      id: string;
      version: number;
      request_id: string;
      patch: ItemPatch;
    }
  | { kind: "publish"; intent: Intent; id: string; version: number; request_id: string }
  | {
      kind: "confirm";
      intent: "confirm";
      id: string;
      version: number;
      request_id: string;
      category: Category;
      color: Color;
    };
type Props = {
  /** 由父页面提供当前用户的已有拾获；切换记录时使用对应 id 作为组件 key。 */
  initialItem?: Item;
  /** 登录入口由集成页面决定，不在 B2 中约定路由。 */
  onLoginRequired?: () => void;
};

const categoryOptions: { label: string; value: Category }[] = [
  { label: "耳机", value: "earphones" },
  { label: "校园卡", value: "campus_card" },
  { label: "钥匙", value: "keys" },
  { label: "水杯", value: "bottle" },
  { label: "书", value: "book" },
  { label: "衣物", value: "clothing" },
  { label: "电子产品", value: "electronics" },
  { label: "伞", value: "umbrella" },
  { label: "包", value: "bag" },
  { label: "其他", value: "other" },
  { label: "未知", value: "unknown" },
];

const colorOptions: { label: string; value: Color }[] = [
  { label: "黑", value: "black" },
  { label: "白", value: "white" },
  { label: "灰", value: "gray" },
  { label: "红", value: "red" },
  { label: "橙", value: "orange" },
  { label: "黄", value: "yellow" },
  { label: "绿", value: "green" },
  { label: "蓝", value: "blue" },
  { label: "紫", value: "purple" },
  { label: "粉", value: "pink" },
  { label: "棕", value: "brown" },
  { label: "多色", value: "multi" },
  { label: "未知", value: "unknown" },
];

const dayPartOptions: { label: string; value: DayPart }[] = [
  { label: "上午", value: "morning" },
  { label: "下午", value: "afternoon" },
  { label: "晚上", value: "evening" },
];

const placeOptions: { label: string; value: PlaceCode }[] = [
  { label: "图书馆", value: "library" },
  { label: "教学楼 A", value: "teaching_a" },
  { label: "教学楼 B", value: "teaching_b" },
  { label: "一食堂", value: "canteen_1" },
  { label: "二食堂", value: "canteen_2" },
  { label: "宿舍区", value: "dorm" },
  { label: "体育馆", value: "gym" },
  { label: "行政楼", value: "admin_building" },
];

const fieldLabels: Record<keyof DraftFields, string> = {
  category: "类别",
  color: "颜色",
  brand: "品牌",
  description: "物品描述",
  occurred_on: "拾获日期",
  day_part: "拾获时段",
  found_place: "拾获地点",
  place_note: "补充位置",
};

const statusLabels: Record<ItemStatus, string> = {
  draft: "草稿",
  open: "已发布",
  returned: "已找回",
  closed: "已关闭",
};

const rejectionCodes = [
  "unauthenticated",
  "forbidden",
  "not_found",
  "version_conflict",
  "invalid_state",
  "validation_error",
  "found_already_returned",
];

const imageTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
const maxImageBytes = 5 * 1024 * 1024;

function isFieldName(name: string): name is keyof DraftFields {
  return Object.hasOwn(fieldLabels, name);
}

function toFields(values: FoundFormValues): DraftFields {
  return {
    category:
      values.category == null
        ? null
        : categoryOptions.some((option) => option.value === values.category)
          ? values.category
          : "unknown",
    color:
      values.color == null
        ? null
        : colorOptions.some((option) => option.value === values.color)
          ? values.color
          : "unknown",
    brand: values.brand?.trim() || null,
    description: values.description?.trim() || null,
    occurred_on: values.occurred_on || null,
    day_part: values.day_part ?? null,
    found_place: values.found_place ?? null,
    place_note: values.place_note?.trim() || null,
  };
}

function formValuesFrom(fields: DraftFields): FoundFormValues {
  return {
    category: fields.category ?? undefined,
    color: fields.color ?? undefined,
    brand: fields.brand ?? undefined,
    description: fields.description ?? undefined,
    occurred_on: fields.occurred_on ?? undefined,
    day_part: fields.day_part ?? undefined,
    found_place: fields.found_place ?? undefined,
    place_note: fields.place_note ?? undefined,
  };
}

function changesFrom(fields: DraftFields, item: Item): ItemPatch {
  const previous = toFields(item);
  return Object.fromEntries(
    Object.entries(fields).filter(
      ([key, value]) =>
        JSON.stringify(value) !== JSON.stringify(previous[key as keyof DraftFields]),
    ),
  ) as ItemPatch;
}

function isValidDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(value + "T00:00:00Z");
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

function publishErrors(fields: DraftFields) {
  const errors: { name: keyof DraftFields; errors: string[] }[] = [];
  if (!fields.occurred_on) {
    errors.push({ name: "occurred_on", errors: ["发布前请选择拾获日期"] });
  } else if (!isValidDate(fields.occurred_on)) {
    errors.push({ name: "occurred_on", errors: ["请选择有效日期，格式为 YYYY-MM-DD"] });
  }
  if (!fields.day_part) {
    errors.push({ name: "day_part", errors: ["发布前请选择拾获时段"] });
  }
  if (!fields.found_place) {
    errors.push({ name: "found_place", errors: ["发布前请选择拾获地点"] });
  }
  return errors;
}

function isFormError(error: unknown): boolean {
  return typeof error === "object" && error !== null && "errorFields" in error;
}

/** 类别和颜色都有且都已确认，才允许参与打分（5.5）。 */
function tagsConfirmed(item: Item): boolean {
  return (
    item.tags.some((tag) => tag.key === "category" && tag.confirmed) &&
    item.tags.some((tag) => tag.key === "color" && tag.confirmed)
  );
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export default function FoundFormPage({ initialItem, onLoginRequired }: Props) {
  const [form] = Form.useForm<FoundFormValues>();
  const [item, setItem] = useState<Item | null>(initialItem ?? null);
  const itemRef = useRef<Item | null>(initialItem ?? null);
  const [pending, setPending] = useState<PendingWrite | null>(null);
  const pendingRef = useRef<PendingWrite | null>(null);
  const [busy, setBusy] = useState<Busy>(null);
  const busyRef = useRef(false);
  const [needsRefresh, setNeedsRefresh] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [source, setSource] = useState<SourceImage | null>(null);
  const [redacted, setRedacted] = useState<RedactedImage | null>(null);
  const [imageId, setImageId] = useState<string | null>(initialItem?.image_id ?? null);
  const [strokes, setStrokes] = useState<Stroke[]>([]);
  const [draftRect, setDraftRect] = useState<Rect | null>(null);
  const [display, setDisplay] = useState({ width: 0, height: 0 });
  const [noSensitive, setNoSensitive] = useState(false);
  const [job, setJob] = useState<{
    status: JobStatus;
    errorCode: "timeout" | "no_model" | null;
  } | null>(null);

  const imageRef = useRef<HTMLImageElement | null>(null);
  const overlayRef = useRef<HTMLCanvasElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const dragStartRef = useRef<{ x: number; y: number } | null>(null);
  const sourceUrlRef = useRef<string | null>(null);
  const redactedUrlRef = useRef<string | null>(null);
  const mountedRef = useRef(true);

  const canEditDetails = item === null || (item.type === "found" && item.status === "draft");
  const wrongType = item !== null && item.type !== "found";
  const tagsEditable =
    item === null || (item.type === "found" && (item.status === "draft" || !tagsConfirmed(item)));
  const showConfirm = item !== null && item.status === "open" && !tagsConfirmed(item);
  const actionsDisabled = busy !== null || pending !== null || needsRefresh;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    const image = imageRef.current;
    if (!image || !source) return;
    const measure = () => setDisplay({ width: image.clientWidth, height: image.clientHeight });
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(image);
    return () => observer.disconnect();
  }, [source]);

  useLayoutEffect(() => {
    const canvas = overlayRef.current;
    if (!canvas || !source || source.width <= 0 || display.width <= 0) return;
    canvas.width = Math.round(display.width);
    canvas.height = Math.round(display.height);
    const context = canvas.getContext("2d");
    if (!context) return;
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = "#000000";
    const scaleX = canvas.width / source.width;
    const scaleY = canvas.height / source.height;
    for (const stroke of strokes) {
      context.fillRect(
        stroke.x * scaleX,
        stroke.y * scaleY,
        stroke.width * scaleX,
        stroke.height * scaleY,
      );
    }
    if (draftRect) {
      context.fillRect(draftRect.x, draftRect.y, draftRect.width, draftRect.height);
    }
  }, [display, draftRect, source, strokes]);

  function revokeUrl(urlRef: { current: string | null }) {
    if (urlRef.current !== null) {
      URL.revokeObjectURL(urlRef.current);
      urlRef.current = null;
    }
  }

  function rememberPending(value: PendingWrite | null) {
    pendingRef.current = value;
    setPending(value);
  }

  function rememberItem(value: Item) {
    itemRef.current = value;
    setItem(value);
  }

  function handleError(error: unknown) {
    if (isFormError(error)) {
      setNotice({ type: "error", text: "请检查表单中标出的字段。" });
      return;
    }
    const rejected =
      error instanceof ApiError && error.status < 500 && rejectionCodes.includes(error.code);
    if (pendingRef.current !== null && !rejected) {
      setNotice({ type: "warning", text: "提交结果尚未确认，请点击“重试上次提交”。" });
      return;
    }
    if (!(error instanceof ApiError)) {
      setNotice({
        type: "error",
        text: error instanceof Error && error.message ? error.message : "操作失败，请稍后再试。",
      });
      return;
    }

    rememberPending(null);
    if (error.code === "version_conflict" || error.code === "invalid_state") {
      setNeedsRefresh(true);
      setNotice({
        type: "warning",
        text: "物品已被更新，请载入最新记录并核对后再操作。",
      });
      return;
    }
    if (error.code === "validation_error") {
      const fieldErrors = new Map<keyof DraftFields, string[]>();
      for (const field of error.fields ?? []) {
        const name = field.name.split(".")[0];
        if (!isFieldName(name)) continue;
        const label = fieldLabels[name];
        const text =
          field.code === "required"
            ? label + "不能为空"
            : field.code === "too_long"
              ? label + "超过允许的长度或数量"
              : label + "的内容不合法";
        fieldErrors.set(name, [...(fieldErrors.get(name) ?? []), text]);
      }
      form.setFields([...fieldErrors].map(([name, errors]) => ({ name, errors })));
      setNotice({ type: "error", text: "提交字段不符合要求，请检查并修改。" });
      return;
    }
    if (error.code === "unauthenticated") {
      setNotice({ type: "error", text: "请先登录，再继续操作。" });
      onLoginRequired?.();
      return;
    }
    const errorText: Record<string, string> = {
      forbidden: "没有权限进行此操作。",
      not_found: "未找到该物品。",
      found_already_returned: "该拾获物品已归还。",
    };
    setNotice({ type: "error", text: errorText[error.code] ?? "请求失败，请稍后再试。" });
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    event.target.value = "";
    if (!file || !canEditDetails) return;
    if (!imageTypes.has(file.type)) {
      setNotice({ type: "error", text: "只支持 JPEG、PNG 或 WebP 图片。" });
      return;
    }
    if (file.size > maxImageBytes) {
      setNotice({ type: "error", text: "图片不能超过 5MB。" });
      return;
    }
    // 换图时丢弃旧的原始图和旧的涂黑结果，避免误上传。
    revokeUrl(sourceUrlRef);
    revokeUrl(redactedUrlRef);
    const url = URL.createObjectURL(file);
    sourceUrlRef.current = url;
    setSource({ file, url, width: 0, height: 0 });
    setRedacted(null);
    setStrokes([]);
    setDraftRect(null);
    setNoSensitive(false);
    setJob(null);
    setNotice(null);
  }

  function pointerPosition(event: ReactPointerEvent<HTMLCanvasElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    return {
      x: clamp(event.clientX - rect.left, 0, rect.width),
      y: clamp(event.clientY - rect.top, 0, rect.height),
      width: rect.width,
      height: rect.height,
    };
  }

  function handlePointerDown(event: ReactPointerEvent<HTMLCanvasElement>) {
    if (!source || busy !== null || !canEditDetails) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const point = pointerPosition(event);
    dragStartRef.current = { x: point.x, y: point.y };
    setDraftRect({ x: point.x, y: point.y, width: 0, height: 0 });
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLCanvasElement>) {
    const start = dragStartRef.current;
    if (!start) return;
    const point = pointerPosition(event);
    setDraftRect({
      x: Math.min(start.x, point.x),
      y: Math.min(start.y, point.y),
      width: Math.abs(point.x - start.x),
      height: Math.abs(point.y - start.y),
    });
  }

  function handlePointerUp(event: ReactPointerEvent<HTMLCanvasElement>) {
    const start = dragStartRef.current;
    dragStartRef.current = null;
    setDraftRect(null);
    if (!start || !source || source.width <= 0) return;
    const point = pointerPosition(event);
    const rect: Rect = {
      x: Math.min(start.x, point.x),
      y: Math.min(start.y, point.y),
      width: Math.abs(point.x - start.x),
      height: Math.abs(point.y - start.y),
    };
    // 屏幕坐标换算为原图像素后再保存（5.13）。
    if (rect.width < 4 || rect.height < 4 || point.width <= 0 || point.height <= 0) return;
    const scaleX = source.width / point.width;
    const scaleY = source.height / point.height;
    const x = clamp(Math.round(rect.x * scaleX), 0, source.width - 1);
    const y = clamp(Math.round(rect.y * scaleY), 0, source.height - 1);
    setStrokes((previous) => [
      ...previous,
      {
        x,
        y,
        width: Math.max(1, Math.min(source.width - x, Math.round(rect.width * scaleX))),
        height: Math.max(1, Math.min(source.height - y, Math.round(rect.height * scaleY))),
      },
    ]);
  }

  function handlePointerCancel() {
    dragStartRef.current = null;
    setDraftRect(null);
  }

  async function redactAndUpload() {
    if (!source || busyRef.current || !canEditDetails) return;
    if (strokes.length === 0 && !noSensitive) {
      setNotice({
        type: "warning",
        text: "请先在照片上拖动鼠标，涂黑姓名、学号等敏感信息。",
      });
      return;
    }
    busyRef.current = true;
    setBusy("redact");
    setNotice(null);
    try {
      // 按原图像素导出；导出后原图立即丢弃，只保留涂黑图。
      const blob = await redactImage(source.file, strokes);
      revokeUrl(sourceUrlRef);
      setSource(null);
      setStrokes([]);
      setDraftRect(null);
      setNoSensitive(false);
      revokeUrl(redactedUrlRef);
      const url = URL.createObjectURL(blob);
      redactedUrlRef.current = url;
      setRedacted({ blob, url });

      setBusy("upload");
      const id = await uploadFile(blob);
      if (!mountedRef.current) return;
      setImageId(id);
      setNotice({ type: "success", text: "涂黑图已上传，请继续填写拾获信息。" });
    } catch (error) {
      handleError(error);
    } finally {
      busyRef.current = false;
      setBusy(null);
    }
  }

  async function retryUpload() {
    if (!redacted || busyRef.current) return;
    busyRef.current = true;
    setBusy("upload");
    setNotice(null);
    try {
      const id = await uploadFile(redacted.blob);
      if (!mountedRef.current) return;
      setImageId(id);
      setNotice({ type: "success", text: "涂黑图已上传，请继续填写拾获信息。" });
    } catch (error) {
      handleError(error);
    } finally {
      busyRef.current = false;
      setBusy(null);
    }
  }

  function buildPayload(fields: DraftFields): ItemCreate {
    return {
      type: "found",
      request_id: newRequestId(),
      category: fields.category,
      color: fields.color,
      brand: fields.brand,
      description: fields.description,
      occurred_on: fields.occurred_on,
      day_part: fields.day_part,
      found_place: fields.found_place,
      place_note: fields.place_note,
      image_id: imageId,
      // 拾获没有路线和订阅字段（5.5）。
      visited_places: null,
      places_ordered: null,
      subscribe_matches: null,
    };
  }

  async function sendPending(): Promise<Item> {
    const operation = pendingRef.current;
    if (operation === null) throw new Error("没有待提交的操作。");
    let result: Item;
    if (operation.kind === "create") {
      result = await createItem(operation.payload);
    } else if (operation.kind === "update") {
      result = await updateItem(
        operation.id,
        operation.version,
        operation.patch,
        operation.request_id,
      );
    } else if (operation.kind === "publish") {
      result = await publishItem(operation.id, operation.version, operation.request_id);
    } else {
      result = await confirmTags(
        operation.id,
        operation.version,
        operation.category,
        operation.color,
        operation.request_id,
      );
    }
    rememberItem(result);
    rememberPending(null);
    return result;
  }

  async function runJob(record: Item) {
    if (record.job_id === null) return;
    setJob({ status: "processing", errorCode: null });
    try {
      const result = await pollJob(record.job_id);
      if (!mountedRef.current) return;
      setJob({ status: result.status, errorCode: result.error_code });
      if (result.status !== "succeeded") return;
      try {
        const latest = await request<Item>("/items/" + encodeURIComponent(record.id));
        if (!mountedRef.current) return;
        rememberItem(latest);
        form.setFieldsValue(formValuesFrom(toFields(latest)));
      } catch (error) {
        handleError(error);
      }
    } catch (error) {
      if (mountedRef.current) handleError(error);
    }
  }

  async function submit(intent: Intent, retry = false) {
    if (busyRef.current || needsRefresh) return;
    if (!retry && pendingRef.current !== null) return;
    if (retry && pendingRef.current === null) return;
    const current = itemRef.current;
    if (!retry && current !== null && (current.type !== "found" || current.status !== "draft"))
      return;

    busyRef.current = true;
    setBusy(intent);
    setNotice(null);
    try {
      let record = current;
      if (!retry) {
        const values = await form.validateFields();
        const fields = toFields(values);
        if (intent === "publish") {
          const errors = publishErrors(fields);
          if (errors.length) {
            form.setFields(errors);
            form.scrollToField(errors[0].name);
            setNotice({
              type: "error",
              text: "发布前请填写拾获日期、时段和拾获地点。",
            });
            return;
          }
        }
        if (record === null) {
          rememberPending({
            kind: "create",
            intent,
            request_id: newRequestId(),
            payload: buildPayload(fields),
          });
        } else {
          const patch = changesFrom(fields, record);
          if ((imageId ?? null) !== (record.image_id ?? null)) {
            patch.image_id = imageId;
          }
          if (Object.keys(patch).length) {
            rememberPending({
              kind: "update",
              intent,
              id: record.id,
              version: record.version,
              request_id: newRequestId(),
              patch,
            });
          }
        }
      }
      if (pendingRef.current !== null) record = await sendPending();
      if (record === null) throw new Error("尚未保存草稿。");

      if (intent === "publish" && record.status !== "open") {
        if (record.status !== "draft") throw new Error("当前状态不能发布。");
        const errors = publishErrors(toFields(record));
        if (errors.length) {
          form.setFields(errors);
          setNotice({ type: "error", text: "草稿已保存，但发布所需的信息尚未完整。" });
          return;
        }
        rememberPending({
          kind: "publish",
          intent,
          id: record.id,
          version: record.version,
          request_id: newRequestId(),
        });
        record = await sendPending();
      }
      setNotice({
        type: "success",
        text: intent === "publish" ? "拾获信息已发布。" : "草稿已保存。",
      });
      if (intent === "publish" && record.job_id !== null) {
        void runJob(record);
      }
    } catch (error) {
      handleError(error);
    } finally {
      busyRef.current = false;
      setBusy(null);
    }
  }

  async function submitConfirm(retry = false) {
    if (busyRef.current || needsRefresh) return;
    const record = itemRef.current;
    if (record === null) return;
    if (!retry && pendingRef.current !== null) return;
    if (retry && pendingRef.current === null) return;

    busyRef.current = true;
    setBusy("confirm");
    setNotice(null);
    try {
      if (!retry) {
        const values = await form.validateFields(["category", "color"]);
        const category = values.category;
        const color = values.color;
        if (!category || !color) {
          setNotice({ type: "error", text: "请先选择类别和颜色，再确认。" });
          return;
        }
        rememberPending({
          kind: "confirm",
          intent: "confirm",
          id: record.id,
          version: record.version,
          request_id: newRequestId(),
          category,
          color,
        });
      }
      await sendPending();
      // 确认后清除识别失败的提示，避免与“已确认”状态矛盾。
      setJob(null);
      setNotice({ type: "success", text: "类别和颜色已确认，系统开始匹配。" });
    } catch (error) {
      handleError(error);
    } finally {
      busyRef.current = false;
      setBusy(null);
    }
  }

  async function refreshItem() {
    if (busyRef.current || pendingRef.current !== null || itemRef.current === null) return;
    busyRef.current = true;
    setBusy("refresh");
    try {
      const latest = await request<Item>("/items/" + encodeURIComponent(itemRef.current.id));
      rememberItem(latest);
      form.setFieldsValue(formValuesFrom(toFields(latest)));
      setImageId(latest.image_id ?? null);
      setNeedsRefresh(false);
      setNotice({ type: "success", text: "已载入最新记录，请核对后再操作。" });
    } catch (error) {
      handleError(error);
    } finally {
      busyRef.current = false;
      setBusy(null);
    }
  }

  const jobAlert =
    job === null
      ? null
      : job.status === "processing"
        ? { type: "info" as const, text: "正在识别类别和颜色，请稍候…" }
        : job.status === "succeeded"
          ? { type: "success" as const, text: "识别完成，请核对类别和颜色后点击确认。" }
          : {
              type: "warning" as const,
              text:
                job.errorCode === "timeout"
                  ? "识别超时，请手动填写类别和颜色后点击确认。"
                  : "当前没有可用的识别模型，请手动填写类别和颜色后点击确认。",
            };

  return (
    <ConfigProvider locale={zhCN}>
      <section style={{ maxWidth: 720, margin: "0 auto" }}>
        <Typography.Title level={2}>拾获登记</Typography.Title>
        {item !== null && (
          <Typography.Paragraph>当前状态：{statusLabels[item.status]}</Typography.Paragraph>
        )}
        {wrongType && (
          <Alert
            type="error"
            showIcon
            message="此页面用于拾获登记，请打开对应的失物页面。"
            style={{ marginBottom: 16 }}
          />
        )}
        {notice !== null && (
          <Alert type={notice.type} showIcon message={notice.text} style={{ marginBottom: 16 }} />
        )}

        <Card title="第一步：拍照并涂黑" style={{ marginBottom: 16 }}>
          <Alert
            type="warning"
            showIcon
            message="涂黑前请遮挡姓名、学号、独特图案、码数和序列号（校园卡、书、衣物、电子产品尤其注意）。原图不会上传，导出涂黑图后会立即从页面丢弃。"
            style={{ marginBottom: 16 }}
          />
          <Space wrap>
            <Button
              htmlType="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={!canEditDetails || actionsDisabled}
            >
              选择照片
            </Button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              hidden
              onChange={handleFileChange}
            />
            {source !== null && (
              <>
                <Button
                  htmlType="button"
                  onClick={() => setStrokes((previous) => previous.slice(0, -1))}
                  disabled={strokes.length === 0 || actionsDisabled}
                >
                  撤销上一笔
                </Button>
                <Button
                  htmlType="button"
                  onClick={() => setStrokes([])}
                  disabled={strokes.length === 0 || actionsDisabled}
                >
                  清空涂黑
                </Button>
              </>
            )}
          </Space>

          {source !== null && (
            <>
              <div
                style={{
                  position: "relative",
                  maxWidth: 560,
                  marginTop: 16,
                  touchAction: "none",
                  userSelect: "none",
                }}
              >
                <img
                  ref={imageRef}
                  src={source.url}
                  alt="待涂黑的拾获照片"
                  draggable={false}
                  style={{ display: "block", width: "100%" }}
                  onLoad={(event) => {
                    const image = event.currentTarget;
                    setSource((previous) =>
                      previous === null
                        ? previous
                        : { ...previous, width: image.naturalWidth, height: image.naturalHeight },
                    );
                  }}
                />
                <canvas
                  ref={overlayRef}
                  aria-label="涂黑区域"
                  style={{
                    position: "absolute",
                    inset: 0,
                    width: "100%",
                    height: "100%",
                    cursor: "crosshair",
                  }}
                  onPointerDown={handlePointerDown}
                  onPointerMove={handlePointerMove}
                  onPointerUp={handlePointerUp}
                  onPointerCancel={handlePointerCancel}
                />
              </div>
              <div style={{ marginTop: 8 }}>
                <Typography.Text type="secondary">
                  在照片上按住并拖动，画出需要涂黑的矩形。可连续画多块。
                </Typography.Text>
              </div>
              <Checkbox
                checked={noSensitive}
                disabled={actionsDisabled}
                onChange={(event) => setNoSensitive(event.target.checked)}
                style={{ marginTop: 8 }}
              >
                照片不含需要遮挡的敏感信息
              </Checkbox>
              <div style={{ marginTop: 12 }}>
                <Button
                  type="primary"
                  htmlType="button"
                  onClick={() => void redactAndUpload()}
                  loading={busy === "redact" || busy === "upload"}
                  disabled={actionsDisabled || (strokes.length === 0 && !noSensitive)}
                >
                  涂黑并上传
                </Button>
              </div>
            </>
          )}

          {redacted !== null && (
            <div style={{ marginTop: 16 }}>
              <Typography.Text type="secondary">
                涂黑图预览（只有这张会上传，原图已丢弃）
              </Typography.Text>
              <img
                src={redacted.url}
                alt="涂黑后的拾获照片"
                style={{ display: "block", maxWidth: "100%", marginTop: 8 }}
              />
              <Space style={{ marginTop: 8 }} wrap>
                <a href={redacted.url} download="redacted-image">
                  下载涂黑图
                </a>
                {imageId === null && (
                  <Button
                    htmlType="button"
                    onClick={() => void retryUpload()}
                    loading={busy === "upload"}
                    disabled={actionsDisabled}
                  >
                    重新上传
                  </Button>
                )}
              </Space>
            </div>
          )}

          {imageId !== null && (
            <Typography.Paragraph type="success" style={{ marginTop: 8 }}>
              涂黑图已上传。
            </Typography.Paragraph>
          )}
        </Card>

        <Card title="第二步：填写拾获信息" style={{ marginBottom: 16 }}>
          <Form
            form={form}
            layout="vertical"
            initialValues={formValuesFrom(toFields(initialItem ?? {}))}
            onValuesChange={(changed: FoundFormValues) => {
              setNotice(null);
              form.setFields(
                Object.keys(changed)
                  .filter(isFieldName)
                  .map((name) => ({ name, errors: [] })),
              );
            }}
          >
            <Form.Item name="category" label="类别">
              <Select<Category>
                options={categoryOptions}
                placeholder="可稍后手填"
                allowClear
                disabled={!tagsEditable || wrongType}
              />
            </Form.Item>
            <Form.Item name="color" label="颜色">
              <Select<Color>
                options={colorOptions}
                placeholder="可稍后手填"
                allowClear
                disabled={!tagsEditable || wrongType}
              />
            </Form.Item>
            <Form.Item
              name="occurred_on"
              label="拾获日期"
              rules={[
                {
                  validator: (_, value: string | null | undefined) =>
                    !value || isValidDate(value)
                      ? Promise.resolve()
                      : Promise.reject(new Error("请选择有效日期，格式为 YYYY-MM-DD")),
                },
              ]}
            >
              <Input type="date" disabled={!canEditDetails || wrongType} />
            </Form.Item>
            <Form.Item
              name="day_part"
              label="拾获时段"
              rules={[
                {
                  type: "enum",
                  enum: dayPartOptions.map((option) => option.value),
                  message: "请选择有效时段",
                },
              ]}
            >
              <Select<DayPart>
                options={dayPartOptions}
                placeholder="请选择时段"
                allowClear
                disabled={!canEditDetails || wrongType}
              />
            </Form.Item>
            <Form.Item name="found_place" label="拾获地点">
              <Select<PlaceCode>
                options={placeOptions}
                placeholder="请选择拍照所在的一栋楼"
                allowClear
                disabled={!canEditDetails || wrongType}
              />
            </Form.Item>
            <Form.Item
              name="place_note"
              label="补充位置（可选）"
              rules={[{ max: 80, message: "补充位置最多填写 80 个字符" }]}
            >
              <Input
                placeholder="例如：二楼靠窗"
                maxLength={80}
                showCount
                disabled={!canEditDetails || wrongType}
              />
            </Form.Item>
            <Form.Item
              name="brand"
              label="品牌（可选）"
              rules={[{ max: 40, message: "品牌最多填写 40 个字符" }]}
            >
              <Input
                placeholder="例如物品的品牌名称"
                maxLength={40}
                showCount
                disabled={!canEditDetails || wrongType}
              />
            </Form.Item>
            <Form.Item
              name="description"
              label="物品描述（可选）"
              rules={[{ max: 500, message: "物品描述最多填写 500 个字符" }]}
            >
              <Input.TextArea
                placeholder="补充物品的外观等信息"
                rows={3}
                maxLength={500}
                showCount
                disabled={!canEditDetails || wrongType}
              />
            </Form.Item>
          </Form>
        </Card>

        {jobAlert !== null && (
          <Alert
            type={jobAlert.type}
            showIcon
            icon={job?.status === "processing" ? <Spin size="small" /> : undefined}
            message={jobAlert.text}
            style={{ marginBottom: 16 }}
          />
        )}

        <Space wrap>
          {canEditDetails && (
            <>
              <Button
                htmlType="button"
                onClick={() => void submit("save")}
                loading={busy === "save"}
                disabled={actionsDisabled || wrongType}
              >
                保存草稿
              </Button>
              <Button
                type="primary"
                htmlType="button"
                onClick={() => void submit("publish")}
                loading={busy === "publish"}
                disabled={actionsDisabled || wrongType}
              >
                发布
              </Button>
            </>
          )}
          {showConfirm && (
            <Button
              type="primary"
              htmlType="button"
              onClick={() => void submitConfirm()}
              loading={busy === "confirm"}
              disabled={actionsDisabled || job?.status === "processing"}
            >
              确认类别和颜色
            </Button>
          )}
          {pending !== null && (
            <Button
              htmlType="button"
              onClick={() =>
                void (pending.kind === "confirm"
                  ? submitConfirm(true)
                  : submit(pending.intent, true))
              }
              disabled={busy !== null}
            >
              重试上次提交
            </Button>
          )}
          {needsRefresh && (
            <Button
              htmlType="button"
              onClick={() => void refreshItem()}
              loading={busy === "refresh"}
              disabled={busy !== null}
            >
              刷新并载入服务器内容
            </Button>
          )}
        </Space>
      </section>
    </ConfigProvider>
  );
}
