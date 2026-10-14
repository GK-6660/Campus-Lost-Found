import { useRef, useState } from "react";
import { Alert, Button, Checkbox, Form, Input, Select, Space } from "antd";
import { ApiError, newRequestId, request } from "../api/client";
import { createItem, publishItem, updateItem } from "../api/items";
import type {
  Category,
  Color,
  DayPart,
  Item,
  ItemCreate,
  ItemPatch,
  PlaceCode,
} from "../api/types";

type LostFormValues = Pick<
  ItemPatch,
  | "category"
  | "color"
  | "brand"
  | "description"
  | "occurred_on"
  | "day_part"
  | "visited_places"
  | "places_ordered"
  | "subscribe_matches"
>;
type DraftFields = Required<LostFormValues>;
type Intent = "save" | "publish";
type PendingWrite =
  | { kind: "create"; intent: Intent; payload: ItemCreate }
  | {
      kind: "update";
      intent: Intent;
      id: string;
      version: number;
      request_id: string;
      patch: ItemPatch;
    }
  | {
      kind: "publish";
      intent: "publish";
      id: string;
      version: number;
      request_id: string;
    };
type Notice = { type: "success" | "error" | "warning"; text: string };
type Props = {
  /** 由父页面提供当前用户的已有失物；切换记录时使用对应 id 作为组件 key。 */
  initialItem?: Item;
  /** 登录入口由集成页面决定，不在 B1 中约定路由。 */
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
  occurred_on: "丢失日期",
  day_part: "丢失时段",
  visited_places: "去过的楼",
  places_ordered: "楼栋顺序设置",
  subscribe_matches: "通知设置",
};

function isFieldName(name: string): name is keyof DraftFields {
  return Object.hasOwn(fieldLabels, name);
}

function toFields(values: LostFormValues): DraftFields {
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
    visited_places: values.visited_places?.length ? [...values.visited_places] : null,
    places_ordered: values.places_ordered ?? true,
    subscribe_matches: values.subscribe_matches ?? true,
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
  if (!fields.category) errors.push({ name: "category", errors: ["发布前请选择物品类别"] });
  if (!fields.occurred_on) errors.push({ name: "occurred_on", errors: ["发布前请选择丢失日期"] });
  if (!fields.day_part) errors.push({ name: "day_part", errors: ["发布前请选择丢失时段"] });
  if (!fields.visited_places?.length) {
    errors.push({
      name: "visited_places",
      errors: ["发布前请至少选择一栋去过的楼"],
    });
  }
  return errors;
}

function isFormError(error: unknown): boolean {
  return typeof error === "object" && error !== null && "errorFields" in error;
}

const rejectionCodes = [
  "unauthenticated",
  "forbidden",
  "not_found",
  "version_conflict",
  "invalid_state",
  "validation_error",
  "found_already_returned",
];

