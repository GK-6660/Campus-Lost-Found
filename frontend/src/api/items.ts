/** B1：创建、修改、发布和确认标签，所有请求通过公共入口。 */
import { newRequestId, request } from "./client";
import type { Category, Color, Item, ItemCreate, ItemPatch } from "./types";

/** 重试前由调用方保留 payload.request_id 和原请求内容。 */
export function createItem(payload: ItemCreate): Promise<Item> {
  return request<Item>("/items", {
    method: "POST",
    body: { ...payload, request_id: payload.request_id ?? newRequestId() },
  });
}

/** 同一次重试必须传入原 requestId、version 和 patch。 */
export function updateItem(
  id: string,
  version: number,
  patch: ItemPatch,
  requestId: string = newRequestId(),
): Promise<Item> {
  return request<Item>("/items/" + encodeURIComponent(id), {
    method: "PATCH",
    body: { ...patch, version, request_id: requestId },
  });
}

/** 拾获响应带 job_id 时，由 B2 调用方继续 pollJob。 */
export function publishItem(
  id: string,
  version: number,
  requestId: string = newRequestId(),
): Promise<Item> {
  return request<Item>("/items/" + encodeURIComponent(id) + "/publish", {
    method: "POST",
    body: { version, request_id: requestId },
  });
}

export function confirmTags(
  id: string,
  version: number,
  category: Category,
  color: Color,
  requestId: string = newRequestId(),
): Promise<Item> {
  return updateItem(id, version, { category, color, confirm_tags: true }, requestId);
}