export default function LostFormPage({ initialItem, onLoginRequired }: Props) {
  const [form] = Form.useForm<LostFormValues>();
  const [item, setItem] = useState<Item | null>(initialItem ?? null);
  const itemRef = useRef<Item | null>(initialItem ?? null);
  const [pending, setPending] = useState<PendingWrite | null>(null);
  const pendingRef = useRef<PendingWrite | null>(null);
  const [busy, setBusy] = useState<Intent | "refresh" | null>(null);
  const busyRef = useRef(false);
  const [needsRefresh, setNeedsRefresh] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const editable = item === null || (item.type === "lost" && item.status === "draft");

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
      setNotice({
        type: "warning",
        text: "提交结果尚未确认，请点击“重试上次提交”。",
      });
      return;
    }
    if (!(error instanceof ApiError)) {
      setNotice({
        type: "error",
        text: error instanceof Error ? error.message : "操作失败，请稍后再试。",
      });
      return;
    }

    rememberPending(null);
    if (error.code === "version_conflict" || error.code === "invalid_state") {
      setNeedsRefresh(true);
      setNotice({
        type: "warning",
        text: "物品已被更新，请载入最新记录并核对后再操作。刷新会替换当前填写内容。",
      });
      return;
    }
    if (error.code === "validation_error") {
      const fieldErrors = new Map<keyof DraftFields, string[]>();
      for (const field of error.fields ?? []) {
        const name = field.name.split(".")[0];
        if (!isFieldName(name)) continue;
        const label = fieldLabels[name as keyof DraftFields];
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
    setNotice({ type: "error", text: error.message });
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
    } else {
      result = await publishItem(operation.id, operation.version, operation.request_id);
    }
    rememberItem(result);
    rememberPending(null);
    return result;
  }

  async function submit(intent: Intent, retry = false) {
    if (busyRef.current || needsRefresh) return;
    if (pendingRef.current !== null && !retry) return;
    if (retry && pendingRef.current === null) return;
    const current = itemRef.current;
    if (!retry && current !== null && (current.type !== "lost" || current.status !== "draft"))
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
              text: "发布前请选择物品类别，并填写丢失日期、时段和至少一栋去过的楼。",
            });
            return;
          }
        }
        if (record === null) {
          rememberPending({
            kind: "create",
            intent,
            payload: {
              ...fields,
              type: "lost",
              request_id: newRequestId(),
              found_place: null,
              place_note: null,
              image_id: null,
            },
          });
        } else {
          const patch = changesFrom(fields, record);
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
          setNotice({
            type: "error",
            text: "草稿已保存，但发布所需的信息尚未完整。",
          });
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
        text: intent === "publish" ? "失物已发布。" : "草稿已保存。",
      });
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
      form.setFieldsValue({
        ...toFields(latest),
        visited_places: latest.visited_places ?? [],
      });
      setNeedsRefresh(false);
      setNotice({ type: "success", text: "已载入最新记录，请核对后再操作。" });
    } catch (error) {
      handleError(error);
    } finally {
      busyRef.current = false;
      setBusy(null);
    }
  }

  const actionsDisabled = busy !== null || pending !== null || needsRefresh || !editable;
  const statusText =
    item === null
      ? null
      : {
          draft: "草稿",
          open: "已发布",
          returned: "已找回",
          closed: "已关闭",
        }[item.status];

  return (
    <section>
      <h1>失物登记</h1>
      {statusText && <p>当前状态：{statusText}</p>}
      {item?.type === "found" && (
        <Alert type="error" showIcon message="此页面用于失物登记，请打开对应的拾获页面。" />
      )}
      {notice && (
        <Alert type={notice.type} showIcon message={notice.text} style={{ marginBottom: 16 }} />
      )}
      {needsRefresh && (
        <Button
          onClick={refreshItem}
          loading={busy === "refresh"}
          disabled={busy !== null}
          style={{ marginBottom: 16 }}
        >
          刷新并载入服务器内容
        </Button>
      )}
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          ...toFields(initialItem ?? {}),
          visited_places: initialItem?.visited_places ?? [],
        }}
        disabled={actionsDisabled}
        onValuesChange={(changed: LostFormValues) => {
          setNotice(null);
          form.setFields(
            Object.keys(changed)
              .filter(isFieldName)
              .map((name) => ({ name, errors: [] })),
          );
        }}
      >
        <Form.Item name="category" label="类别（发布时必填）">
          <Select<Category> options={categoryOptions} placeholder="请选择类别" allowClear />
        </Form.Item>
        <Form.Item name="color" label="颜色">
          <Select<Color> options={colorOptions} placeholder="请选择颜色" allowClear />
        </Form.Item>
        <Form.Item
          name="brand"
          label="品牌（可选）"
          rules={[{ max: 40, message: "品牌最多填写 40 个字符" }]}
        >
          <Input placeholder="例如物品的品牌名称" maxLength={40} showCount />
        </Form.Item>
        <Form.Item
          name="description"
          label="物品描述（可选）"
          rules={[{ max: 500, message: "物品描述最多填写 500 个字符" }]}
        >
          <Input.TextArea placeholder="补充物品的外观等信息" rows={4} maxLength={500} showCount />
        </Form.Item>
        <Form.Item
          name="occurred_on"
          label="丢失日期"
          rules={[
            {
              validator: (_, value: string | null | undefined) =>
                !value || isValidDate(value)
                  ? Promise.resolve()
                  : Promise.reject(new Error("请选择有效日期，格式为 YYYY-MM-DD")),
            },
          ]}
        >
          <Input type="date" />
        </Form.Item>
        <Form.Item
          name="day_part"
          label="丢失时段"
          rules={[
            {
              type: "enum",
              enum: dayPartOptions.map((option) => option.value),
              message: "请选择有效时段",
            },
          ]}
        >
          <Select<DayPart> options={dayPartOptions} placeholder="请选择时段" allowClear />
        </Form.Item>
        <Form.Item
          name="visited_places"
          label="按顺序去过的楼"
          extra="请按经过的先后顺序依次选择，最多八栋。调整顺序时，请清空后重新选择。"
          rules={[{ type: "array", max: 8, message: "最多选择八栋楼" }]}
        >
          <Select<PlaceCode[]>
            mode="multiple"
            options={placeOptions}
            maxCount={8}
            placeholder="请依次选择去过的楼"
            allowClear
          />
        </Form.Item>
        <Form.Item name="places_ordered" valuePropName="checked">
          <Checkbox>我按当天经过的先后顺序填写了这些楼</Checkbox>
        </Form.Item>
        <Form.Item name="subscribe_matches" valuePropName="checked">
          <Checkbox>有新的匹配候选时，接收站内通知</Checkbox>
        </Form.Item>
        <Form.Item>
          <Space wrap>
            <Button
              htmlType="button"
              onClick={() => void submit("save")}
              loading={busy === "save"}
              disabled={actionsDisabled}
            >
              保存草稿
            </Button>
            <Button
              type="primary"
              htmlType="button"
              onClick={() => void submit("publish")}
              loading={busy === "publish"}
              disabled={actionsDisabled}
            >
              发布
            </Button>
            {pending && (
              <Button
                htmlType="button"
                onClick={() => void submit(pending.intent, true)}
                disabled={busy !== null}
              >
                重试上次提交
              </Button>
            )}
          </Space>
        </Form.Item>
      </Form>
    </section>
  );
}
